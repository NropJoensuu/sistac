"""
.. topic:: Convênios (views)

    Os Convênios são instrumentos de parceria entre o CNPq e Entidades Parceiras Estaduais - EPEs onde
    há repasse direto de recursos das partes para a conta do convênio.

    Os convênios são gerenciados por meio do SICONV, contudo o trâmite administrativo no CNPq demanda os registros em processo
    SEI.

    Um convênio tem atributos relativos ao SEI registrados manualmente. Demais dados podem ser importados do SICONV.

    Os campos relativos ao SEI são:

    * Número do convênio no SICONV
    * Ano do convênio no SICONV
    * Número do processo SEI
    * Sigla da EPE
    * Unidade da Federação da EPE
    * Sigla do programa

    Dados relativos ao importado do SICONV estão em implementação...

.. topic:: Ações relacionadas aos convênios

    * Lista programas da coordenação: lista_programas_pref
    * Atualiza lista de programas da coordenação: prog_pref_update
    * Atualizar dados SEI de um convenio: update_SEI (a ser retirado)
    * Registrar um dados SEI de um convê no sistema: cria_SEI
    * Listar convênios SICONV: lista_convenios_SICONV
    * Mostra detalhes de um determinado convênio: convenio_detalhes
    * Listar demandas de um determinado Convênio: SEI_demandas
    * Listar mensagens SICONV previamente carregadas: msg_siconv
    * Mostra quadro de convênios por UF: quadro_convenios
    * Mostra mapa do Brasil com dados dos convênios: brasil_convenios
    * Lista os convênios conforme selecionado no quado de convênios: lista_convenios_mapa
    * Lista todos os convênios de uma UF selecionada no quado de convênios: lista_convenios_uf
    * Mostra dados gerais dos programas e seus convênios: resumo_convenios

"""

# views.py na pasta convenios

from flask import render_template,url_for,flash, redirect,request,Blueprint,send_from_directory
from flask_login import current_user,login_required
from sqlalchemy import func, distinct, literal, text, or_
from sqlalchemy.sql import label
from sqlalchemy.orm import aliased
from project import db
from project.models import DadosSEI, Convenio, Demanda, User, Programa_Interesse, RefSICONV, Empenho,\
                           Desembolso, Pagamento, Chamadas, MSG_Siconv, Proposta, Programa, Coords, Emp_Cap_Cus, Crono_Desemb, Plano_Trabalho
from project.convenios.forms import SEIForm, ProgPrefForm, ListaForm, NDForm, ChamadaConvForm
from project.demandas.views import registra_log_auto
from project.convenios import services

import locale
import datetime
from datetime import date
from calendar import monthrange

import csv
import folium
from folium import Map, Circle, Popup
from folium.plugins import FloatImage
import math
from fpdf import FPDF
import os.path




convenios = Blueprint('convenios',__name__,
                            template_folder='templates/convenios')

#

def none_0(a):
    '''
    DOCSTRING: Transforma None em 0.
    INPUT: campo a ser trandormado.
    OUTPUT: 0, se a entrada for None, caso contrário, a entrada.
    '''
    if a == None:
        a = 0
    return a


def cria_csv(arq,linha,tabela):
  '''Recebe caminho do arquivo como string, campos da tabela como lista e a tabela propriamente dita'''
  with open(arq,'w',encoding='UTF8',newline='') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(linha)
        writer.writerows(tabela)


## lista programas da coordenação

@convenios.route('/lista_programas_pref')
def lista_programas_pref():
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta uma lista dos programas da instituição.                                      |
    |                                                                                       |
    +---------------------------------------------------------------------------------------+
    """
    progs, cod_inst = services.listar_programas()

    return render_template('lista_programas_pref.html', progs=progs, quantidade=len(progs), cod_inst=cod_inst)

#
### ATUALIZAR LISTA DE PROGRAMAS PREFERENCIAIS (PROGRAMAS DA COORDENAÇÃO)

@convenios.route("/<int:cod_prog>/update", methods=['GET', 'POST'])
@login_required
def prog_pref_update(cod_prog):
    """
    +----------------------------------------------------------------------------------------------+
    |Permite atualizar os dados de um programa preferencial (programa da coordenação).             |
    |                                                                                              |
    |Recebe o código do progrma como parâmetro.                                                    |
    +----------------------------------------------------------------------------------------------+
    """

    programa = services.buscar_programa(cod_prog)
    programa_interesse = services.buscar_programa_interesse(cod_prog)

    form = ProgPrefForm()

    if form.validate_on_submit():

        _, status = services.salvar_programa_interesse(
            programa.COD_PROGRAMA, form.sigla.data, form.coord.data, current_user.id)

        if status == 'inserido':
            flash('Programa preferencial inserido!','sucesso')
        else:
            flash('Programa preferencial atualizado!','sucesso')

        return redirect(url_for('convenios.lista_programas_pref'))
    # traz a informação atual do programa
    elif request.method == 'GET':

        form.cod_programa.data = programa.COD_PROGRAMA
        form.desc.data         = programa.NOME_PROGRAMA
        if programa_interesse is None:
            form.sigla.data        = ''
            form.coord.data        = ''
        else:
            form.sigla.data        = programa_interesse.sigla
            form.coord.data        = programa_interesse.coord

    return render_template('add_prog_pref.html',
                           form=form)

## lista convênios

@convenios.route('/<lista>/<coord>/lista_convenios_SICONV', methods=['GET', 'POST'])
def lista_convenios_SICONV(lista,coord):
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta uma lista dos convênios.                                                     |
    |                                                                                       |
    +---------------------------------------------------------------------------------------+
    """

    # pega unidade do usuário logado
    unidade = db.session.query(User.coord).filter(User.id==current_user.id).first()

    form = ListaForm()

    if form.validate_on_submit():

        coord = form.coord.data

        if coord == '' or coord == None:
            coord = '*'

        return redirect(url_for('convenios.lista_convenios_SICONV',lista=lista,coord=coord))

    else:

        #
        if coord == '*':

            form.coord.data = ''

            programa = db.session.query(Proposta.ID_PROPOSTA,
                                        Proposta.ID_PROGRAMA,
                                        Proposta.UF_PROPONENTE,
                                        Programa.COD_PROGRAMA,
                                        Programa_Interesse.sigla,
                                        Programa.ANO_DISPONIBILIZACAO,
                                        Programa_Interesse.coord)\
                                        .join(Programa,Programa.ID_PROGRAMA == Proposta.ID_PROGRAMA)\
                                        .outerjoin(Programa_Interesse,Programa_Interesse.cod_programa == Programa.COD_PROGRAMA)\
                                        .subquery()
        elif coord == 'usu':

            form.coord.data = unidade.coord

            # se unidade for pai, pega filhos
            filhos = db.session.query(Coords.sigla).filter(Coords.pai == unidade.coord).all()
            l_filhos = [f.sigla for f in filhos]
            l_filhos.append(unidade.coord)

            if filhos:
                unid = l_filhos
                programa = db.session.query(Proposta.ID_PROPOSTA,
                                        Proposta.ID_PROGRAMA,
                                        Proposta.UF_PROPONENTE,
                                        Programa.COD_PROGRAMA,
                                        Programa_Interesse.sigla,
                                        Programa.ANO_DISPONIBILIZACAO,
                                        Programa_Interesse.coord)\
                                        .join(Programa,Programa.ID_PROGRAMA == Proposta.ID_PROGRAMA)\
                                        .outerjoin(Programa_Interesse,Programa_Interesse.cod_programa == Programa.COD_PROGRAMA)\
                                        .filter(Programa_Interesse.coord.in_(unid))\
                                        .subquery()
            else:
                unid = unidade.coord
                programa = db.session.query(Proposta.ID_PROPOSTA,
                                        Proposta.ID_PROGRAMA,
                                        Proposta.UF_PROPONENTE,
                                        Programa.COD_PROGRAMA,
                                        Programa_Interesse.sigla,
                                        Programa.ANO_DISPONIBILIZACAO,
                                        Programa_Interesse.coord)\
                                        .join(Programa,Programa.ID_PROGRAMA == Proposta.ID_PROGRAMA)\
                                        .outerjoin(Programa_Interesse,Programa_Interesse.cod_programa == Programa.COD_PROGRAMA)\
                                        .filter(Programa_Interesse.coord == unid)\
                                        .subquery()
        
        else:

            form.coord.data = coord

            if coord == 'inst':
                programa = db.session.query(Proposta.ID_PROPOSTA,
                                            Proposta.ID_PROGRAMA,
                                            Proposta.UF_PROPONENTE,
                                            Programa.COD_PROGRAMA,
                                            Programa_Interesse.sigla,
                                            Programa.ANO_DISPONIBILIZACAO,
                                            Programa_Interesse.coord)\
                                            .join(Programa,Programa.ID_PROGRAMA == Proposta.ID_PROGRAMA)\
                                            .outerjoin(Programa_Interesse,Programa_Interesse.cod_programa == Programa.COD_PROGRAMA)\
                                            .subquery()
            else:
                programa = db.session.query(Proposta.ID_PROPOSTA,
                                            Proposta.ID_PROGRAMA,
                                            Proposta.UF_PROPONENTE,
                                            Programa.COD_PROGRAMA,
                                            Programa_Interesse.sigla,
                                            Programa.ANO_DISPONIBILIZACAO,
                                            Programa_Interesse.coord)\
                                            .join(Programa,Programa.ID_PROGRAMA == Proposta.ID_PROGRAMA)\
                                            .join(Programa_Interesse,Programa_Interesse.cod_programa == Programa.COD_PROGRAMA)\
                                            .filter(Programa_Interesse.coord.like('%'+coord+'%'))\
                                            .subquery()

        if lista == 'todos':

            convenio = db.session.query(Convenio.NR_CONVENIO,
                                        programa.c.ANO_DISPONIBILIZACAO,
                                        programa.c.coord,
                                        DadosSEI.sei,
                                        DadosSEI.epe,
                                        programa.c.UF_PROPONENTE,
                                        programa.c.sigla,
                                        Convenio.SIT_CONVENIO,
                                        Convenio.SUBSITUACAO_CONV,
                                        Convenio.DIA_FIM_VIGENC_CONV,
                                        Convenio.VL_REPASSE_CONV,
                                        Convenio.VL_CONTRAPARTIDA_CONV,
                                        Convenio.VL_DESEMBOLSADO_CONV,
                                        Convenio.VL_INGRESSO_CONTRAPARTIDA,
                                        (Convenio.VL_REPASSE_CONV - Convenio.VL_DESEMBOLSADO_CONV).label('vl_a_desembolsar'),
                                        (Convenio.DIA_FIM_VIGENC_CONV - datetime.date.today()).label('prazo'))\
                                        .filter(Convenio.DIA_PUBL_CONV != '')\
                                        .join(programa, programa.c.ID_PROPOSTA == Convenio.ID_PROPOSTA)\
                                        .outerjoin(DadosSEI, Convenio.NR_CONVENIO == DadosSEI.nr_convenio)\
                                        .order_by(programa.c.sigla.desc(),Convenio.SIT_CONVENIO.desc())\
                                        .all()
    #
        elif lista == 'em execução':

            convenio = db.session.query(Convenio.NR_CONVENIO,
                                        programa.c.ANO_DISPONIBILIZACAO,
                                        programa.c.coord,
                                        DadosSEI.sei,
                                        DadosSEI.epe,
                                        programa.c.UF_PROPONENTE,
                                        programa.c.sigla,
                                        Convenio.SIT_CONVENIO,
                                        Convenio.SUBSITUACAO_CONV,
                                        Convenio.DIA_FIM_VIGENC_CONV,
                                        Convenio.VL_REPASSE_CONV,
                                        Convenio.VL_CONTRAPARTIDA_CONV,
                                        Convenio.VL_DESEMBOLSADO_CONV,
                                        Convenio.VL_INGRESSO_CONTRAPARTIDA,
                                        (Convenio.VL_REPASSE_CONV - Convenio.VL_DESEMBOLSADO_CONV).label('vl_a_desembolsar'),
                                        (Convenio.DIA_FIM_VIGENC_CONV - datetime.date.today()).label('prazo'))\
                                        .join(programa, programa.c.ID_PROPOSTA == Convenio.ID_PROPOSTA)\
                                        .outerjoin(DadosSEI, Convenio.NR_CONVENIO == DadosSEI.nr_convenio)\
                                        .filter(Convenio.SIT_CONVENIO == 'Em execução')\
                                        .order_by(Convenio.SUBSITUACAO_CONV.desc(),Convenio.DIA_FIM_VIGENC_CONV,
                                                  programa.c.sigla.desc())\
                                        .all()

        #
        elif lista[:8] == 'programa':

            convenio = db.session.query(Convenio.NR_CONVENIO,
                                        programa.c.ANO_DISPONIBILIZACAO,
                                        programa.c.coord,
                                        DadosSEI.sei,
                                        DadosSEI.epe,
                                        programa.c.UF_PROPONENTE,
                                        programa.c.sigla,
                                        Convenio.SIT_CONVENIO,
                                        Convenio.SUBSITUACAO_CONV,
                                        Convenio.DIA_FIM_VIGENC_CONV,
                                        Convenio.VL_REPASSE_CONV,
                                        Convenio.VL_CONTRAPARTIDA_CONV,
                                        Convenio.VL_DESEMBOLSADO_CONV,
                                        Convenio.VL_INGRESSO_CONTRAPARTIDA,
                                        (Convenio.VL_REPASSE_CONV - Convenio.VL_DESEMBOLSADO_CONV).label('vl_a_desembolsar'),
                                        (Convenio.DIA_FIM_VIGENC_CONV - datetime.date.today()).label('prazo'))\
                                        .join(programa, programa.c.ID_PROPOSTA == Convenio.ID_PROPOSTA)\
                                        .outerjoin(DadosSEI, Convenio.NR_CONVENIO == DadosSEI.nr_convenio)\
                                        .filter(Convenio.DIA_PUBL_CONV != '',
                                                programa.c.sigla == lista[21:],
                                                programa.c.ANO_DISPONIBILIZACAO == lista[13:17])\
                                        .order_by(Convenio.SIT_CONVENIO,Convenio.DIA_FIM_VIGENC_CONV,
                                                  programa.c.sigla.desc())\
                                        .all()

        ## lê data de carga dos dados dos convênios
        data_carga = db.session.query(RefSICONV.data_ref).first()

        quantidade = len(convenio)

        cria_csv('/app/project/static/convenios.csv',
                 ['conv','ano','coord','sei','epe','uf','sigla','sit','subsit','fim','repasse','contrapartida','desemb','ingres_contra','vl_a_desembolsar','prazo'],
                 convenio)    

        # o comandinho mágico que permite fazer o download de um arquivo
        send_from_directory('/app/project/static', 'convenios.csv') 

        return render_template('list_convenios.html', convenio = convenio,   
                                                      quantidade = quantidade, 
                                                      lista = lista,
                                                      form = form,
                                                      data_carga = str(data_carga[0]))

