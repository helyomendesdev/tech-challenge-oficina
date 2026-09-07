"""Coloca a raiz do repositorio no sys.path.

Os testes daqui importam `scripts.gerar_carga_observabilidade` e o pacote
`atendimento`, e esta pasta nao e um pacote Python. Sem isso, rodar
`pytest scripts/tests/` de outro diretorio quebraria no import.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
