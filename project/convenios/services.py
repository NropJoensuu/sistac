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
import locale
import math
from datetime import date
from calendar import monthrange

from folium import Map, Circle
from fpdf import FPDF
from sqlalchemy import func, or_
from sqlalchemy.sql import label

from project import db, app
from project.models import (
    Programa, Programa_Interesse, RefSICONV, Proposta, Convenio, DadosSEI,
    Coords, User, Empenho, Desembolso, Pagamento, Chamadas, Emp_Cap_Cus,
    Crono_Desemb, Demanda, MSG_Siconv,
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


# =============================================================================
# Convênio (núcleo) — detalhes de um convênio
# =============================================================================

def buscar_dados_sei(conv):
    """Busca o registro de dados SEI de um convênio, se existir."""
    return db.session.query(DadosSEI).filter(DadosSEI.nr_convenio == conv).first()


def salvar_dados_sei(conv, dados_sei, sei, epe, fiscal, usuario_id):
    """
    Cria ou atualiza o registro de dados SEI de um convênio. Retorna
    uma tupla (dados_sei, status), onde status é 'inserido' ou
    'atualizado'.
    """
    if dados_sei is None:
        dados_sei = DadosSEI(nr_convenio=conv, sei=sei, epe=epe, fiscal=fiscal)
        db.session.add(dados_sei)
        db.session.commit()
        registra_log_auto(usuario_id, None, 'sei')
        return dados_sei, 'inserido'

    dados_sei.nr_convenio = conv
    dados_sei.sei = sei
    dados_sei.epe = epe
    dados_sei.fiscal = fiscal
    db.session.commit()
    registra_log_auto(usuario_id, None, 'sei')
    return dados_sei, 'atualizado'


def detalhes_convenio(conv, dados_sei):
    """
    Calcula todos os dados de detalhe de um convênio: valores
    formatados, cronograma de desembolso (com verificação de atraso e
    projeção de prorrogação), empenhos, desembolsos agrupados,
    pagamentos e chamadas associadas. Retorna um dicionário pronto
    para o template convenio_detalhes.html.
    """
    convenio = db.session.query(Convenio).get(conv)

    data_carga = db.session.query(RefSICONV.data_ref).first()

    empenho = db.session.query(Empenho.NR_EMPENHO, Empenho.DESC_TIPO_NOTA, Empenho.DATA_EMISSAO,
                               Empenho.DESC_SITUACAO_EMPENHO, Empenho.VALOR_EMPENHO,
                               Emp_Cap_Cus.nd, Empenho.ID_EMPENHO)\
                              .outerjoin(Emp_Cap_Cus, Emp_Cap_Cus.id_empenho == Empenho.ID_EMPENHO)\
                              .filter(Empenho.NR_CONVENIO == conv)\
                              .order_by(Empenho.DATA_EMISSAO).all()

    desembolso_agrupado = db.session.query(Desembolso.DATA_DESEMBOLSO, Desembolso.NR_SIAFI,
                                            label('vl_desemb_agru', func.sum(Desembolso.VL_DESEMBOLSADO)))\
                                     .filter(Desembolso.NR_CONVENIO == conv)\
                                     .order_by(Desembolso.DATA_DESEMBOLSO)\
                                     .group_by(Desembolso.DATA_DESEMBOLSO, Desembolso.NR_SIAFI)\
                                     .all()

    empenho_tot = db.session.query(label('emp_tot', func.sum(Empenho.VALOR_EMPENHO)))\
                            .filter(Empenho.NR_CONVENIO == conv)

    pagamento = db.session.query(Pagamento.IDENTIF_FORNECEDOR, Pagamento.NOME_FORNECEDOR,
                                 label("pago", func.sum(Pagamento.VL_PAGO)),
                                 label("qtd", func.count(Pagamento.VL_PAGO)))\
                          .filter(Pagamento.NR_CONVENIO == conv)\
                          .group_by(Pagamento.NOME_FORNECEDOR, Pagamento.IDENTIF_FORNECEDOR)\
                          .order_by(Pagamento.NOME_FORNECEDOR).all()

    if dados_sei is not None:
        chamadas = db.session.query(Chamadas.id, Chamadas.chamada, Chamadas.qtd_projetos,
                                    Chamadas.vl_total_chamada, Chamadas.doc_sei, Chamadas.obs,
                                    Chamadas.id_relaciona)\
                             .filter(Chamadas.id_relaciona == 'C' + conv).all()
    else:
        chamadas = None

    proposta = db.session.query(Proposta).filter(Proposta.ID_PROPOSTA == convenio.ID_PROPOSTA).first()

    programa = db.session.query(Programa).filter(Programa.ID_PROGRAMA == proposta.ID_PROGRAMA).first()

    # cronograma de desembolso, com verificação de atraso e projeção de prorrogação
    crono_desemb_query = db.session.query(
        Crono_Desemb.NR_CONVENIO, Crono_Desemb.NR_PARCELA_CRONO_DESEMBOLSO,
        Crono_Desemb.MES_CRONO_DESEMBOLSO, Crono_Desemb.ANO_CRONO_DESEMBOLSO,
        Crono_Desemb.TIPO_RESP_CRONO_DESEMBOLSO, Crono_Desemb.VALOR_PARCELA_CRONO_DESEMBOLSO
    ).filter(Crono_Desemb.NR_CONVENIO == conv)\
     .order_by(Crono_Desemb.TIPO_RESP_CRONO_DESEMBOLSO, Crono_Desemb.ANO_CRONO_DESEMBOLSO,
               Crono_Desemb.MES_CRONO_DESEMBOLSO).all()

    crono_desemb_l = []
    acu = 0

    for parcela in crono_desemb_query:
        data_repasse = dt.date(
            int(parcela.ANO_CRONO_DESEMBOLSO), int(parcela.MES_CRONO_DESEMBOLSO),
            monthrange(int(parcela.ANO_CRONO_DESEMBOLSO), int(parcela.MES_CRONO_DESEMBOLSO))[1])

        valor_repasse_acumulado = parcela.VALOR_PARCELA_CRONO_DESEMBOLSO + float(acu)

        if parcela.TIPO_RESP_CRONO_DESEMBOLSO == 'Concedente':
            sit = 'Quitada' if valor_repasse_acumulado <= convenio.VL_DESEMBOLSADO_CONV else 'Em aberto'
        else:
            sit = ''

        data_desemb = None
        desemb_acu = 0

        for desemb in desembolso_agrupado:
            vl_desemb_acu = desemb.vl_desemb_agru + desemb_acu

            if valor_repasse_acumulado <= vl_desemb_acu:
                data_desemb = desemb.DATA_DESEMBOLSO
                break
            else:
                if sit == 'Em aberto':
                    data_desemb = data_repasse

            desemb_acu = vl_desemb_acu

        data_ref_atraso = data_desemb if sit == 'Quitada' else dt.date.today()

        if data_desemb is None:
            atraso = 0
            data_prorrog = None
        else:
            atraso = (data_ref_atraso - data_repasse).days
            data_prorrog = convenio.DIA_FIM_VIGENC_CONV + dt.timedelta(days=atraso)

        crono_desemb_l.append([
            parcela.NR_PARCELA_CRONO_DESEMBOLSO, data_repasse, parcela.TIPO_RESP_CRONO_DESEMBOLSO,
            locale.currency(parcela.VALOR_PARCELA_CRONO_DESEMBOLSO, symbol=False, grouping=True),
            sit, atraso, data_prorrog, data_ref_atraso,
        ])

        acu = valor_repasse_acumulado

    crono_desemb = list(enumerate(crono_desemb_l, 1))

    # valores formatados e percentuais
    VL_GLOBAL_CONV = locale.currency(convenio.VL_GLOBAL_CONV, symbol=False, grouping=True)

    percent_desemb_repass = 0 if not convenio.VL_REPASSE_CONV else round(100 * convenio.VL_DESEMBOLSADO_CONV / convenio.VL_REPASSE_CONV)
    percent_ingre_contrap = 0 if not convenio.VL_CONTRAPARTIDA_CONV else round(100 * convenio.VL_INGRESSO_CONTRAPARTIDA / convenio.VL_CONTRAPARTIDA_CONV)
    percent_empen_repass = 0 if not convenio.VL_REPASSE_CONV else round(100 * convenio.VL_EMPENHADO_CONV / convenio.VL_REPASSE_CONV)

    VL_REPASSE_CONV = locale.currency(convenio.VL_REPASSE_CONV, symbol=False, grouping=True)
    VL_DESEMBOLSADO_CONV = locale.currency(convenio.VL_DESEMBOLSADO_CONV, symbol=False, grouping=True)
    VL_EMPENHADO_CONV = locale.currency(convenio.VL_EMPENHADO_CONV, symbol=False, grouping=True)
    VL_CONTRAPARTIDA_CONV = locale.currency(convenio.VL_CONTRAPARTIDA_CONV, symbol=False, grouping=True)
    VL_INGRESSO_CONTRAPARTIDA = locale.currency(convenio.VL_INGRESSO_CONTRAPARTIDA, symbol=False, grouping=True)
    VL_RENDIMENTO_APLICACAO = locale.currency(convenio.VL_RENDIMENTO_APLICACAO, symbol=False, grouping=True)

    vl_a_empenhar = locale.currency(convenio.VL_REPASSE_CONV - convenio.VL_EMPENHADO_CONV, symbol=False, grouping=True)
    vl_a_desembolsar = locale.currency(convenio.VL_REPASSE_CONV - convenio.VL_DESEMBOLSADO_CONV, symbol=False, grouping=True)

    pagamento_s = []
    pag_tot = 0
    for pag in pagamento:
        pag_s = list(pag)
        pag_tot += pag[2]
        if pag_s[2] is not None:
            pag_s[2] = locale.currency(pag_s[2], symbol=False, grouping=True)
        pagamento_s.append(pag_s)

    qtd_pag = len(pagamento)

    empenho_l = []
    for emp in empenho:
        empenho_l.append([
            emp.NR_EMPENHO, emp.DESC_TIPO_NOTA, emp.DATA_EMISSAO, emp.DESC_SITUACAO_EMPENHO,
            locale.currency(emp.VALOR_EMPENHO, symbol=False, grouping=True), emp.nd, emp.ID_EMPENHO,
        ])

    desembolso_l = []
    for desemb in desembolso_agrupado:
        desembolso_l.append([
            desemb.DATA_DESEMBOLSO,
            locale.currency(desemb.vl_desemb_agru, symbol=False, grouping=True),
            desemb.NR_SIAFI,
        ])

    chamadas_s = []
    chamadas_tot = 0
    qtd_proj = 0
    qtd_chamadas = 0
    if dados_sei is not None and dados_sei.sei != "N.I.":
        for chamada in chamadas:
            chamadas_s.append([
                chamada.id, chamada.chamada, chamada.qtd_projetos,
                locale.currency(chamada.vl_total_chamada, symbol=False, grouping=True),
                chamada.doc_sei, chamada.obs,
            ])
            chamadas_tot += chamada.vl_total_chamada
            qtd_proj += chamada.qtd_projetos
        qtd_chamadas = len(chamadas)

    if dados_sei is not None and dados_sei.sei != "N.I.":
        sei = str(dados_sei.sei).split('/')[0] + '_' + str(dados_sei.sei).split('/')[1]
    else:
        sei = 'Nº SEI não informado'

    emp_total = 0 if empenho_tot[0][0] is None else empenho_tot[0][0]

    return {
        'convenio': convenio,
        'dadosSEI': dados_sei,
        'VL_GLOBAL_CONV': VL_GLOBAL_CONV,
        'VL_REPASSE_CONV': VL_REPASSE_CONV,
        'VL_DESEMBOLSADO_CONV': VL_DESEMBOLSADO_CONV,
        'VL_EMPENHADO_CONV': VL_EMPENHADO_CONV,
        'VL_CONTRAPARTIDA_CONV': VL_CONTRAPARTIDA_CONV,
        'VL_INGRESSO_CONTRAPARTIDA': VL_INGRESSO_CONTRAPARTIDA,
        'VL_RENDIMENTO_APLICACAO': VL_RENDIMENTO_APLICACAO,
        'vl_a_empenhar': vl_a_empenhar,
        'vl_a_desembolsar': vl_a_desembolsar,
        'empenho': empenho_l,
        'desembolso': desembolso_l,
        'pagamento': pagamento_s,
        'qtd_pag': qtd_pag,
        'pag_tot': locale.currency(pag_tot, symbol=False, grouping=True),
        'emp_tot': locale.currency(emp_total, symbol=False, grouping=True),
        'desemb_tot': locale.currency(convenio.VL_DESEMBOLSADO_CONV, symbol=False, grouping=True),
        'chamadas': chamadas_s,
        'qtd_chamadas': qtd_chamadas,
        'qtd_proj': qtd_proj,
        'chamadas_tot': locale.currency(chamadas_tot, symbol=False, grouping=True),
        'sei': sei,
        'data_carga': data_carga[0],
        'proposta': proposta,
        'percent_desemb_repass': percent_desemb_repass,
        'percent_ingre_contrap': percent_ingre_contrap,
        'percent_empen_repass': percent_empen_repass,
        'programa': programa,
        'crono_desemb': crono_desemb,
    }


def gerar_pdf_convenio(conv, dados):
    """
    Gera o PDF de detalhes do convênio em project/static/convenio.pdf
    (caminho portável, funciona fora do container Docker).
    """
    convenio = dados['convenio']
    dadosSEI = dados['dadosSEI']
    proposta = dados['proposta']
    programa = dados['programa']

    class PDF_convenio(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 10)
            self.set_text_color(127, 127, 127)
            self.cell(0, 10, 'Dados do Convênio ' + str(conv) + ' - gerado em ' + dt.date.today().strftime('%d/%m/%Y'), 1, 1, 'C')
            self.ln(10)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.set_text_color(127, 127, 127)
            self.cell(0, 10, 'Página ' + str(self.page_no()) + '/{nb}', 0, 0, 'C')

    pdf = PDF_convenio()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_font('Times', '', 12)

    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 10, 'Dados Gerais', 0, 0)
    pdf.ln(7)

    if dadosSEI:
        pdf.set_font('Arial', '', 10)
        pdf.cell(pdf.get_string_width('SEI: '), 10, 'SEI: ', 0, 0)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 10, dadosSEI.sei, 0, 0)
        pdf.ln(7)

        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 10, 'EP: ', 0, 0)
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 10, dadosSEI.epe, 0, 0)
        pdf.ln(7)
        pdf.multi_cell(0, 5, proposta.NM_PROPONENTE.encode('latin-1', 'replace').decode('latin-1'))

        pdf.set_font('Arial', '', 10)
        pdf.cell(pdf.get_string_width('Fiscal: '), 10, 'Fiscal: ', 0, 0)
        pdf.set_font('Arial', 'B', 10)
        if dadosSEI.fiscal:
            pdf.cell(0, 10, dadosSEI.fiscal, 0, 0)
        else:
            pdf.cell(0, 10, 'N.I.', 0, 0)
        pdf.ln(7)

    pdf.set_font('Arial', '', 10)
    pdf.cell(pdf.get_string_width('Ano: '), 10, 'Ano: ', 0, 0)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 10, programa.ANO_DISPONIBILIZACAO, 0, 0)
    pdf.ln(7)

    pdf.set_font('Arial', '', 10)
    pdf.cell(pdf.get_string_width('UF: '), 10, 'UF: ', 0, 0)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 10, proposta.UF_PROPONENTE, 0, 0)
    pdf.ln(7)

    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 10, 'Programa: ', 0, 0)
    pdf.ln(7)
    pdf.set_font('Arial', 'B', 10)
    pdf.multi_cell(0, 5, programa.COD_PROGRAMA + ' - ' + programa.NOME_PROGRAMA.encode('latin-1', 'replace').decode('latin-1'))

    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 10, 'Assinado em: ' + convenio.DIA_ASSIN_CONV + '   Publicado em: ' + convenio.DIA_PUBL_CONV + '   Início: ' + convenio.DIA_INIC_VIGENC_CONV + '   Término: ' + convenio.DIA_FIM_VIGENC_CONV.strftime('%x'), 0, 0)
    pdf.ln(6)
    pdf.cell(0, 10, 'Situação da contratação: ' + convenio.SITUACAO_CONTRATACAO + '  Situação do convênio: ' + convenio.SIT_CONVENIO + '  Subsituação: ' + convenio.SUBSITUACAO_CONV + '  Opera OBTV: ' + convenio.IND_OPERA_OBTV, 0, 0)
    pdf.ln(6)

    vazio_zero = lambda a: 0 if a == '' else a
    pdf.cell(0, 10, 'TAs já celebrados: ' + str(vazio_zero(convenio.QTD_TA)) + '          Prorrogações já realizadas: ' + str(vazio_zero(convenio.QTD_PRORROGA)), 0, 0)
    pdf.ln(6)

    pdf.cell(0, 10, 'Valor Global: R$ ' + dados['VL_GLOBAL_CONV'], 0, 0)
    pdf.ln(6)

    pdf.cell(0, 10, 'Repasse: R$ ' + dados['VL_REPASSE_CONV'] + '   Empenhado: R$ ' + dados['VL_EMPENHADO_CONV'] + ' (' + str(dados['percent_empen_repass']) + '%)' + '   Desembolsado: R$ ' + dados['VL_DESEMBOLSADO_CONV'] + ' (' + str(dados['percent_desemb_repass']) + '%) ', 0, 0)
    pdf.ln(6)

    pdf.cell(0, 10, 'Rendimento de aplicação: R$ ' + dados['VL_RENDIMENTO_APLICACAO'] + '   A Empenhar: R$ ' + dados['vl_a_empenhar'] + ' (' + str(100 - dados['percent_empen_repass']) + '%)' + '   A Desembolsar: R$ ' + dados['vl_a_desembolsar'] + ' (' + str(100 - dados['percent_desemb_repass']) + '%)', 0, 0)
    pdf.ln(6)

    pdf.cell(0, 10, 'Contrapartida: R$ ' + dados['VL_CONTRAPARTIDA_CONV'] + '     ' + 'Ingresso contrapartida: R$ ' + dados['VL_INGRESSO_CONTRAPARTIDA'] + ' (' + str(dados['percent_ingre_contrap']) + '%)', 0, 0)
    pdf.ln(6)

    pdf.ln(6)
    pdf.dashed_line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y(), 2, 3)
    pdf.ln(5)

    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 10, 'Crono Desembolso', 0, 0)
    pdf.ln(15)

    pdf.set_font('Times', '', 10)
    pdf.cell(20, 10, 'PARCELA', 0, 0, 'C')
    pdf.cell(20, 10, 'PREVISÃO', 0, 0, 'C')
    pdf.cell(20, 10, 'RESP.', 0, 0, 'C')
    pdf.cell(20, 10, 'VALOR', 0, 0, 'C')
    pdf.cell(40, 10, 'SITUAÇÃO', 0, 0, 'C')
    pdf.cell(20, 10, 'ATRASO', 0, 0, 'C')
    pdf.cell(20, 10, 'NOVA DATA', 0, 0, 'C')
    pdf.ln(5)

    for parcela in dados['crono_desemb']:
        pdf.cell(20, 10, str(parcela[0]), 0, 0, 'C')
        pdf.cell(20, 10, parcela[1][1].strftime('%x'), 0, 0, 'C')
        resp = lambda: 'CNPq' if parcela[1][2] == 'Concedente' else ('Rendimento' if parcela[1][2][:10] == 'Rendimento' else 'Convenente')
        pdf.cell(20, 10, resp(), 0, 0, 'C')
        pdf.cell(20, 10, parcela[1][3], 0, 0, 'C')
        sit = lambda: 'Quitada em ' + parcela[1][7].strftime('%x') if (parcela[1][2] == 'Concedente' and parcela[1][4] == 'Quitada' and parcela[1][7] is not None) \
                                                                else ('Quitada em ???' if parcela[1][2] == 'Concedente' and parcela[1][4] == 'Quitada' and parcela[1][7] is None else \
                                                                parcela[1][4])
        pdf.cell(40, 10, sit(), 0, 0, 'C')
        atraso = lambda: 'Não houve' if parcela[1][5] <= 0 else str(parcela[1][5]) + ' dias'
        pdf.cell(20, 10, atraso(), 0, 0, 'C')
        nova_data = lambda: parcela[1][6].strftime('%x') if parcela[1][5] > 0 else ''
        pdf.cell(20, 10, nova_data(), 0, 0, 'C')
        pdf.ln(5)

    pdf.ln(5)
    pdf.dashed_line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y(), 2, 3)

    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 10, 'Empenhos', 0, 0)
    pdf.ln(15)

    pdf.set_font('Times', '', 10)
    pdf.cell(35, 10, 'Empenho', 0, 0, 'C')
    pdf.cell(45, 10, 'Tipo nota', 0, 0, 'C')
    pdf.cell(25, 10, 'Data emissão', 0, 0, 'C')
    pdf.cell(30, 10, 'Situação', 0, 0, 'C')
    pdf.cell(25, 10, 'Valor (R$)', 0, 0, 'C')
    pdf.cell(15, 10, 'ND', 0, 0, 'C')
    pdf.ln(5)

    for item in dados['empenho']:
        pdf.cell(35, 10, str(item[0]), 0, 0, 'C')
        pdf.cell(45, 10, str(item[1]), 0, 0, 'C')
        none_vazio = lambda a: '' if a is None else a.strftime('%x')
        pdf.cell(25, 10, str(none_vazio(item[2])), 0, 0, 'C')
        pdf.cell(30, 10, str(item[3]), 0, 0, 'C')
        pdf.cell(25, 10, str(item[4]), 0, 0, 'C')
        pdf.cell(15, 10, str(item[5]), 0, 0, 'C')
        pdf.ln(5)

    pdf.ln(5)
    pdf.dashed_line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y(), 2, 3)

    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 10, 'Desembolsos', 0, 0)
    pdf.ln(15)

    pdf.set_font('Times', '', 10)
    pdf.cell(25, 10, 'Data', 0, 0, 'C')
    pdf.cell(25, 10, 'Nr Siafi', 0, 0, 'C')
    pdf.cell(25, 10, 'Valor (R$)', 0, 0, 'C')
    pdf.ln(5)

    for item in dados['desembolso']:
        none_vazio = lambda a: '' if a is None else a.strftime('%x')
        pdf.cell(25, 10, str(none_vazio(item[0])), 0, 0, 'C')
        pdf.cell(25, 10, str(item[2]), 0, 0, 'C')
        pdf.cell(25, 10, str(item[1]), 0, 0, 'C')
        pdf.ln(5)

    pdf.ln(5)
    pdf.dashed_line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y(), 2, 3)

    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 10, 'Chamadas', 0, 0)
    pdf.ln(15)

    pdf.set_font('Times', '', 10)
    for chamada in dados['chamadas']:
        pdf.multi_cell(0, 5, str(chamada[1]).encode('latin-1', 'replace').decode('latin-1'), 0, 'L')
        pdf.cell(pdf.get_string_width('Projetos: ' + str(chamada[2])), 10, 'Projetos: ' + str(chamada[2]), 0, 0, 'L')
        pdf.cell(pdf.get_string_width('  Valor: ' + str(chamada[3])), 10, '  Valor: ' + str(chamada[3]), 0, 0, 'L')
        pdf.cell(pdf.get_string_width('  Ref. SEI: ' + str(chamada[4])), 10, '  Ref. SEI: ' + str(chamada[4]), 0, 0, 'L')
        pdf.ln(10)
        pdf.multi_cell(0, 5, 'Obs: ' + str(chamada[5]).encode('latin-1', 'replace').decode('latin-1'), 0, 'L')

    pdf.ln(5)
    pdf.dashed_line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y(), 2, 3)

    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 10, 'Pagamentos', 0, 0)
    pdf.ln(15)

    pdf.set_font('Times', '', 10)
    pdf.cell(35, 10, 'ID', 0, 0, 'C')
    pdf.cell(99, 10, 'NOME', 0, 0, 'C')
    pdf.cell(20, 10, 'QTD', 0, 0, 'C')
    pdf.cell(25, 10, 'VALOR', 0, 0, 'C')
    pdf.ln(5)

    for pag in dados['pagamento']:
        pdf.cell(35, 10, str(pag[0]), 0, 0, 'C')
        pdf.cell(100, 10, str(pag[1]), 0, 0, 'C')
        pdf.cell(20, 10, str(pag[3]), 0, 0, 'C')
        pdf.cell(25, 10, str(pag[2]), 0, 0, 'C')
        pdf.ln(5)

    pdf.ln(5)
    pdf.dashed_line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y(), 2, 3)

    # Caminho portável (funciona em qualquer ambiente, não só no container Docker)
    pasta_pdf = os.path.join(app.root_path, 'static', 'convenio.pdf')
    pdf.output(pasta_pdf)

