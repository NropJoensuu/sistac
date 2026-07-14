"""
.. topic:: Convênios (services) — Programas de interesse

    Camada de regra de negócio do grupo "Programas de interesse" do
    módulo de convênios: listagem de programas e definição dos
    programas preferenciais de cada coordenação. Sem dependência de
    objetos de request/response do Flask (redirect, flash) — as rotas
    (views.py) decidem o que fazer com o resultado.
"""

import csv
import os.path

from project import db, app
from project.models import Programa, Programa_Interesse, RefSICONV
from project.demandas.views import registra_log_auto


def none_0(a):
    """Transforma None em 0."""
    if a is None:
        a = 0
    return a


def cria_csv(arq, linha, tabela):
    """Recebe caminho do arquivo como string, cabeçalho como lista e a tabela propriamente dita."""
    with open(arq, 'w', encoding='UTF8', newline='') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(linha)
        writer.writerows(tabela)


def listar_programas():
    """
    Retorna a lista de programas com seus dados de interesse (sigla e
    coordenação, quando cadastrados) e o código da instituição no
    SICONV. Também grava um CSV de referência em project/static.
    """
    progs = db.session.query(
        Programa.COD_PROGRAMA, Programa.NOME_PROGRAMA, Programa.SIT_PROGRAMA,
        Programa.ANO_DISPONIBILIZACAO, Programa_Interesse.sigla, Programa_Interesse.coord
    ).outerjoin(Programa_Interesse, Programa_Interesse.cod_programa == Programa.COD_PROGRAMA)\
     .order_by(Programa.ANO_DISPONIBILIZACAO, Programa.NOME_PROGRAMA).all()

    inst = db.session.query(RefSICONV.cod_inst).first()

    # Caminho portável (funciona em qualquer ambiente, não só no container Docker)
    caminho_csv = os.path.join(app.root_path, 'static', 'programas_conv.csv')
    cria_csv(caminho_csv, ['Programa', 'Nome', 'Situação', 'Ano', 'Sigla', 'Coordenação'], progs)

    return progs, inst.cod_inst


def buscar_programa(cod_prog):
    """Busca um programa pelo código, ou levanta 404 se não existir."""
    return Programa.query.filter(Programa.COD_PROGRAMA == str(cod_prog)).first_or_404()


def buscar_programa_interesse(cod_prog):
    """Busca o registro de interesse (sigla/coordenação) de um programa, se existir."""
    return Programa_Interesse.query.get(str(cod_prog))


def salvar_programa_interesse(cod_prog, sigla, coord, usuario_id):
    """
    Cria ou atualiza o registro de programa preferencial (interesse) de
    uma coordenação. Retorna uma tupla (programa_interesse, status),
    onde status é 'inserido' ou 'atualizado'.
    """
    programa_interesse = buscar_programa_interesse(cod_prog)

    if programa_interesse is None:
        programa_interesse = Programa_Interesse(cod_programa=cod_prog, sigla=sigla, coord=coord)
        db.session.add(programa_interesse)
        db.session.commit()

        registra_log_auto(usuario_id, None, 'pre')

        return programa_interesse, 'inserido'

    programa_interesse.sigla = sigla
    programa_interesse.coord = coord
    db.session.commit()

    registra_log_auto(usuario_id, None, 'pre')

    return programa_interesse, 'atualizado'
