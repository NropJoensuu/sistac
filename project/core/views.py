"""
.. topic:: Core (views)

    Este é o módulo inicial do sistema.

    Apresenta as telas de início, informação, o procedimento para carga de dados de pagamento de bolsistas: planilha COSAO
    e carga dos dados do SICONV (convênios). Aqui também estão os procedimentos das Chamadas.

.. topic:: Ações relacionadas aos bolsistas

    * Tela inicial: index
    * Tela de informações: info
    * Carregar dados PDCTR: carregaPDCTR
    * Carregar dados SICONV: carregaSICONV
    * Inserir dados de chamadas homologadas: cria_chamada
    * Atualizar dados de chamada homologada: update_chamada
    * Pega dados de projetos homologados em um arquivo: carrega_homologados
    * Gera lista de homologados de um chamada: lista_homologados
    * Altera dados de um homologado: edita_homologado
    * Remove registro na lista de homologados: deleta_homologado
    * Carregar mensagens do SICONV: carregaMSG


"""

# core/views.py

from flask import render_template,url_for,flash, redirect,request,Blueprint,abort
from flask_login import login_required, current_user
from sqlalchemy import func, distinct, and_, or_
from sqlalchemy.sql import label
from project import db, sched, app
from project.models import PagamentosPDCTR, RefCargaPDCTR, Programa, Proposta, Convenio,\
                           Pagamento, Empenho, Desembolso, RefSICONV,\
                           Chamadas, MSG_Siconv, Bolsa, Processo_Mae,\
                           Processo_Filho, Sistema, Crono_Desemb, Homologados, Plano_Aplic,\
                           Programa_CNPq, Acordo_ProcMae, Coords, grupo_programa_cnpq,\
                           chamadas_cnpq, chamadas_cnpq_acordos, Log_Auto

from project.demandas.views import registra_log_auto
from project.convenios.forms import ChamadaForm, SEIForm
from project.acordos.forms import ArquivoForm, HomologadoForm

import os
import re
import datetime
from datetime import datetime as dt
import xlrd
import shutil
import urllib.request
import csv
import locale
from threading import Thread
from werkzeug.utils import secure_filename
import tempfile
import zipfile
import oracledb
import traceback

core = Blueprint("core",__name__)

from project.core import services

# função que pega dados do DW