# =============================================================================
# Convênio (núcleo) — chamadas, natureza de despesa, demandas SEI, mensagens
# =============================================================================

def chamadas_disponiveis():
    """Retorna as chamadas ainda não associadas a nenhum convênio, formatadas para um SelectField."""
    chamadas = db.session.query(Chamadas.id, Chamadas.chamada)\
                         .filter(or_(Chamadas.id_relaciona == None, Chamadas.id_relaciona == ''))\
                         .order_by(Chamadas.chamada)\
                         .all()

    lista_chamadas = [
        (str(c.id), c.chamada[:110] + '...') if len(c.chamada) > 110 else (str(c.id), c.chamada)
        for c in chamadas
    ]
    lista_chamadas.insert(0, ('', ''))

    return lista_chamadas


def associar_chamadas(conv, chamada_ids):
    """Associa uma ou mais chamadas a um convênio."""
    for c in chamada_ids:
        chamada = Chamadas.query.get_or_404(int(c))
        chamada.id_relaciona = 'C' + conv
        db.session.commit()


def desassociar_chamada(chamada_id):
    """Remove a associação de uma chamada com qualquer convênio."""
    chamada = Chamadas.query.get_or_404(chamada_id)
    chamada.id_relaciona = ''
    db.session.commit()


def buscar_nd(id):
    """Busca o registro de natureza de despesa (ND) de um empenho, se existir."""
    return Emp_Cap_Cus.query.get(id)


