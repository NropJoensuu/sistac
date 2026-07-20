"""
.. topic:: Acordos (services) — Chamadas do acordo / Programas CNPq

    Camada de regra de negócio dos grupos "Chamadas do acordo" e
    "Programas CNPq" do módulo de acordos. Sem dependência de objetos
    de request/response do Flask (redirect, flash) — as rotas
    (views.py) decidem o que fazer com o resultado.
"""

import os
import tempfile
import locale
import datetime
from datetime import datetime as dt

import xlrd
from dateutil.rrule import rrule, MONTHLY
from folium import Map, Circle, Popup
from werkzeug.utils import secure_filename
from sqlalchemy import func, distinct, or_
from sqlalchemy.sql import label

from project import db, app
from project.models import (
    Acordo, Acordo_ProcMae, Processo_Mae, Processo_Filho, Coords,
    Programa_CNPq, grupo_programa_cnpq, chamadas_cnpq, chamadas_cnpq_acordos,
    PagamentosPDCTR, Chamadas, DadosSEI, financeiro_acordo, User, Demanda,
    capital_custeio, RefSICONV,
)
from project.demandas.views import registra_log_auto
from project.core.services import consultaDW, chamadas_DW


def cria_csv(arq, linha, tabela):
    """Recebe caminho do arquivo como string, campos da tabela como lista e a tabela propriamente dita."""
    with open(arq, 'w', encoding='UTF8', newline='') as f:
        import csv
        writer = csv.writer(f, delimiter=';')
        writer.writerow(linha)
        writer.writerows(tabela)


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


# =============================================================================
# Processos mãe / filho / bolsistas
# =============================================================================

def cargaSit(entrada):
    """
    Lê a planilha de situações (gerada via SIGEF) e atualiza a
    situação dos processos-filho e pagamentos PDCTR correspondentes.
    """
    print('\n')
    print('<<', dt.now().strftime("%x %X"), '>> ', ' Carga de arquivo de situações de processos-filho iniciada...')

    book = xlrd.open_workbook(filename=entrada, ragged_rows=True)
    planilha = book.sheet_by_index(0)

    linha_cabeçalho = planilha.row_values(0, start_colx=0, end_colx=None)

    print('Planilha: SIGEF')
    print(f'Cabeçalho original: {len(linha_cabeçalho)} campos')
    print(f'Quantidade de registros na planilha: {planilha.nrows - 1}')
    print('\n')

    qtd_linhas = planilha.nrows - 1

    for i in range(qtd_linhas):

        proc = planilha.cell_value(i + 1, linha_cabeçalho.index('Processo'))
        sit = planilha.cell_value(i + 1, linha_cabeçalho.index('Situação'))

        processo_filho = db.session.query(Processo_Filho).filter(Processo_Filho.processo == proc).all()

        for p in processo_filho:
            if p.situ_filho != sit:
                p.situ_filho = sit

        db.session.commit()

        pag_PDCTR = db.session.query(PagamentosPDCTR).filter(PagamentosPDCTR.processo == proc).all()

        for p in pag_PDCTR:
            if p.situ_filho != sit:
                p.situ_filho = sit

        db.session.commit()

    print('Carga finalizada!')
    print('\n')


def salvar_arquivo_upload(arquivo_form):
    """Salva o arquivo enviado por um FileField num diretório temporário, e retorna o caminho."""
    tempdirectory = tempfile.gettempdir()
    fname = secure_filename(arquivo_form.filename)
    caminho = os.path.join(tempdirectory, fname)
    arquivo_form.save(caminho)
    return caminho


def processos_mae_do_acordo(acordo_id):
    """
    Retorna o acordo e os processos-mãe vinculados a ele. Retorna
    acordo=None se o acordo não existir (corrige bug real: o código
    original acessava `.id`/`.nome`/`.epe`/`.uf` sem checar se a
    consulta retornou algo).
    """
    acordo = db.session.query(Acordo).filter(Acordo.id == acordo_id).first()

    processos = db.session.query(Acordo_ProcMae.proc_mae_id,
                                 Processo_Mae.proc_mae,
                                 Processo_Mae.coordenador,
                                 Processo_Mae.inic_mae,
                                 Processo_Mae.term_mae,
                                 Processo_Mae.situ_mae,
                                 label('qtd_filhos', func.count(Processo_Filho.processo)),
                                 label('pago', func.sum(Processo_Filho.pago_total)),
                                 label('max_ult_pag', func.max(Processo_Filho.dt_ult_pag)),
                                 Processo_Mae.pago_custeio,
                                 Processo_Mae.pago_capital,
                                 label('pago_cap_cus', Processo_Mae.pago_custeio + Processo_Mae.pago_capital),
                                 Processo_Mae.id_chamada)\
                          .join(Processo_Mae, Processo_Mae.id == Acordo_ProcMae.proc_mae_id)\
                          .outerjoin(Processo_Filho, Processo_Filho.proc_mae == Processo_Mae.proc_mae)\
                          .filter(Acordo_ProcMae.acordo_id == acordo_id)\
                          .group_by(Acordo_ProcMae.proc_mae_id,
                                    Processo_Mae.proc_mae,
                                    Processo_Mae.coordenador,
                                    Processo_Mae.inic_mae,
                                    Processo_Mae.term_mae,
                                    Processo_Mae.situ_mae,
                                    Processo_Mae.pago_custeio,
                                    Processo_Mae.pago_capital,
                                    Processo_Mae.id_chamada)\
                          .all()

    return acordo, processos


def buscar_processo_mae_por_texto(proc_mae):
    """Busca um processo-mãe pelo número formatado (com '_' trocado por '/')."""
    return db.session.query(Processo_Mae).filter(Processo_Mae.proc_mae == proc_mae.replace('_', '/')).first()


def atualizar_processo_mae_manual(processo_mae, coordenador, situ_mae, usuario_id):
    """Atualiza manualmente o coordenador e a situação de um processo-mãe."""
    processo_mae.coordenador = coordenador
    processo_mae.situ_mae = situ_mae

    db.session.commit()

    registra_log_auto(usuario_id, None, 'mae')


def maes_disponiveis_para_acordo(acordo_id):
    """Retorna os processos-mãe das chamadas associadas a um acordo, formatados para um SelectField."""
    chamadas = db.session.query(chamadas_cnpq)\
                         .join(chamadas_cnpq_acordos, chamadas_cnpq_acordos.chamada_cnpq_id == chamadas_cnpq.id)\
                         .filter(chamadas_cnpq_acordos.acordo_id == acordo_id)\
                         .all()

    lista_chamadas = [c.id for c in chamadas]

    maes = db.session.query(Processo_Mae).filter(Processo_Mae.id_chamada.in_(lista_chamadas))

    return [(str(m.id), m.proc_mae) for m in maes]


def associar_maes_ao_acordo(acordo_id, lista_ids_mae, usuario_id):
    """Associa um ou mais processos-mãe a um acordo."""
    for mae in lista_ids_mae:
        acordo_procmae = Acordo_ProcMae(acordo_id=acordo_id, proc_mae_id=int(mae))
        db.session.add(acordo_procmae)

    db.session.commit()

    registra_log_auto(usuario_id, None, 'ass')


