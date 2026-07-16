"""
.. topic:: Core (services) — Home / Info / Cargas de arquivo

    Camada de regra de negócio dos grupos "Home/Info" e "Cargas de
    arquivo" do módulo core: tela inicial, tela de informações,
    agendamento das cargas automáticas, e as cargas manuais de
    arquivo (folha de pagamento PDCTR e mensagens SICONV).

    Nota técnica 1: `agendar_cargas_iniciais` importa `cargaSICONV` e
    `chamadas_DW` de dentro da própria função (import local), e não no
    topo do arquivo, porque essas duas funções ainda vivem em
    `project/core/views.py` (serão movidas para este services.py só
    no grupo C — Integração SICONV/DW). Um import no topo do arquivo
    causaria import circular (views.py -> services.py -> views.py).
    Quando o grupo C for refatorado, este import interno deve ser
    atualizado para apontar para as funções já migradas.

    Nota técnica 2: `cargaPDCTR` usa `flash`/`redirect` diretamente
    (exceção à regra geral de manter services.py livre de objetos de
    request/response do Flask). Isso preserva o comportamento exato do
    código original: se a planilha não tiver os campos esperados, uma
    mensagem de erro é definida via `flash`, mas a função retorna um
    valor que a rota chamadora (`carregaPDCTR`) atualmente ignora — ou
    seja, o fluxo continua normalmente após o erro. Esse comportamento
    é preservado aqui sem alteração; fica como candidato a revisão
    numa futura mudança de regra de negócio, não nesta refatoração.
"""

import os
import re
import datetime
from datetime import datetime as dt
import tempfile

import xlrd
from werkzeug.utils import secure_filename
from flask import flash, redirect, url_for
from sqlalchemy import func
from sqlalchemy.sql import label

from project import db, sched
from project.models import (
    Sistema, Log_Auto, PagamentosPDCTR, RefCargaPDCTR, Bolsa,
    Processo_Filho, Processo_Mae, MSG_Siconv,
)
from project.demandas.views import registra_log_auto


def dados_sistema():
    """Retorna o registro único de configuração geral do sistema."""
    return db.session.query(Sistema).first()


def agendar_cargas_iniciais():
    """
    Agenda os jobs de carga automática (SICONV e DW) na inicialização
    do sistema, se a carga automática estiver habilitada em Sistema.
    Não faz nada se `sistema.carga_auto != 1`.
    """
    # import local: ver nota técnica no topo do arquivo
    from project.core.views import cargaSICONV, chamadas_DW

    sistema = dados_sistema()

    if sistema.carga_auto != 1:
        return

    # pega último agendamento registrado, se houver
    log_agenda_ant_envio = db.session.query(Log_Auto.user_id, Log_Auto.id, Log_Auto.tipo_registro)\
                                     .filter(Log_Auto.tipo_registro == 'agc')\
                                     .order_by(Log_Auto.id.desc())\
                                     .first()

    # corrige bug real: o código original acessava .user_id direto,
    # sem checar se a query retornou None (acontece numa instalação
    # nova, antes de qualquer agendamento anterior existir).
    id_user = log_agenda_ant_envio.user_id if log_agenda_ant_envio else None

    # AGENDA CARGA SICONV NA INICIALIZAÇÃO DO SISTEMA
    id_1 = 'carga_siconv'

    try:
        job_existente = sched.get_job(id_1)
        executa = not job_existente
    except Exception:
        executa = True

    if executa:
        dia_semana = 'mon-fri'
        hora = 8
        minuto = 13

        print('*** Agendamento inicial ' + id_1 + ', rodando ' + dia_semana + ', às ' + str(hora) + ':' + str(minuto) + ' ***')
        try:
            sched.add_job(trigger='cron', id=id_1, func=cargaSICONV, day_of_week=dia_semana, hour=hora, minute=minuto, misfire_grace_time=3600, coalesce=True)
            sched.start()
        except Exception:
            sched.reschedule_job(id_1, trigger='cron', day_of_week=dia_semana, hour=hora, minute=minuto)

        # só registra o log se houver um usuário válido para atribuir a ação
        # (numa instalação nova, sem nenhum agendamento anterior, não há)
        if id_user is not None:
            registra_log_auto(id_user, None, 'agi - agendamento cargaSICONV.')

    # AGENDA CARGA DW NA INICIALIZAÇÃO DO SISTEMA
    id_2 = 'carga_chamadas_DW'

    try:
        job_existente = sched.get_job(id_2)
        executa = not job_existente
    except Exception:
        executa = True

    if executa:
        dia = '2nd tue'
        hora = 18
        minuto = 18

        print('*** Agendamento inicial ' + id_2 + ', rodando ' + dia + ', às ' + str(hora) + ':' + str(minuto) + ' ***')
        try:
            sched.add_job(trigger='cron', id=id_2, func=chamadas_DW, day=dia, hour=hora, minute=minuto, misfire_grace_time=3600, coalesce=True)
            sched.start()
        except Exception:
            sched.reschedule_job(id_2, trigger='cron', day=dia, hour=hora, minute=minuto)

        if id_user is not None:
            registra_log_auto(id_user, None, 'agi - agendamento chamadas_DW.')


