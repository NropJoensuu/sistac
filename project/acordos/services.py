"""
.. topic:: Acordos (services) — Chamadas do acordo / Programas CNPq

    Camada de regra de negócio dos grupos "Chamadas do acordo" e
    "Programas CNPq" do módulo de acordos. Sem dependência de objetos
    de request/response do Flask (redirect, flash) — as rotas
    (views.py) decidem o que fazer com o resultado.
"""

from sqlalchemy import func, distinct
from sqlalchemy.sql import label

from project import db
from project.models import (
    Acordo, Acordo_ProcMae, Processo_Mae, Processo_Filho, Coords,
    Programa_CNPq, grupo_programa_cnpq, chamadas_cnpq, chamadas_cnpq_acordos,
)
from project.demandas.views import registra_log_auto


def acordo_id_por_proc_mae(proc_mae_id):
    """
    Retorna o ID do acordo associado a um processo-mãe, ou None se não
    houver associação (corrige bug real: o código original acessava
    `.acordo_id` sem checar se a consulta retornou algo).
    """
    associacao = db.session.query(Acordo_ProcMae)\
                           .filter(Acordo_ProcMae.proc_mae_id == proc_mae_id)\
                           .first()

    return associacao.acordo_id if associacao else None


def buscar_acordo(acordo_id):
    """Busca um acordo pelo ID, ou levanta 404 se não existir."""
    return Acordo.query.get_or_404(acordo_id)


def chamadas_do_acordo(acordo_id):
    """
    Retorna as chamadas do CNPq associadas a um acordo, com a
    quantidade de processos-mãe de cada uma, o total de valor das
    chamadas e o total de processos.
    """
    acordo = buscar_acordo(acordo_id)

    processos = db.session.query(Processo_Mae.id_chamada,
                                 label('qtd_proc', func.count(Processo_Mae.id)))\
                          .group_by(Processo_Mae.id_chamada)\
                          .subquery()

    chamadas = db.session.query(chamadas_cnpq.id,
                                chamadas_cnpq.tipo,
                                chamadas_cnpq.nome,
                                chamadas_cnpq.sigla,
                                chamadas_cnpq.valor,
                                chamadas_cnpq.cod_programa,
                                chamadas_cnpq.id_dw,
                                chamadas_cnpq.qtd_processos,
                                processos.c.qtd_proc)\
                         .join(chamadas_cnpq_acordos, chamadas_cnpq_acordos.chamada_cnpq_id == chamadas_cnpq.id)\
                         .outerjoin(processos, processos.c.id_chamada == chamadas_cnpq.id)\
                         .filter(chamadas_cnpq_acordos.acordo_id == acordo.id)\
                         .all()

    chamadas_tot = 0
    total_processos = 0

    for chamada in chamadas:
        chamadas_tot += chamada.valor
        if chamada.qtd_processos:
            total_processos += chamada.qtd_processos

    return {
        'acordo': acordo,
        'chamadas': chamadas,
        'qtd_chamadas': len(chamadas),
        'chamadas_tot': chamadas_tot,
        'total_processos': total_processos,
    }


