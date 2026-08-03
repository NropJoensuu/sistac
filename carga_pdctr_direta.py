"""
Roda a carga de folha de pagamento (PDCTR) direto no terminal, sem passar
pelo navegador - evita qualquer limite de tamanho do proxy do Codespace.
"""

import sys
import time

sys.path.insert(0, '.')
from project import app
from project.core import services


def main(caminho_arquivo):
    inicio = time.time()
    print(f'Iniciando carga de: {caminho_arquivo}')
    print('(isso pode demorar bastante para 53 mil linhas - acompanhe pelo '
          'terminal, ou pela tela "Ver diario" do sistema em outra aba)')

    with app.app_context():
        services.cargaPDCTR(caminho_arquivo)

    fim = time.time()
    print(f'\nCarga finalizada em {fim - inicio:.1f} segundos.')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Uso: venv/bin/python carga_pdctr_direta.py caminho/do/arquivo.xlsx')
        sys.exit(1)
    main(sys.argv[1])