def consultaDW(**entrada):

    if entrada['tipo'] == 'programas_unid': # programas associados a uma unidade, procura no FT_PAGAMENTO por seq_id_programa_PROC e seq_id_programa

        sql = "SELECT DISTINCT \
                    p.cod_programa COD_PROGRAMA,\
                    p.nme_programa NOME_PROGRAMA,\
                    p.dsc_programa_abrev SIGLA_PROGRAMA,\
                    u.SGL_UNID_ORG UNIDADE\
                FROM  DWFATO.FT_PAGAMENTO \
                JOIN DWDIM.di_programa p ON p.seq_id_programa = dwfato.ft_pagamento.seq_id_programa_PROC\
                JOIN DWDIM.di_unidade_organizacional u ON u.seq_id_unid_org = DWFATO.FT_PAGAMENTO.SEQ_ID_UNID_ORG\
                WHERE u.SGL_UNID_ORG = '"+ entrada['unid'] +"'\
                UNION \
                SELECT DISTINCT\
                    p.cod_programa COD_PROGRAMA,\
                    p.nme_programa NOME_PROGRAMA,\
                    p.dsc_programa_abrev SIGLA_PROGRAMA,\
                    u.SGL_UNID_ORG UNIDADE\
                FROM  DWFATO.FT_PAGAMENTO \
                JOIN DWDIM.di_programa p ON p.seq_id_programa = dwfato.ft_pagamento.seq_id_programa\
                JOIN DWDIM.di_unidade_organizacional u ON u.seq_id_unid_org = DWFATO.FT_PAGAMENTO.SEQ_ID_UNID_ORG\
                WHERE u.SGL_UNID_ORG = '"+ entrada['unid'] +"'\
                ORDER BY UNIDADE, SIGLA_PROGRAMA"
    
    elif entrada['tipo'] == 'chamadas_programas': # chamadas associadas a um programa

        sql = "select \
                    DWDIM.DI_CHAMADA.nme_tipo_chamada                            TIPO_CHAMADA,\
                    DWDIM.DI_CHAMADA.sgl_chamada                                 SIGLA_CHAMADA,\
                    DWDIM.DI_CHAMADA.NME_CHAMADA                                 CHAMADA,\
                    COUNT(DISTINCT dwdim.di_processo.cod_proc_mae)               PROCESSOS_MAE,\
                    DWDIM.DI_CHAMADA.seq_id_chamada                              ID_CHAMADA,\
                    (select \
                            SUM (vlr_total_item_despesa_folha)\
                        FROM  DWFATO.FT_PAGAMENTO FT2\
                        JOIN DWDIM.DI_CHAMADA CH2 ON CH2.SEQ_ID_CHAMADA = FT2.SEQ_ID_CHAMADA\
                        WHERE FT2.seq_id_chamada = DWDIM.DI_CHAMADA.seq_id_chamada\
                        GROUP BY FT2.seq_id_chamada)                                        VALOR_FOLHA,\
                    (select \
                            SUM (vlr_total_item_despesa)\
                        FROM  DWFATO.FT_PAGAMENTO FT2\
                        JOIN DWDIM.DI_CHAMADA CH2 ON CH2.SEQ_ID_CHAMADA = FT2.SEQ_ID_CHAMADA\
                        WHERE FT2.seq_id_chamada = DWDIM.DI_CHAMADA.seq_id_chamada\
                        GROUP BY FT2.seq_id_chamada)                                       VALOR,\
                    DWDIM.DI_PROGRAMA.COD_PROGRAMA                                         COD_PROGRAMA\
                FROM  DWFATO.FT_PAGAMENTO FT1\
                JOIN DWDIM.DI_CHAMADA  ON DWDIM.DI_CHAMADA.SEQ_ID_CHAMADA   = FT1.SEQ_ID_CHAMADA\
                JOIN DWDIM.di_programa ON DWDIM.di_programa.seq_id_programa = FT1.seq_id_programa\
                JOIN DWDIM.DI_PROCESSO ON DWDIM.DI_PROCESSO.SEQ_ID_PROCESSO = FT1.SEQ_ID_PROCESSO\
                WHERE (DWDIM.di_programa.cod_programa = '"+ entrada['cod_programa'] +"') \
                GROUP BY DWDIM.DI_CHAMADA.seq_id_chamada, dwdim.di_programa.cod_programa, DWDIM.DI_CHAMADA.sgl_chamada, DWDIM.DI_CHAMADA.NME_CHAMADA,DWDIM.DI_CHAMADA.nme_tipo_chamada\
                order by DWDIM.DI_CHAMADA.sgl_chamada"

    elif entrada['tipo'] == 'processos_chamadas': # processos mãe associados a uma chamada

        sql = "SELECT DISTINCT \
                DWDIM.DI_PROGRAMA.COD_PROGRAMA             COD_PROGRAMA,\
                DWDIM.DI_CHAMADA.NME_CHAMADA               NOME_CHAMADA,\
                DWDIM.DI_PROCESSO.COD_PROC_MAE             PROC_MAE,\
                COUNT(DISTINCT DWDIM.DI_PROCESSO.COD_PROC) QTD_FILHOS,\
                (select DTA_INICIO from DWDIM.DI_PROCESSO           PR where PR.COD_PROC = DWDIM.DI_PROCESSO.COD_PROC_MAE and ROWNUM = 1) INICIO,\
                (select DTA_TERMINO from DWDIM.DI_PROCESSO          PR where PR.COD_PROC = DWDIM.DI_PROCESSO.COD_PROC_MAE and ROWNUM = 1) FIM,\
                (select DSC_SIT_PROC from DWDIM.DI_PROCESSO         PR where PR.COD_PROC = DWDIM.DI_PROCESSO.COD_PROC_MAE and ROWNUM = 1) SIT,\
                (select DSC_DETALHE_SIT_PROC from DWDIM.DI_PROCESSO PR where PR.COD_PROC = DWDIM.DI_PROCESSO.COD_PROC_MAE and ROWNUM = 1) SIT_DETALHE,\
                (select TXT_TITULO_PROC from DWDIM.DI_PROCESSO      PR where PR.COD_PROC = DWDIM.DI_PROCESSO.COD_PROC_MAE and ROWNUM = 1) TITULO,\
                (select PE.NME_PESSOA \
                        FROM DWFATO.FT_PAGAMENTO FT\
                        JOIN DWDIM.DI_PROCESSO PR ON PR.SEQ_ID_PROCESSO = FT.SEQ_ID_PROCESSO\
                        JOIN DWDIM.DI_PESSOA   PE ON PE.SEQ_ID_PESSOA   = FT.SEQ_ID_PESSOA_BENEF\
                        where PR.COD_PROC = DWDIM.DI_PROCESSO.COD_PROC_MAE and ROWNUM = 1)                             PESSOA,\
                (select SUM(FT2.VLR_TOTAL_ITEM_DESPESA)\
                        FROM  DWFATO.FT_PAGAMENTO FT2 \
                        JOIN DWDIM.DI_ITEM_DESPESA ID ON ID.SEQ_ID_ITEM_DESPESA = FT2.SEQ_ID_ITEM_DESPESA\
                        JOIN DWDIM.DI_PROCESSO     PR ON PR.SEQ_ID_PROCESSO     = FT2.SEQ_ID_PROCESSO\
                        where ID.NME_CATEG_ECONOMICA = 'Bolsa' AND PR.COD_PROC_MAE = DWDIM.DI_PROCESSO.COD_PROC_MAE)   PAGO_BOLSA,\
                (select SUM(FT2.VLR_TOTAL_ITEM_DESPESA)\
                        FROM  DWFATO.FT_PAGAMENTO FT2 \
                        JOIN DWDIM.DI_ITEM_DESPESA ID ON ID.SEQ_ID_ITEM_DESPESA = FT2.SEQ_ID_ITEM_DESPESA\
                        JOIN DWDIM.DI_PROCESSO     PR ON PR.SEQ_ID_PROCESSO     = FT2.SEQ_ID_PROCESSO\
                        where ID.NME_CATEG_ECONOMICA = 'Capital' AND PR.COD_PROC_MAE = DWDIM.DI_PROCESSO.COD_PROC_MAE) PAGO_CAPITAL,\
                (select SUM(FT2.VLR_TOTAL_ITEM_DESPESA)\
                        FROM  DWFATO.FT_PAGAMENTO FT2 \
                        JOIN DWDIM.DI_ITEM_DESPESA ID ON ID.SEQ_ID_ITEM_DESPESA = FT2.SEQ_ID_ITEM_DESPESA\
                        JOIN DWDIM.DI_PROCESSO     PR ON PR.SEQ_ID_PROCESSO     = FT2.SEQ_ID_PROCESSO\
                        where ID.NME_CATEG_ECONOMICA = 'Custeio' AND PR.COD_PROC_MAE = DWDIM.DI_PROCESSO.COD_PROC_MAE) PAGO_CUSTEIO\
                FROM  DWFATO.FT_PAGAMENTO \
           JOIN DWDIM.DI_CHAMADA  ON DWDIM.DI_CHAMADA.SEQ_ID_CHAMADA   = DWFATO.FT_PAGAMENTO.SEQ_ID_CHAMADA\
           JOIN DWDIM.di_programa ON DWDIM.di_programa.seq_id_programa = DWFATO.FT_PAGAMENTO.seq_id_programa\
           JOIN DWDIM.DI_PROCESSO ON DWDIM.DI_PROCESSO.SEQ_ID_PROCESSO = DWFATO.FT_PAGAMENTO.SEQ_ID_PROCESSO\
           WHERE DWDIM.DI_CHAMADA.seq_id_chamada = '"+ entrada['id_chamada'] +"' AND DWDIM.DI_PROCESSO.COD_PROC_MAE IS NOT NULL \
           GROUP BY DWDIM.DI_PROCESSO.cod_proc_mae, \
                    DWDIM.DI_PROGRAMA.COD_PROGRAMA, \
                    DWDIM.DI_CHAMADA.NME_CHAMADA\
           order by DWDIM.DI_PROCESSO.COD_PROC_MAE"          

    elif entrada['tipo'] == 'filhos_chamadas': # processos filho associados a uma chamada

        sql = "SELECT\
                DWDIM.DI_PROGRAMA.COD_PROGRAMA         COD_PROGRAMA,\
                DWDIM.DI_CHAMADA.NME_CHAMADA           NOME_CHAMADA,\
                DWDIM.DI_PROCESSO.COD_PROC             PROCESSO,\
                DWDIM.DI_PROCESSO.COD_PROC_MAE         PROCESSO_MAE,\
                DWDIM.DI_PROCESSO.DTA_INICIO           INICIO,\
                DWDIM.DI_PROCESSO.DTA_TERMINO          FIM,\
                DWDIM.DI_PROCESSO.DSC_SIT_PROC         SIT,\
                DWDIM.DI_PROCESSO.DSC_DETALHE_SIT_PROC SIT_DETALHE,\
                DWDIM.DI_PROCESSO.NME_ESTADO_FOMENTO   ESTADO_FOMENTO,\
                DWDIM.DI_PROCESSO.TXT_TITULO_PROC      TITULO,\
                DWDIM.DI_PESSOA.CPF_PESSOA             CPF,\
                DWDIM.DI_PESSOA.NME_PESSOA             PESSOA,\
                DWDIM.DI_MODALIDADE.COD_MODAL          MODAL,\
                DWDIM.DI_MODALIDADE.COD_CATEG_NIVEL    NIVEL,\
                SUM(DWFATO.FT_PAGAMENTO.QTD_BOLSAS)                   QTD_BOLSAS,\
                SUM(DWFATO.FT_PAGAMENTO.VLR_TOTAL_ITEM_DESPESA_FOLHA) PAGO_BOLSAS,\
                (select SUM(FT2.VLR_TOTAL_ITEM_DESPESA)\
                        FROM  DWFATO.FT_PAGAMENTO FT2 \
                        JOIN DWDIM.DI_ITEM_DESPESA ID ON ID.SEQ_ID_ITEM_DESPESA = FT2.SEQ_ID_ITEM_DESPESA\
                        JOIN DWDIM.DI_PROCESSO     PR ON PR.SEQ_ID_PROCESSO     = FT2.SEQ_ID_PROCESSO\
                        where ID.NME_CATEG_ECONOMICA = 'Capital' AND PR.COD_PROC = DWDIM.DI_PROCESSO.COD_PROC) PAGO_CAPITAL,\
                (select SUM(FT2.VLR_TOTAL_ITEM_DESPESA)\
                        FROM  DWFATO.FT_PAGAMENTO FT2 \
                        JOIN DWDIM.DI_ITEM_DESPESA ID ON ID.SEQ_ID_ITEM_DESPESA = FT2.SEQ_ID_ITEM_DESPESA\
                        JOIN DWDIM.DI_PROCESSO     PR ON PR.SEQ_ID_PROCESSO     = FT2.SEQ_ID_PROCESSO\
                        where ID.NME_CATEG_ECONOMICA = 'Custeio' AND PR.COD_PROC = DWDIM.DI_PROCESSO.COD_PROC) PAGO_CUSTEIO,\
                DWDIM.DI_PROCESSO.DTA_CARGA                                                                    DTA_CARGA\
                FROM  DWFATO.FT_PAGAMENTO \
           JOIN DWDIM.DI_PESSOA       ON DWDIM.DI_PESSOA.SEQ_ID_PESSOA             = DWFATO.FT_PAGAMENTO.SEQ_ID_PESSOA_BENEF\
           JOIN DWDIM.DI_CHAMADA      ON DWDIM.DI_CHAMADA.SEQ_ID_CHAMADA           = DWFATO.FT_PAGAMENTO.SEQ_ID_CHAMADA\
           JOIN DWDIM.di_programa     ON DWDIM.di_programa.seq_id_programa         = DWFATO.FT_PAGAMENTO.seq_id_programa\
           JOIN DWDIM.DI_PROCESSO     ON DWDIM.DI_PROCESSO.SEQ_ID_PROCESSO         = DWFATO.FT_PAGAMENTO.SEQ_ID_PROCESSO\
           JOIN DWDIM.DI_MODALIDADE   ON DWDIM.DI_MODALIDADE.SEQ_ID_MODALIDADE     = DWFATO.FT_PAGAMENTO.SEQ_ID_MODALIDADE\
           WHERE DWDIM.DI_CHAMADA.seq_id_chamada = '"+ entrada['id_chamada'] +"' \
           GROUP BY DWDIM.DI_PROGRAMA.COD_PROGRAMA     ,\
                DWDIM.DI_CHAMADA.NME_CHAMADA           ,\
                DWDIM.DI_PROCESSO.COD_PROC             ,\
                DWDIM.DI_PROCESSO.COD_PROC_MAE         ,\
                DWDIM.DI_PROCESSO.DTA_INICIO           ,\
                DWDIM.DI_PROCESSO.DTA_TERMINO          ,\
                DWDIM.DI_PROCESSO.DSC_SIT_PROC         ,\
                DWDIM.DI_PROCESSO.DSC_DETALHE_SIT_PROC ,\
                DWDIM.DI_PROCESSO.NME_ESTADO_FOMENTO   ,\
                DWDIM.DI_PROCESSO.TXT_TITULO_PROC      ,\
                DWDIM.DI_PESSOA.CPF_PESSOA             ,\
                DWDIM.DI_PESSOA.NME_PESSOA             ,\
                DWDIM.DI_MODALIDADE.COD_MODAL          ,\
                DWDIM.DI_MODALIDADE.COD_CATEG_NIVEL    ,\
                DWDIM.DI_PROCESSO.DTA_CARGA \
           order by DWDIM.DI_PESSOA.NME_PESSOA"

    elif entrada['tipo'] == 'financeiro_processos': # dados financeiros do que foi pago em processos informados

        sql = f"SELECT \
                        SUM(DWFATO.FT_PAGAMENTO.QTD_ITEM_DESPESA)           QTD,\
                        SUM(DWFATO.FT_PAGAMENTO.VLR_TOTAL_ITEM_DESPESA)     PAGO,\
                        DWDIM.DI_FONTE_RECURSO.COD_FONTE_RECURSO            COD_FONTE,\
                        DWDIM.DI_FONTE_RECURSO.NME_FONTE_RECURSO            NOME_FONTE,\
                        DWDIM.DI_PLANO_INTERNO.COD_PLANO_INTERNO            COD_PI,\
                        DWDIM.DI_PLANO_INTERNO.NME_PLANO_INTERNO            NOME_PI,\
                        DWDIM.DI_ITEM_DESPESA.NME_CATEG_ECONOMICA           NME_CATEG_ECONOMICA,\
                        DWDIM.DI_NATUREZA_DESP.NME_NATUR_DESP               NAUREZA_DESPESA\
                    FROM DWFATO.FT_PAGAMENTO \
                    JOIN DWDIM.DI_PROCESSO      ON DWDIM.DI_PROCESSO.SEQ_ID_PROCESSO           = DWFATO.FT_PAGAMENTO.SEQ_ID_PROCESSO\
                    JOIN DWDIM.DI_FONTE_RECURSO ON dwdim.di_fonte_recurso.seq_id_fonte_recurso = DWFATO.FT_PAGAMENTO.SEQ_ID_FONTE_RECURSO\
                    JOIN DWDIM.DI_PLANO_INTERNO ON DWDIM.DI_PLANO_INTERNO.SEQ_ID_PLANO_INTERNO = DWFATO.FT_PAGAMENTO.SEQ_ID_PLANO_INTERNO\
                    JOIN DWDIM.DI_ITEM_DESPESA  ON DWDIM.DI_ITEM_DESPESA.SEQ_ID_ITEM_DESPESA   = DWFATO.FT_PAGAMENTO.SEQ_ID_ITEM_DESPESA\
                    JOIN DWDIM.DI_NATUREZA_DESP ON DWDIM.DI_NATUREZA_DESP.SEQ_ID_NATUR_DESP    = DWFATO.FT_PAGAMENTO.SEQ_ID_NATUR_DESP\
                    WHERE DWDIM.DI_PROCESSO.COD_PROC IN {entrada['lista_processos']}\
                    GROUP BY DWDIM.DI_FONTE_RECURSO.NME_FONTE_RECURSO,\
                            DWDIM.DI_FONTE_RECURSO.COD_FONTE_RECURSO,\
                            DWDIM.DI_PLANO_INTERNO.COD_PLANO_INTERNO,\
                            DWDIM.DI_PLANO_INTERNO.NME_PLANO_INTERNO,\
                            DWDIM.DI_ITEM_DESPESA.NME_CATEG_ECONOMICA,\
                            DWDIM.DI_NATUREZA_DESP.NME_NATUR_DESP\
                    ORDER BY DWDIM.DI_FONTE_RECURSO.NME_FONTE_RECURSO"

    else:
        flash('TIPO INVÁLIDO','erro')
        return res

    dsn = os.environ.get('DSN_ORACLE')
    user = os.environ.get('USER_ORACLE')
    password = os.environ.get('PASSWORD_ORACLE')

    oracledb.init_oracle_client()

    conn = oracledb.connect(
                            user=user, 
                            password=password, 
                            dsn=dsn,
                            encoding="UTF-8"
                            )
    c = conn.cursor()

    c.execute(sql)
    
    res = c.fetchall()
            
    c.close()
    conn.close()

    return res