def salvar_nd(id, nd_registro, nd_valor, usuario_id):
    """Cria ou atualiza a natureza de despesa (ND) de um empenho."""
    if nd_registro is not None:
        nd_registro.nd = nd_valor
    else:
        nd_registro = Emp_Cap_Cus(id_empenho=id, nd=nd_valor)
        db.session.add(nd_registro)

    db.session.commit()

    registra_log_auto(usuario_id, None, 'and')


def buscar_numero_empenho(id):
    """Busca o número do empenho a partir do seu ID."""
    return db.session.query(Empenho.NR_EMPENHO).filter(Empenho.ID_EMPENHO == id).first()


def demandas_do_convenio(conv):
    """
    Retorna os dados necessários para exibir as demandas relacionadas
    a um convênio: contagem, lista de demandas, SEI e autores.
    """
    programa_siconv = db.session.query(
        Proposta.ID_PROPOSTA, Proposta.ID_PROGRAMA, Proposta.UF_PROPONENTE,
        Programa.COD_PROGRAMA, Programa_Interesse.sigla, Programa.ANO_DISPONIBILIZACAO
    ).join(Programa, Programa.ID_PROGRAMA == Proposta.ID_PROGRAMA)\
     .outerjoin(Programa_Interesse, Programa_Interesse.cod_programa == Programa.COD_PROGRAMA)\
     .subquery()

    conv_SEI = db.session.query(DadosSEI.sei, programa_siconv.c.sigla, DadosSEI.nr_convenio)\
                         .filter_by(nr_convenio=conv)\
                         .join(Convenio, DadosSEI.nr_convenio == Convenio.NR_CONVENIO)\
                         .join(programa_siconv, programa_siconv.c.ID_PROPOSTA == Convenio.ID_PROPOSTA)\
                         .first()

    if conv_SEI is not None:
        SEI = conv_SEI.sei
        SEI_s = str(SEI).split('/')[0] + '_' + str(SEI).split('/')[1]
        conv_SEI_programa = conv_SEI.sigla
        conv_SEI_nr_convenio = conv_SEI.nr_convenio
        conv_SEI_ano = 0
    else:
        SEI = "?"
        SEI_s = "?"
        conv_SEI_programa = "?"
        conv_SEI_nr_convenio = 0
        conv_SEI_ano = 0

    demandas_count = Demanda.query.filter(Demanda.convênio == conv).count()

    demandas = Demanda.query.filter(Demanda.convênio == conv)\
                            .order_by(Demanda.data.desc()).all()

    autores = []
    for demanda in demandas:
        autores.append(str(User.query.filter_by(id=demanda.user_id).first()).split(';')[0])

    dados = [conv_SEI_programa, SEI_s, conv_SEI_nr_convenio, conv_SEI_ano]

    return {
        'demandas_count': demandas_count,
        'demandas': demandas,
        'sei': SEI,
        'autores': autores,
        'dados': dados,
    }