def incluir_processo_mae_manual(acordo_id, proc_mae, inic_mae, term_mae, coordenador, situ_mae, usuario_id):
    """Registra manualmente um processo-mãe no sistema e o associa a um acordo."""
    proc_mae_manual = Processo_Mae(
        cod_programa=None, nome_chamada=None, proc_mae=proc_mae, inic_mae=inic_mae,
        term_mae=term_mae, coordenador=coordenador, situ_mae=situ_mae, id_chamada=None,
        pago_capital=0, pago_custeio=0, pago_bolsas=0,
    )

    db.session.add(proc_mae_manual)
    db.session.commit()

    registra_log_auto(usuario_id, None, 'mae')

    acordo_procmae = Acordo_ProcMae(acordo_id=acordo_id, proc_mae_id=proc_mae_manual.id)

    db.session.add(acordo_procmae)
    db.session.commit()

    registra_log_auto(usuario_id, None, 'ass')

    return proc_mae_manual


def excluir_associacao_processo_mae(processo_mae_id, acordo_id, usuario_id):
    """
    Remove a associação de um processo-mãe com um acordo. Corrige bug
    real: o código original chamava `db.session.delete()` mesmo
    quando a associação não existia (None), o que levanta erro.
    """
    assoc = db.session.query(Acordo_ProcMae)\
                      .filter(Acordo_ProcMae.acordo_id == acordo_id,
                              Acordo_ProcMae.proc_mae_id == processo_mae_id)\
                      .first()

    if assoc is None:
        return False

    db.session.delete(assoc)
    db.session.commit()

    registra_log_auto(usuario_id, None, 'ass')

    return True


def processos_filho_do_mae(proc_mae):
    """
    Retorna os processos-filho de um processo-mãe, a quantidade e a
    data do último pagamento mais recente. Corrige bug real: o código
    original acessava `.qtd_filhos` de um resultado que podia ser None
    (quando não há nenhum processo-filho para o processo-mãe).
    """
    proc_mae_real = proc_mae.replace('_', '/')

    filhos_banco = db.session.query(Processo_Filho.processo,
                              Processo_Filho.nome,
                              Processo_Filho.cpf,
                              Processo_Filho.modalidade,
                              Processo_Filho.nivel,
                              Processo_Filho.situ_filho,
                              Processo_Filho.inic_filho,
                              Processo_Filho.term_filho,
                              Processo_Filho.mens_pagas,
                              Processo_Filho.pago_total,
                              Processo_Filho.dt_ult_pag)\
                       .filter(Processo_Filho.proc_mae == proc_mae_real)\
                       .order_by(Processo_Filho.nome, Processo_Filho.situ_filho)\
                       .all()

    qtd_filhos_registro = db.session.query(Processo_Filho.proc_mae,
                                  label('qtd_filhos', func.count(distinct(Processo_Filho.processo))))\
                           .filter(Processo_Filho.proc_mae == proc_mae_real)\
                           .group_by(Processo_Filho.proc_mae)\
                           .first()

    qtd_filhos = qtd_filhos_registro.qtd_filhos if qtd_filhos_registro else 0

    if filhos_banco:
        ult_pag = [filho.dt_ult_pag for filho in filhos_banco if filho.dt_ult_pag is not None]
        max_ult_pag = max(ult_pag).strftime("%m/%Y") if ult_pag else 0
    else:
        max_ult_pag = 0

    return filhos_banco, qtd_filhos, max_ult_pag


def _formata_bolsista(cpf):
    """Formata uma linha agregada de bolsista (proveniente de query com func.min/max/sum) para exibição."""
    inicio = cpf.min_inic_filho.strftime("%x") if cpf.min_inic_filho is not None else ''
    termino = cpf.max_term_filho.strftime("%x") if cpf.max_term_filho is not None else ''
    pago = locale.currency(cpf.pago, symbol=False, grouping=True) if cpf.pago is not None else ''
    apagar = locale.currency(cpf.apagar, symbol=False, grouping=True) if cpf.apagar is not None else ''

    return [
        cpf.nome, cpf.cpf, cpf.modalidade, cpf.nivel, cpf.situ_filho,
        inicio, termino, cpf.mens_p, pago, cpf.mens_ap, apagar,
    ]


def bolsistas_do_processo_mae(proc_mae):
    """Retorna os bolsistas (CPFs agregados) de um processo-mãe, formatados para exibição."""
    proc_mae_real = proc_mae.replace('_', '/')

    cpfs_banco = db.session.query(Processo_Filho.nome,
                              Processo_Filho.cpf,
                              Processo_Filho.modalidade,
                              Processo_Filho.nivel,
                              Processo_Filho.situ_filho,
                              label('min_inic_filho', func.min(Processo_Filho.inic_filho)),
                              label('max_term_filho', func.max(Processo_Filho.term_filho)),
                              label('mens_p', func.sum(Processo_Filho.mens_pagas)),
                              label('pago', func.sum(Processo_Filho.pago_total)),
                              label('mens_ap', func.sum(Processo_Filho.mens_apagar)),
                              label('apagar', func.sum(Processo_Filho.valor_apagar)))\
                       .filter(Processo_Filho.proc_mae == proc_mae_real)\
                       .group_by(Processo_Filho.cpf,
                                 Processo_Filho.nome,
                                 Processo_Filho.modalidade,
                                 Processo_Filho.nivel,
                                 Processo_Filho.situ_filho)\
                       .order_by(Processo_Filho.nome).all()

    cpfs = [_formata_bolsista(cpf) for cpf in cpfs_banco]

    return cpfs


def processos_filho_do_acordo(acordo_id):
    """Retorna o acordo, os processos-mãe e os processos-filho vinculados a um acordo."""
    acordo = db.session.get(Acordo, acordo_id)

    procs_mae = db.session.query(Processo_Mae.proc_mae)\
                          .join(Acordo_ProcMae, Processo_Mae.id == Acordo_ProcMae.proc_mae_id)\
                          .filter(Acordo_ProcMae.acordo_id == acordo_id).all()

    l_procs_mae = [p.proc_mae for p in procs_mae]

    filhos_banco = db.session.query(Processo_Filho.processo,
                                Processo_Filho.nome,
                                Processo_Filho.cpf,
                                Processo_Filho.modalidade,
                                Processo_Filho.nivel,
                                Processo_Filho.situ_filho,
                                Processo_Filho.inic_filho,
                                Processo_Filho.term_filho,
                                Processo_Filho.mens_pagas,
                                Processo_Filho.pago_total,
                                Processo_Filho.dt_ult_pag,
                                Processo_Filho.valor_apagar,
                                Processo_Filho.mens_apagar)\
                        .filter(Processo_Filho.proc_mae.in_(l_procs_mae))\
                        .order_by(Processo_Filho.situ_filho, Processo_Filho.nome).all()

    if filhos_banco:
        ult_pag = [filho.dt_ult_pag for filho in filhos_banco if filho.dt_ult_pag is not None]
        max_ult_pag = max(ult_pag).strftime("%m/%Y") if ult_pag else 0
    else:
        max_ult_pag = 0

    return {
        'acordo': acordo,
        'qtd_maes': len(procs_mae),
        'filhos': filhos_banco,
        'qtd_filhos': len(filhos_banco),
        'max_ult_pag': max_ult_pag,
    }