# função de que executa carga de dados de chamadas do DW para acordos e TEDs

def chamadas_DW():

    # quando o envio for feito pelo agendamento, current_user está vazio, pega então o usuário que fez o últinmo agendamento 
    if current_user == None or current_user.get_id() == None:
        user_agenda = db.session.query(Log_Auto.user_id)\
                                .filter(Log_Auto.tipo_registro == 'agc')\
                                .order_by(Log_Auto.id.desc())\
                                .first()
        id_user = user_agenda.user_id
        # por enquanto, a carga automática será só da COPES
        unidade = 'COPES'
    else:
        id_user = current_user.id
        # pega programas da unidade do usuário
        unidade = current_user.coord

    # se unidade for pai, junta ela com seus filhos
    hierarquia = db.session.query(Coords.sigla).filter(Coords.pai == unidade).all()

    if hierarquia:
        l_unid = [f.sigla for f in hierarquia]
        l_unid.append(unidade)
    else:
        l_unid = [unidade]

    programas = db.session.query(Programa_CNPq.COD_PROGRAMA).filter(Programa_CNPq.COORD.in_(l_unid)).all()

    cn = ca = pn = pa = fn = fm = 0 # contadores de chamadas e processos 

    print ('*** Consulta ao DW e carga no banco do SICOPES: Chamadas, mães e filhos')
    registra_log_auto(id_user,None,'car - Inciada consulta DW e carga no SICOPES.')

    for p in programas:
        # pega no DW dados de todas as chamadas de cada um dos programas identificados
        chamadas_programas = consultaDW(tipo = 'chamadas_programas', cod_programa = p.COD_PROGRAMA)
        print('** Programa: ',p.COD_PROGRAMA)
        print(' ')
        
        for cha_prog in chamadas_programas:

            nome = cha_prog[0] +' - '+ cha_prog[1] +' - '+ cha_prog[2]   # junta tipo, sigla e nome para formar novo nome
            id_chamada_DW = cha_prog[4]
            chamada = db.session.query(chamadas_cnpq).filter(chamadas_cnpq.id_dw == id_chamada_DW).first()
            # pegar somente chamadas cujos programas tenham vinculação com algum acordo
            programas_acordos = db.session.query(Programa_CNPq)\
                                          .join(grupo_programa_cnpq, grupo_programa_cnpq.id_programa == Programa_CNPq.ID_PROGRAMA)\
                                          .filter(Programa_CNPq.COD_PROGRAMA == p.COD_PROGRAMA)\
                                          .all()  
            if programas_acordos:

                if not chamada:
                    cn += 1
                    nova_chamada = chamadas_cnpq(tipo          = cha_prog[0],
                                                 sigla         = cha_prog[1],   
                                                 nome          = cha_prog[2],
                                                 valor         = cha_prog[6],  # VALOR, para VALOR_FOLHA, usar cha_prog[5]
                                                 cod_programa  = cha_prog[7],
                                                 id_dw         = cha_prog[4],
                                                 qtd_processos = cha_prog[3]) 
                    db.session.add(nova_chamada) 

                    chamada_id = nova_chamada.id

                else:
                    ca += 1
                    chamada.tipo          = cha_prog[0]
                    chamada.sigla         = cha_prog[1]
                    chamada.nome          = cha_prog[2]
                    chamada.cod_programa  = cha_prog[7]
                    chamada.valor         = cha_prog[6] # VALOR, para VALOR_FOLHA, usar cha_prog[5]
                    chamada.qtd_processos = cha_prog[3]

                    chamada_id = chamada.id

                print('** Chamadas: ',cn,' novas ',ca,' atualizadas',' id: ',id_chamada_DW)  
                print(' ')  
                
                if chamada:

                    chamada_cnpq_acordo = db.session.query(chamadas_cnpq_acordos).filter(chamadas_cnpq_acordos.chamada_cnpq_id == chamada_id).first()

                    if chamada_cnpq_acordo: # pegar mães e filhos somente se a chamada já estiver relacinada a um acordo/TED

                        if cha_prog[3] > 0:  # pega mães e filhos se ouver pelo menos um processo mãe na chamada

                            # pega projetos vinculados à chamada e carrega em processos_mae (id_chamada recebe o seq_id_chamada)
                            processos_chamadas = consultaDW(tipo = 'processos_chamadas', id_chamada = str(id_chamada_DW)) 
                            # pegar processos filho de cada chamada
                            filhos_chamadas = consultaDW(tipo = 'filhos_chamadas', id_chamada = str(id_chamada_DW))  

                            print('** Pegando mães e fihos da chamada: ',chamada.nome)  
                            print(' ')

                            # varre todos os processos mãe de cada chamada oriunddos do DW para carga no banco do sicopes
                            for pro_cha in processos_chamadas:
                                # ajusta conteúdo de situação caso seja nulo
                                if pro_cha[6]:
                                    situ = pro_cha[6]
                                else: 
                                    situ = ''  
                                if pro_cha[7]:
                                    situ = situ + ' ' + pro_cha[7]
                                # formata número do processo mãe
                                proc_mae_formatado = str(pro_cha[2])[4:10]+'/'+str(pro_cha[2])[:4]+'-'+str(pro_cha[2])[10:]
                                # pega processos mãe conforme encontrado no DW, não existinto cria, caso contrário atualiza        
                                proc_mae = db.session.query(Processo_Mae).filter(Processo_Mae.proc_mae == proc_mae_formatado).first()
                                if not proc_mae:
                                    pn += 1      
                                    novo_proc_mae = Processo_Mae(cod_programa = str(pro_cha[0]),
                                                                 nome_chamada = pro_cha[1],
                                                                 proc_mae     = proc_mae_formatado,
                                                                 inic_mae     = pro_cha[4],
                                                                 term_mae     = pro_cha[5],
                                                                 coordenador  = pro_cha[9],
                                                                 situ_mae     = situ,
                                                                 id_chamada   = chamada_id,
                                                                 pago_capital = pro_cha[11],
                                                                 pago_custeio = pro_cha[12],
                                                                 pago_bolsas  = pro_cha[10])
                                    db.session.add(novo_proc_mae)
                                    id_proc_mae = novo_proc_mae.id
                                else:
                                    pa += 1
                                    proc_mae.cod_programa = str(pro_cha[0])
                                    proc_mae.nome_chamada = pro_cha[1]
                                    proc_mae.inic_mae     = pro_cha[4]
                                    proc_mae.term_mae     = pro_cha[5]
                                    #proc_mae.coordenador  = pro_cha[9]  # ver se é possível pegar coordenador via DW
                                    proc_mae.situ_mae     = situ
                                    proc_mae.id_chamada   = chamada_id
                                    proc_mae.pago_capital = pro_cha[11]
                                    proc_mae.pago_custeio = pro_cha[12]
                                    proc_mae.pago_bolsas  = pro_cha[10]

                                    id_proc_mae = proc_mae.id

                                # se a chamamada tiver só um mãe, já associa ele ao acordo
                                if cha_prog[3] == 1:
                                    acordo_procmae = db.session.query(Acordo_ProcMae)\
                                                               .filter(Acordo_ProcMae.acordo_id == chamada_cnpq_acordo.acordo_id,
                                                                       Acordo_ProcMae.proc_mae_id ==  id_proc_mae)\
                                                               .all()
                                    if not acordo_procmae:
                                        associa_acordo_procmae = Acordo_ProcMae(acordo_id   = chamada_cnpq_acordo.acordo_id,
                                                                                proc_mae_id = id_proc_mae)
                                        db.session.add(associa_acordo_procmae)    
                                    
                        
                                # deleta todos os filhos do processo mãe da vez para carga limpa
                                procs_filho = db.session.query(Processo_Filho).filter(Processo_Filho.proc_mae == proc_mae_formatado).delete()
                                db.session.commit()

                                # para cada processo mãe, varre processos filho encontrados no DW
                                dic_fil_cha = {}
                                for fil_cha in filhos_chamadas:
                                    
                                    # carrega dicionário com valores obtidos do processo filho
                                    dic_fil_cha['COD_PROGRAMA']   = fil_cha[0]
                                    dic_fil_cha['NOME_CHAMADA']   = fil_cha[1]
                                    dic_fil_cha['PROCESSO']       = fil_cha[2]
                                    dic_fil_cha['PROCESSO_MAE']   = fil_cha[3]
                                    dic_fil_cha['INICIO']         = fil_cha[4]
                                    dic_fil_cha['FIM']            = fil_cha[5]
                                    dic_fil_cha['SIT']            = fil_cha[6]
                                    dic_fil_cha['SIT_DETALHE']    = fil_cha[7]
                                    dic_fil_cha['ESTADO_FOMENTO'] = fil_cha[8]
                                    dic_fil_cha['TITULO']         = fil_cha[9]
                                    dic_fil_cha['CPF']            = fil_cha[10]
                                    dic_fil_cha['PESSOA']         = fil_cha[11]
                                    dic_fil_cha['MODAL']          = fil_cha[12]
                                    dic_fil_cha['NIVEL']          = fil_cha[13]
                                    dic_fil_cha['QTD_BOLSAS']     = fil_cha[14]
                                    dic_fil_cha['PAGO_BOLSAS']    = fil_cha[15]
                                    dic_fil_cha['PAGO_CAPITAL']   = fil_cha[16]
                                    dic_fil_cha['PAGO_CUSTEIO']   = fil_cha[17]
                                    dic_fil_cha['DTA_CARGA']      = fil_cha[18]

                                    if fil_cha[3] == pro_cha[2]:  # grava filho se ele for do processo mãe da vez

                                        # ajusta conteúdo de situação caso seja nulo
                                        if dic_fil_cha['SIT']:
                                            situ_filho = dic_fil_cha['SIT']
                                            if dic_fil_cha['SIT_DETALHE']:
                                                situ_filho = str(situ_filho) + ' ' + dic_fil_cha['SIT_DETALHE']
                                        elif dic_fil_cha['ESTADO_FOMENTO']:
                                            situ_filho = dic_fil_cha['ESTADO_FOMENTO']
                                        else: 
                                            situ_filho = ''

                                        # zerando valores nulos
                                        if dic_fil_cha['QTD_BOLSAS']:
                                            mens_pagas = dic_fil_cha['QTD_BOLSAS']
                                        else:
                                            mens_pagas = 0
                                        if dic_fil_cha['PAGO_BOLSAS']:
                                            pago_total = dic_fil_cha['PAGO_BOLSAS']
                                        else:
                                            pago_total = 0  

                                        # calcular valor a pagar e mensalidades a pagar

                                        bolsa = db.session.query(Bolsa).filter(Bolsa.mod == dic_fil_cha['MODAL'] and Bolsa.niv == dic_fil_cha['NIVEL']).first()
                                        if bolsa:
                                            valor_bolsa = bolsa.mensalidade
                                        else:
                                            valor_bolsa = 0

                                         # aqui calcula-se a quantidade de meses entre a data da carga e o final da vigencia do filho
                                         # esta quandidade é inserida no dicionário para ser gravada na tabela ao final
                                        if situ_filho == 'ATIVACAO Em folha de pagamento' and dic_fil_cha['FIM'] >= dic_fil_cha['DTA_CARGA']:
                                            dic_fil_cha['MENS_APAGAR'] = (dic_fil_cha['FIM'].year  - dic_fil_cha['DTA_CARGA'].year) * 12 +\
                                                        (dic_fil_cha['FIM'].month - dic_fil_cha['DTA_CARGA'].month)
                                            if dic_fil_cha['MENS_APAGAR'] < 0:
                                                dic_fil_cha['MENS_APAGAR'] = 0
                                        else:
                                            dic_fil_cha['MENS_APAGAR'] = 0 

                                         # Calculando o valor a pagar para o bolsista
                                        dic_fil_cha['VALOR_APAGAR'] = valor_bolsa * dic_fil_cha['MENS_APAGAR']

                                        # formata número do processo filho
                                        proc_filho_formatado = str(dic_fil_cha['PROCESSO'])[4:10]+'/'+str(dic_fil_cha['PROCESSO'])[:4]+'-'+str(dic_fil_cha['PROCESSO'])[10:]

                                        fn += 1
                                        novo_proc_filho = Processo_Filho(cod_programa = fil_cha[0],
                                                                         nome_chamada = None,
                                                                         proc_mae     = str(dic_fil_cha['PROCESSO_MAE'])[4:10]+'/'+str(dic_fil_cha['PROCESSO_MAE'])[:4]+'-'+str(dic_fil_cha['PROCESSO_MAE'])[10:],
                                                                         processo     = proc_filho_formatado,
                                                                         nome         = dic_fil_cha['PESSOA'],
                                                                         cpf          = dic_fil_cha['CPF'],
                                                                         modalidade   = dic_fil_cha['MODAL'],
                                                                         nivel        = dic_fil_cha['NIVEL'],
                                                                         situ_filho   = situ_filho,
                                                                         inic_filho   = dic_fil_cha['INICIO'],
                                                                         term_filho   = dic_fil_cha['FIM'],
                                                                         mens_pagas   = mens_pagas,
                                                                         pago_total   = pago_total,
                                                                         valor_apagar = dic_fil_cha['VALOR_APAGAR'],
                                                                         mens_apagar  = dic_fil_cha['MENS_APAGAR'],
                                                                         dt_ult_pag   = dic_fil_cha['DTA_CARGA'])
                                        db.session.add(novo_proc_filho)

                                            

                                    elif dic_fil_cha['PROCESSO_MAE'] == None: # verificando se ha nesta chamada processos sem mãe, pois além de mães com filho, a chamada pode ter processos de auxílio somente   
                                        
                                        # ajusta conteúdo de situação caso seja nulo
                                        if dic_fil_cha['SIT']:
                                            situ_filho = dic_fil_cha['SIT']
                                            if dic_fil_cha['SIT_DETALHE']:
                                                situ_filho = situ_filho + ' ' + dic_fil_cha['SIT_DETALHE']
                                        elif dic_fil_cha['ESTADO_FOMENTO']:
                                            situ_filho = dic_fil_cha['ESTADO_FOMENTO']
                                        else: 
                                            situ_filho = ''  

                                        # zerando valores nulos
                                        if dic_fil_cha['PAGO_BOLSAS']:
                                            pago_bolsas = dic_fil_cha['PAGO_BOLSAS']
                                        else:
                                            pago_bolsas = 0 
                                        if dic_fil_cha['PAGO_CAPITAL']:
                                            pago_capital = dic_fil_cha['PAGO_CAPITAL']
                                        else:
                                            pago_capital = 0
                                        if dic_fil_cha['PAGO_CUSTEIO']:
                                            pago_custeio = dic_fil_cha['PAGO_CUSTEIO']
                                        else:
                                            pago_custeio = 0    
                                        
                                        # formata número do processo filho
                                        proc_filho_formatado = str(dic_fil_cha['PROCESSO'])[4:10]+'/'+str(dic_fil_cha['PROCESSO'])[:4]+'-'+str(dic_fil_cha['PROCESSO'])[10:]

                                        # verifia se o processo já existe na tabela de processos mãe, não existinto cria, caso contrário atualiza        
                                        proc_mae = db.session.query(Processo_Mae).filter(Processo_Mae.proc_mae == proc_filho_formatado).first()
                                        if not proc_mae:
                                            novo_proc_mae = Processo_Mae(cod_programa = str(fil_cha[0]),
                                                                         nome_chamada = dic_fil_cha['NOME_CHAMADA'],
                                                                         proc_mae     = proc_filho_formatado,
                                                                         inic_mae     = dic_fil_cha['INICIO'],
                                                                         term_mae     = dic_fil_cha['FIM'],
                                                                         coordenador  = dic_fil_cha['CPF'],
                                                                         situ_mae     = situ_filho,
                                                                         id_chamada   = chamada_id,
                                                                         pago_capital = pago_capital,
                                                                         pago_custeio = pago_custeio,
                                                                         pago_bolsas  = pago_bolsas)
                                            db.session.add(novo_proc_mae)
                                            id_proc_mae = novo_proc_mae.id
                                        else:
                                            proc_mae.cod_programa = str(fil_cha[0])
                                            proc_mae.nome_chamada = dic_fil_cha['NOME_CHAMADA']
                                            proc_mae.inic_mae     = dic_fil_cha['INICIO']
                                            proc_mae.term_mae     = dic_fil_cha['FIM']
                                            proc_mae.coordenador  = dic_fil_cha['PESSOA']  
                                            proc_mae.situ_mae     = situ_filho
                                            proc_mae.id_chamada   = chamada_id
                                            proc_mae.pago_capital = pago_capital
                                            proc_mae.pago_custeio = pago_custeio
                                            proc_mae.pago_bolsas  = pago_bolsas

                                            id_proc_mae = proc_mae.id
                                        fm += 1 

                                        # se houver somente um filho sem mãe, já associa ele ao acordo
                                        if len(filhos_chamadas) == 1:
                                            acordo_procmae = db.session.query(Acordo_ProcMae)\
                                                               .filter(Acordo_ProcMae.acordo_id == chamada_cnpq_acordo.acordo_id,
                                                                       Acordo_ProcMae.proc_mae_id ==  id_proc_mae)\
                                                               .all()
                                            if not acordo_procmae:
                                                associa_acordo_procmae = Acordo_ProcMae(acordo_id   = chamada_cnpq_acordo.acordo_id,
                                                                                        proc_mae_id = id_proc_mae)
                                                db.session.add(associa_acordo_procmae)


                            print('** Mães: ',pn,' novos - ',pa,' antigos')    
                            print('** Filhos: ',fn, ' novos' ,' mãe: ',proc_mae_formatado)
                            print('** Processos de auxílio: ',fm)


                        else: # se a chamada tiver 0 mães, tem que pegar processos sem mãe e os colocam como mãe no banco do sicopes  
                            # pegar processos filho de cada chamada
                            filhos_chamadas = consultaDW(tipo = 'filhos_chamadas', id_chamada = str(id_chamada_DW))    

                            for fil_cha in filhos_chamadas:

                                if dic_fil_cha['PROCESSO_MAE'] == None: # pegando somente os que não tem mãe

                                    # ajusta conteúdo de situação caso seja nulo
                                    if dic_fil_cha['SIT']:
                                        situ_filho = dic_fil_cha['SIT']
                                        if dic_fil_cha['SIT_DETALHE']:
                                            situ_filho = situ_filho + ' ' + dic_fil_cha['SIT_DETALHE']
                                    elif dic_fil_cha['ESTADO_FOMENTO']:
                                        situ_filho = dic_fil_cha['ESTADO_FOMENTO']
                                    else: 
                                        situ_filho = ''

                                    # zerando valores nulos
                                    if dic_fil_cha['PAGO_BOLSAS']:
                                        pago_bolsas = dic_fil_cha['PAGO_BOLSAS']
                                    else:
                                        pago_bolsas = 0 
                                    if dic_fil_cha['PAGO_CAPITAL']:
                                        pago_capital = dic_fil_cha['PAGO_CAPITAL']
                                    else:
                                        pago_capital = 0
                                    if dic_fil_cha['PAGO_CUSTEIO']:
                                        pago_custeio = dic_fil_cha['PAGO_CUSTEIO']
                                    else:
                                        pago_custeio = 0

                                    
                                    # formata número do processo filho
                                    proc_filho_formatado = str(dic_fil_cha['PROCESSO'])[4:10]+'/'+str(dic_fil_cha['PROCESSO'])[:4]+'-'+str(dic_fil_cha['PROCESSO'])[10:]

                                    # verifia se o processo já existe na tabela de processos mãe, não existinto cria, caso contrário atualiza        
                                    proc_mae = db.session.query(Processo_Mae).filter(Processo_Mae.proc_mae == proc_filho_formatado).first()
                                    if not proc_mae:
                                        novo_proc_mae = Processo_Mae(cod_programa = str(fil_cha[0]),
                                                                        nome_chamada = dic_fil_cha['NOME_CHAMADA'],
                                                                        proc_mae     = proc_filho_formatado,
                                                                        inic_mae     = dic_fil_cha['INICIO'],
                                                                        term_mae     = dic_fil_cha['FIM'],
                                                                        coordenador  = dic_fil_cha['CPF'],
                                                                        situ_mae     = situ_filho,
                                                                        id_chamada   = chamada_id,
                                                                        pago_capital = pago_capital,
                                                                        pago_custeio = pago_custeio,
                                                                        pago_bolsas  = pago_bolsas)
                                        db.session.add(novo_proc_mae)
                                        id_proc_mae = novo_proc_mae.id
                                    else:
                                        proc_mae.cod_programa = str(fil_cha[0])
                                        proc_mae.nome_chamada = dic_fil_cha['NOME_CHAMADA']
                                        proc_mae.inic_mae     = dic_fil_cha['INICIO']
                                        proc_mae.term_mae     = dic_fil_cha['FIM']
                                        proc_mae.coordenador  = dic_fil_cha['PESSOA']  
                                        proc_mae.situ_mae     = situ_filho
                                        proc_mae.id_chamada   = chamada_id
                                        proc_mae.pago_capital = pago_capital
                                        proc_mae.pago_custeio = pago_custeio
                                        proc_mae.pago_bolsas  = pago_bolsas

                                        id_proc_mae = proc_mae.id
                                    fm += 1 

                                    # se houver somente um processo, já associa ele ao acordo
                                    if len(filhos_chamadas) == 1:
                                        acordo_procmae = db.session.query(Acordo_ProcMae)\
                                                               .filter(Acordo_ProcMae.acordo_id == chamada_cnpq_acordo.acordo_id,
                                                                       Acordo_ProcMae.proc_mae_id ==  id_proc_mae)\
                                                               .all()
                                        if not acordo_procmae:
                                            associa_acordo_procmae = Acordo_ProcMae(acordo_id   = chamada_cnpq_acordo.acordo_id,
                                                                                    proc_mae_id = id_proc_mae)
                                            db.session.add(associa_acordo_procmae)

                            print('** Processos de auxílio: ',fm)
                

        db.session.commit()

    print ('*** FIM DA ROTINA DE CARGA DE CHAMADAS DW ***')

    ref_siconv = db.session.query(RefSICONV).first()

    ref_siconv.data_cha_dw = datetime.date.today()

    db.session.commit()

    registra_log_auto(id_user,None,'car - Finalizada Consulta ao DW e carga no SICOPES.')


    return [cn,ca,pn,pa,fn,fm]