def mensagens_siconv():
    """
    Retorna as mensagens do SICONV previamente carregadas, junto com a
    data de referência da carga (ou None, se não houver mensagens).
    """
    programa_siconv = db.session.query(
        Proposta.ID_PROPOSTA, Proposta.ID_PROGRAMA, Proposta.UF_PROPONENTE,
        Programa.COD_PROGRAMA, Programa_Interesse.sigla, Programa.ANO_DISPONIBILIZACAO
    ).join(Programa, Programa.ID_PROGRAMA == Proposta.ID_PROGRAMA)\
     .outerjoin(Programa_Interesse, Programa_Interesse.cod_programa == Programa.COD_PROGRAMA)\
     .subquery()

    msgs = db.session.query(
        MSG_Siconv.data_ref, MSG_Siconv.nr_convenio, MSG_Siconv.desc,
        programa_siconv.c.sigla, DadosSEI.epe, programa_siconv.c.UF_PROPONENTE,
        DadosSEI.sei, Convenio.SIT_CONVENIO, MSG_Siconv.sit
    ).join(DadosSEI, MSG_Siconv.nr_convenio == DadosSEI.nr_convenio)\
     .join(Convenio, MSG_Siconv.nr_convenio == Convenio.NR_CONVENIO)\
     .join(programa_siconv, programa_siconv.c.ID_PROPOSTA == Convenio.ID_PROPOSTA)\
     .order_by(programa_siconv.c.sigla, MSG_Siconv.desc).all()

    data_ref = msgs[0].data_ref if msgs else None

    return msgs, data_ref