# =============================================================================
# Cargas de arquivo
# =============================================================================

def cargaPDCTR(entrada):

    data_referência = ''

    campos_bolsistas_para_db = ['Processo','Nome','Sexo Proc. Filho','CPF','Sit Filho','Data da Situação Filho', 'Inicio Filho',
                                'Termino Filho','Processo Mãe','Coordenador','Inicio Mãe','Termino Mãe','Titulo do Processo Filho', 'Nome Chamada',
                                'Modalidade','Cat Nivel','Cod Programa','Grande Área','Área de Conhecimento','Sigla Instituição',
                                'UF Instituição','Cidade Instituição','Data do Pagamento','Tipo de Pagamento','Valor Pago','Sit Mãe']

    print ('\n')
    print ('<<',dt.now().strftime("%x %X"),'>> ',' Carga de arquivo de folha de pagamento iniciada...')

    # abre arquivo (book), planilha (sheet) e linha com os nomes dos campos (linha_cabeçalho)

    book = xlrd.open_workbook(filename=entrada,ragged_rows=True)
    planilha = book.sheet_by_index(0)

    procura_cabeçalho = 0

    while planilha.row_len(procura_cabeçalho) < len(campos_bolsistas_para_db):

        procura_cabeçalho += 1

    linha_cabeçalho = planilha.row_values(procura_cabeçalho, start_colx=0, end_colx=None)

    linha_cabeçalho_lower = [item.lower() for item in linha_cabeçalho]

    for campo in campos_bolsistas_para_db:
        if campo.lower() not in linha_cabeçalho_lower:
            print ('** ATENÇÃO: o campo ',campo,' não existe na planinha original, verifique o parâmetro inserido. **')
            flash('ERRO! O campo '+str(campo)+' não existe na planinha original, verifique o parâmetro inserido.','erro')
            return redirect(url_for('core.inicio'))

    try:
        data_referência = planilha.cell_value(3,1)[-10:]
        data_referência = datetime.date(int(data_referência[-4:]),int(data_referência[-7:-5]),
                                         int(data_referência[0:2]))
    except:

        try:
            data_referência = planilha.cell_value(3,0)[-10:]
            data_referência = datetime.date(int(data_referência[-4:]),int(data_referência[-7:-5]),
                                             int(data_referência[0:2]))
        except:
            print ('** Erro ao tentar pegar a data de referência do arquivo. Usarei a data de hoje **')
            data_referência = datetime.date.today()

    print ('Planilha: CNPq')
    print (f'Cabeçalho original: {len(linha_cabeçalho)} campos')
    print (f'Cabeçalho após extração: {len(campos_bolsistas_para_db)} campos')
    print (f'Quantidade de registros na planilha: {planilha.nrows - procura_cabeçalho - 1 }')
    print ('Começará a extração com o cabeçalho na linha ',procura_cabeçalho + 1)
    print ('Data de referência: ', data_referência)
    print ('\n')

    qtd_linhas = planilha.nrows - procura_cabeçalho - 1

    # varre linha por linha da planilha de entrada

    print ('<<',dt.now().strftime("%x %X"),'>> ',' Gravando dados no banco...')

    for i in range(qtd_linhas):

        linha_base = planilha.row_values(i + procura_cabeçalho + 1 , start_colx=0, end_colx=None)

        linha = []
        iter  = 0

        # pega os campos de interess na planilha conforme o defindo em campos_bolsistas_para_db

        for campo in campos_bolsistas_para_db:

            dado_célula = planilha.cell_value(i + procura_cabeçalho + 1,
                                                               linha_cabeçalho_lower.index(campo.lower()))
            tipo_célula = planilha.cell_type (i + procura_cabeçalho + 1,
                                                               linha_cabeçalho_lower.index(campo.lower()))

            if str(dado_célula) == '':  # células vazias recebem None
                dado_célula = None

            if re.search('\d{2}/\d{2}/\d{4}', str(dado_célula)) != None: # identifica campos de texto, mas que contém data dd/mm/aaaa
                                                                         # e coloca no formado de data para o banco aaaa-mm-dd
                dado_célula = datetime.datetime.strptime(str(dado_célula), '%d/%m/%Y').date()

            if tipo_célula == 3:  # identifica células que tem formato de data no excell e coloca como aaaa-mm-dd

                ano_mes_dia = (str(xlrd.xldate.xldate_as_datetime(dado_célula, 0))[0:10])
                dia_mes_ano = ano_mes_dia[8:10] + '/' + ano_mes_dia[5:7] + '/' + ano_mes_dia[0:4]

                dado_célula = datetime.datetime.strptime(str(dia_mes_ano), '%d/%m/%Y').date()

            linha.append(dado_célula)

        # verifica se o registro a ser inserido já não existe no banco, identificado por processo, data pagamento e tipo pagamento
        #bolsista_pagamento = PagamentosPDCTR.query.filter_by(processo = linha[0], data_pagamento = linha[21], tipo_pagamento = linha[22]).first()
        bolsista_pagamento = db.session.query(PagamentosPDCTR)\
                                       .filter_by(processo = linha[0], data_pagamento = linha[22], tipo_pagamento = linha[23])\
                                       .first()

        # não existindo, adiciona registro na tabela PagamentosPDCTR:

        if bolsista_pagamento == None:

            # coloca '*' no nível, caso ele venha vazio
            if linha[15] == '' or linha[15] == None:
                linha[15] = '*'

            pagamento = PagamentosPDCTR(processo          = linha[0],
                                        nome              = linha[1],
                                        sexo_proc_filho   = linha[2],
                                        cpf               = linha[3],
                                        situ_filho        = linha[4],
                                        data_situ_filho   = linha[5],
                                        inic_filho        = linha[6],
                                        term_filho        = linha[7],
                                        proc_mae          = linha[8],
                                        coordenador       = linha[9],
                                        inic_mae          = linha[10],
                                        term_mae          = linha[11],
                                        titu_proc_filho   = linha[12],
                                        nome_chamada      = linha[13],
                                        modalidade        = linha[14],
                                        nivel             = linha[15],
                                        cod_programa      = linha[16],
                                        grande_area       = linha[17],
                                        area_conhecimento = linha[18],
                                        sigla_inst        = linha[19],
                                        uf_inst           = linha[20],
                                        cidade_inst       = linha[21],
                                        data_pagamento    = linha[22],
                                        tipo_pagamento    = linha[23],
                                        valor_pago        = linha[24],
                                        situ_mae          = linha[25])

            db.session.add(pagamento)

        # existindo, se coordenador estiver vazio, atualiza

        else:

            if bolsista_pagamento.coordenador != linha[9]:
                bolsista_pagamento.coordenador = linha[9]

            if bolsista_pagamento.situ_filho != linha[4]:
                bolsista_pagamento.situ_filho = linha[4]

            if bolsista_pagamento.situ_mae != linha[25]:
                bolsista_pagamento.situ_mae = linha[25]

    db.session.commit()

    # grava em tabela própria a data de referência da tabela gerada pela COSAO
    refer = RefCargaPDCTR(data_ref = data_referência)
    db.session.add(refer)
    db.session.commit()

    print ('<<',dt.now().strftime("%x %X"),'>> ',' Dados de pagamento carregados. Iniciando criação de tabelas...')

    # pega processos filho da tabela dos dados de folha de pagamento (PagamentosPDCTR)

    processos_filho = db.session.query(PagamentosPDCTR.cod_programa,
                                       PagamentosPDCTR.nome_chamada,
                                       PagamentosPDCTR.proc_mae,
                                       PagamentosPDCTR.processo,
                                       PagamentosPDCTR.nome,
                                       PagamentosPDCTR.cpf,
                                       PagamentosPDCTR.modalidade,
                                       PagamentosPDCTR.nivel,
                                       PagamentosPDCTR.situ_filho,
                                       PagamentosPDCTR.inic_filho,
                                       label('max_term_filho',func.max(PagamentosPDCTR.term_filho)),
                                       label('mens_pagas', func.count(PagamentosPDCTR.processo)),
                                       label('pago_total', func.sum(PagamentosPDCTR.valor_pago)),
                                       label('valor_apagar', Bolsa.mensalidade),
                                       label('max_dt_ult_pag', func.max(PagamentosPDCTR.data_pagamento)))\
                                       .outerjoin(Bolsa, (PagamentosPDCTR.modalidade+PagamentosPDCTR.nivel)==(Bolsa.mod+Bolsa.niv))\
                                       .group_by(PagamentosPDCTR.proc_mae,
                                                 PagamentosPDCTR.processo,
                                                 PagamentosPDCTR.cod_programa,
                                                 PagamentosPDCTR.nome_chamada,
                                                 PagamentosPDCTR.nome,
                                                 PagamentosPDCTR.cpf,
                                                 PagamentosPDCTR.modalidade,
                                                 PagamentosPDCTR.nivel,
                                                 PagamentosPDCTR.situ_filho,
                                                 PagamentosPDCTR.inic_filho,
                                                 Bolsa.mensalidade)\
                                       .all()