def bolsistas_do_acordo(acordo_id):
    """Retorna os bolsistas (CPFs agregados) de todos os processos-mãe de um acordo."""
    procs_mae = db.session.query(Processo_Mae.proc_mae)\
                          .join(Acordo_ProcMae, Processo_Mae.id == Acordo_ProcMae.proc_mae_id)\
                          .filter(Acordo_ProcMae.acordo_id == acordo_id).all()

    l_procs_mae = [p.proc_mae for p in procs_mae]

    cpfs_banco = db.session.query(Processo_Filho.nome,
                              Processo_Filho.cpf,
                              Processo_Filho.modalidade,
                              Processo_Filho.nivel,
                              Processo_Filho.situ_filho,
                              label('min_inic_filho', func.min(Processo_Filho.inic_filho)),
                              label('max_term_filho', func.max(Processo_Filho.term_filho)),
                              label('mens_p', func.sum(Processo_Filho.mens_pagas)),
                              label('pago', func.sum(Processo_Filho.pago_total)),
                              label('mens_ap', func.sum(Processo_Filho.mens_apagar)),
                              label('apagar', func.sum(Processo_Filho.valor_apagar)))\
                       .filter(Processo_Filho.proc_mae.in_(l_procs_mae))\
                       .group_by(Processo_Filho.cpf,
                                 Processo_Filho.nome,
                                 Processo_Filho.modalidade,
                                 Processo_Filho.nivel,
                                 Processo_Filho.situ_filho)\
                       .order_by(Processo_Filho.nome).all()

    cpfs = [_formata_bolsista(cpf) for cpf in cpfs_banco]

    return l_procs_mae, cpfs


# =============================================================================
# Integração DW
# =============================================================================

def carregar_programas_por_unidade_DW(unidade):
    """
    Alimenta a tabela Programa_CNPq com dados do Data Warehouse,
    restringindo a busca aos registros relacionados à unidade
    informada (e suas filhas, se houver).
    """
    l_unid = _unidades_hierarquia(unidade)

    u = 0
    pn = pa = 0

    for unid in l_unid:
        u += 1

        consulta = consultaDW(tipo='programas_unid', unid=unid)

        for item in consulta:
            programa = db.session.query(Programa_CNPq)\
                                 .filter(Programa_CNPq.COD_PROGRAMA == item[0], Programa_CNPq.COORD == item[3])\
                                 .first()

            if not programa:
                pn += 1
                novo_programa = Programa_CNPq(
                    COD_PROGRAMA=item[0], NOME_PROGRAMA=item[1],
                    SIGLA_PROGRAMA=item[2], COORD=item[3],
                )
                db.session.add(novo_programa)
            else:
                pa += 1
                programa.NOME_PROGRAMA = item[1]
                programa.SIGLA_PROGRAMA = item[2]
                programa.COORD = item[3]

    db.session.commit()

    return pn, pa, u


def carregar_chamadas_programa_DW():
    """Executa a carga de chamadas/processos-mãe/filhos do DW (delega para chamadas_DW do core)."""
    return chamadas_DW()


def carregar_dados_financeiros_acordos_DW(unidade):
    """
    Alimenta a tabela financeiro_acordo com dados financeiros obtidos
    do Data Warehouse, para os acordos da unidade informada (e suas
    filhas, se houver).
    """
    l_unid = _unidades_hierarquia(unidade)

    dfn = 0

    acordos = db.session.query(Acordo).filter(Acordo.unidade_cnpq.in_(l_unid)).all()

    for acordo in acordos:
        processos = db.session.query(Processo_Mae.proc_mae)\
                              .join(Acordo_ProcMae, Acordo_ProcMae.proc_mae_id == Processo_Mae.id)\
                              .filter(Acordo_ProcMae.acordo_id == acordo.id)\
                              .all()
        if processos:
            l_processos_mae = [(p.proc_mae[7:11] + p.proc_mae[:6] + p.proc_mae[-1]) for p in processos]
        else:
            l_processos_mae = []

        processos_filho = db.session.query(Processo_Filho.processo)\
                              .join(Processo_Mae, Processo_Mae.proc_mae == Processo_Filho.proc_mae)\
                              .join(Acordo_ProcMae, Acordo_ProcMae.proc_mae_id == Processo_Mae.id)\
                              .filter(Acordo_ProcMae.acordo_id == acordo.id)\
                              .all()
        if processos_filho:
            l_processos_filho = [(p.processo[7:11] + p.processo[:6] + p.processo[-1]) for p in processos_filho]
        else:
            l_processos_filho = []

        l_processos = l_processos_mae + l_processos_filho

        if len(l_processos) >= 1:

            if len(l_processos) == 1:
                l_processos = f"('{l_processos[0]}')"
            else:
                l_processos = tuple(l_processos)

            dados_financeiros = consultaDW(tipo='financeiro_processos', lista_processos=l_processos)

            db.session.query(financeiro_acordo).filter(financeiro_acordo.id_acordo == acordo.id).delete()
            db.session.commit()

            for dados in dados_financeiros:
                novo_financeiro = financeiro_acordo(
                    id_acordo=acordo.id, qtd_item_despesa=dados[0], valor_total_item_despesa=dados[1],
                    cod_fonte_recurso=dados[2], nme_fonte_recurso=dados[3], cod_plano_interno=dados[4],
                    nme_plano_interno=dados[5], nme_categ_economica=dados[6], nme_natur_desp=dados[7],
                )
                db.session.add(novo_financeiro)
                dfn += 1

    db.session.commit()

    return dfn


def dados_financeiros_do_acordo(acordo_id):
    """
    Retorna o acordo e seus dados financeiros. Retorna acordo=None se
    o acordo não existir (corrige bug real: o código original não
    checava se a consulta retornou algo antes de usar o resultado no
    template).
    """
    acordo = db.session.query(Acordo).filter(Acordo.id == acordo_id).first()

    dados_financeiros = db.session.query(financeiro_acordo).filter(financeiro_acordo.id_acordo == acordo_id).all()

    return acordo, dados_financeiros


def atualizar_id_relaciona_chamadas():
    """
    Uso eventual: para cada chamada, tenta relacioná-la a um acordo ou
    convênio existente (mesmo SEI), preenchendo id_relaciona.
    """
    chamadas = db.session.query(Chamadas).all()
    i = 0

    for chamada in chamadas:
        acordo = db.session.query(Acordo.id).filter(Acordo.sei == chamada.sei).first()
        if acordo:
            chamada.id_relaciona = acordo.id
            i += 1
        else:
            convenio = db.session.query(DadosSEI.nr_convenio).filter(DadosSEI.sei == chamada.sei).first()
            if convenio:
                chamada.id_relaciona = 'C' + convenio.nr_convenio
                i += 1

    db.session.commit()

    return i