# =============================================================================
# Dashboards / mapas
# =============================================================================

def _unidades_hierarquia(unidade):
    """Retorna a lista de coordenações a considerar (a própria unidade + filhas, se houver)."""
    hierarquia = db.session.query(Coords.sigla).filter(Coords.pai == unidade).all()

    if hierarquia:
        l_unid = [f.sigla for f in hierarquia]
        l_unid.append(unidade)
        return l_unid

    return [unidade]


def quadro_convenios(unidade):
    """
    Monta o quadro de convênios em execução, cruzando UF x Programa,
    para a coordenação do usuário (e suas filhas, se houver).
    """
    l_unid = _unidades_hierarquia(unidade)

    programas = db.session.query(Programa.ID_PROGRAMA, Programa_Interesse.sigla,
                                 label('UF', Proposta.UF_PROPONENTE), Proposta.ID_PROPOSTA)\
                          .join(Proposta, Proposta.ID_PROGRAMA == Programa.ID_PROGRAMA)\
                          .join(Programa_Interesse, Programa_Interesse.cod_programa == Programa.COD_PROGRAMA)\
                          .filter(Programa_Interesse.coord.in_(l_unid))\
                          .subquery()

    convenios = db.session.query(func.count(Convenio.NR_CONVENIO), programas.c.sigla,
                                 func.sum(Convenio.VL_GLOBAL_CONV), programas.c.UF)\
                          .filter(Convenio.SIT_CONVENIO == "Em execução")\
                          .join(programas, programas.c.ID_PROPOSTA == Convenio.ID_PROPOSTA)\
                          .order_by(programas.c.UF, programas.c.sigla)\
                          .group_by(programas.c.UF, programas.c.sigla)\
                          .all()

    ufs = sorted(set(uf.UF for uf in convenios))
    programas_int = sorted(set(p.sigla for p in convenios))

    data_carga = db.session.query(RefSICONV.data_ref).first()

    convenios_s = []
    for conv in convenios:
        conv_s = list(conv)
        if conv_s[2] is not None:
            conv_s[2] = locale.currency(conv_s[2], symbol=False, grouping=True)
        convenios_s.append(conv_s)

    linhas = []
    for uf in ufs:
        linha = []
        for prog in programas_int:
            flag = False
            item = []
            for conv in convenios_s:
                if conv[3] == uf:
                    if conv[1] == prog:
                        linha.append(conv)
                        flag = True
                    else:
                        item = [0, prog, '', uf]

            if not flag:
                linha.append(item)

        linhas.append(linha)

    return {
        'quantidade': len(ufs),
        'programas': programas_int,
        'linhas': linhas,
        'data_carga': str(data_carga[0]),
    }


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

