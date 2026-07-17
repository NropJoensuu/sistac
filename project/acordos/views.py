"""
.. topic:: Acordos (views)

    Os Acordos são instrumentos de parceria entre o CNPq e Entidades Parceiras Estaduais - EPEs onde
    não há repasse direto de recursos entre as partes.

    O CNPq custeia as bolsas dos contemplados em processos seletivos organizados pelas EPEs
    e estas, a título de contrapartida, custeiam outras despesas dos projetos.

    Toda bolsa é implementada por meio de um processo de bolsa (processo filho), que, por sua vez, deve estar vinculado a
    um processo mãe.

    Em princípio, é no processo mãe que são definidos a quantidade máxima de bolsas que poderão ser implementadas no projeto,
    pois o processo mãe tem um valor de concessão definido, bem como uma vigência que limita as vigências dos processos filho.

    A indicação dos bolsisstas  é feita pela EPE em plataforma específica do CNPq e este módulo trabalha com os
    dados fornecidos por este sistema, via planilha excel enviada pela COSAO, sob demanda da COPES.

    Um acordo tem atributos que são registrados no momento de sua criação. Todos são obrigatórios:

    * Edição do programa ao qual ele está vinculado
    * Número do processo SEI
    * Sigla da EPE
    * Unidade da Federação da EPE
    * Data de início
    * Data de término
    * Valor alocado pelo CNPq
    * Valor alocado pela EPE

    Os valores pagos são calculados pela soma de todos os pagamentos registrados para cada processo filho da planilha COSAO.
    Da mesma forma, é feito o cálculo da quantidade de mensalides pagas.

    Os valores a pagar consistem da multiplicação da quantidade de meses entre a data de referência (data de geração da
    planilha COSAO) e o fim de vigência de cada processo-filho pelo valor da respectiva memsalidade do nível de bolsa no
    qual o bolsista foi enquadrado. Da mesma forma, é feito o cálculo da quantidade de mensalides a pagar.

.. topic:: Ações relacionadas aos acordos

    * Listar acordos por edição do programa: lista_acordos
    * Atualizar dados de um acordo: update
    * Registrar um acordo no sistema: cria_acordo
    * Deletar o registro de um acordo: deleta_acordo
    * Listar demandas de um determinado acordo: acordo_demandas
    * Registrar um programa do CNPq no sistema: cria_programa_cnpq
    * Listar programas do CNPq: lista_programa_cnpq
    * Atualizar programas do CNPq: atualiza_programa_cnpq
    * Lista processos mãe de um acordo: lista_processos_mae_por_acordo
    * Alterada dados de processo_mãe: altera_mae
    * Associar processos mãe a um acordo: processo_mae_acordo
    * Desassociar processo mãe de um acordo: deleta_processo_mae
    * Listar processos filho de um processo mãe: lista_processos_filho
    * Listar bolsistas (cpf) de um processo mãe: lista_bolsistas
    * Listar os processos filho de um acordo: lista_processos_filho_por_acordo
    * Carregar situações de arquivo do sigef: carrega_sit_sigef
    * Listar bolsistas (cpf) de um acordo: lista_bolsistas_acordo
    * Acordos por Programa: resumo_acordos
    * Acordos por UF: brasil_acordos
    * Edições de cada programa: edic_programa
    * Gasto mensal por acordo: gasto_mes
    * Listar processos de uma chamada: processos_chamada

"""

# views.py na pasta acordos

from re import I
from flask import render_template,url_for,flash, redirect,request,Blueprint,send_from_directory,abort
from flask_login import current_user,login_required
from sqlalchemy import func, distinct, not_, or_, cast, String, literal
from sqlalchemy.sql import label
from project import db
from project.models import Acordo, RefCargaPDCTR, PagamentosPDCTR, Processo_Mae, Bolsa, User, Demanda,\
                           Chamadas, Programa_CNPq, Acordo_ProcMae, Processo_Filho, Coords, grupo_programa_cnpq,\
                           capital_custeio,DadosSEI, chamadas_cnpq, chamadas_cnpq_acordos, financeiro_acordo, RefSICONV
from project.acordos.forms import AcordoForm, Programa_CNPqForm, func_ProcMae_Acordo, ListaForm, ArquivoForm,\
                                  Altera_proc_mae_Form, ProgAcordoForm, Inclui_proc_mae_Form, ChamadaAcordoForm,\
                                  EscolheMaeForm
from project.demandas.views import registra_log_auto
from project.core.services import consultaDW, chamadas_DW
from project.acordos import services

import locale
import datetime
from datetime import datetime as dt
from dateutil.rrule import rrule, MONTHLY
import xlrd
import tempfile
from werkzeug.utils import secure_filename
import os
from folium import Map, Circle, Popup
import csv
import re

acordos = Blueprint('acordos',__name__,
                            template_folder='templates/acordos')

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

#
def cria_csv(arq,linha,tabela):
  '''Recebe caminho do arquivo como string, campos da tabela como lista e a tabela propriamente dita'''
  with open(arq,'w',encoding='UTF8',newline='') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(linha)
        writer.writerows(tabela)