#
## Mostra detalhes SICONV de um convênio e permite alterar dados SEI
@convenios.route('/<conv>/convenio_detalhes', methods=['GET', 'POST'])
def convenio_detalhes(conv):
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta os dados de um convênio específico.                                          |
    |Recebe o número do convênio como parâmetros.                                           |
    +---------------------------------------------------------------------------------------+
    """
    # pega dados SEI do convenio
    dadosSEI = db.session.query(DadosSEI).filter(DadosSEI.nr_convenio == conv).first()

    #grava dados enviados via formulário se este for submetido
    form = SEIForm()

    if form.validate_on_submit():

        if dadosSEI is None:

            dadosSEI = DadosSEI (nr_convenio = conv,
                                 sei         = form.sei.data,
                                 epe         = form.epe.data,
                                 fiscal      = form.fiscal.data)

            db.session.add(dadosSEI)

            db.session.commit()

            registra_log_auto(current_user.id,None,'sei')

            flash('Inserido registro SEI do convênio!','sucesso')

        else:

            dadosSEI.nr_convenio = conv
            dadosSEI.sei         = form.sei.data
            dadosSEI.epe         = form.epe.data
            dadosSEI.fiscal      = form.fiscal.data

            db.session.commit()

            registra_log_auto(current_user.id,None,'sei')

            flash('Registro SEI do convênio atualizado!','sucesso')

        return redirect(url_for('convenios.convenio_detalhes',conv=conv,form=form))

    # ou alimenta os campos da tela quando da consulta
    elif request.method == 'GET':

        if dadosSEI != None:
            form.nr_convenio.data = conv
            form.sei.data         = dadosSEI.sei
            form.epe.data         = dadosSEI.epe
            form.fiscal.data      = dadosSEI.fiscal
        else:
            form.nr_convenio.data = conv
            form.sei.data         = ''
            form.epe.data         = ''
            form.fiscal.data      = ''
    #
        convenio = db.session.query(Convenio).get(conv)

        ## lê data de carga dos dados dos convênios
        data_carga = db.session.query(RefSICONV.data_ref).first()

        # retirado pois a relação empenho/desembolso do SICONV é furada
        # empenho_desembolso = db.session.query(Empenho.NR_EMPENHO,
        #                                       Empenho.DESC_TIPO_NOTA,
        #                                       Empenho.DATA_EMISSAO,
        #                                       Empenho.DESC_SITUACAO_EMPENHO,
        #                                       Empenho.VALOR_EMPENHO,
        #                                       Desembolso.DATA_DESEMBOLSO,
        #                                       Desembolso.NR_SIAFI,
        #                                       Desembolso.VL_DESEMBOLSADO,
        #                                       Emp_Cap_Cus.nd,
        #                                       Empenho.ID_EMPENHO)\
        #                                      .outerjoin(Desembolso, Desembolso.ID_EMPENHO == Empenho.ID_EMPENHO)\
        #                                      .outerjoin(Emp_Cap_Cus, Emp_Cap_Cus.id_empenho == Empenho.ID_EMPENHO)\
        #                                      .filter(Empenho.NR_CONVENIO == conv, Desembolso.NR_CONVENIO == conv)\
        #                                      .order_by(Desembolso.DATA_DESEMBOLSO,Empenho.DATA_EMISSAO).all()

        # pegando somente dados de empenho
        empenho = db.session.query(Empenho.NR_EMPENHO,
                                              Empenho.DESC_TIPO_NOTA,
                                              Empenho.DATA_EMISSAO,
                                              Empenho.DESC_SITUACAO_EMPENHO,
                                              Empenho.VALOR_EMPENHO,
                                              Emp_Cap_Cus.nd,
                                              Empenho.ID_EMPENHO)\
                                             .outerjoin(Emp_Cap_Cus, Emp_Cap_Cus.id_empenho == Empenho.ID_EMPENHO)\
                                             .filter(Empenho.NR_CONVENIO == conv)\
                                             .order_by(Empenho.DATA_EMISSAO).all()

        desembolso_agrupado = db.session.query(Desembolso.DATA_DESEMBOLSO,
                                               Desembolso.NR_SIAFI,
                                               label('vl_desemb_agru',func.sum(Desembolso.VL_DESEMBOLSADO)))\
                                        .filter(Desembolso.NR_CONVENIO == conv)\
                                        .order_by(Desembolso.DATA_DESEMBOLSO)\
                                        .group_by(Desembolso.DATA_DESEMBOLSO, Desembolso.NR_SIAFI)\
                                        .all()

        empenho_tot = db.session.query(label('emp_tot',func.sum(Empenho.VALOR_EMPENHO)))\
                                   .filter(Empenho.NR_CONVENIO == conv)

        pagamento = db.session.query(Pagamento.IDENTIF_FORNECEDOR,
                                     Pagamento.NOME_FORNECEDOR,
                                     label("pago",func.sum(Pagamento.VL_PAGO)),
                                     label("qtd",func.count(Pagamento.VL_PAGO)))\
                                     .filter(Pagamento.NR_CONVENIO == conv)\
                                     .group_by(Pagamento.NOME_FORNECEDOR,Pagamento.IDENTIF_FORNECEDOR)\
                                     .order_by(Pagamento.NOME_FORNECEDOR).all()

        if dadosSEI != None:
            chamadas = db.session.query(Chamadas.id,
                                        Chamadas.chamada,
                                        Chamadas.qtd_projetos,
                                        Chamadas.vl_total_chamada,
                                        Chamadas.doc_sei,
                                        Chamadas.obs,
                                        Chamadas.id_relaciona)\
                                 .filter(Chamadas.id_relaciona == 'C'+conv).all()
        else:
            chamadas = None

        proposta = db.session.query(Proposta).filter(Proposta.ID_PROPOSTA == convenio.ID_PROPOSTA).first()

        programa = db.session.query(Programa).filter(Programa.ID_PROGRAMA == proposta.ID_PROGRAMA).first()

    # pega o cronograma de desembolso do convênio

        crono_desemb = db.session.query(Crono_Desemb.NR_CONVENIO,
                                        Crono_Desemb.NR_PARCELA_CRONO_DESEMBOLSO,
                                        Crono_Desemb.MES_CRONO_DESEMBOLSO,
                                        Crono_Desemb.ANO_CRONO_DESEMBOLSO,
                                        Crono_Desemb.TIPO_RESP_CRONO_DESEMBOLSO,
                                        Crono_Desemb.VALOR_PARCELA_CRONO_DESEMBOLSO)\
                                        .filter(Crono_Desemb.NR_CONVENIO == conv)\
                                        .order_by(Crono_Desemb.TIPO_RESP_CRONO_DESEMBOLSO,
                                                  Crono_Desemb.ANO_CRONO_DESEMBOLSO,
                                                  Crono_Desemb.MES_CRONO_DESEMBOLSO).all()

    # para cada parcela do cronograma, verifica que foi quitada, se houve atraso e projeta data para prorrogação de ofício
        crono_desemb_l = []
        acu = 0

        for parcela in crono_desemb:

            data_repasse = date(int(parcela.ANO_CRONO_DESEMBOLSO),
                                int(parcela.MES_CRONO_DESEMBOLSO),
                                monthrange(int(parcela.ANO_CRONO_DESEMBOLSO), int(parcela.MES_CRONO_DESEMBOLSO))[1])

            valor_repasse_acumulado =  parcela.VALOR_PARCELA_CRONO_DESEMBOLSO + float(acu)

            if parcela.TIPO_RESP_CRONO_DESEMBOLSO == 'Concedente':
                if valor_repasse_acumulado <= convenio.VL_DESEMBOLSADO_CONV:
                    sit = 'Quitada'
                else:
                    sit = 'Em aberto'
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

            if sit == 'Quitada':
                data_ref_atraso = data_desemb
            else:
                data_ref_atraso = datetime.date.today()

            if data_desemb == None:
                atraso = 0
                data_prorrog = None
            else:
                atraso       = (data_ref_atraso - data_repasse).days
                data_prorrog = convenio.DIA_FIM_VIGENC_CONV + datetime.timedelta(days=atraso)

            crono_desemb_l.append([parcela.NR_PARCELA_CRONO_DESEMBOLSO,
                                   data_repasse,
                                   parcela.TIPO_RESP_CRONO_DESEMBOLSO,
                                   locale.currency(parcela.VALOR_PARCELA_CRONO_DESEMBOLSO, symbol=False, grouping = True),
                                   sit,
                                   atraso,
                                   data_prorrog,
                                   data_ref_atraso])

            crono_desemb=list(enumerate(crono_desemb_l,1))                       

            acu = valor_repasse_acumulado

    #

        VL_GLOBAL_CONV              = locale.currency(convenio.VL_GLOBAL_CONV, symbol=False, grouping = True)

        if convenio.VL_REPASSE_CONV == 0 or convenio.VL_REPASSE_CONV == None:
            percent_desemb_repass   = 0
        else:
            percent_desemb_repass   = round(100*convenio.VL_DESEMBOLSADO_CONV / convenio.VL_REPASSE_CONV)

        if convenio.VL_CONTRAPARTIDA_CONV == 0 or convenio.VL_CONTRAPARTIDA_CONV == None:
            percent_ingre_contrap   = 0
        else:
            percent_ingre_contrap   = round(100*convenio.VL_INGRESSO_CONTRAPARTIDA / convenio.VL_CONTRAPARTIDA_CONV)

        if convenio.VL_REPASSE_CONV == 0 or convenio.VL_REPASSE_CONV == None:
            percent_empen_repass    = 0
        else:
            percent_empen_repass    = round(100*convenio.VL_EMPENHADO_CONV / convenio.VL_REPASSE_CONV)

        VL_REPASSE_CONV             = locale.currency(convenio.VL_REPASSE_CONV, symbol=False, grouping = True)
        VL_DESEMBOLSADO_CONV        = locale.currency(convenio.VL_DESEMBOLSADO_CONV, symbol=False, grouping = True)
        VL_EMPENHADO_CONV           = locale.currency(convenio.VL_EMPENHADO_CONV, symbol=False, grouping = True)
        VL_CONTRAPARTIDA_CONV       = locale.currency(convenio.VL_CONTRAPARTIDA_CONV, symbol=False, grouping = True)
        VL_INGRESSO_CONTRAPARTIDA   = locale.currency(convenio.VL_INGRESSO_CONTRAPARTIDA, symbol=False, grouping = True)
        VL_RENDIMENTO_APLICACAO     = locale.currency(convenio.VL_RENDIMENTO_APLICACAO, symbol=False, grouping = True)

        vl_a_empenhar    = locale.currency(convenio.VL_REPASSE_CONV - convenio.VL_EMPENHADO_CONV, symbol=False, grouping = True)
        vl_a_desembolsar = locale.currency(convenio.VL_REPASSE_CONV - convenio.VL_DESEMBOLSADO_CONV, symbol=False, grouping = True)

        pagamento_s = []
        pag_tot = 0
        for pag in pagamento:
            pag_s = list(pag)
            pag_tot += pag[2]
            if pag_s[2] is not None:
                pag_s[2] = locale.currency(pag_s[2], symbol=False, grouping = True)

            pagamento_s.append(pag_s)

        qtd_pag = len(pagamento)

        # formatação de dados da junção empenho e desembolso
        # emp_tot = 0
        # desemb_tot = 0
        # empenho_desembolso_s = []
        #
        # for e_d in empenho_desembolso:
        #     e_d_s = list (e_d)
        #     if e_d_s[4] == None:
        #         p_emp = ''
        #     else:
        #         p_emp = locale.currency(e_d_s[4], symbol=False, grouping = True)
        #     if e_d_s[7] == None:
        #         p_des = ''
        #     else:
        #         p_des = locale.currency(e_d_s[7], symbol=False, grouping = True)
        #     if e_d_s[6] == None:
        #         siafi = ''
        #     else:
        #         siafi = e_d_s[6]
        #     if e_d_s[8] == None:
        #         nd = '?'
        #     else:
        #         nd = e_d_s[8]
        #
        #     empenho_desembolso_s.append([e_d_s[0],e_d_s[1],e_d_s[2],e_d_s[3],p_emp,e_d_s[5],siafi,p_des,nd,e_d_s[9]])
        #
        #     if e_d.VL_DESEMBOLSADO == None:
        #         desemb_tot += 0
        #     else:
        #         desemb_tot += e_d.VL_DESEMBOLSADO

        empenho_l = []

        for emp in empenho:

            empenho_l.append([emp.NR_EMPENHO, emp.DESC_TIPO_NOTA, emp.DATA_EMISSAO,
                              emp.DESC_SITUACAO_EMPENHO,
                              locale.currency(emp.VALOR_EMPENHO, symbol=False, grouping = True),
                              emp.nd,
                              emp.ID_EMPENHO])

        desembolso_l = []

        for desemb in desembolso_agrupado:

            desembolso_l.append([desemb.DATA_DESEMBOLSO,
                                 locale.currency(desemb.vl_desemb_agru, symbol=False, grouping = True),
                                 desemb.NR_SIAFI])

        chamadas_s = []
        chamadas_tot = 0
        qtd_proj = 0
        qtd_chamadas = 0
        if dadosSEI != None and dadosSEI.sei != "N.I.":
            for chamada in chamadas:
                chamadas_s.append([chamada.id,chamada.chamada,chamada.qtd_projetos,
                                  locale.currency(chamada.vl_total_chamada, symbol=False, grouping = True),
                                  chamada.doc_sei,chamada.obs])
                chamadas_tot += chamada.vl_total_chamada
                qtd_proj += chamada.qtd_projetos
            qtd_chamadas = len(chamadas)

        if dadosSEI != None and dadosSEI.sei != "N.I.":
            sei = str(dadosSEI.sei).split('/')[0]+'_'+str(dadosSEI.sei).split('/')[1]
        else:
            sei = 'Nº SEI não informado'

        if empenho_tot[0][0] == None:
            emp_total = 0
        else:
            emp_total = empenho_tot[0][0]


    # Prepara um pdf com detalhes do convênio

    class PDF_convenio(FPDF):
        # cabeçalho
        def header(self):

            self.set_font('Arial', 'B', 10)
            self.set_text_color(127,127,127)
            self.cell(0, 10, 'Dados do Convênio '+ str(conv) +' - gerado em '+date.today().strftime('%d/%m/%Y'), 1, 1,'C')
            self.ln(10)

        # Rodape da página
        def footer(self):
            # Posicionado a 1,5 cm do final da página
            self.set_y(-15)
            # Arial italic 8 cinza
            self.set_font('Arial', 'I', 8)
            self.set_text_color(127,127,127)
            # Numeração de página
            self.cell(0, 10, 'Página ' + str(self.page_no()) + '/{nb}', 0, 0, 'C')

    # Instanciando a classe herdada
    pdf = PDF_convenio()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_font('Times', '', 12)

    # Dados Gerais
    pdf.set_text_color(0,0,0)
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
    pdf.multi_cell(0, 5, programa.COD_PROGRAMA+' - '+programa.NOME_PROGRAMA.encode('latin-1', 'replace').decode('latin-1'))

    pdf.set_font('Arial', '', 10)

    pdf.cell(0, 10, 'Assinado em: '+ convenio.DIA_ASSIN_CONV + '   Publicado em: '+convenio.DIA_PUBL_CONV + '   Início: '+convenio.DIA_INIC_VIGENC_CONV + '   Término: '+convenio.DIA_FIM_VIGENC_CONV.strftime('%x'), 0, 0)
    pdf.ln(6)
    pdf.cell(0, 10, 'Situação da contratação: '+ convenio.SITUACAO_CONTRATACAO + '  Situação do convênio: '+convenio.SIT_CONVENIO + '  Subsituação: '+convenio.SUBSITUACAO_CONV + '  Opera OBTV: '+convenio.IND_OPERA_OBTV, 0, 0)
    pdf.ln(6)

    vazio_zero = lambda a: 0 if a=='' else a
    pdf.cell(0, 10, 'TAs já celebrados: '+str(vazio_zero(convenio.QTD_TA)) + '          Prorrogações já realizadas: '+str(vazio_zero(convenio.QTD_PRORROGA)), 0, 0)
    pdf.ln(6)

    pdf.cell(0, 10, 'Valor Global: R$ '+VL_GLOBAL_CONV, 0, 0)
    pdf.ln(6)

    pdf.cell(0, 10, 'Repasse: R$ '+ VL_REPASSE_CONV + '   Empenhado: R$ '+VL_EMPENHADO_CONV+' ('+str(percent_empen_repass)+'%)' + '   Desembolsado: R$ '+VL_DESEMBOLSADO_CONV+' ('+str(percent_desemb_repass)+'%) ', 0, 0)
    pdf.ln(6)

    pdf.cell(0, 10, 'Rendimento de aplicação: R$ '+ VL_RENDIMENTO_APLICACAO + '   A Empenhar: R$ '+vl_a_empenhar+' ('+str(100-percent_empen_repass)+'%)' + '   A Desembolsar: R$ '+vl_a_desembolsar+' ('+str(100-percent_desemb_repass)+'%)', 0, 0)
    pdf.ln(6)

    pdf.cell(0, 10, 'Contrapartida: R$ '+ VL_CONTRAPARTIDA_CONV +'     '+ 'Ingresso contrapartida: R$ '+VL_INGRESSO_CONTRAPARTIDA+' ('+str(percent_ingre_contrap)+'%)', 0, 0)
    pdf.ln(6)

    pdf.ln(6)
    pdf.dashed_line(pdf.get_x(), pdf.get_y(), pdf.get_x()+190, pdf.get_y(), 2, 3)
    pdf.ln(5)

    # Crono desembolso
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

    for parcela in crono_desemb:
        # pdf.cell(w = 20, h = 0, txt = '', border = 0, ln = 0, align = '', fill = False, link = '')
        pdf.cell(20, 10, str(parcela[0]), 0, 0, 'C')
        pdf.cell(20, 10, parcela[1][1].strftime('%x'), 0, 0, 'C')
        resp = lambda: 'CNPq' if parcela[1][2]=='Concedente' else ('Rendimento' if parcela[1][2][:10] == 'Rendimento' else 'Convenente')
        pdf.cell(20, 10, resp(), 0, 0, 'C')
        pdf.cell(20, 10, parcela[1][3], 0, 0, 'C')
        sit = lambda: 'Quitada em '+parcela[1][7].strftime('%x') if (parcela[1][2]=='Concedente' and parcela[1][4]=='Quitada' and parcela[1][7] != None) \
                                                                else ('Quitada em ???' if parcela[1][2]=='Concedente' and parcela[1][4]=='Quitada' and parcela[1][7] == None else \
                                                                parcela[1][4])                                                                         
        pdf.cell(40, 10, sit(), 0, 0, 'C')
        atraso = lambda: 'Não houve' if parcela[1][5] <= 0 else str(parcela[1][5])+' dias'
        pdf.cell(20, 10, atraso(), 0, 0, 'C')
        nova_data = lambda: parcela[1][6].strftime('%x') if parcela[1][5] > 0 else ''
        pdf.cell(20, 10, nova_data(), 0, 0, 'C')
        pdf.ln(5)

    pdf.ln(5)
    pdf.dashed_line(pdf.get_x(), pdf.get_y(), pdf.get_x()+190, pdf.get_y(), 2, 3)

    # Empenhos
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

    for item in empenho_l:
        # pdf.cell(w = 20, h = 0, txt = '', border = 0, ln = 0, align = '', fill = False, link = '')
        pdf.cell(35, 10, str(item[0]), 0, 0, 'C')
        pdf.cell(45, 10, str(item[1]), 0, 0, 'C')
        none_vazio = lambda a: '' if a==None else a.strftime('%x')
        pdf.cell(25, 10, str(none_vazio(item[2])), 0, 0, 'C')
        pdf.cell(30, 10, str(item[3]), 0, 0, 'C')
        pdf.cell(25, 10, str(item[4]), 0, 0, 'C')
        pdf.cell(15, 10, str(item[5]), 0, 0, 'C')
        pdf.ln(5)

    pdf.ln(5)
    pdf.dashed_line(pdf.get_x(), pdf.get_y(), pdf.get_x()+190, pdf.get_y(), 2, 3)

    # Desembolsos
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 10, 'Desembolsos', 0, 0)
    pdf.ln(15)

    pdf.set_font('Times', '', 10)
    pdf.cell(25, 10, 'Data', 0, 0, 'C')
    pdf.cell(25, 10, 'Nr Siafi', 0, 0, 'C')
    pdf.cell(25, 10, 'Valor (R$)', 0, 0, 'C')
    pdf.ln(5)

    for item in desembolso_l:
        # pdf.cell(w = 20, h = 0, txt = '', border = 0, ln = 0, align = '', fill = False, link = '')
        none_vazio = lambda a: '' if a==None else a.strftime('%x')
        pdf.cell(25, 10, str(none_vazio(item[0])), 0, 0, 'C')
        pdf.cell(25, 10, str(item[2]), 0, 0, 'C')
        pdf.cell(25, 10, str(item[1]), 0, 0, 'C')
        pdf.ln(5)

    pdf.ln(5)
    pdf.dashed_line(pdf.get_x(), pdf.get_y(), pdf.get_x()+190, pdf.get_y(), 2, 3)

    # Chamadas 
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 10, 'Chamadas', 0, 0)
    pdf.ln(15)

    pdf.set_font('Times', '', 10)

    for chamada in chamadas_s:
        # pdf.cell(w = 20, h = 0, txt = '', border = 0, ln = 0, align = '', fill = False, link = '')
        pdf.multi_cell(0, 5, str(chamada[1]).encode('latin-1', 'replace').decode('latin-1'), 0, 'L')
        pdf.cell(pdf.get_string_width('Projetos: '+str(chamada[2])), 10, 'Projetos: '+str(chamada[2]), 0, 0, 'L')
        pdf.cell(pdf.get_string_width('  Valor: '+str(chamada[3])), 10, '  Valor: '+str(chamada[3]), 0, 0, 'L')
        pdf.cell(pdf.get_string_width('  Ref. SEI: '+str(chamada[4])), 10, '  Ref. SEI: '+str(chamada[4]), 0, 0, 'L')
        pdf.ln(10)
        pdf.multi_cell(0, 5, 'Obs: '+str(chamada[5]).encode('latin-1', 'replace').decode('latin-1'), 0, 'L')

    pdf.ln(5)
    pdf.dashed_line(pdf.get_x(), pdf.get_y(), pdf.get_x()+190, pdf.get_y(), 2, 3)

    # Pagamentos
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 10, 'Pagamentos', 0, 0)
    pdf.ln(15)

    pdf.set_font('Times', '', 10)
    pdf.cell(35, 10, 'ID', 0, 0, 'C')
    pdf.cell(99, 10, 'NOME', 0, 0, 'C')
    pdf.cell(20, 10, 'QTD', 0, 0, 'C')
    pdf.cell(25, 10, 'VALOR', 0, 0, 'C')
    pdf.ln(5)

    for pag in pagamento_s:
        # pdf.cell(w = 20, h = 0, txt = '', border = 0, ln = 0, align = '', fill = False, link = '')
        pdf.cell(35, 10, str(pag[0]), 0, 0, 'C')
        pdf.cell(100, 10, str(pag[1]), 0, 0, 'C')
        pdf.cell(20, 10, str(pag[3]), 0, 0, 'C')
        pdf.cell(25, 10, str(pag[2]), 0, 0, 'C')
        pdf.ln(5)

    pdf.ln(5)
    pdf.dashed_line(pdf.get_x(), pdf.get_y(), pdf.get_x()+190, pdf.get_y(), 2, 3)
          
    pasta_pdf = os.path.normpath('/app/project/static/convenio.pdf')

    pdf.output(pasta_pdf, 'F')

    # o comandinho mágico que permite fazer o download de um arquivo
    send_from_directory('/app/project/static', 'convenio.pdf') 



    return render_template('convenio_detalhes.html',convenio=convenio,
                                                   dadosSEI = dadosSEI,
                                                   VL_GLOBAL_CONV = VL_GLOBAL_CONV,
                                                   VL_REPASSE_CONV = VL_REPASSE_CONV,
                                                   VL_DESEMBOLSADO_CONV = VL_DESEMBOLSADO_CONV,
                                                   VL_EMPENHADO_CONV = VL_EMPENHADO_CONV,
                                                   VL_CONTRAPARTIDA_CONV = VL_CONTRAPARTIDA_CONV,
                                                   VL_INGRESSO_CONTRAPARTIDA = VL_INGRESSO_CONTRAPARTIDA,
                                                   VL_RENDIMENTO_APLICACAO = VL_RENDIMENTO_APLICACAO,
                                                   vl_a_empenhar = vl_a_empenhar,
                                                   vl_a_desembolsar = vl_a_desembolsar,
                                                   empenho = empenho_l,
                                                   desembolso = desembolso_l,
                                                   pagamento=pagamento_s,
                                                   qtd_pag=qtd_pag,
                                                   pag_tot=locale.currency(pag_tot, symbol=False, grouping = True),
                                                   emp_tot=locale.currency(emp_total, symbol=False, grouping = True),
                                                   desemb_tot=locale.currency(convenio.VL_DESEMBOLSADO_CONV, symbol=False, grouping = True),
                                                   chamadas=chamadas_s,
                                                   qtd_chamadas=qtd_chamadas,
                                                   qtd_proj=qtd_proj,
                                                   chamadas_tot=locale.currency(chamadas_tot, symbol=False, grouping = True),
                                                   sei = sei,
                                                   data_carga = data_carga[0],
                                                   proposta=proposta,
                                                   percent_desemb_repass=percent_desemb_repass,
                                                   percent_ingre_contrap=percent_ingre_contrap,
                                                   percent_empen_repass=percent_empen_repass,
                                                   programa=programa,
                                                   crono_desemb=crono_desemb,
                                                   form=form)


### associar chamada a Convênio

@convenios.route("/associa_chamada/<conv>", methods=['GET', 'POST'])
@login_required
def associa_chamada(conv):
    """
    +---------------------------------------------------------------------------------------+
    |Permite associar uma chamada presente em uma lista a um convênio.                      |
    +---------------------------------------------------------------------------------------+
    """

    chamadas = db.session.query(Chamadas.id,Chamadas.chamada)\
                         .filter(or_(Chamadas.id_relaciona == None, Chamadas.id_relaciona == ''))\
                         .order_by(Chamadas.chamada)\
                         .all()

    lista_chamadas = [(str(c.id),c.chamada[:110]+'...') if len(c.chamada) >110 else (str(c.id),c.chamada) for c in chamadas]
    lista_chamadas.insert(0,('',''))

    form = ChamadaConvForm()

    form.chamada.choices= lista_chamadas

    if form.validate_on_submit():

        for c in form.chamada.data:
            chamada = Chamadas.query.get_or_404(int(c))
            chamada.id_relaciona = 'C'+conv
            db.session.commit()

        flash('Chamada(s) associada(s) ao Convênio!','sucesso')

        return redirect(url_for('convenios.convenio_detalhes', conv=conv))

    return render_template('add_chamada_convenio.html',
                            conv=conv,
                            form=form)   


### desassociar chamada de Convênio

@convenios.route("<int:id>/<conv>/desassocia_chamada", methods=['GET', 'POST'])
@login_required
def desassocia_chamada(id,conv):
    """
    +---------------------------------------------------------------------------------------+
    |Permite desassociar uma chamada de um convênio.                                        |
    +---------------------------------------------------------------------------------------+
    """

    chamada = Chamadas.query.get_or_404(id)

    chamada.id_relaciona = ''
    
    db.session.commit()

    flash('Chamada desassociada do Convênio!','sucesso')

    return redirect(url_for('convenios.convenio_detalhes', conv=conv))
 

### altera dados de natureza de despesa

@convenios.route("/<id>/<conv>/update_nd", methods=['GET', 'POST'])
@login_required
def update_nd(id,conv):
    """
    +---------------------------------------------------------------------------------------+
    |Permite alterar os dados de natureza de despesa de um empenho.                         |
    |                                                                                       |
    |Recebe o id do empenho como parâmetro.                                                 |
    +---------------------------------------------------------------------------------------+
    """

    nd = Emp_Cap_Cus.query.get(id)

    form = NDForm()

    if form.validate_on_submit():

        if nd != None:
            nd.nd = form.nd.data
        else:
            nd = Emp_Cap_Cus(id_empenho = id,
                             nd         = form.nd.data)
            db.session.add(nd)

        db.session.commit()

        registra_log_auto(current_user.id,None,'and')

        flash('ND atualizada!','sucesso')

        return redirect(url_for('convenios.convenio_detalhes', conv=conv))
    #
    # traz a informação atual
    elif request.method == 'GET':

        if nd != None:
            form.nd.data = nd.nd

    emp = db.session.query(Empenho.NR_EMPENHO).filter(Empenho.ID_EMPENHO == id).first()

    return render_template('add_nd.html', form=form, emp=emp)

# lista das demandas relacionadas a um convênio

@convenios.route('/<conv>')
def SEI_demandas (conv):
    """+--------------------------------------------------------------------------------------+
       |Mostra as demandas relacionadas a um processo SEI quando seu NUP é selecionado em uma |
       |lista de convênios.                                                                   |
       |Recebe o número do convênio como parâmetro.                                           |
       +--------------------------------------------------------------------------------------+
    """

    programa_siconv = db.session.query(Proposta.ID_PROPOSTA,
                                       Proposta.ID_PROGRAMA,
                                       Proposta.UF_PROPONENTE,
                                       Programa.COD_PROGRAMA,
                                       Programa_Interesse.sigla,
                                       Programa.ANO_DISPONIBILIZACAO)\
                                .join(Programa,Programa.ID_PROGRAMA == Proposta.ID_PROGRAMA)\
                                .outerjoin(Programa_Interesse,Programa_Interesse.cod_programa == Programa.COD_PROGRAMA)\
                                .subquery()

    conv_SEI = db.session.query(DadosSEI.sei,
                                programa_siconv.c.sigla,
                                DadosSEI.nr_convenio)\
                         .filter_by(nr_convenio=conv)\
                         .join(Convenio,DadosSEI.nr_convenio == Convenio.NR_CONVENIO)\
                         .join(programa_siconv, programa_siconv.c.ID_PROPOSTA == Convenio.ID_PROPOSTA)\
                         .first()

    if conv_SEI != None:
        SEI = conv_SEI.sei
        SEI_s = str(SEI).split('/')[0]+'_'+str(SEI).split('/')[1]
        conv_SEI_programa = conv_SEI.sigla
        conv_SEI_nr_convenio = conv_SEI.nr_convenio
        conv_SEI_ano = 0
    else:
        SEI = "?"
        SEI_s = "?"
        conv_SEI_programa = "?"
        conv_SEI_nr_convenio = 0
        conv_SEI_ano = 0

    #demandas_count = Demanda.query.filter(Demanda.sei.like('%'+SEI+'%')).count()
    demandas_count = Demanda.query.filter(Demanda.convênio == conv).count()

    #demandas = Demanda.query.filter(Demanda.sei.like('%'+SEI+'%'))\
    #                        .order_by(Demanda.data.desc()).all()
    demandas = Demanda.query.filter(Demanda.convênio == conv)\
                            .order_by(Demanda.data.desc()).all()


    autores=[]
    for demanda in demandas:
        autores.append(str(User.query.filter_by(id=demanda.user_id).first()).split(';')[0])

    dados = [conv_SEI_programa,SEI_s,conv_SEI_nr_convenio,conv_SEI_ano]

    return render_template('SEI_demandas.html',demandas_count=demandas_count,demandas=demandas,sei=SEI, autores=autores,dados=dados)


# lista das demandas relacionadas a um convênio

@convenios.route('/msg_siconv')
def msg_siconv ():
    """+--------------------------------------------------------------------------------------+
       |Lista as mensagens da tela inicial do SICONV que foram previamente carregadas em      |
       |procedimento próprio.                                                                 |
       +--------------------------------------------------------------------------------------+
    """

    programa_siconv = db.session.query(Proposta.ID_PROPOSTA,
                                       Proposta.ID_PROGRAMA,
                                       Proposta.UF_PROPONENTE,
                                       Programa.COD_PROGRAMA,
                                       Programa_Interesse.sigla,
                                       Programa.ANO_DISPONIBILIZACAO)\
                                .join(Programa,Programa.ID_PROGRAMA == Proposta.ID_PROGRAMA)\
                                .outerjoin(Programa_Interesse,Programa_Interesse.cod_programa == Programa.COD_PROGRAMA)\
                                .subquery()

    msgs = db.session.query(MSG_Siconv.data_ref,
                            MSG_Siconv.nr_convenio,
                            MSG_Siconv.desc,
                            programa_siconv.c.sigla,
                            DadosSEI.epe,
                            programa_siconv.c.UF_PROPONENTE,
                            DadosSEI.sei,
                            Convenio.SIT_CONVENIO,
                            MSG_Siconv.sit)\
                            .join(DadosSEI,MSG_Siconv.nr_convenio == DadosSEI.nr_convenio)\
                            .join(Convenio,MSG_Siconv.nr_convenio == Convenio.NR_CONVENIO)\
                            .join(programa_siconv, programa_siconv.c.ID_PROPOSTA == Convenio.ID_PROPOSTA)\
                            .order_by(programa_siconv.c.sigla,MSG_Siconv.desc).all()

    data_ref = msgs[0].data_ref

    return render_template('MSG_Siconv.html',msgs=msgs,data_ref=data_ref)

#
## quadro dos convênios

@convenios.route('/quadro_convenios')
def quadro_convenios():
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta um quadro de convênios selecionáveis por UF e Programa que estejam           |
    |em execução.                                                                           |
    +---------------------------------------------------------------------------------------+
    """

    unidade = current_user.coord

    # se unidade for pai, junta ela com seus filhos
    hierarquia = db.session.query(Coords.sigla).filter(Coords.pai == unidade).all()

    if hierarquia:
        l_unid = [f.sigla for f in hierarquia]
        l_unid.append(unidade)
    else:
        l_unid = [unidade]

    programas = db.session.query(Programa.ID_PROGRAMA,
                                 Programa_Interesse.sigla,
                                 label('UF',Proposta.UF_PROPONENTE),
                                 Proposta.ID_PROPOSTA)\
                          .join(Proposta,Proposta.ID_PROGRAMA == Programa.ID_PROGRAMA)\
                          .join(Programa_Interesse,Programa_Interesse.cod_programa == Programa.COD_PROGRAMA)\
                          .filter(Programa_Interesse.coord.in_(l_unid))\
                          .subquery()

    convenios = db.session.query(func.count(Convenio.NR_CONVENIO),
                                 programas.c.sigla,
                                 func.sum(Convenio.VL_GLOBAL_CONV),
                                 programas.c.UF)\
                          .filter(Convenio.SIT_CONVENIO == "Em execução")\
                          .join(programas, programas.c.ID_PROPOSTA == Convenio.ID_PROPOSTA)\
                          .order_by(programas.c.UF,programas.c.sigla)\
                          .group_by(programas.c.UF, programas.c.sigla)\
                          .all()

    ufs = [uf.UF for uf in convenios]
    ufs = set(ufs)
    ufs = list(ufs)
    ufs.sort()

    programas_int = [p.sigla for p in convenios]
    programas_int = set(programas_int)
    programas_int = list(programas_int)
    programas_int.sort()


    ## lê data de carga dos dados dos convênios
    data_carga = db.session.query(RefSICONV.data_ref).first()

    convenios_s = []
    for conv in convenios:

        conv_s = list(conv)
        if conv_s[2] is not None:
            conv_s[2] = locale.currency(conv_s[2], symbol=False, grouping = True)

        convenios_s.append(conv_s)

    quantidade = len(ufs)

    linha  = []
    linhas = []
    item   = []

    for uf in ufs:

        for prog in programas_int:
            
            flag = False
            for conv in convenios_s:

                if conv[3] == uf:
                    if conv[1] == prog:
                        linha.append(conv)
                        flag = True
                    else:
                        item = [0,prog,'',uf]

            if not flag:
                linha.append(item)
                flag = False

        linhas.append(linha)
        linha=[]

    return render_template('quadro_convenios.html',
                            quantidade=quantidade,
                            programas=programas_int,
                            linhas=linhas,
                            data_carga = str(data_carga[0]))