def processos_da_chamada(chamada_id_dw):
    """
    Retorna a chamada (pelo ID do DW) e os processos-mãe vinculados a
    ela, com quantidade de filhos e valores pagos agregados.
    """
    chamada = db.session.query(chamadas_cnpq)\
                        .filter(chamadas_cnpq.id_dw == chamada_id_dw).first()

    if chamada is None:
        return None, []

    processos = db.session.query(Processo_Mae.id,
                                 Acordo_ProcMae.proc_mae_id,
                                 Processo_Mae.proc_mae,
                                 Processo_Mae.coordenador,
                                 Processo_Mae.inic_mae,
                                 Processo_Mae.term_mae,
                                 Processo_Mae.situ_mae,
                                 label('qtd_filhos', func.count(distinct(Processo_Filho.processo))),
                                 label('pago', func.sum(Processo_Filho.pago_total)),
                                 label('max_ult_pag', func.max(Processo_Filho.dt_ult_pag)),
                                 Processo_Mae.pago_custeio,
                                 Processo_Mae.pago_capital,
                                 label('pago_cap_cus', Processo_Mae.pago_custeio + Processo_Mae.pago_capital))\
                          .outerjoin(Processo_Filho, Processo_Filho.proc_mae == Processo_Mae.proc_mae)\
                          .outerjoin(Acordo_ProcMae, Acordo_ProcMae.proc_mae_id == Processo_Mae.id)\
                          .filter(Processo_Mae.id_chamada == chamada.id)\
                          .group_by(Processo_Mae.id,
                                    Acordo_ProcMae.proc_mae_id,
                                    Processo_Mae.proc_mae,
                                    Processo_Mae.coordenador,
                                    Processo_Mae.inic_mae,
                                    Processo_Mae.term_mae,
                                    Processo_Mae.situ_mae,
                                    Processo_Mae.pago_custeio,
                                    Processo_Mae.pago_capital)\
                          .all()

    return chamada, processos


def _unidades_hierarquia(unidade):
    """Retorna a lista de coordenações a considerar (a própria unidade + filhas, se houver)."""
    hierarquia = db.session.query(Coords.sigla).filter(Coords.pai == unidade).all()

    if hierarquia:
        l_unid = [f.sigla for f in hierarquia]
        l_unid.append(unidade)
        return l_unid

    return [unidade]


def programas_choices_para_acordo(unidade):
    """Retorna a lista de programas do CNPq da coordenação (e filhas), formatada para um SelectField."""
    l_unid = _unidades_hierarquia(unidade)

    programas_cnpq = db.session.query(Programa_CNPq.ID_PROGRAMA,
                                      Programa_CNPq.COD_PROGRAMA,
                                      Programa_CNPq.SIGLA_PROGRAMA,
                                      Programa_CNPq.COORD)\
                               .filter(Programa_CNPq.COORD.in_(l_unid))\
                               .order_by(Programa_CNPq.NOME_PROGRAMA)\
                               .all()

    lista_progs = [
        (str(prog.ID_PROGRAMA), prog.COD_PROGRAMA + ' - ' + prog.SIGLA_PROGRAMA + ' - ' + prog.COORD)
        for prog in programas_cnpq
    ]
    lista_progs.insert(0, ('', ''))

    return lista_progs


def associar_programas_ao_acordo(id_acordo, lista_ids_programa):
    """Associa uma ou mais programas do CNPq a um acordo."""
    for p in lista_ids_programa:
        novo_grupo = grupo_programa_cnpq(id_acordo=id_acordo, id_programa=int(p), cod_programa=None)
        db.session.add(novo_grupo)

    db.session.commit()


def chamadas_choices_para_acordo(id_acordo):
    """Retorna a lista de chamadas do CNPq dos programas já associados ao acordo, formatada para um SelectField."""
    acordo = buscar_acordo(id_acordo)

    programas = db.session.query(Programa_CNPq.COD_PROGRAMA)\
                          .join(grupo_programa_cnpq, grupo_programa_cnpq.id_programa == Programa_CNPq.ID_PROGRAMA)\
                          .filter(grupo_programa_cnpq.id_acordo == acordo.id)\
                          .all()

    l_programas = set(p.COD_PROGRAMA for p in programas)

    chamadas = db.session.query(chamadas_cnpq.id,
                                chamadas_cnpq.tipo,
                                chamadas_cnpq.nome,
                                chamadas_cnpq.sigla)\
                         .filter(chamadas_cnpq.cod_programa.in_(l_programas))\
                         .order_by(chamadas_cnpq.nome)\
                         .all()

    lista_chamadas = []
    for c in chamadas:
        texto = c.tipo + ' - ' + c.sigla + ' - ' + c.nome
        if len(texto) > 125:
            texto = texto[:125] + '...'
        lista_chamadas.append((str(c.id), texto))

    lista_chamadas.insert(0, ('', ''))

    return acordo, lista_chamadas


