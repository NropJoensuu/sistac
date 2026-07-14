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
import datetime as dt

from project import db, app
from project.models import (
    Programa, Programa_Interesse, RefSICONV, Proposta, Convenio, DadosSEI,
    Coords, User,
)
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


# =============================================================================
# Convênio (núcleo) — listagem SICONV
# =============================================================================

def coord_do_usuario(usuario_id):
    """Retorna a sigla da coordenação de um usuário."""
    return db.session.query(User.coord).filter(User.id == usuario_id).first().coord


def _subquery_programa(coord, unidade_coord):
    """Monta a subquery de programas conforme o filtro de coordenação."""
    campos = (
        Proposta.ID_PROPOSTA, Proposta.ID_PROGRAMA, Proposta.UF_PROPONENTE,
        Programa.COD_PROGRAMA, Programa_Interesse.sigla,
        Programa.ANO_DISPONIBILIZACAO, Programa_Interesse.coord,
    )

    if coord == '*' or coord == 'inst':
        coord_normalizado = '' if coord == '*' else coord
        programa = db.session.query(*campos)\
                             .join(Programa, Programa.ID_PROGRAMA == Proposta.ID_PROGRAMA)\
                             .outerjoin(Programa_Interesse, Programa_Interesse.cod_programa == Programa.COD_PROGRAMA)\
                             .subquery()
        return programa, coord_normalizado

    if coord == 'usu':
        filhos = db.session.query(Coords.sigla).filter(Coords.pai == unidade_coord).all()
        l_filhos = [f.sigla for f in filhos]
        l_filhos.append(unidade_coord)

        base = db.session.query(*campos)\
                         .join(Programa, Programa.ID_PROGRAMA == Proposta.ID_PROGRAMA)\
                         .outerjoin(Programa_Interesse, Programa_Interesse.cod_programa == Programa.COD_PROGRAMA)

        if filhos:
            programa = base.filter(Programa_Interesse.coord.in_(l_filhos)).subquery()
        else:
            programa = base.filter(Programa_Interesse.coord == unidade_coord).subquery()

        return programa, unidade_coord

    # filtro por sigla parcial de coordenação
    programa = db.session.query(*campos)\
                         .join(Programa, Programa.ID_PROGRAMA == Proposta.ID_PROGRAMA)\
                         .join(Programa_Interesse, Programa_Interesse.cod_programa == Programa.COD_PROGRAMA)\
                         .filter(Programa_Interesse.coord.like('%' + coord + '%'))\
                         .subquery()

    return programa, coord


def listar_convenios_siconv(lista, coord, unidade_coord):
    """
    Retorna a lista de convênios filtrada por coordenação e critério de
    lista ('todos', 'em execução', ou 'programaAAAA...SIGLA'), a data
    da última carga SICONV, e o valor normalizado de coordenação (para
    popular o form de filtro). Também grava um CSV de referência em
    project/static.
    """
    programa, coord_normalizado = _subquery_programa(coord, unidade_coord)

    campos_convenio = (
        Convenio.NR_CONVENIO, programa.c.ANO_DISPONIBILIZACAO, programa.c.coord,
        DadosSEI.sei, DadosSEI.epe, programa.c.UF_PROPONENTE, programa.c.sigla,
        Convenio.SIT_CONVENIO, Convenio.SUBSITUACAO_CONV, Convenio.DIA_FIM_VIGENC_CONV,
        Convenio.VL_REPASSE_CONV, Convenio.VL_CONTRAPARTIDA_CONV, Convenio.VL_DESEMBOLSADO_CONV,
        Convenio.VL_INGRESSO_CONTRAPARTIDA,
        (Convenio.VL_REPASSE_CONV - Convenio.VL_DESEMBOLSADO_CONV).label('vl_a_desembolsar'),
        (Convenio.DIA_FIM_VIGENC_CONV - dt.date.today()).label('prazo'),
    )

    query = db.session.query(*campos_convenio)\
                      .join(programa, programa.c.ID_PROPOSTA == Convenio.ID_PROPOSTA)\
                      .outerjoin(DadosSEI, Convenio.NR_CONVENIO == DadosSEI.nr_convenio)

    if lista == 'todos':
        convenio = query.filter(Convenio.DIA_PUBL_CONV != '')\
                        .order_by(programa.c.sigla.desc(), Convenio.SIT_CONVENIO.desc()).all()

    elif lista == 'em execução':
        convenio = query.filter(Convenio.SIT_CONVENIO == 'Em execução')\
                        .order_by(Convenio.SUBSITUACAO_CONV.desc(), Convenio.DIA_FIM_VIGENC_CONV,
                                  programa.c.sigla.desc()).all()

    elif lista[:8] == 'programa':
        convenio = query.filter(Convenio.DIA_PUBL_CONV != '',
                                programa.c.sigla == lista[21:],
                                programa.c.ANO_DISPONIBILIZACAO == lista[13:17])\
                        .order_by(Convenio.SIT_CONVENIO, Convenio.DIA_FIM_VIGENC_CONV,
                                  programa.c.sigla.desc()).all()
    else:
        convenio = []

    data_carga = db.session.query(RefSICONV.data_ref).first()

    caminho_csv = os.path.join(app.root_path, 'static', 'convenios.csv')
    cria_csv(
        caminho_csv,
        ['conv', 'ano', 'coord', 'sei', 'epe', 'uf', 'sigla', 'sit', 'subsit', 'fim', 'repasse',
         'contrapartida', 'desemb', 'ingres_contra', 'vl_a_desembolsar', 'prazo'],
        convenio,
    )

    return convenio, coord_normalizado, str(data_carga[0])