#
## convênios no mapa do Brasil

@convenios.route('/brasil_convenios')
def brasil_convenios():
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta um mapa onde se pode verificar os convênios por UF.                          |
    |Para constar no mapa, o convênio deve ter dados sei.                                   |
    +---------------------------------------------------------------------------------------+
    """
    programa_siconv = db.session.query(Proposta.ID_PROPOSTA,
                                       Proposta.ID_PROGRAMA,
                                       Proposta.UF_PROPONENTE,
                                       Programa.COD_PROGRAMA,
                                       Programa_Interesse.sigla,
                                       Programa.ANO_DISPONIBILIZACAO)\
                                .join(Programa,Programa.ID_PROGRAMA == Proposta.ID_PROGRAMA)\
                                .outerjoin(Programa_Interesse,Programa_Interesse.cod_programa == Programa.COD_PROGRAMA)\
                                .subquery()

    convenios = db.session.query(func.count(Convenio.NR_CONVENIO),
                                programa_siconv.c.sigla,
                                func.sum(Convenio.VL_GLOBAL_CONV),
                                programa_siconv.c.UF_PROPONENTE)\
                                .filter(Convenio.DIA_PUBL_CONV != '')\
                                .join(programa_siconv, programa_siconv.c.ID_PROPOSTA == Convenio.ID_PROPOSTA)\
                                .order_by(programa_siconv.c.UF_PROPONENTE,programa_siconv.c.sigla)\
                                .group_by(programa_siconv.c.UF_PROPONENTE)\
                                .group_by(programa_siconv.c.sigla)\
                                .all()

    convenios_s = []

    for conv in convenios:

        conv_s = list(conv)
        if conv_s[2] is not None:
            conv_s[2] = locale.currency(conv_s[2], symbol=False, grouping = True)
        if conv_s[1] is not None:
            convenios_s.append(conv_s)

    linha = []

    gps = {'AC':[-9.977916,-67.826068],
           'AL':[-9.649433,-35.709335],
           'AM':[-3.074759,-60.028723],
           'AP':[0.052334,-51.070093],
           'BA':[-13.008304,-38.512027],
           'CE':[-3.795849,-38.497930],
           'DF':[-15.710702,-47.911077],
           'ES':[-20.276832,-40.300442],
           'GO':[-16.680903,-49.250701],
           'MA':[-2.501711,-44.284316],
           'MG':[-19.884511,-43.915749],
           'MS':[-20.447545,-54.603542],
           'MT':[-15.566057,-56.072258],
           'PA':[-1.454934,-48.475778],
           'PB':[-7.205724,-35.921335],
           'PE':[-8.060426,-34.901544],
           'PI':[-5.096300,-42.798928],
           'PR':[-25.446918,-49.245448],
           'RJ':[-22.904571,-43.173827],
           'RN':[-5.829595,-35.212017],
           'RO':[-8.625350,-63.844920],
           'RR':[2.930872,-60.672953],
           'RS':[-30.028724,-51.228277],
           'SC':[-27.571250,-48.509038],
           'SE':[-10.909057,-37.050032],
           'SP':[-23.536390,-46.714247],
           'TO':[-10.182099,-48.331027]}

    progs = {}

    programas = db.session.query(Programa_Interesse.sigla).order_by(Programa_Interesse.sigla).group_by(Programa_Interesse.sigla)

    for p in programas:

       i = list(programas).index(p)
       if i == 0:
           progs[p.sigla]=[0,0]
       else:
           ang = (i-1)*(2*math.pi/len(list(programas)))
           x = 0.4*math.cos(ang)
           y = 0.4*math.sin(ang)
           progs[p.sigla]=[x,y]

    for conv in convenios_s:
        conv.append(gps[conv[3]])
        conv.append(progs[conv[1]])
        linha.append(conv)

    m = Map(location=[-15.7, -47.9],
            tiles='OpenStreetMap',
            control_scale = True,
            zoom_start = 2,
            min_zoom=2)

    m.fit_bounds([[-34,-74],[3,-34]])

    for l in linha:

        tip = '<b>'+l[3]+' - '+l[1]+'</b>'+'<br>'+str(l[0])+' conv&ecirc;nio(s)'+'<br>'+'Valor Global: '+l[2]

        if l[1] == 'PRONEX':
            cor = 'blue'
        elif l[1] == 'PRONEM':
            cor = 'orange'
        elif l[1] == 'PPP':
            cor = 'green'
        elif l[1] == 'EMENDA':
            cor = 'purple'
        else:
            cor = 'gray'

        #Circulos com raios em metros
        Circle(location = [float(l[4][0])+float(l[5][0]), float(l[4][1])+float(l[5][1])],
               #radius = (-2*int(linha[1])+2000),
               radius = 12000 * int(l[0]),
               tooltip = tip,
               fill = True,
               fill_opacity = (0.2),
               color=cor).add_to(m)


    return render_template('brasil_convenios.html', m = m._repr_html_())
    #return m._repr_html_()
#
## lista convênios do quadro por UF e por programa

@convenios.route('/<uf>/<programa>/lista_convenios_quadro')
def lista_convenios_quadro(uf,programa):
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta uma lista dos convênios de uma determinada UF em um programa específico      |
    |                                                                                       |
    +---------------------------------------------------------------------------------------+
    """

    unidade = current_user.coord

    # se unidade for pai, junta ela com seus filhos
    hierarquia = db.session.query(Coords.sigla).filter(Coords.pai == unidade).all()

    if hierarquia:
        l_unid = [f.sigla for f in hierarquia]
        l_unid.append(unidade)
    else:
        l_unid = [unidade]

    programa_siconv = db.session.query(Proposta.ID_PROPOSTA,
                                       Proposta.ID_PROGRAMA,
                                       Proposta.UF_PROPONENTE,
                                       Programa.COD_PROGRAMA,
                                       Programa_Interesse.sigla,
                                       Programa.ANO_DISPONIBILIZACAO)\
                                .join(Programa,Programa.ID_PROGRAMA == Proposta.ID_PROGRAMA)\
                                .join(Programa_Interesse,Programa_Interesse.cod_programa == Programa.COD_PROGRAMA)\
                                .filter(Programa_Interesse.coord.in_(l_unid))\
                                .subquery()

    convenio = db.session.query(Convenio.NR_CONVENIO,
                                DadosSEI.nr_convenio,
                                programa_siconv.c.ANO_DISPONIBILIZACAO,
                                DadosSEI.sei,
                                DadosSEI.epe,
                                programa_siconv.c.UF_PROPONENTE,
                                programa_siconv.c.sigla,
                                Convenio.SIT_CONVENIO,
                                Convenio.SUBSITUACAO_CONV,
                                Convenio.DIA_FIM_VIGENC_CONV,
                                Convenio.VL_GLOBAL_CONV,
                                DadosSEI.id,
                                Convenio.VL_REPASSE_CONV,
                                Convenio.VL_DESEMBOLSADO_CONV,
                                Convenio.VL_CONTRAPARTIDA_CONV,
                                Convenio.VL_INGRESSO_CONTRAPARTIDA)\
                         .filter(Convenio.SIT_CONVENIO == "Em execução",programa_siconv.c.UF_PROPONENTE == uf, programa_siconv.c.sigla == programa)\
                         .join(programa_siconv, programa_siconv.c.ID_PROPOSTA == Convenio.ID_PROPOSTA)\
                         .outerjoin(DadosSEI, Convenio.NR_CONVENIO == DadosSEI.nr_convenio)\
                         .order_by(Convenio.DIA_FIM_VIGENC_CONV,programa_siconv.c.ANO_DISPONIBILIZACAO.desc())\
                         .all()

    ## lê data de carga dos dados dos convênios
    data_carga = db.session.query(RefSICONV.data_ref).first()

    convenio_s = []

    for conv in convenio:

        conv_s = list(conv)
        if conv_s[10] is not None:
            conv_s[10] = locale.currency(conv_s[10], symbol=False, grouping = True)
        if conv_s[12] is not None:
            conv_s[12] = locale.currency(conv_s[12], symbol=False, grouping = True)
        if conv_s[14] is not None:
            conv_s[14] = locale.currency(conv_s[14], symbol=False, grouping = True)
        if conv_s[9] is not None:
            conv_s[9] = conv_s[9].strftime('%x')

        if conv.VL_DESEMBOLSADO_CONV == 0 or conv.VL_DESEMBOLSADO_CONV == None:
            percent_repass_desemb = 0
        else:
            percent_repass_desemb   = round(100*conv.VL_DESEMBOLSADO_CONV / conv.VL_REPASSE_CONV)

        if conv.VL_CONTRAPARTIDA_CONV == 0 or conv.VL_CONTRAPARTIDA_CONV == None:
            percent_ingre_contrap   = 0
        else:
            percent_ingre_contrap   = round(100*conv.VL_INGRESSO_CONTRAPARTIDA / conv.VL_CONTRAPARTIDA_CONV)

        conv_s.append((conv.DIA_FIM_VIGENC_CONV - datetime.date.today()).days)

        conv_s.append(percent_repass_desemb)

        conv_s.append(percent_ingre_contrap)

        convenio_s.append(conv_s)

    quantidade = len(convenio)


    return render_template('list_convenios_quadro.html', 
                           convenio = convenio_s,
                           quantidade=quantidade,
                           uf=uf,
                           programa=programa,
                           data_carga = str(data_carga[0]))