# =============================================================================
# Dashboards / mapas
# =============================================================================

def resumo_acordos_por_programa(unidade):
    """Retorna o resumo de acordos por programa da coordenação (e suas filhas, se houver)."""
    l_unid = _unidades_hierarquia(unidade)

    maes_filhos = db.session.query(Processo_Filho.cod_programa,
                                   label('qtd_maes', func.count(distinct(Processo_Filho.proc_mae))),
                                   label('qtd_filhos', func.count(distinct(Processo_Filho.processo))),
                                   label('qtd_cpfs', func.count(distinct(Processo_Filho.cpf))),
                                   label('pago_bolsas', func.sum(Processo_Filho.pago_total)))\
                             .group_by(Processo_Filho.cod_programa)\
                             .subquery()

    chamadas = db.session.query(chamadas_cnpq.cod_programa,
                                label('pago_chamada', func.sum(chamadas_cnpq.valor)))\
                         .group_by(chamadas_cnpq.cod_programa)\
                         .subquery()

    return db.session.query(Programa_CNPq.COD_PROGRAMA,
                            Programa_CNPq.SIGLA_PROGRAMA,
                            label('vl_cnpq', func.sum(Acordo.valor_cnpq)),
                            label('vl_epe', func.sum(Acordo.valor_epe)),
                            label('qtd', func.count(Acordo.id)),
                            label('qtd_edic', func.count(distinct(Acordo.nome))),
                            maes_filhos.c.qtd_maes,
                            maes_filhos.c.qtd_filhos,
                            maes_filhos.c.qtd_cpfs,
                            maes_filhos.c.pago_bolsas,
                            chamadas.c.pago_chamada)\
                     .join(grupo_programa_cnpq, grupo_programa_cnpq.id_programa == Programa_CNPq.ID_PROGRAMA)\
                     .join(Acordo, Acordo.id == grupo_programa_cnpq.id_acordo)\
                     .outerjoin(maes_filhos, maes_filhos.c.cod_programa == Programa_CNPq.COD_PROGRAMA)\
                     .outerjoin(chamadas, chamadas.c.cod_programa == Programa_CNPq.COD_PROGRAMA)\
                     .filter(Programa_CNPq.COORD.in_(l_unid))\
                     .group_by(Programa_CNPq.SIGLA_PROGRAMA,
                               Programa_CNPq.COD_PROGRAMA,
                               maes_filhos.c.qtd_maes,
                               maes_filhos.c.qtd_filhos,
                               maes_filhos.c.qtd_cpfs,
                               maes_filhos.c.pago_bolsas,
                               chamadas.c.pago_chamada)\
                     .all()


# Coordenadas aproximadas (latitude, longitude) do centro de cada UF, usadas
# para posicionar os círculos no mapa do Brasil.
_GPS_UF = {
    'AC': [-9.977916, -67.826068], 'AL': [-9.649433, -35.709335],
    'AM': [-3.074759, -60.028723], 'AP': [0.052334, -51.070093],
    'BA': [-13.008304, -38.512027], 'CE': [-3.795849, -38.497930],
    'DF': [-15.710702, -47.911077], 'ES': [-20.276832, -40.300442],
    'GO': [-16.680903, -49.250701], 'MA': [-2.501711, -44.284316],
    'MG': [-19.884511, -43.915749], 'MS': [-20.447545, -54.603542],
    'MT': [-15.566057, -56.072258], 'PA': [-1.454934, -48.475778],
    'PB': [-7.205724, -35.921335], 'PE': [-8.060426, -34.901544],
    'PI': [-5.096300, -42.798928], 'PR': [-25.446918, -49.245448],
    'RJ': [-22.904571, -43.173827], 'RN': [-5.829595, -35.212017],
    'RO': [-8.625350, -63.844920], 'RR': [2.930872, -60.672953],
    'RS': [-30.028724, -51.228277], 'SC': [-27.571250, -48.509038],
    'SE': [-10.909057, -37.050032], 'SP': [-23.536390, -46.714247],
    'TO': [-10.182099, -48.331027],
}


def gerar_mapa_brasil_acordos():
    """Gera o mapa (folium) de acordos vigentes por UF."""
    hoje = dt.today()

    programas = db.session.query(Programa_CNPq.SIGLA_PROGRAMA,
                                 Programa_CNPq.COD_PROGRAMA,
                                 Programa_CNPq.COORD,
                                 Programa_CNPq.ID_PROGRAMA,
                                 Acordo.uf,
                                 Acordo.epe,
                                 label('qtd_acordos', func.count(Acordo.id)))\
                          .join(grupo_programa_cnpq, grupo_programa_cnpq.id_programa == Programa_CNPq.ID_PROGRAMA)\
                          .join(Acordo, Acordo.id == grupo_programa_cnpq.id_acordo)\
                          .filter(Acordo.data_fim >= hoje)\
                          .order_by(Programa_CNPq.SIGLA_PROGRAMA)\
                          .group_by(Acordo.uf,
                                    Programa_CNPq.SIGLA_PROGRAMA,
                                    Programa_CNPq.COD_PROGRAMA,
                                    Programa_CNPq.COORD,
                                    Programa_CNPq.ID_PROGRAMA,
                                    Acordo.epe)\
                          .all()

    m = Map(location=[-15.7, -47.9], tiles='OpenStreetMap', control_scale=True,
            zoom_start=2, min_zoom=2)
    m.fit_bounds([[-34, -74], [3, -34]])

    for uf in _GPS_UF:
        qtd_na_uf = 0
        pop = '<b>Acordos - ' + uf + ':</b><br>'
        tip = '<b>' + uf + '</b>'

        for p in programas:
            if p.uf == uf:
                qtd_na_uf += p.qtd_acordos
                tip = '<b>' + uf + '</b><br>' + str(qtd_na_uf) + ' acordos vigentes'
                pop += '<p>' + p.SIGLA_PROGRAMA + ' (' + str(p.qtd_acordos) + ')</p>'

        if pop == '<b>Acordos - ' + uf + ':</b><br>':
            pop = 'N&atilde;o h&aacute; Acordos celebrados com <b>' + uf + '</b>.'

        Circle(
            location=[float(_GPS_UF[uf][0]), float(_GPS_UF[uf][1])],
            radius=18000 + qtd_na_uf * 8000,
            tooltip=tip,
            popup=Popup(pop, max_width=150),
            fill=True,
            fill_opacity=0.2,
            weight=1,
            color='blue',
        ).add_to(m)

    return m._repr_html_()