###########################################################################################################

#                função que executa carga de dados SICONV - é executada de forma assíncrona

###########################################################################################################

def cargaSICONV():

    # quando o envio for feito pelo agendamento, current_user está vazio, pega então o usuário que fez o últinmo agendamento 
    if current_user == None or current_user.get_id() == None:
        user_agenda = db.session.query(Log_Auto.user_id)\
                                .filter(Log_Auto.tipo_registro == 'agc')\
                                .order_by(Log_Auto.id.desc())\
                                .first()
        id = user_agenda.user_id
    else:
        id = current_user.id 


    ## parâmetros internos de download e carga: default 'sim' (colocar 'não' quando quiser pular fase)
    pega                 = 'sim'
    descompacta          = 'sim'
    carrega_programas    = 'sim'
    carrega_propostas    = 'sim'
    carrega_convenios    = 'sim'
    carrega_pagamentos   = 'sim'
    carrega_empenhos     = 'sim'
    carrega_desembolsos  = 'sim'
    carrega_crono_desemb = 'sim'
    carrega_plano_aplic  = 'não'

    ## pega arquivos do portal siconv e os descompacta, gerando os respectivos .csv
    print ('*****************************************************************')
    print ('<<',dt.now().strftime("%x %X"),'>> ','Downloading and unpacking SICONV files...')
    print ('*****************************************************************')
    registra_log_auto(id,None,'car - download e descompactação.')

    #url_base = 'http://portal.convenios.gov.br/images/docs/CGSIS/csv/'
    #url_base = 'http://plataformamaisbrasil.gov.br/images/docs/CGSIS/csv/'
    # url_base = 'http://repositorio.dados.gov.br/seges/detru/'

    url_base = os.environ.get('URL_SICONV')

    print(' URL ORIGEM: ',url_base)

    pasta_compactados = os.path.normpath('/temp/arqs_siconv')
    #pasta_compactados = 'arqs_siconv'
    if not os.path.exists(pasta_compactados):
        os.makedirs(os.path.normpath(pasta_compactados))

    # SEM 'siconv_prorroga_oficio.csv' e 'siconv_termo_aditivo.csv'
    arquivos = ['siconv_programa.csv','siconv_programa_proposta.csv','siconv_proposta.csv',
                'siconv_convenio.csv','siconv_empenho.csv','siconv_desembolso.csv','siconv_pagamento.csv',
                'siconv_cronograma_desembolso.csv','siconv_empenho_desembolso.csv','data_carga_siconv.csv']


                #
                #,'siconv_plano_aplicacao.csv'

    ## usando o urlretrieve para pegar os arquivos e o shutil para descompactar
    if pega == 'sim':

        #solução para erro de SSl certificado expirado
        import ssl
        ssl._create_default_https_context = ssl._create_unverified_context

        print ('*****************************************************************')

        for arquivo in arquivos:

            url = url_base + arquivo + '.zip'
            arq = os.path.normpath(pasta_compactados+'/'+arquivo+'.zip')

            urllib.request.urlretrieve (url,arq)
            print ('<<',dt.now().strftime("%x %X"),'>> ','Pegou ' + arquivo + '.zip')

        print ('*****************************************************************')

    if descompacta == 'sim':

        print ('*****************************************************************')

        for arquivo in arquivos:

            arq = os.path.normpath(pasta_compactados+'/'+arquivo+'.zip')

            #shutil.unpack_archive(arq,pasta_compactados,'zip')

            print ('<<',dt.now().strftime("%x %X"),'>> ','Tentará descompactar ' + arquivo)

            with zipfile.ZipFile(arq,"r") as zip_ref:
                zip_ref.extractall(pasta_compactados)

            print ('<<',dt.now().strftime("%x %X"),'>> ','Descompactou ' + arquivo)

        print ('*****************************************************************')
        registra_log_auto(id,None,'car - descompactou arquivos.')

        ## caso o urlretrieve seja deprecado, usar o urlopen e gravar o arquivo de destino
        #for arquivo in arquivos:
        #    url = url_base + arquivo + '.zip'
        #    response = urllib.request.urlopen(url)
        #    f = open(arquivo+'.zip', 'wb')
        #    f.write(response.read())
        #    f.close()
        #    shutil.unpack_archive(arquivo+'.zip',pasta_compactados,'zip')

        ## OBS: esta lista deve ser adquida do banco acordos_conv, tabela conv_programas_a_pegar
        ## os cod_programas vem do banco com uma lista de tuplas (vírcula no final e entre parenteses)
        ## tive que criar uma lista para pegar só o valor do cod_programa

    #funções internas

    def data_banco (dia):
        '''
        DOCSTRING: coloca data no padrao dd/mm/aaaa para aaaa-mm-dd
        INPUT: string - data dd/mm/aaaa
        OUTPUT: date - data aaaa-mm-dd
        '''
        return datetime.date(int(dia[-4:]),int(dia[3:5]),int(dia[0:2]))

    def valor_banco (valor):
        '''
        DOCSTRING: coloca valor no padrao 999,99 para 999.99
        INPUT: string - valor com , como separador decimal
        OUTPUT: float - valor com . como separador decimal
        '''
        if valor == None or valor == '':
            valor = '0'

        return float(valor.replace(',','.'))


    ##################################################
    ##             pegar dados de programas         ##
    ##################################################
    if carrega_programas == 'sim':

        arq = 'siconv_programa'
        arq = os.path.normpath(pasta_compactados+'/'+arq+'.csv')

        print ('*****************************************************************')
        print ('<<',dt.now().strftime("%x %X"),'>> ','Carregando dados de programas...')
        registra_log_auto(id,None,'car - carregando dados de programas.')

        # pega código da instituição para resgate dos programas associados
        cod_inst = db.session.query(RefSICONV.cod_inst).first()

        # abre csv dos programas e gera a lista data_lines
        with open(arq, newline='',encoding = 'utf-8-sig') as data:
            data_lines = csv.DictReader(data,delimiter=';')
            programas = []

        # gera a lista programas pegando somente os cujo código começa com 20501 (CNPq)
            for line in data_lines:

                if str(line['COD_PROGRAMA'][0:5]) == cod_inst.cod_inst:

                    programas.append([line['ID_PROGRAMA'],line['COD_PROGRAMA'],line['NOME_PROGRAMA'],line['SIT_PROGRAMA'],line['ANO_DISPONIBILIZACAO']])

            # classifica a lista programas pelo id_programa e gera a lista programas_unic retirando as repetições
            programas.sort(key=lambda x: x[0])

            ## deletar linhas da tabela programa e carregá-la com programas sem repetições
            id_programa = ''
            programas_unic = []

            db.session.query(Programa).delete()
            db.session.commit()

            for programa in programas:

                if programa[0] != id_programa:

                    programas_unic.append(programa)
                    programa_gravar = Programa(ID_PROGRAMA          = programa[0],
                                               COD_PROGRAMA         = programa[1],
                                               NOME_PROGRAMA        = programa[2],
                                               SIT_PROGRAMA         = programa[3],
                                               ANO_DISPONIBILIZACAO = programa[4])
                    db.session.add(programa_gravar)

                id_programa = programa[0]

            db.session.commit()

        if os.path.exists(arq):
            os.remove(arq + '.zip')
            os.remove(arq)

    ##################################################
    ##             pegar dados de propostas         ##
    ##################################################
    if carrega_propostas == 'sim':

        print ('<<',dt.now().strftime("%x %X"),'>> ','Carregando dados de propostas...')
        registra_log_auto(id,None,'car - carregando dados de propostas.')
        #lista dos identificadores de programas
        ids_programas = [id[0] for id in programas_unic]

        # abre csv do programa_proposta e gera a lista data_lines
        programa_proposta = []

        arq1 = 'siconv_programa_proposta'
        arq1 = os.path.normpath(pasta_compactados+'/'+arq1+'.csv')

        with open(arq1, newline='',encoding = 'utf-8') as data:
            data_lines = csv.DictReader(data,delimiter=';')

            id_programa_campo = data_lines.fieldnames[0]

            # gera a lista programa_proposta pegando somente os que tem id_programa na lista ids_programas
            for line in data_lines:
                if line[id_programa_campo] in ids_programas:
                    programa_proposta.append(line)

        # abre csv de propostas e gera a lista data_lines
        propostas = []

        arq2 = 'siconv_proposta'
        arq2 = os.path.normpath(pasta_compactados+'/'+arq2+'.csv')

        with open(arq2, newline='',encoding = 'utf-8') as data:
            data_lines = csv.DictReader(data,delimiter=';')

            # indica campos de interesse
            # tira lixo que vem no início do nome do primeiro campo

            campos_proposta = ['ID_PROPOSTA','UF_PROPONENTE','NM_PROPONENTE','OBJETO_PROPOSTA']

            id_proposta_campo = data_lines.fieldnames[0]

            # gera a lista propostas pegando somente os que coincidem com a programa_proposta,
            # incluindo o id_programa na primeira posição
            # ID_PROPOSTA está como chave primária em Proposta, então evitarei ocorrências repetidas

            set_id_proposta = set([item['ID_PROPOSTA'] for item in programa_proposta])

            for line in data_lines:
                if line[id_proposta_campo] in set_id_proposta:
                    propostas.append([line[id_proposta_campo],line[campos_proposta[1]],line[campos_proposta[2]],line[campos_proposta[3]]])

            db.session.query(Proposta).delete()
            db.session.commit()

            for proposta in propostas:

                for item in programa_proposta:
                    if item['ID_PROPOSTA'] == proposta[0]:
                        proposta.insert(0,item[id_programa_campo])
                        # deve parar quando achar a primeira equivalência de forma a não violar a chave primária de Proposta
                        break

                proposta_gravar = Proposta(ID_PROGRAMA      = proposta[0],
                                           ID_PROPOSTA      = proposta[1],
                                           UF_PROPONENTE    = proposta[2],
                                           NM_PROPONENTE    = proposta[3],
                                           OBJETO_PROPOSTA  = proposta[4])
                db.session.add(proposta_gravar)

            db.session.commit()

        if os.path.exists(arq1):
            os.remove(arq1 + '.zip')
            os.remove(arq1)

        if os.path.exists(arq2):
            os.remove(arq2 + '.zip')
            os.remove(arq2)

    ##################################################
    ##             pegar dados de convenios         ##
    ##################################################
    if carrega_convenios == 'sim':

        print ('<<',dt.now().strftime("%x %X"),'>> ','Carregando dados de convênios...')
        registra_log_auto(id,None,'car - carregando dados de convênios.')
        # abre csv de propostas e gera a lista data_lines
        arq = 'siconv_convenio'
        arq = os.path.normpath(pasta_compactados+'/'+arq+'.csv')

        with open(arq, newline='',encoding = 'utf-8') as data:
            data_lines = csv.DictReader(data,delimiter=';')

            convenios = []
            convenios_nr = []

            # PEGA NOME DO PRIMEIRO CAMPO, POIS COSTUAM VIR COM CARACTER ESTRANHO NO INÍCIO (?)

            nr_convenio_campo = data_lines.fieldnames[0]

            # grava convenios pegando somente os que coincidem com a programa_proposta

            db.session.query(Convenio).delete()
            db.session.commit()

            for line in data_lines:
                if line['ID_PROPOSTA'] in [item['ID_PROPOSTA'] for item in programa_proposta]:

                    if line[nr_convenio_campo] not in convenios_nr:

                        convenios.append(line)
                        convenios_nr.append(line[nr_convenio_campo])

                        convenio_gravar = Convenio(NR_CONVENIO                   = line[nr_convenio_campo],
                                                    ID_PROPOSTA                   = line['ID_PROPOSTA'],
                                                    DIA                           = line['DIA'],
                                                    MES                           = line['MES'],
                                                    ANO                           = line['ANO'],
                                                    DIA_ASSIN_CONV                = line['DIA_ASSIN_CONV'],
                                                    SIT_CONVENIO                  = line['SIT_CONVENIO'],
                                                    SUBSITUACAO_CONV              = line['SUBSITUACAO_CONV'],
                                                    SITUACAO_PUBLICACAO           = line['SITUACAO_PUBLICACAO'],
                                                    INSTRUMENTO_ATIVO             = line['INSTRUMENTO_ATIVO'],
                                                    IND_OPERA_OBTV                = line['IND_OPERA_OBTV'],
                                                    NR_PROCESSO                   = line['NR_PROCESSO'],
                                                    UG_EMITENTE                   = line['UG_EMITENTE'],
                                                    DIA_PUBL_CONV                 = line['DIA_PUBL_CONV'],
                                                    DIA_INIC_VIGENC_CONV          = line['DIA_INIC_VIGENC_CONV'],
                                                    DIA_FIM_VIGENC_CONV           = data_banco(line['DIA_FIM_VIGENC_CONV']),
                                                    DIA_FIM_VIGENC_ORIGINAL_CONV  = line['DIA_FIM_VIGENC_ORIGINAL_CONV'],
                                                    DIAS_PREST_CONTAS             = line['DIAS_PREST_CONTAS'],
                                                    DIA_LIMITE_PREST_CONTAS       = line['DIA_LIMITE_PREST_CONTAS'],
                                                    SITUACAO_CONTRATACAO          = line['SITUACAO_CONTRATACAO'],
                                                    IND_ASSINADO                  = line['IND_ASSINADO'],
                                                    MOTIVO_SUSPENSAO              = line['MOTIVO_SUSPENSAO'],
                                                    IND_FOTO                      = line['IND_FOTO'],
                                                    QTDE_CONVENIOS                = line['QTDE_CONVENIOS'],
                                                    QTD_TA                        = line['QTD_TA'],
                                                    QTD_PRORROGA                  = line['QTD_PRORROGA'],
                                                    VL_GLOBAL_CONV                = valor_banco(line['VL_GLOBAL_CONV']),
                                                    VL_REPASSE_CONV               = valor_banco(line['VL_REPASSE_CONV']),
                                                    VL_CONTRAPARTIDA_CONV         = valor_banco(line['VL_CONTRAPARTIDA_CONV']),
                                                    VL_EMPENHADO_CONV             = valor_banco(line['VL_EMPENHADO_CONV']),
                                                    VL_DESEMBOLSADO_CONV          = valor_banco(line['VL_DESEMBOLSADO_CONV']),
                                                    VL_SALDO_REMAN_TESOURO        = valor_banco(line['VL_SALDO_REMAN_TESOURO']),
                                                    VL_SALDO_REMAN_CONVENENTE     = valor_banco(line['VL_SALDO_REMAN_CONVENENTE']),
                                                    VL_RENDIMENTO_APLICACAO       = valor_banco(line['VL_RENDIMENTO_APLICACAO']),
                                                    VL_INGRESSO_CONTRAPARTIDA     = valor_banco(line['VL_INGRESSO_CONTRAPARTIDA']),
                                                    VL_SALDO_CONTA                = valor_banco(line['VL_SALDO_CONTA']),
                                                    VALOR_GLOBAL_ORIGINAL_CONV    = valor_banco(line['VALOR_GLOBAL_ORIGINAL_CONV']))

                        db.session.add(convenio_gravar)
                    
                    else:

                        print ('<<',dt.now().strftime("%x %X"),'>> ','Convênio '+str(line[nr_convenio_campo])+' não incluído. DUPLICADO!')


            db.session.commit()

        if os.path.exists(arq):
            os.remove(arq + '.zip')
            os.remove(arq)


    ##
    ##################################################
    ##             pegar dados de empenho           ##
    ##################################################
    if carrega_empenhos == 'sim':

        print ('<<',dt.now().strftime("%x %X"),'>> ','Carregando dados de empenhos...')
        registra_log_auto(id,None,'car - carregando dados de empenhos.')
        # abre csv de empenho e gera a lista data_lines
        empenhos = []
        arq = 'siconv_empenho'
        arq = os.path.normpath(pasta_compactados+'/'+arq+'.csv')

        with open(arq, newline='',encoding = 'utf-8-sig') as data:
            data_lines = csv.DictReader(data,delimiter=';')
            #
            db.session.query(Empenho).delete()
            db.session.commit()

            convs = [convenio[nr_convenio_campo] for convenio in convenios]

            # gera a lista empenhos pegando somente os que coincidem com convenios
            for line in data_lines:

                if line['NR_CONVENIO'] in convs:

                    empenhos.append(line)
                    emp = Empenho(ID_EMPENHO              = line['ID_EMPENHO'],
                                  NR_CONVENIO             = line['NR_CONVENIO'],
                                  NR_EMPENHO              = line['NR_EMPENHO'],
                                  TIPO_NOTA               = line['TIPO_NOTA'],
                                  DESC_TIPO_NOTA          = line['DESC_TIPO_NOTA'],
                                  DATA_EMISSAO            = data_banco(line['DATA_EMISSAO']),
                                  COD_SITUACAO_EMPENHO    = line['COD_SITUACAO_EMPENHO'],
                                  DESC_SITUACAO_EMPENHO   = line['DESC_SITUACAO_EMPENHO'],
                                  VALOR_EMPENHO           = valor_banco(line['VALOR_EMPENHO']))
                    db.session.add(emp)

            # identificando ID_EMPENHO duplicados
            seen = {}
            dupes = []

            for x in empenhos:
                if x['NR_CONVENIO'] in convs:
                    if x['ID_EMPENHO'] not in seen:
                        seen[x['ID_EMPENHO']] = 1
                    else:
                        if seen[x['ID_EMPENHO']] == 1:
                            dupes.append(x['ID_EMPENHO'])
                        seen[x['ID_EMPENHO']] += 1
            print ('<<',dt.now().strftime("%x %X"),'>> ','ID_EMPENHO duplicados: ',dupes)

            db.session.commit()

        if os.path.exists(arq):
            os.remove(arq + '.zip')
            os.remove(arq)

    ##
    ##################################################
    ##             pegar dados de desembolso        ##
    ##################################################
    if carrega_desembolsos == 'sim':

        # abre csv do empenho_desembolso e gera a lista data_lines
        empenho_desembolso = []
        arq1 = 'siconv_empenho_desembolso'
        arq1 = os.path.normpath(pasta_compactados+'/'+arq1+'.csv')

        with open(arq1, newline='',encoding = 'utf-8-sig') as data:
            data_lines = csv.DictReader(data,delimiter=';')

            # gera a lista empenho_desembolso
            for line in data_lines:
                empenho_desembolso.append(line)

        print ('<<',dt.now().strftime("%x %X"),'>> ','Carregando dados de desembolso...')
        registra_log_auto(id,None,'car - carregando dados de desembolso.')

        # abre csv de desembolso e gera a lista data_lines
        desembolsos = []
        arq2 = 'siconv_desembolso'
        arq2 = os.path.normpath(pasta_compactados+'/'+arq2+'.csv')

        #
        db.session.query(Desembolso).delete()
        db.session.commit()

        with open(arq2, newline='',encoding = 'utf-8-sig') as data:
            data_lines = csv.DictReader(data,delimiter=';')

            # gera a lista desembolsos pegando somente os que coincidem com a empenhos
            for line in data_lines:
                if line['NR_CONVENIO'] in [convenio[nr_convenio_campo] for convenio in convenios] \
                   and line['ID_DESEMBOLSO'] != '' and line['ID_DESEMBOLSO'] != None \
                   and line['ID_DESEMBOLSO'] in [desembolso['ID_DESEMBOLSO'] for desembolso in empenho_desembolso]:

                    for item in empenho_desembolso:
                        if item['ID_DESEMBOLSO'] == line['ID_DESEMBOLSO']:
                            if item['ID_EMPENHO'] != '' and item['ID_EMPENHO'] != None:
                                line['ID_EMPENHO'] = item['ID_EMPENHO']
                            else:
                                line['ID_EMPENHO'] = ''    

                    des = Desembolso(ID_DESEMBOLSO           = line['ID_DESEMBOLSO'],
                                     NR_CONVENIO             = line['NR_CONVENIO'],
                                     DT_ULT_DESEMBOLSO       = data_banco(line['DT_ULT_DESEMBOLSO']),
                                     QTD_DIAS_SEM_DESEMBOLSO = line['QTD_DIAS_SEM_DESEMBOLSO'],
                                     DATA_DESEMBOLSO         = data_banco(line['DATA_DESEMBOLSO']),
                                     ANO_DESEMBOLSO          = line['ANO_DESEMBOLSO'],
                                     MES_DESEMBOLSO          = line['MES_DESEMBOLSO'],
                                     NR_SIAFI                = line['NR_SIAFI'],
                                     VL_DESEMBOLSADO         = valor_banco(line['VL_DESEMBOLSADO']),
                                     ID_EMPENHO              = line['ID_EMPENHO'])
                    db.session.add(des)

            db.session.commit()

        if os.path.exists(arq2):
            os.remove(arq2 + '.zip')
            os.remove(arq2)

        if os.path.exists(arq1):
            os.remove(arq1 + '.zip')
            os.remove(arq1)    

    #
    ##################################################
    ##             pegar dados de pagamento         ##
    ##################################################
    if carrega_pagamentos == 'sim':

        print ('<<',dt.now().strftime("%x %X"),'>> ','Carregando dados de pagamentos...')
        registra_log_auto(id,None,'car - carregando dados de pagamentos.')
        # abre csv de pagamento e gera a lista data_lines
        pagamentos = []

        db.session.query(Pagamento).delete()
        db.session.commit()

        arq = 'siconv_pagamento'
        arq = os.path.normpath(pasta_compactados+'/'+arq+'.csv')

        with open(arq, newline='',encoding = 'utf-8') as data:
            data_lines = csv.DictReader(data,delimiter=';')

            i = 0
            # gera a lista pagamentos pegando somente os que coincidem com convenios
            for line in data_lines:

                if line['NR_CONVENIO'] in [convenio[nr_convenio_campo] for convenio in convenios]:

                    pag = Pagamento(NR_CONVENIO          = line['NR_CONVENIO'],
                                    IDENTIF_FORNECEDOR   = line['IDENTIF_FORNECEDOR'],
                                    NOME_FORNECEDOR      = line['NOME_FORNECEDOR'],
                                    VL_PAGO              = float(valor_banco(line['VL_PAGO'])))

                    db.session.add(pag)

            db.session.commit()

        if os.path.exists(arq):
            os.remove(arq + '.zip')
            os.remove(arq)

    #
    ##########################################################
    ##             pegar dados de crono-desembolso          ##
    ##########################################################
    if carrega_crono_desemb == 'sim':

        print ('<<',dt.now().strftime("%x %X"),'>> ','Carregando dados de cronograma_desembolso...')
        registra_log_auto(id,None,'car - carregando dados de cronograma_desembolso.')

        # abre csv de cronograma_desembolso e gera a lista data_lines

        db.session.query(Crono_Desemb).delete()
        db.session.commit()

        arq = 'siconv_cronograma_desembolso'
        arq = os.path.normpath(pasta_compactados+'/'+arq+'.csv')

        with open(arq, newline='',encoding = 'utf-8-sig') as data:
            data_lines = csv.DictReader(data,delimiter=';')

            # gera a lista cronograma_desembolso pegando somente os que coincidem com convenios
            for line in data_lines:

                if line['NR_CONVENIO'] in [convenio[nr_convenio_campo] for convenio in convenios]:

                    crono_desemb = Crono_Desemb(ID_PROPOSTA                    = line['ID_PROPOSTA'],
                                                NR_CONVENIO                    = line['NR_CONVENIO'],
                                                NR_PARCELA_CRONO_DESEMBOLSO    = line['NR_PARCELA_CRONO_DESEMBOLSO'],
                                                MES_CRONO_DESEMBOLSO           = line['MES_CRONO_DESEMBOLSO'],
                                                ANO_CRONO_DESEMBOLSO           = line['ANO_CRONO_DESEMBOLSO'],
                                                TIPO_RESP_CRONO_DESEMBOLSO     = line['TIPO_RESP_CRONO_DESEMBOLSO'],
                                                VALOR_PARCELA_CRONO_DESEMBOLSO = float(valor_banco(line['VALOR_PARCELA_CRONO_DESEMBOLSO'])))

                    db.session.add(crono_desemb)

            db.session.commit()

        if os.path.exists(arq):
            os.remove(arq + '.zip')
            os.remove(arq)

    #
    ############################################################
    ##             pegar dados de plano de aplicação         ##
    ###########################################################
    if carrega_plano_aplic == 'sim':

        print ('<<',dt.now().strftime("%x %X"),'>> ','Carregando dados de plano de aplicação...')
        registra_log_auto(id,None,'car - carregando dados de plano de aplicação.')
        # abre csv de propostas e gera a lista data_lines
        arq = 'siconv_plano_aplicacao'
        arq = os.path.normpath(pasta_compactados+'/'+arq+'.csv')

        with open(arq, newline='',encoding = 'utf-8-sig') as data:
            data_lines = csv.DictReader(data,delimiter=';')

            # grava plano_aplic pegando somente os que coincidem com a programa_proposta

            db.session.query(Plano_Aplic).delete()
            db.session.commit()

            for line in data_lines:
                if line['ID_PROPOSTA'] in [item['ID_PROPOSTA'] for item in programa_proposta]:

                    plano_aplic = Plano_Aplic( ID_PROPOSTA          = line['ID_PROPOSTA'],
                                               NATUREZA_AQUISICAO   = line['NATUREZA_AQUISICAO'],
                                               TIPO_DESPESA_ITEM    = line['TIPO_DESPESA_ITEM'],
                                               COD_NATUREZA_DESPESA = line['COD_NATUREZA_DESPESA'],
                                               QTD_ITEM             = valor_banco(line['QTD_ITEM']),
                                               VALOR_UNITARIO_ITEM  = valor_banco(line['VALOR_UNITARIO_ITEM']),
                                               VALOR_TOTAL_ITEM     = valor_banco(line['VALOR_TOTAL_ITEM']))

                    db.session.add(plano_aplic)

            db.session.commit()

        if os.path.exists(arq):
            os.remove(arq + '.zip')
            os.remove(arq)

    #
    ################################################################################################
    ##       ainda decidindo se vale a pena pegar dados de prorroga_oficio e termo_aditivo        ##
    ################################################################################################

    ##
    ############################################################
    ##             pegar data de referência SICONV           ##
    ##########################################################
    print ('<<',dt.now().strftime("%x %X"),'>> ','Carregando data dos dados...')
    registra_log_auto(id,None,'car - carregando data dos dados.')
    # abre csv de com data da carga e gera a lista data_lines
    arq = 'data_carga_siconv'
    arq = os.path.normpath(pasta_compactados+'/'+arq+'.csv')

    with open(arq, newline='',encoding = 'utf-8') as data:

        data_lines = csv.DictReader(data,delimiter=';')

        nome_campo = data_lines.fieldnames[0]

        for line in data_lines:
            data_ref = dt.strptime(str(line[nome_campo][:10]), '%d/%m/%Y').date()

        ref_siconv = db.session.query(RefSICONV).first()

        ref_siconv.data_ref = data_ref

        db.session.commit()

    if os.path.exists(arq):
        os.remove(arq + '.zip')
        os.remove(arq)

    print ('<<',dt.now().strftime("%x %X"),'>> ','Carga SICONV finalizada!')
    print ('*****************************************************************')

    registra_log_auto(id,None,'car - carga SICONV finalizada.')