def associar_chamadas_ao_acordo(id_acordo, lista_ids_chamada):
    """Associa uma ou mais chamadas do CNPq a um acordo."""
    for c in lista_ids_chamada:
        chamada_cnpq_acordo = chamadas_cnpq_acordos(acordo_id=id_acordo, chamada_cnpq_id=c)
        db.session.add(chamada_cnpq_acordo)

    db.session.commit()


def desassociar_chamada_do_acordo(id_chamada, id_acordo):
    """
    Remove a associação de uma chamada com um acordo, junto com as
    associações dos processos-mãe dessa chamada com o mesmo acordo.
    """
    procs_mae = db.session.query(Processo_Mae).filter(Processo_Mae.id_chamada == id_chamada).all()

    for proc in procs_mae:
        db.session.query(Acordo_ProcMae)\
                  .filter(Acordo_ProcMae.proc_mae_id == proc.id, Acordo_ProcMae.acordo_id == id_acordo)\
                  .delete()

    db.session.commit()

    db.session.query(chamadas_cnpq_acordos)\
             .filter(chamadas_cnpq_acordos.acordo_id == id_acordo,
                     chamadas_cnpq_acordos.chamada_cnpq_id == id_chamada)\
             .delete()

    db.session.commit()


# =============================================================================
# Programas CNPq
# =============================================================================

def coords_choices_para_programa(unidade):
    """Retorna a lista de coordenações (unidade + filhas) formatada para um SelectField."""
    l_unid = _unidades_hierarquia(unidade)
    lista_coords = [(c, c) for c in l_unid]
    lista_coords.insert(0, ('', ''))
    return lista_coords


def criar_programa_cnpq(cod_programa, nome_programa, sigla_programa, coord, usuario_id):
    """Registra um novo programa do CNPq."""
    programa_cnpq = Programa_CNPq(
        COD_PROGRAMA=cod_programa, NOME_PROGRAMA=nome_programa,
        SIGLA_PROGRAMA=sigla_programa, COORD=coord,
    )

    db.session.add(programa_cnpq)
    db.session.commit()

    registra_log_auto(usuario_id, None, 'pac')

    return programa_cnpq


def listar_programas_cnpq(unidade):
    """Lista os programas do CNPq vinculados à unidade do usuário (e suas filhas, se houver)."""
    l_unid = _unidades_hierarquia(unidade)

    return db.session.query(Programa_CNPq)\
                     .filter(Programa_CNPq.COORD.in_(l_unid))\
                     .all()


def programas_do_acordo(id_acordo):
    """
    Retorna os programas usados por um acordo para efetuar pagamentos,
    junto com o nome do acordo. Retorna nome_acordo=None se o acordo
    não existir (corrige bug real: o código original acessava
    `.nome` sem checar se a consulta retornou algo).
    """
    lista_programas = db.session.query(grupo_programa_cnpq.id_acordo,
                                       Programa_CNPq.COD_PROGRAMA,
                                       Programa_CNPq.SIGLA_PROGRAMA,
                                       Programa_CNPq.NOME_PROGRAMA)\
                                .join(Programa_CNPq, Programa_CNPq.ID_PROGRAMA == grupo_programa_cnpq.id_programa)\
                                .filter(grupo_programa_cnpq.id_acordo == id_acordo)\
                                .order_by(Programa_CNPq.SIGLA_PROGRAMA)\
                                .all()

    acordo = db.session.query(Acordo.nome).filter(Acordo.id == id_acordo).first()

    return lista_programas, (acordo.nome if acordo else None)


def buscar_programa_cnpq(id):
    """Busca um programa do CNPq pelo ID, ou levanta 404 se não existir."""
    return Programa_CNPq.query.get_or_404(id)