def quadro_acordos_por_uf(unidade):
    """
    Monta o quadro de acordos vigentes (situação 'Vigente-Z' ou
    'Vigente-Esquecido'), cruzando UF x Programa, para a coordenação
    do usuário (e suas filhas, se houver).
    """
    l_unid = _unidades_hierarquia(unidade)

    acordos = db.session.query(Acordo.uf,
                               Programa_CNPq.SIGLA_PROGRAMA,
                               label('qtd', func.count(Acordo.id)),
                               label('valor_global', func.sum(Acordo.valor_cnpq + Acordo.valor_epe)),
                               Programa_CNPq.COD_PROGRAMA)\
                        .filter(Programa_CNPq.COORD.in_(l_unid),
                                or_(Acordo.situ == 'Vigente-Z', Acordo.situ == 'Vigente-Esquecido'))\
                        .join(grupo_programa_cnpq, grupo_programa_cnpq.id_acordo == Acordo.id)\
                        .join(Programa_CNPq, Programa_CNPq.ID_PROGRAMA == grupo_programa_cnpq.id_programa)\
                        .order_by(Acordo.uf)\
                        .group_by(Acordo.uf, Programa_CNPq.SIGLA_PROGRAMA, Programa_CNPq.COD_PROGRAMA)\
                        .all()

    ufs = sorted(set(a.uf for a in acordos))
    programas_int = sorted(set(p.SIGLA_PROGRAMA + '*' + p.COD_PROGRAMA for p in acordos))

    linhas = []
    for uf in ufs:
        linha = []
        for prog in programas_int:
            flag = False
            item = []
            for acordo in acordos:
                if acordo.uf == uf:
                    if acordo.SIGLA_PROGRAMA == prog.split('*')[0]:
                        linha.append(acordo)
                        flag = True
                    else:
                        item = [uf, prog.split('*')[0], 0, 0, prog.split('*')[1]]

            if not flag:
                linha.append(item)

        linhas.append(linha)

    return {
        'quantidade': len(ufs),
        'programas': programas_int,
        'linhas': linhas,
    }


def gasto_mensal_por_acordo(acordo_id):
    """
    Calcula os gastos mensais (folha PDCTR) de um acordo, mês a mês,
    entre o início e o término dos seus processos-mãe.
    """
    procs_mae = db.session.query(Acordo_ProcMae.proc_mae_id,
                                 Processo_Mae.proc_mae,
                                 Processo_Mae.inic_mae,
                                 Processo_Mae.term_mae)\
                          .join(Processo_Mae, Processo_Mae.id == Acordo_ProcMae.proc_mae_id)\
                          .filter(Acordo_ProcMae.acordo_id == acordo_id).all()

    if not procs_mae:
        return None

    gastos = []

    for proc in procs_mae:

        pags_proc_mae = db.session.query(label('vl_pago', func.sum(PagamentosPDCTR.valor_pago)),
                                        label('qtd', func.count(PagamentosPDCTR.valor_pago)),
                                        PagamentosPDCTR.data_pagamento)\
                                .group_by(PagamentosPDCTR.data_pagamento)\
                                .filter(PagamentosPDCTR.proc_mae == proc.proc_mae).all()

        strt_dt = datetime.date(proc.inic_mae.year, proc.inic_mae.month, 1)
        end_dt = datetime.date(proc.term_mae.year, proc.term_mae.month, 28)

        dates = [d for d in rrule(MONTHLY, dtstart=strt_dt, until=end_dt)]

        for d in dates:
            d1 = datetime.date(d.year, d.month, 1)

            p = 0
            q = 0
            for pag in pags_proc_mae:
                if pag.data_pagamento.year == d.year and pag.data_pagamento.month == d.month:
                    p = pag.vl_pago
                    q = pag.qtd

            gastos.append((d1, p, q))

    datas = set(x[0] for x in gastos)

    lista = []
    for d in datas:
        v = 0
        qtd = 0
        for g in gastos:
            if g[0] == d:
                v += g[1]
                qtd += g[2]
        lista.append((d, v, qtd))

    lista.sort(key=lambda x: x[0])

    return [
        (x[0].year, x[0].month, locale.currency(x[1], symbol=False, grouping=True), x[2])
        for x in lista
    ]


# =============================================================================
# Acordo (núcleo)
# =============================================================================

_CAMPOS_ACORDO = (
    'id_col', 'nome', 'sei', 'epe', 'uf', 'data_inicio', 'data_fim',
    'valor_cnpq', 'valor_epe', 'unid', 'situ', 'desc', 'qtd_prog',
    'siafi', 'qtd_cha', 'capital', 'custeio', 'bolsas',
)


def _contadores_acordo():
    """Subqueries com a quantidade de programas e de chamadas por acordo."""
    cont_prog = db.session.query(grupo_programa_cnpq.id_acordo,
                                 label('qtd_prog', func.count(grupo_programa_cnpq.id_programa)))\
                          .group_by(grupo_programa_cnpq.id_acordo)\
                          .subquery()

    cont_cham = db.session.query(chamadas_cnpq_acordos.acordo_id,
                                 label('qtd_cha', func.count(chamadas_cnpq_acordos.id)))\
                           .group_by(chamadas_cnpq_acordos.acordo_id)\
                           .subquery()

    return cont_prog, cont_cham


def _base_query_acordos(cont_prog, cont_cham):
    """Monta a query base (colunas + joins) reaproveitada por todos os filtros de lista_acordos."""
    return db.session.query(label('id', distinct(Acordo.id)),
                            Acordo.nome, Acordo.sei, Acordo.epe, Acordo.uf,
                            Acordo.data_inicio, Acordo.data_fim,
                            Acordo.valor_cnpq, Acordo.valor_epe,
                            label('unid', Acordo.unidade_cnpq),
                            Acordo.situ, Acordo.desc,
                            cont_prog.c.qtd_prog, Acordo.siafi, cont_cham.c.qtd_cha,
                            Acordo.capital, Acordo.custeio, Acordo.bolsas)\
                     .outerjoin(cont_cham, cont_cham.c.acordo_id == Acordo.id)\
                     .outerjoin(cont_prog, cont_prog.c.id_acordo == Acordo.id)


def _filtro_unidade(query, unid):
    """Aplica o filtro de unidade, que pode ser uma sigla única (like) ou uma lista (in_)."""
    if isinstance(unid, str):
        return query.filter(Acordo.unidade_cnpq.like(unid))
    return query.filter(Acordo.unidade_cnpq.in_(unid))


def _resolver_unidade(coord, unidade_usuario):
    """
    Resolve o filtro de coordenação a partir do parâmetro `coord` da
    rota: '*' (todas), 'usu' (a do usuário + filhas), ou uma sigla
    específica (+ filhas). Retorna (unid, coord_normalizado).
    """
    if coord == '*':
        return '%', ''

    if coord == 'usu':
        filhos = db.session.query(Coords.sigla).filter(Coords.pai == unidade_usuario).all()
        l_filhos = [f.sigla for f in filhos]
        l_filhos.append(unidade_usuario)
        return (l_filhos if filhos else unidade_usuario), unidade_usuario

    filhos = db.session.query(Coords.sigla).filter(Coords.pai == coord).all()
    l_filhos = [f.sigla for f in filhos]
    l_filhos.append(coord)
    return (l_filhos if filhos else coord), coord