@acordos.route('/<lista>/<coord>/lista_acordos', methods=['GET', 'POST'])
def lista_acordos(lista,coord):
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta uma lista dos acordos por edição do programa.                                |
    |                                                                                       |                                                                                |
    |                                                                                       |
    |No topo da tela há a opção de se inserir um novo acordo e o número sequencial de cada  |
    |acordo (#), ao ser clicado, permite que seus dados possam ser editados.                |
    |                                                                                       |
    +---------------------------------------------------------------------------------------+
    """

    hoje = dt.today()

    # pega unidade do usuário logado
    unidade = db.session.query(User.coord).filter(User.id==current_user.id).first()
    
    form = ListaForm()

    if form.validate_on_submit():

        coord = form.coord.data

        if coord == '' or coord == None:
            coord = '*'

        return redirect(url_for('acordos.lista_acordos',lista=lista,coord=coord))

    else:

        ## lê data de carga de chamadas do DW
        data_carga = db.session.query(RefSICONV.data_cha_dw).first()
        data_cha = data_carga.data_cha_dw

        if coord == '*':

            form.coord.data = ''
            unid = '%'

        elif coord == 'usu':

            form.coord.data = unidade.coord

            # se unidade for pai, pega filhos
            filhos = db.session.query(Coords.sigla).filter(Coords.pai == unidade.coord).all()
            l_filhos = [f.sigla for f in filhos]
            l_filhos.append(unidade.coord)

            if filhos:
                unid = l_filhos
            else:
                unid = unidade.coord
        
        else:
            
            form.coord.data = coord

            # se unidade for pai, pega filhos
            filhos = db.session.query(Coords.sigla).filter(Coords.pai == coord).all()
            l_filhos = [f.sigla for f in filhos]
            l_filhos.append(coord)

            if filhos:
                unid = l_filhos               
            else:
                unid = coord


        # contabiliza quantidade de programas por acordo
        cont_prog = db.session.query(grupo_programa_cnpq.id_acordo,
                                     label('qtd_prog',func.count(grupo_programa_cnpq.id_programa)))\
                              .group_by(grupo_programa_cnpq.id_acordo)\
                              .subquery()

        # contabiliza quantidade de chamadas por acordo
        cont_cham = db.session.query(chamadas_cnpq_acordos.acordo_id,
                                     label('qtd_cha',func.count(chamadas_cnpq_acordos.id)))\
                               .group_by(chamadas_cnpq_acordos.acordo_id)\
                               .subquery()                      

        if lista == 'todos':
            if type(unid) is str:
                # acordos onde o nome da unidade está no campo unidade_cnpq
                acordos_v = db.session.query(label('id',distinct(Acordo.id)),
                                            Acordo.nome,
                                            Acordo.sei,
                                            Acordo.epe,
                                            Acordo.uf,
                                            Acordo.data_inicio,
                                            Acordo.data_fim,
                                            Acordo.valor_cnpq,
                                            Acordo.valor_epe,
                                            label('unid',Acordo.unidade_cnpq),
                                            Acordo.situ,
                                            Acordo.desc,
                                            cont_prog.c.qtd_prog,
                                            Acordo.siafi,
                                            cont_cham.c.qtd_cha,
                                            Acordo.capital,
                                            Acordo.custeio,
                                            Acordo.bolsas)\
                                    .outerjoin(cont_cham,cont_cham.c.acordo_id == Acordo.id)\
                                    .outerjoin(cont_prog,cont_prog.c.id_acordo == Acordo.id)\
                                    .filter(Acordo.unidade_cnpq.like(unid))\
                                    .order_by(Acordo.situ.desc(),Acordo.data_fim,Acordo.nome,Acordo.epe).all()

            elif type(unid) is list: 
                # acordos onde o nome da unidade está no campo unidade_cnpq
                acordos_v = db.session.query(label('id',distinct(Acordo.id)),
                                             Acordo.nome,
                                             Acordo.sei,
                                             Acordo.epe,
                                             Acordo.uf,
                                             Acordo.data_inicio,
                                             Acordo.data_fim,
                                             Acordo.valor_cnpq,
                                             Acordo.valor_epe,
                                             label('unid',Acordo.unidade_cnpq),
                                             Acordo.situ,
                                             Acordo.desc,
                                             cont_prog.c.qtd_prog,
                                             Acordo.siafi,
                                             cont_cham.c.qtd_cha,
                                            Acordo.capital,
                                            Acordo.custeio,
                                            Acordo.bolsas)\
                                    .outerjoin(cont_cham,cont_cham.c.acordo_id == Acordo.id)\
                                    .outerjoin(cont_prog,cont_prog.c.id_acordo == Acordo.id)\
                                    .filter(Acordo.unidade_cnpq.in_(unid))\
                                    .order_by(Acordo.situ.desc(),Acordo.data_fim,Acordo.nome,Acordo.epe).all() 

        elif lista == 'em execução':

            if type(unid) is str:
                # acordos onde o nome da unidade está no campo unidade_cnpq
                acordos_v = db.session.query(label('id',distinct(Acordo.id)),
                                            Acordo.nome,
                                            Acordo.sei,
                                            Acordo.epe,
                                            Acordo.uf,
                                            Acordo.data_inicio,
                                            Acordo.data_fim,
                                            Acordo.valor_cnpq,
                                            Acordo.valor_epe,
                                            label('unid',Acordo.unidade_cnpq),
                                            Acordo.situ,
                                            Acordo.desc,
                                            cont_prog.c.qtd_prog,
                                            Acordo.siafi,
                                            cont_cham.c.qtd_cha,
                                            Acordo.capital,
                                            Acordo.custeio,
                                            Acordo.bolsas)\
                                    .outerjoin(cont_cham,cont_cham.c.acordo_id == Acordo.id)\
                                    .outerjoin(cont_prog,cont_prog.c.id_acordo == Acordo.id)\
                                    .filter(Acordo.unidade_cnpq.like(unid),
                                            or_(Acordo.situ=='Vigente-Z',Acordo.situ=='Vigente-Esquecido'))\
                                    .order_by(Acordo.data_fim,Acordo.nome,Acordo.epe).all()

            elif type(unid) is list: 
                # acordos onde o nome da unidade está no campo unidade_cnpq
                acordos_v = db.session.query(label('id',distinct(Acordo.id)),
                                             Acordo.nome,
                                             Acordo.sei,
                                             Acordo.epe,
                                             Acordo.uf,
                                             Acordo.data_inicio,
                                             Acordo.data_fim,
                                             Acordo.valor_cnpq,
                                             Acordo.valor_epe,
                                             label('unid',Acordo.unidade_cnpq),
                                             Acordo.situ,
                                             Acordo.desc,
                                             cont_prog.c.qtd_prog,
                                             Acordo.siafi,
                                             cont_cham.c.qtd_cha,
                                            Acordo.capital,
                                            Acordo.custeio,
                                            Acordo.bolsas)\
                                    .outerjoin(cont_cham,cont_cham.c.acordo_id == Acordo.id)\
                                    .outerjoin(cont_prog,cont_prog.c.id_acordo == Acordo.id)\
                                    .filter(Acordo.unidade_cnpq.in_(unid),
                                            or_(Acordo.situ=='Vigente-Z',Acordo.situ=='Vigente-Esquecido'))\
                                    .order_by(Acordo.data_fim,Acordo.nome,Acordo.epe).all() 

        elif lista[:8] == 'programa':

            # pegar coords do programa
            unidades = db.session.query(Programa_CNPq.COORD).filter(Programa_CNPq.COD_PROGRAMA==lista[8:]).all()
            l_unidades = [c.COORD for c in unidades]

            # acordos com nome de unidade no campo unidade_cnpq
            acordos_v = db.session.query(Acordo.id,
                                         Acordo.nome,
                                         Acordo.sei,
                                         Acordo.epe,
                                         Acordo.uf,
                                         Acordo.data_inicio,
                                         Acordo.data_fim,
                                         Acordo.valor_cnpq,
                                         Acordo.valor_epe,
                                         label('unid',Acordo.unidade_cnpq),
                                         Acordo.situ,
                                         Acordo.desc,
                                         cont_prog.c.qtd_prog,
                                         Acordo.siafi,
                                         cont_cham.c.qtd_cha,
                                            Acordo.capital,
                                            Acordo.custeio,
                                            Acordo.bolsas)\
                                  .outerjoin(cont_cham,cont_cham.c.acordo_id == Acordo.id)\
                                  .outerjoin(cont_prog,cont_prog.c.id_acordo == Acordo.id)\
                                  .join(grupo_programa_cnpq, grupo_programa_cnpq.id_acordo == Acordo.id)\
                                  .join(Programa_CNPq, Programa_CNPq.ID_PROGRAMA == grupo_programa_cnpq.id_programa)\
                                  .filter(Programa_CNPq.COD_PROGRAMA == lista[8:],
                                          Acordo.unidade_cnpq.in_(l_unidades))\
                                  .order_by(Acordo.data_fim,Acordo.nome,Acordo.epe).all()

        elif lista[:10] == 'v_programa':

            # acordos com nome de unidade no campo unidade_cnpq
            acordos_v = db.session.query(Acordo.id,
                                         Acordo.nome,
                                         Acordo.sei,
                                         Acordo.epe,
                                         Acordo.uf,
                                         Acordo.data_inicio,
                                         Acordo.data_fim,
                                         Acordo.valor_cnpq,
                                         Acordo.valor_epe,
                                         label('unid',Acordo.unidade_cnpq),
                                         Acordo.situ,
                                         Acordo.desc,
                                         cont_prog.c.qtd_prog,
                                         Acordo.siafi,
                                        cont_cham.c.qtd_cha,
                                            Acordo.capital,
                                            Acordo.custeio,
                                            Acordo.bolsas)\
                                  .outerjoin(cont_cham,cont_cham.c.acordo_id == Acordo.id)\
                                  .outerjoin(cont_prog,cont_prog.c.id_acordo == Acordo.id)\
                                  .join(grupo_programa_cnpq, grupo_programa_cnpq.id_acordo == Acordo.id)\
                                  .join(Programa_CNPq, Programa_CNPq.ID_PROGRAMA == grupo_programa_cnpq.id_programa)\
                                  .filter(Programa_CNPq.COD_PROGRAMA == lista[10:],
                                          or_(Acordo.situ=='Vigente-Z',Acordo.situ=='Esquecido'))\
                                  .order_by(Acordo.data_fim,Acordo.nome,Acordo.epe).all()
   #
        elif lista[:4] == 'edic':
            acordos_v = db.session.query(Acordo.id,
                                       Acordo.nome,
                                       Acordo.sei,
                                       Acordo.epe,
                                       Acordo.uf,
                                       Acordo.data_inicio,
                                       Acordo.data_fim,
                                       Acordo.valor_cnpq,
                                       Acordo.valor_epe,
                                       label('unid',Acordo.unidade_cnpq),
                                       Acordo.situ,
                                       Acordo.desc,
                                       cont_prog.c.qtd_prog,
                                       Acordo.siafi,
                                       cont_cham.c.qtd_cha,
                                            Acordo.capital,
                                            Acordo.custeio,
                                            Acordo.bolsas)\
                                  .outerjoin(cont_cham,cont_cham.c.acordo_id == Acordo.id)\
                                  .outerjoin(cont_prog,cont_prog.c.id_acordo == Acordo.id)\
                                  .filter(Acordo.nome == lista[4:].replace('#$','/'))\
                                  .order_by(Acordo.data_fim,Acordo.nome,Acordo.epe).all()
        
        elif lista[:2] == 'UF':

            if type(unid) is str:
                # acordos onde o nome da unidade está no campo unidade_cnpq
                acordos_v = db.session.query(label('id',distinct(Acordo.id)),
                                            Acordo.nome,
                                            Acordo.sei,
                                            Acordo.epe,
                                            Acordo.uf,
                                            Acordo.data_inicio,
                                            Acordo.data_fim,
                                            Acordo.valor_cnpq,
                                            Acordo.valor_epe,
                                            label('unid',Acordo.unidade_cnpq),
                                            Acordo.situ,
                                            Acordo.desc,
                                            cont_prog.c.qtd_prog,
                                            Acordo.siafi,
                                            cont_cham.c.qtd_cha,
                                            Acordo.capital,
                                            Acordo.custeio,
                                            Acordo.bolsas)\
                                    .outerjoin(cont_cham,cont_cham.c.acordo_id == Acordo.id)\
                                    .outerjoin(cont_prog,cont_prog.c.id_acordo == Acordo.id)\
                                    .filter(Acordo.unidade_cnpq.like(unid),
                                            Acordo.uf == lista[2:4],
                                            or_(Acordo.situ=='Vigente-Z',Acordo.situ=='Vigente-Esquecido'))\
                                    .order_by(Acordo.data_fim,Acordo.nome,Acordo.epe).all()
 
            elif type(unid) is list: 
                # acordos onde o nome da unidade está no campo unidade_cnpq
                acordos_v = db.session.query(label('id',distinct(Acordo.id)),
                                             Acordo.nome,
                                             Acordo.sei,
                                             Acordo.epe,
                                             Acordo.uf,
                                             Acordo.data_inicio,
                                             Acordo.data_fim,
                                             Acordo.valor_cnpq,
                                             Acordo.valor_epe,
                                             label('unid',Acordo.unidade_cnpq),
                                             Acordo.situ,
                                             Acordo.desc,
                                             cont_prog.c.qtd_prog,
                                             Acordo.siafi,
                                             cont_cham.c.qtd_cha,
                                            Acordo.capital,
                                            Acordo.custeio,
                                            Acordo.bolsas)\
                                    .outerjoin(cont_cham,cont_cham.c.acordo_id == Acordo.id)\
                                    .outerjoin(cont_prog,cont_prog.c.id_acordo == Acordo.id)\
                                    .filter(Acordo.unidade_cnpq.in_(unid),
                                            Acordo.uf == lista[2:4],
                                            or_(Acordo.situ=='Vigente-Z',Acordo.situ=='Vigente-Esquecido'))\
                                    .order_by(Acordo.data_fim,Acordo.nome,Acordo.epe).all() 

        elif lista[:7] == 'PROG_UF':

            if type(unid) is str:
                # acordos onde o nome da unidade está no campo unidade_cnpq
                acordos_v = db.session.query(label('id',distinct(Acordo.id)),
                                            Acordo.nome,
                                            Acordo.sei,
                                            Acordo.epe,
                                            Acordo.uf,
                                            Acordo.data_inicio,
                                            Acordo.data_fim,
                                            Acordo.valor_cnpq,
                                            Acordo.valor_epe,
                                            label('unid',Acordo.unidade_cnpq),
                                            Acordo.situ,
                                            Acordo.desc,
                                            cont_prog.c.qtd_prog,
                                            Acordo.siafi,
                                            cont_cham.c.qtd_cha,
                                            Acordo.capital,
                                            Acordo.custeio,
                                            Acordo.bolsas)\
                                    .outerjoin(cont_cham,cont_cham.c.acordo_id == Acordo.id)\
                                    .outerjoin(cont_prog,cont_prog.c.id_acordo == Acordo.id)\
                                    .join(grupo_programa_cnpq, grupo_programa_cnpq.id_acordo == Acordo.id)\
                                    .join(Programa_CNPq, Programa_CNPq.ID_PROGRAMA == grupo_programa_cnpq.id_programa)\
                                    .filter(Acordo.unidade_cnpq.like(unid),
                                            Acordo.uf == lista[7:9],
                                            Programa_CNPq.COD_PROGRAMA == lista[9:22],
                                            or_(Acordo.situ=='Vigente-Z',Acordo.situ=='Vigente-Esquecido'))\
                                    .order_by(Acordo.data_fim,Acordo.nome,Acordo.epe).all()
 
            elif type(unid) is list: 
                # acordos onde o nome da unidade está no campo unidade_cnpq
                acordos_v = db.session.query(label('id',distinct(Acordo.id)),
                                             Acordo.nome,
                                             Acordo.sei,
                                             Acordo.epe,
                                             Acordo.uf,
                                             Acordo.data_inicio,
                                             Acordo.data_fim,
                                             Acordo.valor_cnpq,
                                             Acordo.valor_epe,
                                             label('unid',Acordo.unidade_cnpq),
                                             Acordo.situ,
                                             Acordo.desc,
                                             cont_prog.c.qtd_prog,
                                             Acordo.siafi,
                                            cont_cham.c.qtd_cha,
                                            Acordo.capital,
                                            Acordo.custeio,
                                            Acordo.bolsas)\
                                    .outerjoin(cont_cham,cont_cham.c.acordo_id == Acordo.id)\
                                    .outerjoin(cont_prog,cont_prog.c.id_acordo == Acordo.id)\
                                    .join(grupo_programa_cnpq, grupo_programa_cnpq.id_acordo == Acordo.id)\
                                    .join(Programa_CNPq, Programa_CNPq.ID_PROGRAMA == grupo_programa_cnpq.id_programa)\
                                    .filter(Acordo.unidade_cnpq.in_(unid),
                                            Acordo.uf == lista[7:9],
                                            Programa_CNPq.COD_PROGRAMA == lista[9:22],
                                            or_(Acordo.situ=='Vigente-Z',Acordo.situ=='Vigente-Esquecido'))\
                                    .order_by(Acordo.data_fim,Acordo.nome,Acordo.epe).all() 

        quantidade = len(acordos_v)

        acordos = []

        for acordo in acordos_v:

            if acordo.data_fim:
                dias = (acordo.data_fim - hoje).days
            else:
                dias = 999

            valor_global = acordo.valor_epe + acordo.valor_cnpq
            valor_cnpq   = acordo.valor_cnpq
            valor_bolsas = acordo.bolsas
            # valor_cnpq   = locale.currency(acordo.valor_cnpq, symbol=False, grouping = True)
            valor_epe    = locale.currency(acordo.valor_epe, symbol=False, grouping = True)

            # pega quantidade de mães, filhos do acordo e totaliza o que foi pago
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
                                          label('qtd_filhos',func.count(Processo_Filho.processo)),
                                          label('pago_filhos',func.sum(Processo_Filho.pago_total)),
                                          label('a_pagar_filhos',func.sum(Processo_Filho.valor_apagar)))\
                                   .filter(Processo_Filho.proc_mae == proc.proc_mae)\
                                   .group_by(Processo_Filho.proc_mae)\
                                   .first()
                if filhos:                   
                    qtd_filhos_acordo += int(filhos.qtd_filhos)
                    pago_acordo += filhos.pago_filhos
                    if filhos.a_pagar_filhos != None:
                        a_pagar += filhos.a_pagar_filhos

            # ver como receber valores pagos em capital e custeio para abater no calculo do saldo
            # pago_capital = ....
            # pago_custeio = ....

            #
            # verifica ser o acordo tem demandas de indicação de bolsisstas
            indic = 0
            indic = db.session.query(Demanda.tipo).filter(Demanda.sei == acordo.sei, Demanda.tipo == 'Bolsistas - Indicação na PICC').count()

            #verificar se situação do acordo pode ser modificada

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
            #
            acordos.append([acordo.id,
                            '',
                            acordo.nome, 
                            acordo.sei, 
                            acordo.epe, 
                            acordo.uf,
                            acordo.data_inicio,
                            acordo.data_fim,
                            valor_epe,
                            valor_cnpq,
                            qtd_proc_mae,
                            qtd_filhos_acordo,
                            pago_acordo,
                            0,
                            0,
                            acordo.unid,
                            dias,
                            '',
                            0,
                            situ,
                            acordo.desc,
                            acordo.qtd_prog,
                            acordo.siafi,
                            acordo.qtd_cha,
                            valor_global,
                            a_pagar,
                            valor_bolsas])

        try:
            cria_csv('/app/project/static/acordos.csv',
                    ['id','***','nome','sei','epe','uf','ini','fim','valor_epe','valor_cnpq','qtd_proc_mae','qtd_filhos','pago','a_pagar','saldo',\
                    'coord','dias','***','qtd_cpfs','situ','desc','qtd_prog','siafi','valor_global','a_pagar','valor_bolsas'],
                    acordos)
            tem_csv = True          
        except:
            flash('Arquivo csv não foi criado!','erro') 
            tem_csv = False             

        # o comandinho mágico que permite fazer o download de um arquivo
        if tem_csv == True:
            send_from_directory('/app/project/static', 'acordos.csv')                     

        return render_template('lista_acordos.html', 
                               acordos=acordos,
                               quantidade=quantidade,
                               lista=lista,
                               form=form,
                               data_cha = data_cha,
                               tem_csv = tem_csv)


### VISUALIZAR E ATUALIZAR detalhes de Acordo

@acordos.route("/<int:acordo_id>/<lista>/update", methods=['GET', 'POST'])
@login_required
def update(acordo_id,lista):
    """
    +---------------------------------------------------------------------------------------+
    |Permite ver e atualizar os dados de um acordo selecionado na tela de consulta.         |
    |                                                                                       |
    |Recebe o ID do acordo como parâmetro.                                                  |
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

    lista_coords = [(c,c) for c in l_unid]
    lista_coords.insert(0,('',''))

    chamadas_s = []

    acordo = Acordo.query.get_or_404(acordo_id)

    # contabiliza quantidade de programas do acordo
    cont_prog = db.session.query(grupo_programa_cnpq.id_acordo,
                                label('qtd_prog',func.count(grupo_programa_cnpq.id_programa)))\
                            .filter(grupo_programa_cnpq.id_acordo == acordo_id)\
                            .group_by(grupo_programa_cnpq.id_acordo)\
                            .first()
    if cont_prog:
        qtd_prog = cont_prog.qtd_prog
    else:
        qtd_prog = 0                        

    # contabiliza quantidade de chamadas PICC do acordo
    cont_cham = db.session.query(chamadas_cnpq_acordos.acordo_id,
                                    label('qtd_cha',func.count(chamadas_cnpq_acordos.id)))\
                            .filter(chamadas_cnpq_acordos.acordo_id == acordo_id)\
                            .group_by(chamadas_cnpq_acordos.acordo_id)\
                            .first()
    if cont_cham:
        qtd_cha = cont_cham.qtd_cha
    else:
        qtd_cha = 0  

    # pega quantidade de mães, filhos do acordo e totaliza o que foi pago
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
    pago_capital = 0
    pago_custeio = 0
    pago_bolsas  = 0

    for proc in procs_mae:

        if proc.pago_capital:
            pago_capital += proc.pago_capital
        if proc.pago_custeio:
            pago_custeio += proc.pago_custeio

        filhos = db.session.query(Processo_Filho.proc_mae,
                                    label('qtd_filhos',func.count(Processo_Filho.processo)),
                                    label('pago_filhos',func.sum(Processo_Filho.pago_total)))\
                            .filter(Processo_Filho.proc_mae == proc.proc_mae)\
                            .group_by(Processo_Filho.proc_mae)\
                            .first()
        if filhos:                   
            qtd_filhos_acordo += int(filhos.qtd_filhos)
            pago_bolsas += filhos.pago_filhos

    chamadas = db.session.query(Chamadas.id,
                                Chamadas.chamada,
                                Chamadas.qtd_projetos,
                                Chamadas.vl_total_chamada,
                                Chamadas.doc_sei,
                                Chamadas.obs,
                                Chamadas.id_relaciona)\
                         .filter(Chamadas.id_relaciona == str(acordo.id)).all()
    qtd_chamadas = len(chamadas)                            

    chamadas_s = []
    chamadas_tot = 0
    total_projetos = 0

    for chamada in chamadas:
        chamadas_s.append([chamada.id, 
                           chamada.chamada,
                           chamada.qtd_projetos,
                           locale.currency(chamada.vl_total_chamada, symbol=False, grouping = True),
                           chamada.doc_sei, 
                           chamada.obs, 
                           chamada.id_relaciona])
        chamadas_tot += chamada.vl_total_chamada
        total_projetos += chamada.qtd_projetos
    
    try:
        sei = str(acordo.sei).split('/')[0]+'_'+str(acordo.sei).split('/')[1]
    except:
        sei = acordo.sei

    form = AcordoForm()    

    form.unid.choices = lista_coords

    form.situacao.choices=[('',''),
                       ('Preparação','Preparação'),
                       ('Assinado','Assinado'),
                       ('Vigente-Esquecido','Vigente-Esquecido'),
                       ('Aguarda Folha','Aguarda Folha'),
                       ('Vigente-Z','Vigente'),
                       ('Expirado (sem RTF)','Expirado (sem RTF)'),
                       ('Expirado (RTF aguarda análise)','Expirado (RTF aguarda análise)'),
                       ('Expirado (RTF aprovado, mas há processo(s) à finalizar)','Expirado (RTF aprovado, mas há processo(s) à finalizar)'),
                       ('Expirado (RTF APROVADO!)','Expirado (RTF APROVADO!)'),
                       ('Expirado (sit. 71 mãe(s), mas há filho(s) pendente(s))','Expirado (sit. 71 mãe(s), mas há filho(s) pendente(s))'),
                       ('Expirado (sit. 71 mãe(s) e filho(s))','Expirado (sit. 71 mãe(s) e filho(s))'),
                       ('Não executado','Não executado')]

    if form.validate_on_submit():

        valor_cnpq = float(form.valor_cnpq.data.replace('.','').replace(',','.'))
        valor_epe  = float(form.valor_epe.data.replace('.','').replace(',','.'))
        capital    = float(form.capital.data.replace('.','').replace(',','.'))
        custeio    = float(form.custeio.data.replace('.','').replace(',','.'))
        bolsas     = float(form.bolsas.data.replace('.','').replace(',','.'))

        valor = valor_cnpq + valor_epe
        nds = capital + custeio + bolsas

        if round(nds,2) != round(valor,2) and (capital > 0 or custeio > 0 or bolsas > 0):
            flash('Atenção: Soma Capital, Custeio e Bolsas não corresponde à soma dos valores do acordo/TED \
                  (Aporte: '+str(locale.currency(round(valor,2), symbol=False, grouping = True ))+', \
                   Soma NDs: '+str(locale.currency(round(nds,2), symbol=False, grouping = True ))+')!','perigo')
            # return redirect(url_for('acordos.update', acordo_id=acordo_id, lista=lista))

        acordo.nome         = form.nome.data
        acordo.sei          = form.sei.data
        acordo.epe          = form.epe.data
        acordo.uf           = form.uf.data
        acordo.data_inicio  = form.data_inicio.data
        acordo.data_fim     = form.data_fim.data
        acordo.valor_cnpq   = valor_cnpq
        acordo.valor_epe    = valor_epe
        acordo.unidade_cnpq = form.unid.data
        acordo.situ         = form.situacao.data
        acordo.desc         = form.desc.data
        acordo.capital      = capital
        acordo.custeio      = custeio
        acordo.bolsas       = bolsas
        acordo.siafi        = form.siafi.data

        db.session.commit()

        # atualiza demandas associadas em caso de alteração do SEI do acordo.
        if form.sei.data != acordo.sei:
            demandas = db.session.query(Demanda).filter(Demanda.sei == acordo.sei).all()
            for demanda in demandas:
                demanda.sei = form.sei.data
            db.session.commit()

        registra_log_auto(current_user.id,None,'aco')

        flash('Acordo atualizado!','sucesso')
        return redirect(url_for('acordos.update', acordo_id=acordo_id, lista=lista))

    # traz a informação atual do acordo
    form.nome.data        = acordo.nome
    form.desc.data        = acordo.desc
    form.sei.data         = acordo.sei
    form.epe.data         = acordo.epe
    form.uf.data          = acordo.uf
    form.data_inicio.data = acordo.data_inicio
    form.data_fim.data    = acordo.data_fim
    form.valor_cnpq.data  = locale.currency( acordo.valor_cnpq, symbol=False, grouping = True )
    form.valor_epe.data   = locale.currency( acordo.valor_epe, symbol=False, grouping = True )
    if acordo.unidade_cnpq.isdigit():
        form.unid.data = None 
    else:
        form.unid.data = acordo.unidade_cnpq  
    form.situacao.data     = acordo.situ
    form.capital.data  = locale.currency( acordo.capital, symbol=False, grouping = True )
    form.custeio.data  = locale.currency( acordo.custeio, symbol=False, grouping = True )
    form.bolsas.data   = locale.currency( acordo.bolsas, symbol=False, grouping = True )
    form.siafi.data    = acordo.siafi


    return render_template('add_acordo.html', title='Update',
                            chamadas=chamadas_s,
                            qtd_chamadas=qtd_chamadas,
                            qtd_proj = total_projetos,
                            chamadas_tot=locale.currency(chamadas_tot, symbol=False, grouping = True),
                            acordo_id=acordo_id,
                            sei=sei,
                            prog="",
                            edic=acordo.nome,
                            epe=acordo.epe,
                            uf=acordo.uf,
                            procs_mae=procs_mae,
                            qtd_procs_mae=len(procs_mae),
                            form=form,
                            cont_prog=qtd_prog,
                            cont_cham=qtd_cha,
                            pago_capital=pago_capital,
                            pago_custeio=pago_custeio,
                            pago_bolsas=pago_bolsas)

# lista acordo de associado a um processo-mãe
@acordos.route("/<int:proc_mae_id>/consulta_acordo_proc_mae")
@login_required
def consulta_acordo_proc_mae(proc_mae_id):
    """
    +---------------------------------------------------------------------------------------+
    |Mostra o acordo associado a u processo-mãe informado.                                  |
    |                                                                                       |
    |Recebe o id do processo mãe como parâmetro.                                            |
    +---------------------------------------------------------------------------------------+
    """

    acordo_id = services.acordo_id_por_proc_mae(proc_mae_id)

    if acordo_id is None:
        flash('Este processo-mãe não está associado a nenhum acordo.', 'erro')
        return redirect(url_for('acordos.lista_acordos', lista='todos', coord='usu'))

    return redirect(url_for('acordos.update', acordo_id=acordo_id, lista='todos'))


@acordos.route("/<int:acordo_id>/chamadas_acordo", methods=['GET', 'POST'])
@login_required
def chamadas_acordo(acordo_id):
    """
    +---------------------------------------------------------------------------------------+
    |Lista das chamadas do CNPq de um acordo.                                               |
    |                                                                                       |
    |Recebe o ID do acordo como parâmetro.                                                  |
    +---------------------------------------------------------------------------------------+
    """

    dados = services.chamadas_do_acordo(acordo_id)

    return render_template('lista_chamadas_acordo.html', **dados)

### LISTAR processos de uma chamada do CNPq

@acordos.route("/<int:chamada_id_dw>/processos_chamada")
def processos_chamada(chamada_id_dw):
    """
    +---------------------------------------------------------------------------------------+
    |Lista processos de uma chamda do CNPq obtidos via carga de dados proveniente do DW.    |
    +---------------------------------------------------------------------------------------+
    """

    chamada, processos = services.processos_da_chamada(chamada_id_dw)

    if chamada is None:
        abort(404)

    qtd_processos = len(processos)

    if qtd_processos == 0:
        flash('Para obter lista dos processos desta chamada, será necessário efetuar nova carga de chamadas!','perigo')


    return render_template('lista_processos_mae.html',procs_mae=processos,
                                                      qtd_processos=qtd_processos,
                                                      chamada = chamada.nome,
                                                      acordo_id=None,
                                                      acordo_tit=None)

### associar programa a Acordo

@acordos.route("/programa_acordo/<int:id_acordo>", methods=['GET', 'POST'])
@login_required
def programa_acordo(id_acordo):
    """
    +---------------------------------------------------------------------------------------+
    |Permite associar programas a um acordo.                                                |
    +---------------------------------------------------------------------------------------+
    """
    acordo = services.buscar_acordo(id_acordo)

    form = ProgAcordoForm()
    form.programa_cnpq.choices = services.programas_choices_para_acordo(current_user.coord)

    if form.validate_on_submit():

        services.associar_programas_ao_acordo(id_acordo, form.programa_cnpq.data)

        flash('Programa(s) associados ao Acordo!','sucesso')
        return redirect(url_for('acordos.lista_acordos',lista='todos',coord='usu'))

    return render_template('add_programa_acordo.html',
                            acordo=acordo,
                            form=form)        


### associar chamada a Acordo

@acordos.route("/associa_chamada/<int:id_acordo>", methods=['GET', 'POST'])
@login_required
def associa_chamada(id_acordo):
    """
    +---------------------------------------------------------------------------------------+
    |Permite associar uma chamada presente em uma lista a um acordo.                        |
    +---------------------------------------------------------------------------------------+
    """

    acordo, lista_chamadas = services.chamadas_choices_para_acordo(id_acordo)

    form = ChamadaAcordoForm()
    form.chamada.choices = lista_chamadas

    if form.validate_on_submit():

        services.associar_chamadas_ao_acordo(id_acordo, form.chamada.data)

        flash('Chamada(s) associada(s) ao Acordo!','sucesso')

        return redirect(url_for('acordos.update', acordo_id=id_acordo, lista='todos'))


    return render_template('add_chamada_acordo.html',
                            acordo=acordo,
                            form=form)   


### desassociar chamada de Acordo

@acordos.route("<int:id>/<int:id_acordo>/desassocia_chamada", methods=['GET', 'POST'])
@login_required
def desassocia_chamada(id,id_acordo):
    """
    +---------------------------------------------------------------------------------------+
    |Permite desassociar uma chamada de um acordo, bem como processos_mae envolvidos.       |
    +---------------------------------------------------------------------------------------+
    """

    services.desassociar_chamada_do_acordo(id, id_acordo)

    flash('Chamada desassociada do Acordo, bem como processos-mãe relacionados!','sucesso')

    return redirect(url_for('acordos.lista_acordos',lista='em execução',coord='usu'))
 

### CRIAR Acordo

@acordos.route("/criar", methods=['GET', 'POST'])
@login_required
def cria_acordo():
    """
    +---------------------------------------------------------------------------------------+
    |Permite registrar os dados de um acordo.                                               |
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

    lista_coords = [(c,c) for c in l_unid]
    lista_coords.insert(0,('',''))

    form = AcordoForm()

    form.unid.choices = lista_coords
    
    form.situacao.choices=[('',''),
                           ('Preparação','Preparação'),
                           ('Assinado','Assinado')]

    if form.validate_on_submit():

        valor_cnpq    = float(form.valor_cnpq.data.replace('.','').replace(',','.'))
        valor_epe     = float(form.valor_epe.data.replace('.','').replace(',','.'))
        capital       = float(form.capital.data.replace('.','').replace(',','.'))
        custeio       = float(form.custeio.data.replace('.','').replace(',','.'))
        bolsas        = float(form.bolsas.data.replace('.','').replace(',','.'))

        valor = valor_cnpq + valor_epe
        nds = capital + custeio + bolsas


        if round(nds,2) != round(valor,2) and (capital != 0 or custeio != 0 or bolsas != 0):
            flash('Atenção: Soma Capital, Custeio e Bolsas não corresponde à soma dos valores do acordo/TED \
                  (Aporte: '+str(locale.currency(round(valor,2), symbol=False, grouping = True ))+', \
                   Soma NDs: '+str(locale.currency(round(nds,2), symbol=False, grouping = True ))+')!','perigo')
            # return redirect(url_for('acordos.cria_acordo'))

        acordo = Acordo(nome          = form.nome.data,
                        desc          = form.desc.data,
                        sei           = form.sei.data,
                        epe           = form.epe.data,
                        uf            = form.uf.data,
                        data_inicio   = form.data_inicio.data,
                        data_fim      = form.data_fim.data,
                        valor_cnpq    = valor_cnpq,
                        valor_epe     = valor_cnpq,
                        unidade_cnpq = form.unid.data,
                        situ          = form.situacao.data,
                        capital       = capital,
                        custeio       = custeio,
                        bolsas        = bolsas,
                        siafi         = form.siafi.data)

        db.session.add(acordo)
        db.session.commit()

        registra_log_auto(current_user.id,None,'aco')

        flash('Acordo criado!','sucesso')
        return redirect(url_for('acordos.lista_acordos',lista='todos',coord='usu'))


    return render_template('add_acordo.html',
                            acordo_id=0,
                            form=form)

## Deletar um acordo

@acordos.route("/<int:acordo_id>/deleta_acordo", methods=['GET', 'POST'])
@login_required
def deleta_acordo(acordo_id):
    """
    +---------------------------------------------------------------------------------------+
    |Permite deletar o registro de um acordo.                                               |
    +---------------------------------------------------------------------------------------+
    """

    acordo = Acordo.query.get_or_404(acordo_id)

    db.session.delete(acordo)
    db.session.commit()

    ## deletar associações do acordo com programas
    programas = db.session.query(grupo_programa_cnpq).filter(grupo_programa_cnpq.id_acordo==acordo_id).all() 
    db.session.delete(programas)
    db.session.commit()

    ## deletar associações do acordo com capital_custeio
    cap_cus = db.session.query(capital_custeio).filter(capital_custeio.id_acordo==acordo_id).all() 
    db.session.delete(cap_cus)
    db.session.commit()

    registra_log_auto(current_user.id,None,'ade')

    flash ('Acordo deletado!','sucesso')

    return redirect(url_for('acordos.lista_acordos',lista='todos',coord='usu'))


# lista das demandas relacionadas a um acordo

@acordos.route('/<acordo_id>/acordo_demandas')
def acordo_demandas (acordo_id):
    """+--------------------------------------------------------------------------------------+
       |Mostra as demandas relacionadas a um acordo quando seu NUP é selecionado em uma       |
       |lista de acordos.                                                                     |
       |Recebe o id do acordo como parâmetro.                                                 |
       +--------------------------------------------------------------------------------------+
    """

    acordo_SEI = db.session.query(Acordo.sei,Acordo.nome).filter_by(id=acordo_id).first()

    SEI = acordo_SEI.sei
    SEI_s = str(SEI).split('/')[0]+'_'+str(SEI).split('/')[1]

    demandas_count = Demanda.query.filter(Demanda.sei.like('%'+SEI+'%')).count()

    demandas = Demanda.query.filter(Demanda.sei.like('%'+SEI+'%'))\
                            .order_by(Demanda.data.desc()).all()

    autores=[]
    for demanda in demandas:
        autores.append(str(User.query.filter_by(id=demanda.user_id).first()).split(';')[0])

    dados = [acordo_SEI.nome,SEI_s,'0','0']

    return render_template('SEI_demandas.html',demandas_count=demandas_count,demandas=demandas,sei=SEI, autores=autores,dados=dados)

#
### CRIAR programa do CNPq

@acordos.route("/cria_programa_cnpq", methods=['GET', 'POST'])
@login_required
def cria_programa_cnpq():
    """
    +---------------------------------------------------------------------------------------+
    |Permite registrar os dados de um programa do CNPq.                                     |
    +---------------------------------------------------------------------------------------+
    """

    form = Programa_CNPqForm()
    form.coord.choices = services.coords_choices_para_programa(current_user.coord)

    if form.validate_on_submit():

        services.criar_programa_cnpq(
            cod_programa=form.cod_programa.data,
            nome_programa=form.nome_programa.data,
            sigla_programa=form.sigla_programa.data,
            coord=form.coord.data,
            usuario_id=current_user.id,
        )

        flash('Programa do CNPq registrado!','sucesso')
        return redirect(url_for('acordos.lista_programa_cnpq'))

    return render_template('cria_programa_cnpq.html', form=form)

#
#
### LISTAR programas do CNPq

@acordos.route("/lista_programa_cnpq")
@login_required
def lista_programa_cnpq():
    """
    +---------------------------------------------------------------------------------------+
    |Permite listar os programas do CNPq vinculados à unidade do usuário logado.            |
    +---------------------------------------------------------------------------------------+
    """

    programas = services.listar_programas_cnpq(current_user.coord)

    return render_template('lista_programa_cnpq.html', programas=programas, quantidade=len(programas))


# lista programas de um acordo
@acordos.route("/<int:id_acordo>/lista_programas_acordo")
@login_required
def lista_programas_acordo(id_acordo):
    """
    +---------------------------------------------------------------------------------------+
    |Lista programas que o acordo usa para efeturar pagamentos.                             |
    |                                                                                       |
    |Recebe o ID do acordo como parâmetro.                                                  |
    +---------------------------------------------------------------------------------------+
    """

    lista_programas, nome_acordo = services.programas_do_acordo(id_acordo)

    if nome_acordo is None:
        abort(404)

    return render_template ('lista_programas_acordo.html',lista_programas=lista_programas,
                                                          qtd_progs=len(lista_programas),
                                                          nome = nome_acordo,
                                                          id_acordo=id_acordo)                            

#
### ATUALIZAR programa do CNPq

@acordos.route("/<int:id>/atualiza_programa_cnpq", methods=['GET', 'POST'])
@login_required
def atualiza_programa_cnpq(id):
    """
    +---------------------------------------------------------------------------------------+
    |Permite atualizar os dados de um programa do CNPq selecionado na tela de consulta.     |
    |                                                                                       |
    |Recebe o ID do programa como parâmetro.                                                |
    +---------------------------------------------------------------------------------------+
    """

    programa_cnpq = services.buscar_programa_cnpq(id)

    form = Programa_CNPqForm()
    form.coord.choices = services.coords_choices_para_programa(current_user.coord)

    if form.validate_on_submit():

        services.atualizar_programa_cnpq(
            id=id,
            cod_programa=form.cod_programa.data,
            nome_programa=form.nome_programa.data,
            sigla_programa=form.sigla_programa.data,
            coord=form.coord.data,
            usuario_id=current_user.id,
        )

        flash('Programa do CNPq atualizado!','sucesso')
        return redirect(url_for('acordos.lista_programa_cnpq'))
    
    # traz a informação atual do programa CNPq
    elif request.method == 'GET':

        form.cod_programa.data   = programa_cnpq.COD_PROGRAMA
        form.nome_programa.data  = programa_cnpq.NOME_PROGRAMA
        form.sigla_programa.data = programa_cnpq.SIGLA_PROGRAMA
        form.coord.data          = programa_cnpq.COORD

    return render_template('cria_programa_cnpq.html', title='Update', form=form)

#
### LISTAR processos mãe de um acordo

@acordos.route("/<int:acordo_id>/lista_processos_mae_por_acordo")
def lista_processos_mae_por_acordo(acordo_id):
    """
    +---------------------------------------------------------------------------------------+
    |Lista os processos mãe vinculados a um acordo.                                         |
    +---------------------------------------------------------------------------------------+
    """

    acordo, processos = services.processos_mae_do_acordo(acordo_id)

    if acordo is None:
        abort(404)

    return render_template('lista_processos_mae.html',procs_mae=processos,
                                                      qtd_processos=len(processos),
                                                      chamada = None,
                                                      acordo_id=acordo.id,
                                                      acordo_tit=acordo.nome +' '+ acordo.epe +'-'+ acordo.uf)
#
### Alterar dados de um processos_mãe de um acordo

@acordos.route("/<acordo_id>/<proc_mae>/altera_mae", methods=['GET', 'POST'])
def altera_mae(acordo_id,proc_mae):
    """
    +---------------------------------------------------------------------------------------+
    |Alterar dados de um processos_mãe de um acordo.                                        |
    +---------------------------------------------------------------------------------------+
    """

    processo_mae = services.buscar_processo_mae_por_texto(proc_mae)

    if processo_mae is None:
        abort(404)

    form = Altera_proc_mae_Form()

    if form.validate_on_submit():

        services.atualizar_processo_mae_manual(processo_mae, form.coordenador.data, form.situ_mae.data, current_user.id)

        flash('Dados de processo-mãe atualizados manualmente!','sucesso')
        return redirect(url_for('acordos.lista_processos_mae_por_acordo',acordo_id=acordo_id))

    elif request.method == 'GET':

        form.coordenador.data = processo_mae.coordenador
        form.situ_mae.data   = processo_mae.situ_mae


    return render_template('altera_mae.html', form=form, proc_mae = proc_mae)

### ASSOCIAR UM processo mãe a um acordo

@acordos.route("/<int:acordo_id>/processo_mae_acordo", methods=['GET', 'POST'])
@login_required
def processo_mae_acordo(acordo_id):
    """
    +---------------------------------------------------------------------------------------+
    |                                                                                       |
    | Permite associar um processos mãe a um acordo.                                        |
    |                                                                                       |
    | Recebe o ID do acodo como parâmetro.                                                  |
    +---------------------------------------------------------------------------------------+
    """

    form = EscolheMaeForm()
    form.mae.choices = services.maes_disponiveis_para_acordo(acordo_id)

    if form.validate_on_submit():

        services.associar_maes_ao_acordo(acordo_id, form.mae.data, current_user.id)

        flash('Processo Mãe relacionado ao Acordo!','sucesso')
        return redirect(url_for('acordos.lista_processos_mae_por_acordo',acordo_id=acordo_id))

    return render_template('associa_processo_mae_acordo.html', form=form,
                                                               acordo_id=acordo_id)

## registrar manualmente um processo-mãe no sistema
@acordos.route("/<int:acordo_id>/inclui_proc_mae", methods=['GET', 'POST'])
def inclui_proc_mae(acordo_id):
    """
    +---------------------------------------------------------------------------------------+
    |Registra um processos_mãe no sistema e o associa a um acordo.                          |
    +---------------------------------------------------------------------------------------+
    """

    form = Inclui_proc_mae_Form()

    if form.validate_on_submit():

        services.incluir_processo_mae_manual(
            acordo_id=acordo_id,
            proc_mae=form.proc_mae.data,
            inic_mae=form.inic_mae.data,
            term_mae=form.term_mae.data,
            coordenador=form.coordenador.data,
            situ_mae=form.situ_mae.data,
            usuario_id=current_user.id,
        )

        flash('Processo-mãe inseridos manualmente e relacionado ao Acordo/TED!','sucesso')


        return redirect(url_for('acordos.lista_processos_mae_por_acordo',acordo_id=acordo_id))


    return render_template('inclui_proc_mae.html', form=form,acordo_id=acordo_id)

#
### DELETAR processo MÃE de um ACORDO

@acordos.route('/<int:processo_mae_id>/<int:acordo_id>/deleta_processo_mae',methods=['GET','POST'])
def deleta_processo_mae(processo_mae_id,acordo_id):
    """
    +---------------------------------------------------------------------------------------+
    |Deleta a associação de um processo mãe com um acordo.                                  |
    |                                                                                       |
    |Recebe o id da associação como parâmetro.                                              |
    +---------------------------------------------------------------------------------------+
    """

    excluida = services.excluir_associacao_processo_mae(processo_mae_id, acordo_id, current_user.id)

    if excluida:
        flash ('Associação Processo Mãe - Acordo desfeita!','sucesso')
    else:
        flash ('Associação não encontrada — nada para desfazer.','erro')

    return redirect(url_for('acordos.lista_processos_mae_por_acordo',acordo_id=acordo_id))


### LISTAR processos filho de um processo mãe

@acordos.route("/<proc_mae>/lista_processos_filho")
def lista_processos_filho(proc_mae):
    """
    +---------------------------------------------------------------------------------------+
    |Lista os processos filho de um determinado processo mãe.                               |
    +---------------------------------------------------------------------------------------+
    """

    filhos_banco, qtd_filhos, max_ult_pag = services.processos_filho_do_mae(proc_mae)

    return render_template('lista_processos_filho.html',proc_mae=proc_mae,
                                                        filhos=filhos_banco,
                                                        qtd_filhos=qtd_filhos,
                                                        lista='mae',
                                                        max_ult_pag=max_ult_pag)

#
@acordos.route("/<proc_mae>/<edic>/<epe>/<uf>/carrega_sit_sigef", methods=['GET', 'POST'])
def carrega_sit_sigef(proc_mae,edic,epe,uf):
    """
    +---------------------------------------------------------------------------------------+
    |Carrega situações dos processos-filho obtidas de uma planilha gerada via sigef         |
    +---------------------------------------------------------------------------------------+
    """

    form =  ArquivoForm()

    if form.validate_on_submit():

        arq_sigef = services.salvar_arquivo_upload(form.arquivo.data)

        print ('\n')
        print ('***  ARQUIVO ***',arq_sigef)

        services.cargaSit(arq_sigef)

        registra_log_auto(current_user.id,None,'car')

        return redirect(url_for('acordos.lista_processos_filho', proc_mae=proc_mae))

    return render_template('grab_file.html',form=form,data_ref="sigef")

#
### LISTAR bolsistas (cpf) de um processo mãe

@acordos.route("/<proc_mae>/lista_bolsistas")
def lista_bolsistas(proc_mae):
    """
    +---------------------------------------------------------------------------------------+
    |Lista bolsistas (cpfs) de um determinado processo mãe.                                 |
    +---------------------------------------------------------------------------------------+
    """

    cpfs = services.bolsistas_do_processo_mae(proc_mae)

    return render_template('lista_bolsistas.html',proc_mae=proc_mae,cpfs=cpfs,
                                                   qtd_cpfs=len(cpfs),
                                                   prog='',edic='',epe='',uf='')
#
### LISTAR processos filhos de um acordo

@acordos.route("/<int:acordo_id>/lista_processos_filho_por_acordo")
def lista_processos_filho_por_acordo(acordo_id):
    """
    +---------------------------------------------------------------------------------------+
    |Lista os processos filhos vinculados a um acordo.                                      |
    +---------------------------------------------------------------------------------------+
    """

    dados = services.processos_filho_do_acordo(acordo_id)

    return render_template('lista_processos_filho.html',filhos=dados['filhos'],
                                                        qtd_maes=dados['qtd_maes'],
                                                        qtd_filhos=dados['qtd_filhos'],
                                                        lista='acordo',
                                                        acordo=dados['acordo'],
                                                        max_ult_pag=dados['max_ult_pag'])
#

#
### LISTAR bolsistas (cpf) de um acordo

@acordos.route("/<int:acordo_id>/lista_bolsistas")
def lista_bolsistas_acordo(acordo_id):
    """
    +---------------------------------------------------------------------------------------+
    |Lista bolsistas (cpfs) de um acordo especifico.                                        |
    +---------------------------------------------------------------------------------------+
    """

    l_procs_mae, cpfs = services.bolsistas_do_acordo(acordo_id)

    return render_template('lista_bolsistas.html',proc_mae=l_procs_mae,cpfs=cpfs,
                                                   qtd_cpfs=len(cpfs),
                                                   prog='',edic='',epe='',uf='')
#
## RESUMO acordos

@acordos.route('/resumo_acordos')
@login_required
def resumo_acordos():
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta um resumo dos acordos por programa da coordenação.                           |
    |                                                                                       |
    +---------------------------------------------------------------------------------------+
    """

    programas = services.resumo_acordos_por_programa(current_user.coord)

    return render_template('resumo_acordos.html',programas=programas,
                                                 unidade=current_user.coord)

#
## RESUMO por nomes dos acordos

@acordos.route('/<cod_programa>/<sigla>/edic_programa')
def edic_programa(cod_programa,sigla):
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta resumo de acordos por nome, que, anteriormente era chamado de edição.        |
    |                                                                                       |
    +---------------------------------------------------------------------------------------+
    """

    edics = services.resumo_edicoes_programa(cod_programa)

    return render_template('edic_programa.html',edics=edics,sigla=sigla)

#
#
## acordos  no mapa do Brasil

@acordos.route('/brasil_acordos')
def brasil_acordos():
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta um mapa onde se pode verificar os acordos e encomendas por UF.               |
    +---------------------------------------------------------------------------------------+
    """

    mapa_html = services.gerar_mapa_brasil_acordos()

    return render_template('brasil_convenios.html', m = mapa_html)


## acordos no quadro por uf

@acordos.route('/quadro_acordos')
@login_required
def quadro_acordos():
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta um quadro onde se pode verificar os acordos por UF.                          |
    +---------------------------------------------------------------------------------------+
    """

    dados = services.quadro_acordos_por_uf(current_user.coord)

    return render_template('quadro_acordos.html', quantidade=dados['quantidade'],
                            programas=dados['programas'],linhas=dados['linhas'])

#
### gasto mês por acordo  (DESCONTINUADO)

@acordos.route("/<int:acordo_id>/<edic>/<epe>/<uf>/gasto_mes")
def gasto_mes(acordo_id,edic,epe,uf):
    """
    +---------------------------------------------------------------------------------------+
    |Lista os gastos mensais por acordo.                                                    |
    +---------------------------------------------------------------------------------------+
    """

    gastos = services.gasto_mensal_por_acordo(acordo_id)

    if gastos is None:
        flash('Não há processos-mãe registrados!','erro')
        return render_template('gasto_mes.html',gastos=[],qtd_meses=0,
                                                    prog='',edic=edic,epe=epe,uf=uf)

    return render_template('gasto_mes.html',gastos=gastos,qtd_meses=len(gastos),
                                                prog='',edic=edic,epe=epe,uf=uf)

#
#
# pega dados de programas no DW
@acordos.route('/programas_por_unidade_DW')
@login_required
def programas_por_unidade_DW():
    """
    +---------------------------------------------------------------------------------------+
    | Alimenta tabela programas_cnpq com dados do DW                                        |
    | Chama função consultaDW, restringindo busca à registros relacionados à unidade        |
    | do usuário.                                                                           |
    +---------------------------------------------------------------------------------------+
    """

    pn, pa, u = services.carregar_programas_por_unidade_DW(current_user.coord)

    flash('Efetuada carga de '+str(pn)+' programas novos e '+str(pa)+' programas já existentes'+\
          ' vinculadas à(s) '+str(u)+' unidade(s) identificadas','sucesso')

    return redirect(url_for('core.inicio'))


# lança tela de espera finalização de carga
@acordos.route('/<carga>/espera_carga')
@login_required
def espera_carga(carga):
    """
    +---------------------------------------------------------------------------------------+
    | Apresenta tela de espera carga enquato a carga e executada                            |
    +---------------------------------------------------------------------------------------+
    """

    return render_template('index_waiting.html',carga='/'+carga.replace('#','/'))


@acordos.route('/chamadas_por_programa_DW')
@login_required
def chamadas_por_programa_DW():
    """
    +---------------------------------------------------------------------------------------+
    | Alimenta tabela chamadas com dados do DW                                              |
    | Chama função consultaDW, restringindo busca à registros relacionados à unidade        |
    | do usuário.                                                                           |
    +---------------------------------------------------------------------------------------+
    """

    cn, ca, pn, pa, fn, fm = services.carregar_chamadas_programa_DW()

    flash('Efetuada carga de '+str(cn)+' chamadas novas, '+str(pn)+' processos novos e '+str(fn)+' filhos e '+\
          'alteração de ' +str(ca)+' chamadas já existentes, '+str(pa)+' processos já existentes e ' + str(fm)+' filhos sem mãe'+\
          ' vinculadas aos programas da unidade do usuário.','sucesso')

    return redirect(url_for('core.inicio'))  
#
# pega dados financeiros de acordos no DW
@acordos.route('/dados_financeiros_acordos_DW')
@login_required
def dados_financeiros_acordos_DW():
    """
    +---------------------------------------------------------------------------------------+
    | Alimenta tabela de dados financeiros com dados do DW                                  |
    | Chama função consultaDW, restringindo busca à registros relacionados à unidade        |
    | do usuário.                                                                           |
    +---------------------------------------------------------------------------------------+
    """

    dfn = services.carregar_dados_financeiros_acordos_DW(current_user.coord)

    flash('Realizada carga de '+str(dfn)+' registros de dados financeiros de acordos.','sucesso')

    return redirect(url_for('core.inicio'))    

# lista dados financeiros de um acordo
@acordos.route('/<int:acordo_id>/lista_dados_financeiros_acordo')
@login_required
def lista_dados_financeiros_acordo(acordo_id):
    """
    +---------------------------------------------------------------------------------------+
    | Lista dados financeiros de um acordo.                                                 |
    | Chama função consultaDW, restringindo busca à registros relacionados à unidade        |
    | do usuário.                                                                           |
    +---------------------------------------------------------------------------------------+
    """

    acordo, dados_financeiros = services.dados_financeiros_do_acordo(acordo_id)

    if acordo is None:
        abort(404)

    return render_template('financeiro_acordo.html',acordo = acordo, dados_financeiros=dados_financeiros)


## uso eventual para carregar chave de relacionamento com acordos e convênios em chamadas
@acordos.route('/carregaidrel')
@login_required
def carregaidrel():

    i = services.atualizar_id_relaciona_chamadas()

    print ('*** ',i,' alterações em chamadas')

    return redirect(url_for('core.inicio'))
