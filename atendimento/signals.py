# C3 CORRIGIDO: Arquivo de signals limpo.
# A baixa de estoque era feita AQUI e também em ItemPecaOS.save(), causando duplo débito.
# A responsabilidade de debitar/devolver estoque pertence exclusivamente ao ItemPecaOS
# (via save() e delete()), que é a fonte de verdade para essa regra de negócio.
#
# O signal de recálculo de total por M2M (serviços) vive em models.py, junto
# com o modelo OrdemServico, para manter a coesão.