# função que executa thread de carga dos dados SICONV
def thread_cargaSICONV():
    with app.app_context():
        print('*** CARGA SICONV EM THREAD SEPARADA ***')
        thr = Thread(target=cargaSICONV)
        thr.start()


@core.route('/')
def index():
    """
    +---------------------------------------------------------------------------------------+
    |Ações quando o aplicativo é colocado no ar.                                            |
    +---------------------------------------------------------------------------------------+
    """
    sistema = services.dados_sistema()

    services.agendar_cargas_iniciais()

    return render_template ('index.html',sistema=sistema) 

@core.route('/inicio')
def inicio():
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta a tela inicial do aplicativo.                                                |
    +---------------------------------------------------------------------------------------+
    """
    sistema = services.dados_sistema()

    return render_template ('index.html',sistema=sistema)    

@core.route('/info')
def info():
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta a tela de informações do aplicativo.                                         |
    +---------------------------------------------------------------------------------------+
    """

    return render_template('info.html')

@core.route('/carregaPDCTR', methods=['GET', 'POST'])
@login_required
def carregaPDCTR():
    """
    +---------------------------------------------------------------------------------------+
    |Executa o procedimento de carga dos dados de folha de pagamento enviados via planilha  |
    |excel, pela COSAO: planilha COSAO.                                                     |
    |                                                                                       |
    |O módulo pede que seja informado o local onde a planilha COSAO foi salva e armazena os |
    |dados úteis ao aplicativo em tabela própria do banco de dados.                         |
    |                                                                                       |
    |Somente são gravados registros que não existam previamente no banco de dados, ou seja, |
    |caso a planilha COSAO tenha dados previamente carregados, não ocorre a duplicação.     |
    |                                                                                       |
    | *É muito importante que a planilha a ser carregada seja da folha de pagamento*        |
    | *imediatamente superior à da última carga de forma a não causar hiato na sequência*   |
    | *dos dados.*                                                                          |
    +---------------------------------------------------------------------------------------+

    .. warning:: A data de referência da tabela a ser carregada não pode ser distante mais do que um mês da data de referência da última carga!
    """

    form = ArquivoForm()

    if form.validate_on_submit():

        folha_pag = services.salvar_arquivo_upload(form.arquivo.data)

        print ('***  ARQUIVO ***',folha_pag)
        services.cargaPDCTR(folha_pag)

        registra_log_auto(current_user.id,None,'car')

        return redirect(url_for('core.inicio'))

    data_ref = services.data_referencia_ultima_carga_pdctr()

    return render_template('grab_file.html',form=form,data_ref=data_ref.dr)