#
## lista convênios do quadro por UF (todos os programas)

@convenios.route('/<uf>/lista_convenios_uf')
def lista_convenios_uf(uf):
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta uma lista dos convênios de uma determinada UF (todos os programas)           |
    |                                                                                       |
    +---------------------------------------------------------------------------------------+
    """

    unidade = current_user.coord

    # se unidade for pai, junta ela com seus filhos
    hierarquia = db.session.query(Coords.sigla).filter(Coords.pai == unidade).all()

    if hierarquia:
        l_unid = [f.sigla for f in hierarquia]
        l_unid.append(unidade)
    else:
        l_unid = [unidade]

    programa_siconv = db.session.query(Proposta.ID_PROPOSTA,
                                       Proposta.ID_PROGRAMA,
                                       Proposta.UF_PROPONENTE,
                                       Programa.COD_PROGRAMA,
                                       Programa_Interesse.sigla,
                                       Programa.ANO_DISPONIBILIZACAO)\
                                .join(Programa,Programa.ID_PROGRAMA == Proposta.ID_PROGRAMA)\
                                .join(Programa_Interesse,Programa_Interesse.cod_programa == Programa.COD_PROGRAMA)\
                                .filter(Programa_Interesse.coord.in_(l_unid))\
                                .subquery()

    convenio = db.session.query(Convenio.NR_CONVENIO,
                                DadosSEI.nr_convenio,
                                programa_siconv.c.ANO_DISPONIBILIZACAO,
                                DadosSEI.sei,
                                DadosSEI.epe,
                                programa_siconv.c.UF_PROPONENTE,
                                programa_siconv.c.sigla,
                                Convenio.SIT_CONVENIO,
                                Convenio.SUBSITUACAO_CONV,
                                Convenio.DIA_FIM_VIGENC_CONV,
                                Convenio.VL_GLOBAL_CONV,
                                DadosSEI.id,
                                Convenio.VL_REPASSE_CONV,
                                Convenio.VL_DESEMBOLSADO_CONV,
                                Convenio.VL_CONTRAPARTIDA_CONV,
                                Convenio.VL_INGRESSO_CONTRAPARTIDA)\
                         .filter(Convenio.SIT_CONVENIO == 'Em execução', programa_siconv.c.UF_PROPONENTE == uf)\
                         .join(programa_siconv, programa_siconv.c.ID_PROPOSTA == Convenio.ID_PROPOSTA)\
                         .outerjoin(DadosSEI, Convenio.NR_CONVENIO == DadosSEI.nr_convenio)\
                         .order_by(programa_siconv.c.sigla,Convenio.SIT_CONVENIO,Convenio.DIA_FIM_VIGENC_CONV,programa_siconv.c.ANO_DISPONIBILIZACAO.desc())\
                         .filter()\
                         .all()

    ## lê data de carga dos dados dos convênios
    data_carga = db.session.query(RefSICONV.data_ref).first()

    convenio_s = []

    for conv in convenio:

        conv_s = list(conv)
        if conv_s[10] is not None:
            conv_s[10] = locale.currency(conv_s[10], symbol=False, grouping = True)
        if conv_s[12] is not None:
            conv_s[12] = locale.currency(conv_s[12], symbol=False, grouping = True)
        if conv_s[14] is not None:
            conv_s[14] = locale.currency(conv_s[14], symbol=False, grouping = True)
        if conv_s[9] is not None:
            conv_s[9] = conv_s[9].strftime('%x')

        if conv.VL_DESEMBOLSADO_CONV == 0 or conv.VL_DESEMBOLSADO_CONV == None:
            percent_repass_desemb = 0
        else:
            percent_repass_desemb   = round(100*conv.VL_DESEMBOLSADO_CONV / conv.VL_REPASSE_CONV)

        if conv.VL_CONTRAPARTIDA_CONV == 0 or conv.VL_CONTRAPARTIDA_CONV == None:
            percent_ingre_contrap   = 0
        else:
            percent_ingre_contrap   = round(100*conv.VL_INGRESSO_CONTRAPARTIDA / conv.VL_CONTRAPARTIDA_CONV)

        conv_s.append((conv.DIA_FIM_VIGENC_CONV - datetime.date.today()).days)

        conv_s.append(percent_repass_desemb)

        conv_s.append(percent_ingre_contrap)

        convenio_s.append(conv_s)

    quantidade = len(convenio)


    return render_template('list_convenios_quadro.html', convenio = convenio_s, quantidade=quantidade,
                            uf=uf,programa='todos', data_carga = str(data_carga[0]))

## lista convênios do quadro por programa

@convenios.route('/<programa>/lista_convenios_prog')
def lista_convenios_prog(programa):
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta uma lista dos convênios de um programa específico                            |
    |                                                                                       |
    +---------------------------------------------------------------------------------------+
    """

    unidade = current_user.coord

    # se unidade for pai, junta ela com seus filhos
    hierarquia = db.session.query(Coords.sigla).filter(Coords.pai == unidade).all()

    if hierarquia:
        l_unid = [f.sigla for f in hierarquia]
        l_unid.append(unidade)
    else:
        l_unid = [unidade]

    programa_siconv = db.session.query(Proposta.ID_PROPOSTA,
                                       Proposta.ID_PROGRAMA,
                                       Proposta.UF_PROPONENTE,
                                       Programa.COD_PROGRAMA,
                                       Programa_Interesse.sigla,
                                       Programa.ANO_DISPONIBILIZACAO)\
                                .join(Programa,Programa.ID_PROGRAMA == Proposta.ID_PROGRAMA)\
                                .join(Programa_Interesse,Programa_Interesse.cod_programa == Programa.COD_PROGRAMA)\
                                .filter(Programa_Interesse.coord.in_(l_unid))\
                                .subquery()

    convenio = db.session.query(Convenio.NR_CONVENIO,
                                DadosSEI.nr_convenio,
                                programa_siconv.c.ANO_DISPONIBILIZACAO,
                                DadosSEI.sei,
                                DadosSEI.epe,
                                programa_siconv.c.UF_PROPONENTE,
                                programa_siconv.c.sigla,
                                Convenio.SIT_CONVENIO,
                                Convenio.SUBSITUACAO_CONV,
                                Convenio.DIA_FIM_VIGENC_CONV,
                                Convenio.VL_GLOBAL_CONV,
                                DadosSEI.id,
                                Convenio.VL_REPASSE_CONV,
                                Convenio.VL_DESEMBOLSADO_CONV,
                                Convenio.VL_CONTRAPARTIDA_CONV,
                                Convenio.VL_INGRESSO_CONTRAPARTIDA)\
                         .filter(Convenio.SIT_CONVENIO == "Em execução", programa_siconv.c.sigla == programa)\
                         .join(programa_siconv, programa_siconv.c.ID_PROPOSTA == Convenio.ID_PROPOSTA)\
                         .outerjoin(DadosSEI, Convenio.NR_CONVENIO == DadosSEI.nr_convenio)\
                         .order_by(Convenio.DIA_FIM_VIGENC_CONV,programa_siconv.c.ANO_DISPONIBILIZACAO.desc())\
                         .all()

    ## lê data de carga dos dados dos convênios
    data_carga = db.session.query(RefSICONV.data_ref).first()

    convenio_s = []

    for conv in convenio:

        conv_s = list(conv)
        if conv_s[10] is not None:
            conv_s[10] = locale.currency(conv_s[10], symbol=False, grouping = True)
        if conv_s[12] is not None:
            conv_s[12] = locale.currency(conv_s[12], symbol=False, grouping = True)
        if conv_s[14] is not None:
            conv_s[14] = locale.currency(conv_s[14], symbol=False, grouping = True)
        if conv_s[9] is not None:
            conv_s[9] = conv_s[9].strftime('%x')

        if conv.VL_DESEMBOLSADO_CONV == 0 or conv.VL_DESEMBOLSADO_CONV == None:
            percent_repass_desemb = 0
        else:
            percent_repass_desemb   = round(100*conv.VL_DESEMBOLSADO_CONV / conv.VL_REPASSE_CONV)

        if conv.VL_CONTRAPARTIDA_CONV == 0 or conv.VL_CONTRAPARTIDA_CONV == None:
            percent_ingre_contrap   = 0
        else:
            percent_ingre_contrap   = round(100*conv.VL_INGRESSO_CONTRAPARTIDA / conv.VL_CONTRAPARTIDA_CONV)

        conv_s.append((conv.DIA_FIM_VIGENC_CONV - datetime.date.today()).days)

        conv_s.append(percent_repass_desemb)

        conv_s.append(percent_ingre_contrap)

        convenio_s.append(conv_s)

    quantidade = len(convenio)


    return render_template('list_convenios_quadro.html', 
                           convenio = convenio_s,
                           quantidade=quantidade,
                           programa=programa,
                           data_carga = str(data_carga[0]),
                           uf='*')


