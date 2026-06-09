"""Adapter de persistencia para ordens de servico via Django ORM.

Implementa OrdemServicoRepositoryPort, concentrando QuerySets, ordenacao,
isolamento por usuario e conversao de erros tecnicos em erros de dominio.
Use cases dependem do port; este adapter e o unico ponto que conhece models
e QuerySets nesse fluxo novo.
"""

from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.db.models import Case, F, IntegerField, Value, When
from django.utils import timezone

from atendimento.application.ports.ordem_servico_repository import (
    OrdemServicoRepositoryPort,
)
from atendimento.domain.enums import StatusItemServico, StatusOrdemServico
from atendimento.domain.exceptions import (
    DomainError,
    EstoqueInsuficienteError,
    OrdemServicoNaoEncontradaError,
    PecaNaoPertenceOrdemServicoError,
    QuantidadeIndisponivelError,
)
from atendimento.domain.policies import (
    FinalizacaoOrdemServicoPolicy,
    OrdemServicoStatusPolicy,
)
from atendimento.models import (
    ConsumoItemServico,
    ItemPecaOS,
    ItemServicoOS,
    OrdemServico,
    Peca,
    Servico,
)


def _campo(dados: Any, nome: str) -> Any:
    if isinstance(dados, dict):
        return dados.get(nome)
    return getattr(dados, nome)


def _mensagem_validacao(exc: DjangoValidationError) -> str:
    if hasattr(exc, "messages"):
        return " ".join(str(mensagem) for mensagem in exc.messages)
    return str(exc)


