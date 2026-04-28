from django.contrib import admin
from .models import Cliente, Veiculo, Servico, Peca, OrdemServico, ItemPecaOS


# Permite editar as peças diretamente dentro da Ordem de Serviço
class ItemPecaOSInline(admin.TabularInline):
    model = ItemPecaOS
    extra = 1


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nome', 'documento', 'email')
    search_fields = ('nome', 'documento')


@admin.register(Veiculo)
class VeiculoAdmin(admin.ModelAdmin):
    list_display = ('placa', 'modelo', 'cliente')
    search_fields = ('placa',)


@admin.register(Servico)
class ServicoAdmin(admin.ModelAdmin):
    list_display = ('descricao', 'valor_mao_de_obra')


@admin.register(Peca)
class PecaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'valor_unitario', 'estoque_atual')


@admin.register(OrdemServico)
class OrdemServicoAdmin(admin.ModelAdmin):
    list_display = ('id', 'veiculo', 'status', 'valor_total', 'data_abertura')
    list_filter = ('status', 'data_abertura')
    inlines = [ItemPecaOSInline]  # Adiciona a lista de peças na tela da OS

    # Botão para forçar o cálculo do total no Admin
    actions = ['recalcular_totais']

    def recalcular_totais(self, request, queryset):
        for os in queryset:
            os.calcular_total()
        self.message_user(request, "Totais recalculados com sucesso.")
