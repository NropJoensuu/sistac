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

    unidade_coord = services.coord_do_usuario(current_user.id)

    form = ListaForm()

    if form.validate_on_submit():

        coord_form = form.coord.data

        if coord_form == '' or coord_form is None:
            coord_form = '*'

        return redirect(url_for('convenios.lista_convenios_SICONV',lista=lista,coord=coord_form))

    convenio, coord_normalizado, data_carga = services.listar_convenios_siconv(lista, coord, unidade_coord)
    form.coord.data = coord_normalizado

    return render_template('list_convenios.html', convenio = convenio,
                                                  quantidade = len(convenio),
                                                  lista = lista,
                                                  form = form,
                                                  data_carga = data_carga)

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
    dadosSEI = services.buscar_dados_sei(conv)

    form = SEIForm()

    if form.validate_on_submit():

        _, status = services.salvar_dados_sei(
            conv, dadosSEI, form.sei.data, form.epe.data, form.fiscal.data, current_user.id)

        if status == 'inserido':
            flash('Inserido registro SEI do convênio!','sucesso')
        else:
            flash('Registro SEI do convênio atualizado!','sucesso')

        return redirect(url_for('convenios.convenio_detalhes',conv=conv,form=form))

    # popula os campos do form quando da consulta (GET ou POST inválido)
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

    # calcula os dados de exibição sempre (GET normal ou POST com dados inválidos),
    # evitando o antigo bug de UnboundLocalError quando o form era submetido com erro
    dados = services.detalhes_convenio(conv, dadosSEI)

    services.gerar_pdf_convenio(conv, dados)

    return render_template('convenio_detalhes.html', form=form, **dados)


### associar chamada a Convênio

@convenios.route("/associa_chamada/<conv>", methods=['GET', 'POST'])
@login_required
def associa_chamada(conv):
    """
    +---------------------------------------------------------------------------------------+
    |Permite associar uma chamada presente em uma lista a um convênio.                      |
    +---------------------------------------------------------------------------------------+
    """

    form = ChamadaConvForm()
    form.chamada.choices = services.chamadas_disponiveis()

    if form.validate_on_submit():

        services.associar_chamadas(conv, form.chamada.data)

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

    services.desassociar_chamada(id)

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

    nd = services.buscar_nd(id)

    form = NDForm()

    if form.validate_on_submit():

        services.salvar_nd(id, nd, form.nd.data, current_user.id)

        flash('ND atualizada!','sucesso')

        return redirect(url_for('convenios.convenio_detalhes', conv=conv))
    #
    # traz a informação atual
    elif request.method == 'GET':

        if nd != None:
            form.nd.data = nd.nd

    emp = services.buscar_numero_empenho(id)

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

    dados = services.demandas_do_convenio(conv)

    return render_template('SEI_demandas.html', **dados)


# lista as mensagens SICONV carregadas

@convenios.route('/msg_siconv')
def msg_siconv ():
    """+--------------------------------------------------------------------------------------+
       |Lista as mensagens da tela inicial do SICONV que foram previamente carregadas em      |
       |procedimento próprio.                                                                 |
       +--------------------------------------------------------------------------------------+
    """

    msgs, data_ref = services.mensagens_siconv()

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