def buscar_acordos(lista, coord, unidade_usuario):
    """
    Retorna a lista de acordos filtrada por coordenação e critério de
    lista ('todos', 'em execução', 'programaXXX', 'v_programaXXX',
    'edicXXX', 'UFxx...', 'PROG_UFxx...'), a data da última carga de
    chamadas do DW, e o valor de coordenação normalizado.
    """
    unid, coord_normalizado = _resolver_unidade(coord, unidade_usuario)

    data_carga = db.session.query(RefSICONV.data_cha_dw).first()
    data_cha = data_carga.data_cha_dw

    cont_prog, cont_cham = _contadores_acordo()
    base = _base_query_acordos(cont_prog, cont_cham)

    if lista == 'todos':
        query = _filtro_unidade(base, unid)
        acordos_v = query.order_by(Acordo.situ.desc(), Acordo.data_fim, Acordo.nome, Acordo.epe).all()

    elif lista == 'em execução':
        query = _filtro_unidade(base, unid)\
                    .filter(or_(Acordo.situ == 'Vigente-Z', Acordo.situ == 'Vigente-Esquecido'))
        acordos_v = query.order_by(Acordo.data_fim, Acordo.nome, Acordo.epe).all()

    elif lista[:8] == 'programa':
        unidades = db.session.query(Programa_CNPq.COORD).filter(Programa_CNPq.COD_PROGRAMA == lista[8:]).all()
        l_unidades = [c.COORD for c in unidades]
        query = base.join(grupo_programa_cnpq, grupo_programa_cnpq.id_acordo == Acordo.id)\
                    .join(Programa_CNPq, Programa_CNPq.ID_PROGRAMA == grupo_programa_cnpq.id_programa)\
                    .filter(Programa_CNPq.COD_PROGRAMA == lista[8:], Acordo.unidade_cnpq.in_(l_unidades))
        acordos_v = query.order_by(Acordo.data_fim, Acordo.nome, Acordo.epe).all()

    elif lista[:10] == 'v_programa':
        query = base.join(grupo_programa_cnpq, grupo_programa_cnpq.id_acordo == Acordo.id)\
                    .join(Programa_CNPq, Programa_CNPq.ID_PROGRAMA == grupo_programa_cnpq.id_programa)\
                    .filter(Programa_CNPq.COD_PROGRAMA == lista[10:],
                            or_(Acordo.situ == 'Vigente-Z', Acordo.situ == 'Esquecido'))
        acordos_v = query.order_by(Acordo.data_fim, Acordo.nome, Acordo.epe).all()

    elif lista[:4] == 'edic':
        query = base.filter(Acordo.nome == lista[4:].replace('#$', '/'))
        acordos_v = query.order_by(Acordo.data_fim, Acordo.nome, Acordo.epe).all()

    elif lista[:2] == 'UF':
        query = _filtro_unidade(base, unid)\
                    .filter(Acordo.uf == lista[2:4],
                            or_(Acordo.situ == 'Vigente-Z', Acordo.situ == 'Vigente-Esquecido'))
        acordos_v = query.order_by(Acordo.data_fim, Acordo.nome, Acordo.epe).all()

    elif lista[:7] == 'PROG_UF':
        query = _filtro_unidade(base, unid)\
                    .join(grupo_programa_cnpq, grupo_programa_cnpq.id_acordo == Acordo.id)\
                    .join(Programa_CNPq, Programa_CNPq.ID_PROGRAMA == grupo_programa_cnpq.id_programa)\
                    .filter(Acordo.uf == lista[7:9],
                            Programa_CNPq.COD_PROGRAMA == lista[9:22],
                            or_(Acordo.situ == 'Vigente-Z', Acordo.situ == 'Vigente-Esquecido'))
        acordos_v = query.order_by(Acordo.data_fim, Acordo.nome, Acordo.epe).all()

    else:
        acordos_v = []

    acordos = _formata_lista_acordos(acordos_v)

    caminho_csv = os.path.join(app.root_path, 'static', 'acordos.csv')
    try:
        cria_csv(
            caminho_csv,
            ['id', '***', 'nome', 'sei', 'epe', 'uf', 'ini', 'fim', 'valor_epe', 'valor_cnpq',
             'qtd_proc_mae', 'qtd_filhos', 'pago', 'a_pagar', 'saldo', 'coord', 'dias', '***',
             'qtd_cpfs', 'situ', 'desc', 'qtd_prog', 'siafi', 'valor_global', 'a_pagar', 'valor_bolsas'],
            acordos,
        )
        tem_csv = True
    except Exception:
        tem_csv = False

    return acordos, len(acordos), coord_normalizado, data_cha, tem_csv