#
    quantidade_filho = len(processos_filho)

    #
    ## deletar linhas da tabela processo_filho e carregá-la com novos dados
    ## isso pode ser feito, pois os dados dos bolsistas de cargas anteriores permancecem na PagamentosPDCTR e serão carregados novamente
    db.session.query(Processo_Filho).delete()
    db.session.commit()

    # Gera tabela  Processo_Filho totalizando mensalidades e valores a pagar
    situ_filho_retirados = [17,18,40,41,61,62,63,66,71,74,83]
    """
    +---------------------------------------------------------------------------------------+
    |                                                                                       |
    |Situações para as quais não se calcula mensalidades e valores a pagar                  |
    | - 17 - CANCELADO POR MOTIVO DE SaúDE                                                  |
    | - 18 - ENCERRADO COM DEVOLUçãO DE RECURSOS                                            |
    | - 40 - CANCELADO POR AQUISIçãO DE VíNCULO EMPREGATíCIO                                |
    | - 41 - CANCELADO POR ACUMULO DE CONCESSõES (OUTRA AgêNCIA/CNPQ)                       |
    | - 61 - CANCELADO PELO CNPQ                                                            |
    | - 62 - CANCELADO A PEDIDO DO BOLSISTA/PESQUISADOR                                     |
    | - 63 - CANCELADO A PEDIDO DO COORDENADOR                                              |
    | - 66 - CANCELADO COM DéBITO                                                           |
    | - 71 - ENCERRADO                                                                      |
    | - 74 - ENCERRADO COM DÉBITO                                                           |
    | - 83 - ENCERRADO POR VIGÊNCIA EXPIRADA                                                |
    |                                                                                       |
    +---------------------------------------------------------------------------------------+
    """

    for filho in processos_filho:

        filho_s = list(filho)

        # aqui calcula-se a quantidade de meses entre o último pagamento e o final da vigencia do filho
        # esta quandidade é inserida ao final da lista para ser gravada na tabela ao final
        if filho_s[8] not in situ_filho_retirados and filho.max_term_filho >= data_referência:
            filho_s.append((filho.max_term_filho.year  - filho.max_dt_ult_pag.year) * 12 +\
                           (filho.max_term_filho.month - filho.max_dt_ult_pag.month))
            if filho_s[15] < 0:
                filho_s[15] = 0
        else:
            filho_s.append(0)

        if filho.valor_apagar != None:
            filho_s[13] = filho.valor_apagar * filho_s[15]
        else:
            filho_s[13] = 0

        filho_gravar = Processo_Filho(cod_programa      = filho_s[0],
                                      nome_chamada      = filho_s[1],
                                      proc_mae          = filho_s[2],
                                      processo          = filho_s[3],
                                      nome              = filho_s[4],
                                      cpf               = filho_s[5],
                                      modalidade        = filho_s[6],
                                      nivel             = filho_s[7],
                                      situ_filho        = filho_s[8],
                                      inic_filho        = filho_s[9],
                                      term_filho        = filho_s[10],
                                      mens_pagas        = filho_s[11],
                                      pago_total        = filho_s[12],
                                      valor_apagar      = filho_s[13],
                                      mens_apagar       = filho_s[15],
                                      dt_ult_pag        = filho_s[14])
        db.session.add(filho_gravar)

    db.session.commit()

    print ('<<',dt.now().strftime("%x %X"),'>> ',' Tabela dos processos-filho criada.')



    #
    # pega processos mãe da planilha de folha de pagamento

    processos_mae = db.session.query(PagamentosPDCTR.proc_mae,
                                     PagamentosPDCTR.coordenador,
                                     PagamentosPDCTR.cod_programa,
                                     PagamentosPDCTR.nome_chamada,
                                     PagamentosPDCTR.inic_mae,
                                     PagamentosPDCTR.term_mae,
                                     label('max_id',func.max(PagamentosPDCTR.id)),
                                     PagamentosPDCTR.situ_mae)\
                               .group_by(PagamentosPDCTR.proc_mae,
                                         PagamentosPDCTR.coordenador,
                                         PagamentosPDCTR.cod_programa,
                                         PagamentosPDCTR.nome_chamada,
                                         PagamentosPDCTR.inic_mae,
                                         PagamentosPDCTR.term_mae,
                                         PagamentosPDCTR.situ_mae)\
                               .all()
                                     #label('max_term_mae',func.max(PagamentosPDCTR.term_mae)))\