_CORES_PROGRAMA = {
    'PRONEX': 'blue', 'PRONEM': 'orange', 'PPP': 'green', 'EMENDA': 'purple',
}


def gerar_mapa_brasil_convenios():
    """
    Gera o mapa (folium) de convênios por UF, com um círculo por
    combinação UF/programa, cujo raio é proporcional à quantidade de
    convênios.
    """
    programa_siconv = db.session.query(
        Proposta.ID_PROPOSTA, Proposta.ID_PROGRAMA, Proposta.UF_PROPONENTE,
        Programa.COD_PROGRAMA, Programa_Interesse.sigla, Programa.ANO_DISPONIBILIZACAO
    ).join(Programa, Programa.ID_PROGRAMA == Proposta.ID_PROGRAMA)\
     .outerjoin(Programa_Interesse, Programa_Interesse.cod_programa == Programa.COD_PROGRAMA)\
     .subquery()

    convenios = db.session.query(func.count(Convenio.NR_CONVENIO), programa_siconv.c.sigla,
                                 func.sum(Convenio.VL_GLOBAL_CONV), programa_siconv.c.UF_PROPONENTE)\
                          .filter(Convenio.DIA_PUBL_CONV != '')\
                          .join(programa_siconv, programa_siconv.c.ID_PROPOSTA == Convenio.ID_PROPOSTA)\
                          .order_by(programa_siconv.c.UF_PROPONENTE, programa_siconv.c.sigla)\
                          .group_by(programa_siconv.c.UF_PROPONENTE)\
                          .group_by(programa_siconv.c.sigla)\
                          .all()

    convenios_s = []
    for conv in convenios:
        conv_s = list(conv)
        if conv_s[2] is not None:
            conv_s[2] = locale.currency(conv_s[2], symbol=False, grouping=True)
        if conv_s[1] is not None:
            convenios_s.append(conv_s)

    progs = {}
    programas = db.session.query(Programa_Interesse.sigla)\
                          .order_by(Programa_Interesse.sigla)\
                          .group_by(Programa_Interesse.sigla).all()

    for i, p in enumerate(programas):
        if i == 0:
            progs[p.sigla] = [0, 0]
        else:
            ang = (i - 1) * (2 * math.pi / len(programas))
            progs[p.sigla] = [0.4 * math.cos(ang), 0.4 * math.sin(ang)]

    linha = []
    for conv in convenios_s:
        conv.append(_GPS_UF[conv[3]])
        conv.append(progs[conv[1]])
        linha.append(conv)

    m = Map(location=[-15.7, -47.9], tiles='OpenStreetMap', control_scale=True,
            zoom_start=2, min_zoom=2)
    m.fit_bounds([[-34, -74], [3, -34]])

    for l in linha:
        tip = '<b>' + l[3] + ' - ' + l[1] + '</b>' + '<br>' + str(l[0]) + ' conv&ecirc;nio(s)' + '<br>' + 'Valor Global: ' + l[2]
        cor = _CORES_PROGRAMA.get(l[1], 'gray')

        Circle(
            location=[float(l[4][0]) + float(l[5][0]), float(l[4][1]) + float(l[5][1])],
            radius=12000 * int(l[0]),
            tooltip=tip,
            fill=True,
            fill_opacity=0.2,
            color=cor,
        ).add_to(m)

    return m._repr_html_()