def _formata_lista_acordos(acordos_v):
    """
    Formata cada acordo da consulta para exibição, calculando dias até
    o término, valores agregados de processos-mãe/filho, e ajustando
    automaticamente a situação do acordo conforme regras de negócio.

    Corrige bug real: `hoje` era construído com `dt.today()`
    (datetime, com hora), mas `Acordo.data_fim`/`data_inicio` são
    `date` (só data) — subtrair os dois tipos incompatíveis levantava
    `TypeError: unsupported operand type(s) for -: 'datetime.date' and
    'datetime.datetime'` ao tentar registrar/listar acordos.
    """
    hoje = datetime.date.today()

    acordos = []

    for acordo in acordos_v:

        if acordo.data_fim:
            dias = (acordo.data_fim - hoje).days
        else:
            dias = 999

        valor_global = acordo.valor_epe + acordo.valor_cnpq
        valor_cnpq = acordo.valor_cnpq
        valor_bolsas = acordo.bolsas
        valor_epe = locale.currency(acordo.valor_epe, symbol=False, grouping=True)

        procs_mae = db.session.query(Acordo_ProcMae.proc_mae_id,
                                     Processo_Mae.proc_mae,
                                     Processo_Mae.situ_mae,
                                     Processo_Mae.pago_capital,
                                     Processo_Mae.pago_custeio)\
                              .join(Processo_Mae, Processo_Mae.id == Acordo_ProcMae.proc_mae_id)\
                              .filter(Acordo_ProcMae.acordo_id == acordo.id)\
                              .all()
        qtd_proc_mae = len(procs_mae)

        qtd_filhos_acordo = 0
        pago_acordo = 0
        a_pagar = 0

        for proc in procs_mae:

            if proc.pago_capital:
                pago_acordo += proc.pago_capital
            if proc.pago_custeio:
                pago_acordo += proc.pago_custeio

            filhos = db.session.query(Processo_Filho.proc_mae,
                                      label('qtd_filhos', func.count(Processo_Filho.processo)),
                                      label('pago_filhos', func.sum(Processo_Filho.pago_total)),
                                      label('a_pagar_filhos', func.sum(Processo_Filho.valor_apagar)))\
                               .filter(Processo_Filho.proc_mae == proc.proc_mae)\
                               .group_by(Processo_Filho.proc_mae)\
                               .first()
            if filhos:
                qtd_filhos_acordo += int(filhos.qtd_filhos)
                pago_acordo += filhos.pago_filhos
                if filhos.a_pagar_filhos is not None:
                    a_pagar += filhos.a_pagar_filhos

        indic = db.session.query(Demanda.tipo)\
                          .filter(Demanda.sei == acordo.sei, Demanda.tipo == 'Bolsistas - Indicação na PICC')\
                          .count()

        situ = acordo.situ
        alterar_sit = False

        if acordo.data_fim != None and acordo.data_fim != '' and acordo.data_inicio != None and acordo.data_inicio != '':
            if situ != 'Vigente-Z' and qtd_proc_mae > 0 and acordo.data_fim >= hoje:
                situ = 'Vigente-Z'
                alterar_sit = True
            if situ[0:8] != 'Expirado' and situ != 'Não executado' and acordo.data_fim < hoje:
                situ = 'Expirado (sem RTF)'
                alterar_sit = True
            if situ == 'Expirado' and acordo.data_fim < hoje:
                situ = 'Expirado (sem RTF)'
                alterar_sit = True
            if (situ[0:8] == 'Expirado' or situ == 'Vigente-Z' or situ == 'Preparação' or situ == 'Vigente-Esquecido' or situ == '' or situ == 'Consta indicação de bolsista') and\
                        qtd_proc_mae == 0 and acordo.data_fim > hoje and indic == 0 and (acordo.data_inicio+datetime.timedelta(days=90)) >= hoje:
                situ = 'Assinado'
                alterar_sit = True
            if (situ[0:8] == 'Expirado' or situ == 'Vigente-Z' or situ == 'Assinado' or situ == 'Preparação' or situ == '' or situ == 'Consta indicação de bolsista') and\
                        qtd_proc_mae == 0 and acordo.data_fim > hoje and indic == 0 and (acordo.data_inicio+datetime.timedelta(days=90)) < hoje:
                situ = 'Vigente-Esquecido'
                alterar_sit = True
            if (situ[0:8] == 'Assinado' or situ == 'Vigente-Esquecido' or situ == 'Aguarda Folha' or situ == 'Bolsas foram indicadas') and indic > 0:
                situ = 'Consta indicação de bolsista'
                alterar_sit = True
        else:
            if situ != 'Preparação' and situ != "Não executado":
                situ = 'Preparação'
                alterar_sit = True

        if alterar_sit:
            acordo_alterar_sit = Acordo.query.get_or_404(acordo.id)
            acordo_alterar_sit.situ = situ
            db.session.commit()

        acordos.append([acordo.id, '', acordo.nome, acordo.sei, acordo.epe, acordo.uf,
                        acordo.data_inicio, acordo.data_fim, valor_epe, valor_cnpq,
                        qtd_proc_mae, qtd_filhos_acordo, pago_acordo, 0, 0, acordo.unid,
                        dias, '', 0, situ, acordo.desc, acordo.qtd_prog, acordo.siafi,
                        acordo.qtd_cha, valor_global, a_pagar, valor_bolsas])

    return acordos


def dados_para_edicao_acordo(acordo_id):
    """
    Calcula todos os dados necessários para exibir/editar um acordo:
    contadores de programas/chamadas, processos-mãe/filho agregados,
    chamadas associadas e o SEI formatado.
    """
    acordo = Acordo.query.get_or_404(acordo_id)

    cont_prog = db.session.query(grupo_programa_cnpq.id_acordo,
                                 label('qtd_prog', func.count(grupo_programa_cnpq.id_programa)))\
                          .filter(grupo_programa_cnpq.id_acordo == acordo_id)\
                          .group_by(grupo_programa_cnpq.id_acordo)\
                          .first()
    qtd_prog = cont_prog.qtd_prog if cont_prog else 0

    cont_cham = db.session.query(chamadas_cnpq_acordos.acordo_id,
                                 label('qtd_cha', func.count(chamadas_cnpq_acordos.id)))\
                          .filter(chamadas_cnpq_acordos.acordo_id == acordo_id)\
                          .group_by(chamadas_cnpq_acordos.acordo_id)\
                          .first()
    qtd_cha = cont_cham.qtd_cha if cont_cham else 0

    procs_mae = db.session.query(Acordo_ProcMae.proc_mae_id,
                                 Processo_Mae.proc_mae,
                                 Processo_Mae.situ_mae,
                                 Processo_Mae.pago_capital,
                                 Processo_Mae.pago_custeio)\
                          .join(Processo_Mae, Processo_Mae.id == Acordo_ProcMae.proc_mae_id)\
                          .filter(Acordo_ProcMae.acordo_id == acordo.id)\
                          .all()

    qtd_filhos_acordo = 0
    pago_capital = 0
    pago_custeio = 0
    pago_bolsas = 0

    for proc in procs_mae:

        if proc.pago_capital:
            pago_capital += proc.pago_capital
        if proc.pago_custeio:
            pago_custeio += proc.pago_custeio

        filhos = db.session.query(Processo_Filho.proc_mae,
                                  label('qtd_filhos', func.count(Processo_Filho.processo)),
                                  label('pago_filhos', func.sum(Processo_Filho.pago_total)))\
                           .filter(Processo_Filho.proc_mae == proc.proc_mae)\
                           .group_by(Processo_Filho.proc_mae)\
                           .first()
        if filhos:
            qtd_filhos_acordo += int(filhos.qtd_filhos)
            pago_bolsas += filhos.pago_filhos

    chamadas = db.session.query(Chamadas.id, Chamadas.chamada, Chamadas.qtd_projetos,
                                Chamadas.vl_total_chamada, Chamadas.doc_sei, Chamadas.obs,
                                Chamadas.id_relaciona)\
                         .filter(Chamadas.id_relaciona == str(acordo.id)).all()

    chamadas_s = []
    chamadas_tot = 0
    total_projetos = 0

    for chamada in chamadas:
        chamadas_s.append([chamada.id, chamada.chamada, chamada.qtd_projetos,
                           locale.currency(chamada.vl_total_chamada, symbol=False, grouping=True),
                           chamada.doc_sei, chamada.obs, chamada.id_relaciona])
        chamadas_tot += chamada.vl_total_chamada
        total_projetos += chamada.qtd_projetos

    try:
        sei = str(acordo.sei).split('/')[0] + '_' + str(acordo.sei).split('/')[1]
    except Exception:
        sei = acordo.sei

    return {
        'acordo': acordo,
        'qtd_prog': qtd_prog,
        'qtd_cha': qtd_cha,
        'procs_mae': procs_mae,
        'qtd_filhos_acordo': qtd_filhos_acordo,
        'pago_capital': pago_capital,
        'pago_custeio': pago_custeio,
        'pago_bolsas': pago_bolsas,
        'chamadas_s': chamadas_s,
        'qtd_chamadas': len(chamadas),
        'chamadas_tot': chamadas_tot,
        'total_projetos': total_projetos,
        'sei': sei,
    }