@core.route('/carregaSICONV', methods=['GET', 'POST'])
@login_required
def carregaSICONV():
    """
    +---------------------------------------------------------------------------------------+
    |Executa o procedimento de carga dos dados do SICONV.                                   |
    |                                                                                       |
    |Faz o dowload dos aquivos compactados diretamente do site do SICONV, descompacta e     |
    |carrega as respectivas tabelas do banco de dados.                                      |
    |                                                                                       |
    |Os dados anteriores são apagados e os novos inseridos nas tabelas.                     |
    |                                                                                       |
    | Para algumas tabelas, somente campos de interesse são carregados.                     |
    +---------------------------------------------------------------------------------------+
    """

    #síncrono
    thread_cargaSICONV()

    #assíncrono
    # cargaSICONV()
   
    registra_log_auto(current_user.id,None,'car - carga SICONV')

    #return render_template('index.html')
    return redirect(url_for('core.inicio'))


#
### inserir chamadas

@core.route("/<id_acordo_convenio>/criar_chamada", methods=['GET', 'POST'])
@login_required
def cria_chamada(id_acordo_convenio):
    """
    +---------------------------------------------------------------------------------------+
    |Permite registrar os dados de uma chamada e associa-la a um acordo/convenio.           |
    |                                                                                       |
    |Recebe o id do acordo/convênio.                                                        |
    +---------------------------------------------------------------------------------------+
    """

    form = ChamadaForm()

    if form.validate_on_submit():

        services.criar_chamada(
            id_acordo_convenio=id_acordo_convenio,
            sei=form.sei.data,
            chamada_nome=form.chamada.data,
            qtd_projetos=form.qtd_projetos.data,
            vl_total_chamada_str=form.vl_total_chamada.data,
            doc_sei=form.doc_sei.data,
            obs=form.obs.data,
            usuario_id=current_user.id,
        )

        flash('Chamada registrada!','sucesso')

        if str(id_acordo_convenio).isdigit():
            return redirect(url_for('acordos.update', acordo_id=int(id_acordo_convenio), lista='todos'))
        else:
            return redirect(url_for('convenios.convenio_detalhes', conv=str(id_acordo_convenio)[1:], form = SEIForm()))

    return render_template('add_chamada.html', form=form)

