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

    unidade = db.session.query(User.coord).filter(User.id==current_user.id).first()

    form = ListaForm()

    if form.validate_on_submit():

        coord_form = form.coord.data

        if coord_form == '' or coord_form is None:
            coord_form = '*'

        return redirect(url_for('acordos.lista_acordos',lista=lista,coord=coord_form))

    acordos, quantidade, coord_normalizado, data_cha, tem_csv = services.buscar_acordos(lista, coord, unidade.coord)
    form.coord.data = coord_normalizado

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

    dados = services.dados_para_edicao_acordo(acordo_id)
    acordo = dados['acordo']

    form = AcordoForm()

    form.unid.choices = services.coords_choices_para_acordo(current_user.coord)

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

        acordo, alerta_nds = services.atualizar_acordo(
            acordo_id=acordo_id,
            nome=form.nome.data,
            sei=form.sei.data,
            epe=form.epe.data,
            uf=form.uf.data,
            data_inicio=form.data_inicio.data,
            data_fim=form.data_fim.data,
            valor_cnpq_str=form.valor_cnpq.data,
            valor_epe_str=form.valor_epe.data,
            unid=form.unid.data,
            situacao=form.situacao.data,
            desc=form.desc.data,
            capital_str=form.capital.data,
            custeio_str=form.custeio.data,
            bolsas_str=form.bolsas.data,
            siafi=form.siafi.data,
            usuario_id=current_user.id,
        )

        if alerta_nds:
            flash(alerta_nds,'perigo')

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
                            chamadas=dados['chamadas_s'],
                            qtd_chamadas=dados['qtd_chamadas'],
                            qtd_proj = dados['total_projetos'],
                            chamadas_tot=locale.currency(dados['chamadas_tot'], symbol=False, grouping = True),
                            acordo_id=acordo_id,
                            sei=dados['sei'],
                            prog="",
                            edic=acordo.nome,
                            epe=acordo.epe,
                            uf=acordo.uf,
                            procs_mae=dados['procs_mae'],
                            qtd_procs_mae=len(dados['procs_mae']),
                            form=form,
                            cont_prog=dados['qtd_prog'],
                            cont_cham=dados['qtd_cha'],
                            pago_capital=dados['pago_capital'],
                            pago_custeio=dados['pago_custeio'],
                            pago_bolsas=dados['pago_bolsas'])
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
    form = AcordoForm()

    form.unid.choices = services.coords_choices_para_acordo(current_user.coord)
    
    form.situacao.choices=[('',''),
                           ('Preparação','Preparação'),
                           ('Assinado','Assinado')]

    if form.validate_on_submit():

        acordo, alerta_nds = services.criar_acordo(
            nome=form.nome.data,
            desc=form.desc.data,
            sei=form.sei.data,
            epe=form.epe.data,
            uf=form.uf.data,
            data_inicio=form.data_inicio.data,
            data_fim=form.data_fim.data,
            valor_cnpq_str=form.valor_cnpq.data,
            valor_epe_str=form.valor_epe.data,
            unid=form.unid.data,
            situacao=form.situacao.data,
            capital_str=form.capital.data,
            custeio_str=form.custeio.data,
            bolsas_str=form.bolsas.data,
            siafi=form.siafi.data,
            usuario_id=current_user.id,
        )

        if alerta_nds:
            flash(alerta_nds,'perigo')

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

    services.excluir_acordo(acordo_id, current_user.id)

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

    dados = services.demandas_do_acordo(acordo_id)

    if dados is None:
        abort(404)

    return render_template('SEI_demandas.html', **dados)

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