class DjangoOrdemServicoRepository(OrdemServicoRepositoryPort):
    """Repository concreto de ordens de servico usando Django ORM."""

    def get_by_id(self, ordem_servico_id: int) -> OrdemServico:
        """Busca uma ordem de servico pelo id."""
        try:
            return OrdemServico.objects.select_related("cliente", "veiculo").get(
                id=ordem_servico_id
            )
        except OrdemServico.DoesNotExist as exc:
            raise OrdemServicoNaoEncontradaError(
                "Ordem de servico nao encontrada."
            ) from exc

    def get_by_id_for_user(
        self,
        ordem_servico_id: int,
        usuario_id: int | None,
        usuario_is_staff: bool,
    ) -> OrdemServico:
        """Busca uma ordem de servico respeitando isolamento por usuario."""
        queryset = OrdemServico.objects.select_related("cliente", "veiculo")
        if not usuario_is_staff:
            queryset = queryset.filter(created_by_id=usuario_id)

        try:
            return queryset.get(id=ordem_servico_id)
        except OrdemServico.DoesNotExist as exc:
            raise OrdemServicoNaoEncontradaError(
                "Ordem de servico nao encontrada."
            ) from exc

    def create(
        self, cliente: Any, veiculo: Any, usuario_id: int | None = None
    ) -> OrdemServico:
        """Cria uma ordem de servico."""
        dados = {
            "cliente": cliente,
            "veiculo": veiculo,
        }
        if usuario_id is not None:
            dados["created_by_id"] = usuario_id
        try:
            return OrdemServico.objects.create(**dados)
        except (DjangoValidationError, IntegrityError) as exc:
            raise DomainError(
                f"Nao foi possivel criar a ordem de servico: {exc}"
            ) from exc

    def adicionar_servicos(
        self,
        ordem_servico: OrdemServico,
        servicos: list[Servico],
        usuario_id: int | None = None,
    ) -> None:
        """Adiciona servicos a uma ordem de servico."""
        for servico in servicos:
            dados = {
                "ordem_servico": ordem_servico,
                "servico": servico,
            }
            if usuario_id is not None:
                dados["created_by_id"] = usuario_id
            try:
                ItemServicoOS.objects.create(**dados)
            except (DjangoValidationError, IntegrityError) as exc:
                raise DomainError(
                    f"Nao foi possivel adicionar servico a OS: {exc}"
                ) from exc

    def adicionar_pecas(
        self,
        ordem_servico: OrdemServico,
        pecas_input: list[Any],
        usuario_id: int | None = None,
        usuario_is_staff: bool = False,
    ) -> None:
        """Adiciona pecas a uma ordem de servico.

        A reserva efetiva de estoque ocorre ao criar ItemPecaOS. Nesta fase,
        ItemPecaOS.save() permanece a fonte da verdade para baixa de estoque,
        preservando compatibilidade com endpoints legados.
        """
        for peca_input in pecas_input:
            peca = self._get_peca_acessivel(
                _campo(peca_input, "peca_id"),
                usuario_id,
                usuario_is_staff,
            )
            dados = {
                "os": ordem_servico,
                "peca": peca,
                "quantidade": _campo(peca_input, "quantidade"),
            }
            if usuario_id is not None:
                dados["created_by_id"] = usuario_id
            try:
                ItemPecaOS.objects.create(**dados)
            except (DjangoValidationError, IntegrityError) as exc:
                mensagem = (
                    _mensagem_validacao(exc)
                    if isinstance(exc, DjangoValidationError)
                    else str(exc)
                )
                if (
                    isinstance(exc, DjangoValidationError)
                    and "estoque insuficiente" in mensagem.lower()
                ):
                    raise EstoqueInsuficienteError(mensagem) from exc

                raise DomainError(
                    f"Nao foi possivel adicionar peca a OS: {mensagem}"
                ) from exc

    def recalcular_total(self, ordem_servico: OrdemServico) -> OrdemServico:
        """Recalcula e atualiza o valor total da ordem de servico."""
        ordem_servico.calcular_total()
        ordem_servico.refresh_from_db(fields=["valor_total"])
        return ordem_servico

    def save(self, ordem_servico: OrdemServico) -> OrdemServico:
        """Persiste alteracoes na ordem de servico."""
        try:
            if ordem_servico.status == StatusOrdemServico.FINALIZADA.value:
                status_atual = self._status_persistido(ordem_servico)
                if status_atual != StatusOrdemServico.FINALIZADA.value:
                    self.validar_finalizacao(
                        ordem_servico,
                        status_atual=status_atual,
                    )
                    OrdemServicoStatusPolicy.validar_transicao(
                        status_atual,
                        StatusOrdemServico.FINALIZADA.value,
                    )
                if not ordem_servico.data_finalizacao:
                    ordem_servico.data_finalizacao = timezone.now()
            ordem_servico.save()
            return ordem_servico
        except (DjangoValidationError, IntegrityError) as exc:
            mensagem = (
                _mensagem_validacao(exc)
                if isinstance(exc, DjangoValidationError)
                else str(exc)
            )
            raise DomainError(
                f"Nao foi possivel salvar a ordem de servico: {mensagem}"
            ) from exc

    def listar_fila_operacional(
        self,
        usuario_id: int | None = None,
        usuario_is_staff: bool = False,
    ) -> list[OrdemServico]:
        """Lista a fila operacional ordenada por prioridade e data de abertura."""
        prioridade_status = Case(
            When(status=StatusOrdemServico.EXECUCAO.value, then=Value(1)),
            When(status=StatusOrdemServico.AGUARDANDO.value, then=Value(2)),
            When(status=StatusOrdemServico.DIAGNOSTICO.value, then=Value(3)),
            When(status=StatusOrdemServico.RECEBIDA.value, then=Value(4)),
            output_field=IntegerField(),
        )

        queryset = OrdemServico.objects.select_related("cliente", "veiculo").filter(
            status__in=[
                StatusOrdemServico.EXECUCAO.value,
                StatusOrdemServico.AGUARDANDO.value,
                StatusOrdemServico.DIAGNOSTICO.value,
                StatusOrdemServico.RECEBIDA.value,
            ]
        )

        if not usuario_is_staff:
            queryset = queryset.filter(created_by_id=usuario_id)

        queryset = queryset.annotate(
            prioridade_status=prioridade_status
        ).order_by("prioridade_status", "data_abertura")
        return list(queryset)

    def listar_fila_operacional_for_user(
        self,
        usuario_id: int | None,
        usuario_is_staff: bool,
    ) -> list[OrdemServico]:
        """Lista a fila operacional respeitando isolamento por usuario."""
        return self.listar_fila_operacional(
            usuario_id=usuario_id,
            usuario_is_staff=usuario_is_staff,
        )

    def consultar_status(
        self,
        ordem_servico_id: int,
        usuario_id: int | None = None,
        usuario_is_staff: bool = False,
    ) -> OrdemServico:
        """Consulta os dados de status de uma ordem de servico."""
        if usuario_id is None and not usuario_is_staff:
            raise OrdemServicoNaoEncontradaError(
                "Ordem de servico nao encontrada."
            )

        return self.get_by_id_for_user(
            ordem_servico_id,
            usuario_id,
            usuario_is_staff,
        )

    def consultar_status_for_user(
        self,
        ordem_servico_id: int,
        usuario_id: int | None,
        usuario_is_staff: bool,
    ) -> OrdemServico:
        """Consulta status respeitando isolamento por usuario."""
        return self.consultar_status(
            ordem_servico_id,
            usuario_id,
            usuario_is_staff,
        )

    def get_item_servico(
        self,
        ordem_servico_id: int,
        item_servico_id: int,
        usuario_id: int | None = None,
        usuario_is_staff: bool = False,
    ) -> ItemServicoOS:
        """Busca um item de servico vinculado a uma ordem de servico."""
        queryset = ItemServicoOS.objects.select_related(
            "servico",
            "ordem_servico",
        ).filter(id=item_servico_id, ordem_servico_id=ordem_servico_id)

        if not usuario_is_staff:
            queryset = queryset.filter(ordem_servico__created_by_id=usuario_id)

        try:
            return queryset.get()
        except ItemServicoOS.DoesNotExist as exc:
            raise OrdemServicoNaoEncontradaError(
                "Item de servico nao encontrado para esta OS."
            ) from exc

    def get_item_peca(
        self, ordem_servico_id: int, item_peca_os_id: int
    ) -> ItemPecaOS:
        """Busca um item de peca vinculado a uma ordem de servico."""
        try:
            return ItemPecaOS.objects.select_related("peca", "os").get(
                id=item_peca_os_id,
                os_id=ordem_servico_id,
            )
        except ItemPecaOS.DoesNotExist as exc:
            raise PecaNaoPertenceOrdemServicoError(
                "Peça não pertence a esta OS."
            ) from exc

    def criar_consumo_item_servico(
        self, item_servico: ItemServicoOS, item_peca: ItemPecaOS, quantidade: int
    ) -> ConsumoItemServico:
        """Cria o consumo de uma peca por um item de servico."""
        try:
            return ConsumoItemServico.objects.create(
                item_servico_os=item_servico,
                item_peca_os=item_peca,
                quantidade=quantidade,
            )
        except (DjangoValidationError, IntegrityError) as exc:
            raise DomainError(
                f"Nao foi possivel registrar consumo do servico: {exc}"
            ) from exc

    def atualizar_quantidade_utilizada_item_peca(
        self, item_peca: ItemPecaOS, quantidade: int
    ) -> ItemPecaOS:
        """Incrementa a quantidade utilizada de uma peca da ordem."""
        atualizados = ItemPecaOS.objects.filter(
            pk=item_peca.pk,
            quantidade_utilizada__lte=F("quantidade") - quantidade,
        ).update(
            quantidade_utilizada=F("quantidade_utilizada") + quantidade
        )
        if not atualizados:
            item_peca.refresh_from_db()
            disponivel = item_peca.quantidade - item_peca.quantidade_utilizada
            raise QuantidadeIndisponivelError(
                f"Quantidade indisponivel para '{item_peca.peca.nome}'. "
                f"Disponivel: {disponivel}, solicitado: {quantidade}."
            )
        item_peca.refresh_from_db()
        return item_peca

    def iniciar_item_servico(
        self, item_servico: ItemServicoOS, data_inicio: Any
    ) -> ItemServicoOS:
        """Marca um item de servico como em execucao."""
        ItemServicoOS.objects.filter(pk=item_servico.pk).update(
            status=StatusItemServico.EM_EXECUCAO.value,
            data_inicio=data_inicio,
        )
        item_servico.refresh_from_db()
        return item_servico

    def finalizar_item_servico(
        self, item_servico: ItemServicoOS, data_finalizacao: Any
    ) -> ItemServicoOS:
        """Marca um item de servico como concluido."""
        ItemServicoOS.objects.filter(pk=item_servico.pk).update(
            status=StatusItemServico.CONCLUIDO.value,
            data_finalizacao=data_finalizacao,
        )
        item_servico.refresh_from_db()
        return item_servico

    def existem_servicos_nao_concluidos(self, ordem_servico: OrdemServico) -> bool:
        """Indica se a ordem possui servicos ainda nao concluidos."""
        return self.possui_servico_nao_concluido(ordem_servico)

    def existem_pecas_nao_utilizadas(self, ordem_servico: OrdemServico) -> bool:
        """Indica se a ordem possui pecas reservadas nao utilizadas."""
        return self.possui_peca_nao_utilizada(ordem_servico)

    def possui_servico_nao_concluido(self, ordem_servico: OrdemServico) -> bool:
        """Indica se a ordem possui ao menos um servico nao concluido."""
        return ItemServicoOS.objects.filter(
            ordem_servico=ordem_servico,
        ).exclude(status=StatusItemServico.CONCLUIDO.value).exists()

    def possui_peca_nao_utilizada(self, ordem_servico: OrdemServico) -> bool:
        """Indica se a ordem possui ao menos uma peca reservada nao utilizada."""
        return ordem_servico.itens_pecas.exclude(
            quantidade_utilizada=F("quantidade")
        ).exists()

    def pode_finalizar(self, ordem_servico: OrdemServico) -> bool:
        """Indica se a ordem atende aos gates de finalizacao."""
        return not (
            self.possui_servico_nao_concluido(ordem_servico)
            or self.possui_peca_nao_utilizada(ordem_servico)
        )

    def validar_finalizacao(
        self,
        ordem_servico: OrdemServico,
        status_atual: str | None = None,
    ) -> None:
        """Valida os gates de finalizacao usando dados simples para a policy."""
        FinalizacaoOrdemServicoPolicy.validar_finalizacao(
            status_atual or ordem_servico.status,
            self._dados_itens_servico_finalizacao(ordem_servico),
            self._dados_itens_peca_finalizacao(ordem_servico),
        )

    def finalizar_ordem_servico(
        self, ordem_servico: OrdemServico, data_finalizacao: Any
    ) -> OrdemServico:
        """Marca uma ordem de servico como finalizada apos validar gates."""
        self.validar_finalizacao(ordem_servico)
        OrdemServicoStatusPolicy.validar_transicao(
            ordem_servico.status,
            StatusOrdemServico.FINALIZADA.value,
        )
        data_finalizacao = data_finalizacao or timezone.now()
        OrdemServico.objects.filter(pk=ordem_servico.pk).update(
            status=StatusOrdemServico.FINALIZADA.value,
            data_finalizacao=data_finalizacao,
        )
        ordem_servico.refresh_from_db()
        return ordem_servico

    def _status_persistido(self, ordem_servico: OrdemServico) -> str:
        if not ordem_servico.pk:
            return ordem_servico.status
        return OrdemServico.objects.only("status").get(pk=ordem_servico.pk).status

    def _get_peca_acessivel(
        self,
        peca_id: int,
        usuario_id: int | None,
        usuario_is_staff: bool,
    ) -> Peca:
        queryset = Peca.objects.all()
        if not usuario_is_staff:
            if usuario_id is None:
                raise DomainError("Peca nao encontrada ou inacessivel.")
            queryset = queryset.filter(created_by_id=usuario_id)

        try:
            return queryset.get(id=peca_id)
        except Peca.DoesNotExist as exc:
            raise DomainError("Peca nao encontrada ou inacessivel.") from exc

    def _dados_itens_servico_finalizacao(
        self,
        ordem_servico: OrdemServico,
    ) -> list[dict[str, Any]]:
        return list(
            ItemServicoOS.objects.filter(ordem_servico=ordem_servico).values(
                "status"
            )
        )

    def _dados_itens_peca_finalizacao(
        self,
        ordem_servico: OrdemServico,
    ) -> list[dict[str, Any]]:
        return list(
            ItemPecaOS.objects.filter(os=ordem_servico).values(
                "quantidade",
                "quantidade_utilizada",
            )
        )