def coords_choices_para_acordo(unidade):
    """Retorna a lista de coordenações (unidade + filhas) formatada para um SelectField."""
    l_unid = _unidades_hierarquia(unidade)
    lista_coords = [(c, c) for c in l_unid]
    lista_coords.insert(0, ('', ''))
    return lista_coords


def atualizar_acordo(acordo_id, nome, sei, epe, uf, data_inicio, data_fim, valor_cnpq_str,
                      valor_epe_str, unid, situacao, desc, capital_str, custeio_str,
                      bolsas_str, siafi, usuario_id):
    """
    Atualiza os dados de um acordo existente. Retorna uma tupla
    (acordo, alerta_nds), onde alerta_nds é uma mensagem de aviso se a
    soma capital+custeio+bolsas não bater com o valor do acordo (ou
    None, se estiver tudo certo).
    """
    acordo = Acordo.query.get_or_404(acordo_id)

    valor_cnpq = float(valor_cnpq_str.replace('.', '').replace(',', '.'))
    valor_epe = float(valor_epe_str.replace('.', '').replace(',', '.'))
    capital = float(capital_str.replace('.', '').replace(',', '.'))
    custeio = float(custeio_str.replace('.', '').replace(',', '.'))
    bolsas = float(bolsas_str.replace('.', '').replace(',', '.'))

    valor = valor_cnpq + valor_epe
    nds = capital + custeio + bolsas

    alerta_nds = None
    if round(nds, 2) != round(valor, 2) and (capital > 0 or custeio > 0 or bolsas > 0):
        alerta_nds = (
            'Atenção: Soma Capital, Custeio e Bolsas não corresponde à soma dos valores do acordo/TED '
            '(Aporte: ' + locale.currency(round(valor, 2), symbol=False, grouping=True) +
            ', Soma NDs: ' + locale.currency(round(nds, 2), symbol=False, grouping=True) + ')!'
        )

    sei_anterior = acordo.sei

    acordo.nome = nome
    acordo.sei = sei
    acordo.epe = epe
    acordo.uf = uf
    acordo.data_inicio = data_inicio
    acordo.data_fim = data_fim
    acordo.valor_cnpq = valor_cnpq
    acordo.valor_epe = valor_epe
    acordo.unidade_cnpq = unid
    acordo.situ = situacao
    acordo.desc = desc
    acordo.capital = capital
    acordo.custeio = custeio
    acordo.bolsas = bolsas
    acordo.siafi = siafi

    db.session.commit()

    if sei != sei_anterior:
        demandas = db.session.query(Demanda).filter(Demanda.sei == sei_anterior).all()
        for demanda in demandas:
            demanda.sei = sei
        db.session.commit()

    registra_log_auto(usuario_id, None, 'aco')

    return acordo, alerta_nds


def criar_acordo(nome, desc, sei, epe, uf, data_inicio, data_fim, valor_cnpq_str,
                  valor_epe_str, unid, situacao, capital_str, custeio_str, bolsas_str,
                  siafi, usuario_id):
    """
    Registra um novo acordo. Retorna uma tupla (acordo, alerta_nds).

    Corrige bug real: o código original gravava `valor_epe =
    valor_cnpq` na criação (erro de copiar-colar) — o valor da EPE era
    sempre sobrescrito pelo valor do CNPq em todo acordo novo.
    """
    valor_cnpq = float(valor_cnpq_str.replace('.', '').replace(',', '.'))
    valor_epe = float(valor_epe_str.replace('.', '').replace(',', '.'))
    capital = float(capital_str.replace('.', '').replace(',', '.'))
    custeio = float(custeio_str.replace('.', '').replace(',', '.'))
    bolsas = float(bolsas_str.replace('.', '').replace(',', '.'))

    valor = valor_cnpq + valor_epe
    nds = capital + custeio + bolsas

    alerta_nds = None
    if round(nds, 2) != round(valor, 2) and (capital != 0 or custeio != 0 or bolsas != 0):
        alerta_nds = (
            'Atenção: Soma Capital, Custeio e Bolsas não corresponde à soma dos valores do acordo/TED '
            '(Aporte: ' + locale.currency(round(valor, 2), symbol=False, grouping=True) +
            ', Soma NDs: ' + locale.currency(round(nds, 2), symbol=False, grouping=True) + ')!'
        )

    acordo = Acordo(
        nome=nome, desc=desc, sei=sei, epe=epe, uf=uf,
        data_inicio=data_inicio, data_fim=data_fim,
        valor_cnpq=valor_cnpq, valor_epe=valor_epe,
        unidade_cnpq=unid, situ=situacao,
        capital=capital, custeio=custeio, bolsas=bolsas, siafi=siafi,
    )

    db.session.add(acordo)
    db.session.commit()

    registra_log_auto(usuario_id, None, 'aco')

    return acordo, alerta_nds


def excluir_acordo(acordo_id, usuario_id):
    """
    Remove um acordo e suas associações com programas e capital/custeio.

    Corrige bug real: o código original chamava
    `db.session.delete(programas)`/`db.session.delete(cap_cus)` com
    LISTAS de registros (resultado de `.all()`), não um único objeto —
    `db.session.delete()` exige um objeto ORM único. Isso quebrava
    sempre que o acordo tinha algum programa ou capital/custeio
    associado.
    """
    acordo = Acordo.query.get_or_404(acordo_id)
    db.session.delete(acordo)
    db.session.commit()

    programas = db.session.query(grupo_programa_cnpq).filter(grupo_programa_cnpq.id_acordo == acordo_id).all()
    for p in programas:
        db.session.delete(p)
    db.session.commit()

    cap_cus = db.session.query(capital_custeio).filter(capital_custeio.id_acordo == acordo_id).all()
    for c in cap_cus:
        db.session.delete(c)
    db.session.commit()

    registra_log_auto(usuario_id, None, 'ade')


def demandas_do_acordo(acordo_id):
    """
    Retorna os dados necessários para exibir as demandas relacionadas
    a um acordo. Retorna None se o acordo não existir (corrige bug
    real: o código original acessava `.sei`/`.nome` sem checar se a
    consulta retornou algo).
    """
    acordo_SEI = db.session.query(Acordo.sei, Acordo.nome).filter_by(id=acordo_id).first()

    if acordo_SEI is None:
        return None

    SEI = acordo_SEI.sei
    SEI_s = str(SEI).split('/')[0] + '_' + str(SEI).split('/')[1]

    demandas_count = Demanda.query.filter(Demanda.sei.like('%' + SEI + '%')).count()

    demandas = Demanda.query.filter(Demanda.sei.like('%' + SEI + '%'))\
                            .order_by(Demanda.data.desc()).all()

    autores = []
    for demanda in demandas:
        autores.append(str(User.query.filter_by(id=demanda.user_id).first()).split(';')[0])

    dados = [acordo_SEI.nome, SEI_s, '0', '0']

    return {
        'demandas_count': demandas_count,
        'demandas': demandas,
        'sei': SEI,
        'autores': autores,
        'dados': dados,
    }