#
    quantidade_mae = len(processos_mae)

    # Atualiza tabela  Processo_Mae
    for mae in processos_mae:

        mae_atual = db.session.query(Processo_Mae).filter(Processo_Mae.proc_mae==mae.proc_mae).first()

        if mae_atual == None:

            print('*** Novo processo mãe inserido: ',mae.proc_mae,' ***')
            mae_gravar = Processo_Mae(cod_programa  = mae.cod_programa,
                                      nome_chamada  = mae.nome_chamada,
                                      proc_mae      = mae.proc_mae,
                                      inic_mae      = mae.inic_mae,
                                      term_mae      = mae.term_mae,
                                      coordenador   = mae.coordenador,
                                      situ_mae      = mae.situ_mae)
            db.session.add(mae_gravar)
            db.session.commit()

        else:
            # altera final do mãe para o que estiver na tabela de pagamentos
            mae_atual.term_mae = mae.term_mae
            # só altera nome do coordenador se na tabela de pagamentos o nome não estiver nulo
            if mae.coordenador != None:
                mae_atual.coordenador = mae.coordenador
            # só altera a situação se na tabela de pagamentos este campo não estiver nulo e se for diferente de 71 tabela de processos_mãe
            if mae.situ_mae != None and mae_atual.situ_mae != '71':
                mae_atual.situ_mae = mae.situ_mae

            db.session.commit()


    print ('<<',dt.now().strftime("%x %X"),'>> ',' Tabela dos processos-mae atualizada.')
    print ('<<',dt.now().strftime("%x %X"),'>> ',' Procedimento finalizado!')
    print ('\n')