def _percentuais_convenio(conv):
    """
    Calcula os percentuais de repasse/desembolso e de ingresso de
    contrapartida de um convênio, evitando divisão por zero (checando
    sempre o denominador, não o numerador).
    """
    if not conv.VL_REPASSE_CONV:
        percent_repass_desemb = 0
    else:
        percent_repass_desemb = round(100 * conv.VL_DESEMBOLSADO_CONV / conv.VL_REPASSE_CONV)

    if not conv.VL_CONTRAPARTIDA_CONV:
        percent_ingre_contrap = 0
    else:
        percent_ingre_contrap = round(100 * conv.VL_INGRESSO_CONTRAPARTIDA / conv.VL_CONTRAPARTIDA_CONV)

    return percent_repass_desemb, percent_ingre_contrap


def _listar_convenios_quadro(unidade, filtros_extra, order_by):
    """
    Consulta compartilhada por lista_convenios_quadro, lista_convenios_uf
    e lista_convenios_prog — a única diferença entre as três telas é o
    filtro aplicado (UF+programa, só UF, ou só programa).
    """
    l_unid = _unidades_hierarquia(unidade)

    programa_siconv = db.session.query(
        Proposta.ID_PROPOSTA, Proposta.ID_PROGRAMA, Proposta.UF_PROPONENTE,
        Programa.COD_PROGRAMA, Programa_Interesse.sigla, Programa.ANO_DISPONIBILIZACAO
    ).join(Programa, Programa.ID_PROGRAMA == Proposta.ID_PROGRAMA)\
     .join(Programa_Interesse, Programa_Interesse.cod_programa == Programa.COD_PROGRAMA)\
     .filter(Programa_Interesse.coord.in_(l_unid))\
     .subquery()

    query = db.session.query(
        Convenio.NR_CONVENIO, DadosSEI.nr_convenio, programa_siconv.c.ANO_DISPONIBILIZACAO,
        DadosSEI.sei, DadosSEI.epe, programa_siconv.c.UF_PROPONENTE, programa_siconv.c.sigla,
        Convenio.SIT_CONVENIO, Convenio.SUBSITUACAO_CONV, Convenio.DIA_FIM_VIGENC_CONV,
        Convenio.VL_GLOBAL_CONV, DadosSEI.id, Convenio.VL_REPASSE_CONV,
        Convenio.VL_DESEMBOLSADO_CONV, Convenio.VL_CONTRAPARTIDA_CONV,
        Convenio.VL_INGRESSO_CONTRAPARTIDA
    ).filter(Convenio.SIT_CONVENIO == "Em execução", *filtros_extra(programa_siconv))\
     .join(programa_siconv, programa_siconv.c.ID_PROPOSTA == Convenio.ID_PROPOSTA)\
     .outerjoin(DadosSEI, Convenio.NR_CONVENIO == DadosSEI.nr_convenio)\
     .order_by(*order_by(programa_siconv))\
     .all()

    data_carga = db.session.query(RefSICONV.data_ref).first()

    convenio_s = []
    for conv in query:
        conv_s = list(conv)
        if conv_s[10] is not None:
            conv_s[10] = locale.currency(conv_s[10], symbol=False, grouping=True)
        if conv_s[12] is not None:
            conv_s[12] = locale.currency(conv_s[12], symbol=False, grouping=True)
        if conv_s[14] is not None:
            conv_s[14] = locale.currency(conv_s[14], symbol=False, grouping=True)
        if conv_s[9] is not None:
            conv_s[9] = conv_s[9].strftime('%x')

        percent_repass_desemb, percent_ingre_contrap = _percentuais_convenio(conv)

        conv_s.append((conv.DIA_FIM_VIGENC_CONV - dt.date.today()).days)
        conv_s.append(percent_repass_desemb)
        conv_s.append(percent_ingre_contrap)

        convenio_s.append(conv_s)

    return {
        'convenio': convenio_s,
        'quantidade': len(query),
        'data_carga': str(data_carga[0]),
    }