#
### altera dados de uma chamada

@core.route("/<int:id>/update_chamada", methods=['GET', 'POST'])
@login_required
def update_chamada(id):
    """
    +---------------------------------------------------------------------------------------+
    |Permite alterar os dados de uma chamada.                                               |
    |                                                                                       |
    |Recebe o id da chamada como parâmetro.                                                 |
    +---------------------------------------------------------------------------------------+
    """

    chamada = services.buscar_chamada(id)

    form = ChamadaForm()

    if form.validate_on_submit():

        services.atualizar_chamada(
            id=id,
            sei=form.sei.data,
            chamada_nome=form.chamada.data,
            qtd_projetos=form.qtd_projetos.data,
            vl_total_chamada_str=form.vl_total_chamada.data,
            doc_sei=form.doc_sei.data,
            obs=form.obs.data,
            usuario_id=current_user.id,
        )

        flash('Chamada homologada atualizada!','sucesso')
        return redirect(url_for('core.inicio'))
    #
    # traz a informação atual do registro SEI
    elif request.method == 'GET':
        dados = services.formata_chamada_para_edicao(chamada)
        form.sei.data              = dados['sei']
        form.chamada.data          = dados['chamada']
        form.qtd_projetos.data     = dados['qtd_projetos']
        form.vl_total_chamada.data = dados['vl_total_chamada']
        form.doc_sei.data          = dados['doc_sei']
        form.obs.data              = dados['obs']

    return render_template('add_chamada.html', form=form)