def atualizar_programa_cnpq(id, cod_programa, nome_programa, sigla_programa, coord, usuario_id):
    """
    Atualiza os dados de um programa do CNPq. Se o código do programa
    mudar, propaga a mudança para todos os acordos que o usam.
    """
    programa_cnpq = buscar_programa_cnpq(id)

    if cod_programa != programa_cnpq.COD_PROGRAMA:
        acordos_afetados = db.session.query(Acordo).filter(Acordo.programa_cnpq == programa_cnpq.COD_PROGRAMA).all()
        if acordos_afetados:
            for a in acordos_afetados:
                a.programa_cnpq = cod_programa
            db.session.commit()

    programa_cnpq.COD_PROGRAMA = cod_programa
    programa_cnpq.NOME_PROGRAMA = nome_programa
    programa_cnpq.SIGLA_PROGRAMA = sigla_programa
    programa_cnpq.COORD = coord

    db.session.commit()

    registra_log_auto(usuario_id, None, 'pac')

    return programa_cnpq


def resumo_edicoes_programa(cod_programa):
    """
    Retorna o resumo de edições (acordos) de um programa do CNPq:
    valores, quantidade de mães/filhos/CPFs e valores pagos agregados.
    """
    chamadas = db.session.query(Acordo.nome,
                                label('pago_chamada', func.sum(chamadas_cnpq.valor)))\
                         .join(chamadas_cnpq_acordos, chamadas_cnpq_acordos.acordo_id == Acordo.id)\
                         .join(chamadas_cnpq, chamadas_cnpq.id == chamadas_cnpq_acordos.chamada_cnpq_id)\
                         .group_by(Acordo.nome)\
                         .subquery()

    maes_filhos = db.session.query(Acordo.nome,
                                   label('qtd_maes', func.count(distinct(Processo_Filho.proc_mae))),
                                   label('qtd_filhos', func.count(distinct(Processo_Filho.processo))),
                                   label('qtd_cpfs', func.count(distinct(Processo_Filho.cpf))),
                                   label('pago_bolsas', func.sum(Processo_Filho.pago_total)))\
                             .join(Acordo_ProcMae, Acordo_ProcMae.acordo_id == Acordo.id)\
                             .join(Processo_Mae, Processo_Mae.id == Acordo_ProcMae.proc_mae_id)\
                             .join(Processo_Filho, Processo_Filho.proc_mae == Processo_Mae.proc_mae)\
                             .group_by(Acordo.nome)\
                             .subquery()

    return db.session.query(Acordo.nome,
                            label('vl_cnpq', func.sum(Acordo.valor_cnpq)),
                            label('vl_epe', func.sum(Acordo.valor_epe)),
                            label('qtd', func.count(Acordo.id)),
                            label('qtd_edic', func.count(distinct(Acordo.nome))),
                            maes_filhos.c.qtd_maes,
                            maes_filhos.c.qtd_filhos,
                            maes_filhos.c.qtd_cpfs,
                            maes_filhos.c.pago_bolsas,
                            chamadas.c.pago_chamada)\
                     .join(grupo_programa_cnpq, grupo_programa_cnpq.id_acordo == Acordo.id)\
                     .join(Programa_CNPq, Programa_CNPq.ID_PROGRAMA == grupo_programa_cnpq.id_programa)\
                     .outerjoin(maes_filhos, maes_filhos.c.nome == Acordo.nome)\
                     .outerjoin(chamadas, chamadas.c.nome == Acordo.nome)\
                     .filter(Programa_CNPq.COD_PROGRAMA == cod_programa)\
                     .group_by(Acordo.nome,
                               maes_filhos.c.qtd_maes,
                               maes_filhos.c.qtd_filhos,
                               maes_filhos.c.qtd_cpfs,
                               maes_filhos.c.pago_bolsas,
                               chamadas.c.pago_chamada)\
                     .order_by(Acordo.nome)\
                     .all()