def listar_convenios_quadro(unidade, uf, programa):
    """Lista de convênios em execução de uma UF em um programa específico."""
    dados = _listar_convenios_quadro(
        unidade,
        filtros_extra=lambda p: (p.c.UF_PROPONENTE == uf, p.c.sigla == programa),
        order_by=lambda p: (Convenio.DIA_FIM_VIGENC_CONV, p.c.ANO_DISPONIBILIZACAO.desc()),
    )
    dados['uf'] = uf
    dados['programa'] = programa
    return dados


def listar_convenios_uf(unidade, uf):
    """Lista de convênios em execução de uma UF, em todos os programas."""
    dados = _listar_convenios_quadro(
        unidade,
        filtros_extra=lambda p: (p.c.UF_PROPONENTE == uf,),
        order_by=lambda p: (p.c.sigla, Convenio.SIT_CONVENIO, Convenio.DIA_FIM_VIGENC_CONV, p.c.ANO_DISPONIBILIZACAO.desc()),
    )
    dados['uf'] = uf
    dados['programa'] = 'todos'
    return dados


def listar_convenios_prog(unidade, programa):
    """Lista de convênios em execução de um programa específico, em todas as UFs."""
    dados = _listar_convenios_quadro(
        unidade,
        filtros_extra=lambda p: (p.c.sigla == programa,),
        order_by=lambda p: (Convenio.DIA_FIM_VIGENC_CONV, p.c.ANO_DISPONIBILIZACAO.desc()),
    )
    dados['uf'] = '*'
    dados['programa'] = programa
    return dados


def resumo_convenios(unidade):
    """
    Monta o resumo de convênios por programa da coordenação (e suas
    filhas, se houver): quantidade, valores agregados e percentuais.
    """
    l_unid = _unidades_hierarquia(unidade)

    convenios_exec = db.session.query(Convenio.ID_PROPOSTA, label('conv_exec', Convenio.NR_CONVENIO))\
                               .filter(Convenio.SIT_CONVENIO == 'Em execução')\
                               .subquery()

    programas = db.session.query(
        Programa_Interesse.cod_programa, Programa_Interesse.sigla,
        label('qtd', func.count(Convenio.NR_CONVENIO)),
        label('vl_global', func.sum(Convenio.VL_GLOBAL_CONV)),
        label('vl_repasse', func.sum(Convenio.VL_REPASSE_CONV)),
        label('vl_empenhado', func.sum(Convenio.VL_EMPENHADO_CONV)),
        label('vl_desembolsado', func.sum(Convenio.VL_DESEMBOLSADO_CONV)),
        label('vl_contrapartida', func.sum(Convenio.VL_CONTRAPARTIDA_CONV)),
        label('vl_ingresso_contra', func.sum(Convenio.VL_INGRESSO_CONTRAPARTIDA)),
        label('qtd_exec', func.count(convenios_exec.c.conv_exec)),
    ).join(Programa, Programa.COD_PROGRAMA == Programa_Interesse.cod_programa)\
     .join(Proposta, Proposta.ID_PROGRAMA == Programa.ID_PROGRAMA)\
     .join(Convenio, Convenio.ID_PROPOSTA == Proposta.ID_PROPOSTA)\
     .filter(Convenio.DIA_PUBL_CONV != '', Programa_Interesse.coord.in_(l_unid))\
     .outerjoin(convenios_exec, convenios_exec.c.ID_PROPOSTA == Proposta.ID_PROPOSTA)\
     .group_by(Programa_Interesse.sigla, Programa_Interesse.cod_programa)\
     .order_by(Programa_Interesse.sigla.desc(), Programa_Interesse.cod_programa)\
     .all()

    data_carga = db.session.query(RefSICONV.data_ref).first()

    programas_s = []
    for prog in programas:
        prog_s = list(prog)

        prog_s[3] = locale.currency(none_0(prog_s[3]), symbol=False, grouping=True)
        prog_s[4] = locale.currency(none_0(prog_s[4]), symbol=False, grouping=True)
        prog_s[5] = locale.currency(none_0(prog_s[5]), symbol=False, grouping=True)
        prog_s[6] = locale.currency(none_0(prog_s[6]), symbol=False, grouping=True)
        prog_s[7] = locale.currency(none_0(prog_s[7]), symbol=False, grouping=True)
        prog_s[8] = locale.currency(none_0(prog_s[8]), symbol=False, grouping=True)

        # Sempre acrescenta os 3 percentuais (com 0 quando o denominador é
        # zero), pois o template acessa essas posições incondicionalmente.
        if none_0(prog.vl_repasse) != 0:
            empenhado_repasse = round(100 * float(none_0(prog.vl_empenhado)) / float(none_0(prog.vl_repasse)))
            desembolsado_repasse = round(100 * float(none_0(prog.vl_desembolsado)) / float(none_0(prog.vl_repasse)))
        else:
            empenhado_repasse = 0
            desembolsado_repasse = 0

        prog_s.append(empenhado_repasse)
        prog_s.append(desembolsado_repasse)

        if none_0(prog.vl_contrapartida) != 0:
            ingressado_contrapartida = round(100 * float(none_0(prog.vl_ingresso_contra)) / float(none_0(prog.vl_contrapartida)))
        else:
            ingressado_contrapartida = 0

        prog_s.append(ingressado_contrapartida)

        programas_s.append(prog_s)

    return programas_s, str(data_carga[0])