def salvar_arquivo_upload(arquivo_form):
    """
    Salva o arquivo enviado por um FileField (Flask-WTF) num diretório
    temporário do sistema operacional, e retorna o caminho completo do
    arquivo salvo.
    """
    tempdirectory = tempfile.gettempdir()
    fname = secure_filename(arquivo_form.filename)
    caminho = os.path.join(tempdirectory, fname)
    arquivo_form.save(caminho)
    return caminho


def data_referencia_ultima_carga_pdctr():
    """Retorna a data de referência da última carga de folha de pagamento (PDCTR) registrada."""
    return db.session.query(label('dr', func.MAX(RefCargaPDCTR.data_ref))).first()


def carregar_mensagens_siconv(caminho_arquivo):
    """
    Lê a planilha de mensagens do SICONV e substitui o conteúdo da
    tabela MSG_Siconv pelos novos registros. Mensagens já existentes
    (mesmo convênio + descrição) são marcadas como 'v' (vistas);
    mensagens novas são marcadas como 'n'.
    """
    print('<<', dt.now().strftime("%x %X"), '>> ', ' Carga de mensagens iniciada...')

    book = xlrd.open_workbook(filename=caminho_arquivo, ragged_rows=True)
    planilha = book.sheet_by_name('Plan1')

    print(f'Quantidade de registros na planilha: {planilha.nrows}')

    qtd_linhas = planilha.nrows

    print('<<', dt.now().strftime("%x %X"), '>> ', ' Gravando dados no banco...')

    reg_msg = []

    for i in range(qtd_linhas):

        linha_base = planilha.row_values(i, start_colx=0, end_colx=None)

        ano_mes_dia = (str(xlrd.xldate.xldate_as_datetime(linha_base[2], 0))[0:10])
        dia_mes_ano = ano_mes_dia[8:10] + '/' + ano_mes_dia[5:7] + '/' + ano_mes_dia[0:4]

        data_ref = datetime.datetime.strptime(str(dia_mes_ano), '%d/%m/%Y').date()

        msg_gravada = db.session.query(MSG_Siconv)\
                                .filter(MSG_Siconv.nr_convenio == linha_base[0],
                                        MSG_Siconv.desc == linha_base[1]).first()

        sit = "v" if msg_gravada is not None else 'n'

        reg_msg.append([linha_base[0], linha_base[1], data_ref, sit])

    db.session.query(MSG_Siconv).delete()
    db.session.commit()

    for reg in reg_msg:
        msg = MSG_Siconv(nr_convenio=reg[0], desc=reg[1], data_ref=reg[2], sit=reg[3])
        db.session.add(msg)

    db.session.commit()

    print('<<', dt.now().strftime("%x %X"), '>> ', ' Carga de mensagens finalizada!')


###########################################################################################################