#
## RESUMO convênios

@convenios.route('/resumo_convenios')
def resumo_convenios():
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta um resumo dos convênios por programa da coordenação.                         |
    |                                                                                       |
    +---------------------------------------------------------------------------------------+
    """

    unidade = current_user.coord

    # se unidade for pai, junta ela com seus filhos
    hierarquia = db.session.query(Coords.sigla).filter(Coords.pai == unidade).all()

    if hierarquia:
        l_unid = [f.sigla for f in hierarquia]
        l_unid.append(unidade)
    else:
        l_unid = [unidade]

    convenios_exec = db.session.query(Convenio.ID_PROPOSTA,
                                      label('conv_exec',Convenio.NR_CONVENIO))\
                               .filter(Convenio.SIT_CONVENIO=='Em execução')\
                               .subquery()


    programas = db.session.query(Programa_Interesse.cod_programa,
                                 Programa_Interesse.sigla,
                                 label('qtd',func.count(Convenio.NR_CONVENIO)),
                                 label('vl_global',func.sum(Convenio.VL_GLOBAL_CONV)),
                                 label('vl_repasse',func.sum(Convenio.VL_REPASSE_CONV)),
                                 label('vl_empenhado',func.sum(Convenio.VL_EMPENHADO_CONV)),
                                 label('vl_desembolsado',func.sum(Convenio.VL_DESEMBOLSADO_CONV)),
                                 label('vl_contrapartida',func.sum(Convenio.VL_CONTRAPARTIDA_CONV)),
                                 label('vl_ingresso_contra',func.sum(Convenio.VL_INGRESSO_CONTRAPARTIDA)),
                                 label('qtd_exec',func.count(convenios_exec.c.conv_exec)))\
                          .join(Programa,Programa.COD_PROGRAMA==Programa_Interesse.cod_programa)\
                          .join(Proposta,Proposta.ID_PROGRAMA==Programa.ID_PROGRAMA)\
                          .join(Convenio,Convenio.ID_PROPOSTA==Proposta.ID_PROPOSTA)\
                          .filter(Convenio.DIA_PUBL_CONV != '',Programa_Interesse.coord.in_(l_unid))\
                          .outerjoin(convenios_exec,convenios_exec.c.ID_PROPOSTA==Proposta.ID_PROPOSTA)\
                          .group_by(Programa_Interesse.sigla,Programa_Interesse.cod_programa)\
                          .order_by(Programa_Interesse.sigla.desc(),Programa_Interesse.cod_programa)\
                          .all()

    ## lê data de carga dos dados dos convênios
    data_carga = db.session.query(RefSICONV.data_ref).first()

    programas_s = []
    for prog in programas:

        prog_s = list(prog)

        prog_s[3] = locale.currency(none_0(prog_s[3]), symbol=False, grouping = True)
        prog_s[4] = locale.currency(none_0(prog_s[4]), symbol=False, grouping = True)
        prog_s[5] = locale.currency(none_0(prog_s[5]), symbol=False, grouping = True)
        prog_s[6] = locale.currency(none_0(prog_s[6]), symbol=False, grouping = True)
        prog_s[7] = locale.currency(none_0(prog_s[7]), symbol=False, grouping = True)
        prog_s[8] = locale.currency(none_0(prog_s[8]), symbol=False, grouping = True)

        if none_0(prog.vl_repasse) != 0:

            empenhado_repasse = round(100*float(none_0(prog.vl_empenhado))/float(none_0(prog.vl_repasse)))
            prog_s.append(empenhado_repasse)

            desembolsado_repasse = round(100*float(none_0(prog.vl_desembolsado))/float(none_0(prog.vl_repasse)))
            prog_s.append(desembolsado_repasse)

        if none_0(prog.vl_contrapartida) != 0:

            ingressado_contrapartida = round(100*float(none_0(prog.vl_ingresso_contra))/float(none_0(prog.vl_contrapartida)))
            prog_s.append(ingressado_contrapartida)

        programas_s.append(prog_s)


    return render_template('resumo_convenios.html',programas=programas_s,data_carga=str(data_carga[0]))