#
## carregar homologados a partir de arquivo excel
#
@core.route('/<chamada_id>/carrega_homologados', methods=['GET', 'POST'])
@login_required
def carrega_homologados(chamada_id):
    """
    +---------------------------------------------------------------------------------------+
    |Executa o procedimento de carga de homologados via planilha excel gerada pelo usuário. |
    |                                                                                       |
    |O módulo pede que seja informado o local onde a planilha está e armazena os dados em   |
    |tabela própria do banco de dados.                                                      |
    |                                                                                       |
    |Somente são gravados registros que não tenham o mesmo nome e cpf em uma mesma          |
    |chamada, visando evitar duplicação.                                                    |
    |                                                                                       |
    +---------------------------------------------------------------------------------------+
    """

    form = ArquivoForm()

    if form.validate_on_submit():

        homologados = services.salvar_arquivo_upload(form.arquivo.data)

        print ('***  ARQUIVO ***',homologados)

        services.carregar_homologados(chamada_id, homologados)

        registra_log_auto(current_user.id,None,'car')

        return redirect(url_for('core.lista_homologados', chamada_id=chamada_id))


    return render_template('grab_file.html',form=form,data_ref='homologados')


### LISTAR projetos ou bolsistas homologados

@core.route("/<int:chamada_id>/homologados")
def lista_homologados(chamada_id):
    """
    +---------------------------------------------------------------------------------------+
    |Lista os projetos ou bolsistas de uma chamada que foram homologados.                   |
    +---------------------------------------------------------------------------------------+
    """

    chamada, homologados = services.buscar_chamada_e_homologados(chamada_id)

    return render_template('lista_homologados.html', chamada_id=chamada_id,
                                                     chamada=chamada,
                                                     homologados=homologados,
                                                     qtd_homologados=len(homologados))


### inserir ou alterar projeto/bolsista homologado

@core.route("/<int:chamada_id>/<int:homologado_id>/edita_homologado", methods=['GET', 'POST'])
@login_required
def edita_homologado(chamada_id,homologado_id):
    """
    +---------------------------------------------------------------------------------------+
    |Permite inserir ou alterar um projeto ou bolsista aprovado na chamada informada e      |
    | homologado pelo CNPq.                                                                 |
    |                                                                                       |
    |Recebe id da chamada e id do homologado como parâmetros.                               |
    +---------------------------------------------------------------------------------------+
    """

    form = HomologadoForm()

    if form.validate_on_submit():

        if homologado_id == 0:
            services.criar_homologado(
                chamada_id=chamada_id, prioridade=form.prioridade.data, nota_str=form.nota.data,
                cpf=form.cpf.data, nome=form.nome.data, mod=form.mod.data, niv=form.niv.data,
                titulo=form.titulo.data, area=form.area.data, valor_str=form.valor.data,
                usuario_id=current_user.id,
            )
        else:
            services.atualizar_homologado(
                homologado_id=homologado_id, chamada_id=chamada_id, prioridade=form.prioridade.data,
                nota_str=form.nota.data, cpf=form.cpf.data, nome=form.nome.data, mod=form.mod.data,
                niv=form.niv.data, titulo=form.titulo.data, area=form.area.data, valor_str=form.valor.data,
                usuario_id=current_user.id,
            )

        flash('Projeto ou bolsista registrado!','sucesso')

        return redirect(url_for('core.lista_homologados', chamada_id=chamada_id))
    #
    # traz formulário em branco
    else:

        if homologado_id != 0:

            homologado = services.buscar_homologado(homologado_id)
            dados = services.formata_homologado_para_edicao(homologado)

            form.prioridade.data = dados['prioridade']
            form.nota.data       = dados['nota']
            form.cpf.data        = dados['cpf']
            form.nome.data       = dados['nome']
            form.mod.data        = dados['mod']
            form.niv.data        = dados['niv']
            form.titulo.data     = dados['titulo']
            form.area.data       = dados['area']
            form.valor.data      = dados['valor']

    return render_template('add_homologado.html', form=form, homologado_id=homologado_id)
#
### DELETAR projeto ou bolsista da lista de homologados de uma chamada

@core.route('/<int:chamada_id>/<int:homologado_id>/deleta_homologado',methods=['GET','POST'])
@login_required
def deleta_homologado(chamada_id,homologado_id):
    """
    +---------------------------------------------------------------------------------------+
    |Deleta um registro da lista de homologados de uma chamada.                             |
    |                                                                                       |
    |Recebe o id da chamada e id do homologado como parâmetros.                             |
    +---------------------------------------------------------------------------------------+
    """
    services.excluir_homologado(homologado_id, current_user.id)

    flash ('Homologado deletado!','sucesso')

    return redirect(url_for('core.lista_homologados', chamada_id=chamada_id))

#
# função que executa carga de mensagens do SICONV
@core.route('/carregaMSG', methods=['GET', 'POST'])
@login_required
def carregaMSG():
    """
    +---------------------------------------------------------------------------------------+
    |Executa o procedimento de carga das mensagens emitidas pelo SICONV que indicam situa-  |
    |ções a verifica.                                                                       |
    |                                                                                       |
    |O módulo pede que seja informado o local onde a planilha de mensagens salva e armazena |
    |os em tabela própria do banco de dados.                                                |
    |                                                                                       |
    |Em cada carga, os dados anteriores são excluidos.                                      |
    +---------------------------------------------------------------------------------------+

    .. warning:: A data de referência é a data do dia da carga e não a data de criação da planilha de entrada!
    """
    #
    form = ArquivoForm()

    if form.validate_on_submit():

        msg_siconv = services.salvar_arquivo_upload(form.arquivo.data)

        print ('***  ARQUIVO ***',msg_siconv)

        services.carregar_mensagens_siconv(msg_siconv)

        registra_log_auto(current_user.id,None,'msg')

        return redirect(url_for('core.inicio'))

    data_ref = ''

    return render_template('grab_file.html',form=form,data_ref=data_ref)



