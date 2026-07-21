"""
.. topic:: Demandas (services) — Base / Plano de trabalho

    Camada de regra de negócio do módulo de demandas. Este módulo é
    especial: `registra_log_auto` é usada por praticamente todo o
    sistema (users, convenios, core, acordos, instrumentos, bolsas).

    Nota técnica: para não obrigar a atualização de 7+ arquivos que já
    fazem `from project.demandas.views import registra_log_auto`, a
    implementação foi movida para cá, e `project/demandas/views.py`
    mantém um re-export (`from project.demandas.services import
    registra_log_auto`) — todos os imports existentes continuam
    funcionando sem alteração.
"""

from threading import Thread
from datetime import datetime

from flask import render_template, abort
from flask_mail import Message
from sqlalchemy import or_, func

import os
import sys
import pickle
from datetime import date, timedelta
from calendar import monthrange

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from fpdf import FPDF

from project import db, mail, app
from sqlalchemy import cast, String
from sqlalchemy.sql import label

from project.models import (
    Log_Auto, Plano_Trabalho, Ativ_Usu, User, Coords, Tipos_Demanda,
    Passos_Tipos, Demanda, Providencia, Despacho, Sistema, DadosSEI,
    Msgs_Recebidas, Acordo, grupo_programa_cnpq, Proposta, Convenio,
)


# =============================================================================
# Base: e-mail e log automático (usados em todo o sistema)
# =============================================================================

def send_async_email(msg):
    """Executa o envio de e-mails de forma assíncrona."""
    with app.app_context():
        mail.send(msg)


def send_email(subject, recipients, text_body, html_body):
    """Envia e-mails em uma thread separada."""
    msg = Message(subject, recipients=recipients)
    msg.body = text_body
    msg.html = html_body
    thr = Thread(target=send_async_email, args=[msg])
    thr.start()


def registra_log_auto(user_id, demanda_id, tipo_registro, atividade=None, duracao=0):
    """
    +---------------------------------------------------------------------------------------+
    |Função que registra ação do usuário na tabela log_auto.                                |
    |INPUT: id usúario, id demanda, tipo de registro                                        |
    |Os tipos de registro estão na tabela log_desc.                                         |
    +---------------------------------------------------------------------------------------+
    """
    # user_id=None sempre quebrava com NotNullViolation (a coluna
    # log_auto.user_id não aceita nulo). Isso acontecia em vários
    # pontos do sistema (agendamentos numa instalação nova, sem nenhum
    # log anterior para identificar o usuário responsável). Pular o
    # registro nesse caso é estritamente mais seguro do que quebrar.
    if user_id is None:
        return

    reg_log = Log_Auto(data_hora=datetime.now(), user_id=user_id, demanda_id=demanda_id,
                       tipo_registro=tipo_registro, atividade=atividade, duracao=duracao)
    db.session.add(reg_log)
    db.session.commit()

    return


# =============================================================================
# Plano de trabalho
# =============================================================================

def _unidades_hierarquia(unidade):
    """Retorna a lista de coordenações a considerar (a própria unidade + filhas, se houver)."""
    hierarquia = db.session.query(Coords.sigla).filter(Coords.pai == unidade).all()

    if hierarquia:
        l_unid = [f.sigla for f in hierarquia]
        l_unid.append(unidade)
        return l_unid

    return [unidade]


def unidades_choices(unidade):
    """Retorna a lista de coordenações (unidade + filhas) formatada para um SelectField."""
    l_unid = _unidades_hierarquia(unidade)
    lista_unids = [(u, u) for u in l_unid]
    lista_unids.insert(0, ('', ''))
    return lista_unids


def listar_plano_trabalho(unidade):
    """Retorna as atividades do plano de trabalho da unidade do usuário (e suas filhas, se houver)."""
    l_unid = _unidades_hierarquia(unidade)

    user_titular = db.session.query(Ativ_Usu.atividade_id, User.username)\
                             .join(User, User.id == Ativ_Usu.user_id)\
                             .filter(Ativ_Usu.nivel == 'Titular')\
                             .subquery()

    user_suplente = db.session.query(Ativ_Usu.atividade_id, User.username)\
                              .join(User, User.id == Ativ_Usu.user_id)\
                              .filter(Ativ_Usu.nivel == 'Suplente')\
                              .subquery()

    atividades = db.session.query(Plano_Trabalho.id, Plano_Trabalho.atividade_sigla,
                                  Plano_Trabalho.atividade_desc, Plano_Trabalho.natureza,
                                  Plano_Trabalho.meta,
                                  user_titular.c.username.label('titular'),
                                  user_suplente.c.username.label('suplente'),
                                  Plano_Trabalho.situa, Plano_Trabalho.unidade)\
                           .outerjoin(user_titular, Plano_Trabalho.id == user_titular.c.atividade_id)\
                           .outerjoin(user_suplente, Plano_Trabalho.id == user_suplente.c.atividade_id)\
                           .filter(Plano_Trabalho.unidade.in_(l_unid))\
                           .order_by(Plano_Trabalho.atividade_sigla)\
                           .all()

    return atividades


def buscar_atividade(id):
    """Busca uma atividade do plano de trabalho pelo ID, ou levanta 404 se não existir."""
    return Plano_Trabalho.query.get_or_404(id)


def atualizar_atividade(id, atividade_sigla, atividade_desc, natureza, meta, situa, unidade, usuario_id):
    """Atualiza os dados de uma atividade do plano de trabalho existente."""
    atividade = buscar_atividade(id)

    atividade.atividade_sigla = atividade_sigla
    atividade.atividade_desc = atividade_desc
    atividade.natureza = natureza
    atividade.meta = meta
    atividade.situa = situa
    atividade.unidade = unidade

    db.session.commit()

    registra_log_auto(usuario_id, None, 'ipt')

    return atividade


def criar_atividade(atividade_sigla, atividade_desc, natureza, meta, situa, unidade, usuario_id):
    """Registra uma nova atividade no plano de trabalho."""
    atividade = Plano_Trabalho(
        atividade_sigla=atividade_sigla, atividade_desc=atividade_desc,
        natureza=natureza, meta=meta, situa=situa, unidade=unidade,
    )

    db.session.add(atividade)
    db.session.commit()

    registra_log_auto(usuario_id, None, 'ipt')

    return atividade


def excluir_atividade(atividade_id, usuario_id):
    """Remove uma atividade do plano de trabalho."""
    atividade = buscar_atividade(atividade_id)

    db.session.delete(atividade)
    db.session.commit()

    registra_log_auto(usuario_id, None, 'xpt')


# =============================================================================
# Tipos de demanda / passos
# =============================================================================

def listar_tipos_demanda(unidade, relevancia_choices):
    """
    Retorna os tipos de demanda da unidade do usuário (e suas filhas,
    se houver), já formatados com a descrição textual da relevância,
    quantidade de passos e quantidade de demandas associadas.
    """
    l_unid = _unidades_hierarquia(unidade)

    tipos = db.session.query(Tipos_Demanda.id, Tipos_Demanda.tipo,
                             Tipos_Demanda.relevancia, Tipos_Demanda.unidade)\
                      .filter(Tipos_Demanda.unidade.in_(l_unid))\
                      .order_by(Tipos_Demanda.tipo).all()

    tipos_s = []
    for tipo in tipos:
        qtd_passos = db.session.query(func.count(Passos_Tipos.tipo_id))\
                               .filter(Passos_Tipos.tipo_id == tipo.id).all()
        demandas_qtd = db.session.query(Demanda.id).filter(Demanda.tipo == tipo.tipo).count()

        tipo_s = list(tipo)
        tipo_s.append(dict(relevancia_choices)[str(tipo.relevancia)])
        tipo_s.append(qtd_passos[0][0])
        tipo_s.append(demandas_qtd)

        tipos_s.append(tipo_s)

    return tipos_s


def gerar_pdf_procedimentos(tipos_s):
    """
    Gera o PDF com a lista de todos os procedimentos (tipos de demanda
    e respectivos passos) em project/static/procedimentos.pdf (caminho
    portável, funciona fora do container Docker).
    """
    class PDF_procedimentos(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 10)
            self.set_text_color(127, 127, 127)
            self.cell(0, 10, 'Lista de procedimentos (Tipos de Demanda e respectivos Passos) - gerado em ' + date.today().strftime('%d/%m/%Y'), 1, 1, 'C')

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.set_text_color(127, 127, 127)
            self.cell(0, 10, 'Página ' + str(self.page_no()) + '/{nb}', 0, 0, 'C')

    pdf = PDF_procedimentos()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_font('Times', '', 12)

    for tipo in tipos_s:

        passos = db.session.query(Passos_Tipos.ordem, Passos_Tipos.passo, Passos_Tipos.desc)\
                            .filter(Passos_Tipos.tipo_id == tipo[0])\
                            .order_by(Passos_Tipos.ordem)\
                            .all()
        qtd = len(passos)

        pdf.set_text_color(0, 0, 0)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 10, tipo[1] + ' (' + str(qtd) + ' passos)' + '    Relevância: ' + tipo[4], 0, 0)
        pdf.ln(10)

        if qtd == 0:
            pdf.set_font('Times', '', 10)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(20, 10, 'Não há passos definidos.', 0, 0)
            pdf.ln(15)
        else:
            for passo in passos:
                pdf.set_font('Times', '', 10)
                pdf.set_text_color(0, 0, 0)
                pdf.cell(20, 10, str(passo.ordem) + 'º passo:', 0, 0)

                pdf.set_text_color(0, 0, 0)
                pdf.cell(0, 10, passo.passo, 0, 1)

                texto = passo.desc.encode('latin-1', 'replace').decode('latin-1')
                tamanho_texto = pdf.get_string_width(texto)
                pdf.multi_cell(0, 5, texto)
                if tamanho_texto <= 100:
                    pdf.ln(15)
                else:
                    pdf.ln(tamanho_texto / 20)

        pdf.ln(5)
        pdf.dashed_line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y(), 2, 3)

    # Caminho portável (funciona em qualquer ambiente, não só no container Docker)
    pasta_pdf = os.path.join(app.root_path, 'static', 'procedimentos.pdf')
    pdf.output(pasta_pdf)


def buscar_tipo(id):
    """Busca um tipo de demanda pelo ID, ou levanta 404 se não existir."""
    return Tipos_Demanda.query.get_or_404(id)


def excluir_tipo_demanda(id, usuario_id):
    """
    Remove um tipo de demanda, se não houver nenhuma demanda associada
    a ele. Retorna uma tupla (status, tipo), onde status é 'excluido'
    ou 'em_uso'.
    """
    tipo = buscar_tipo(id)

    demandas_qtd = db.session.query(Demanda.id).filter(Demanda.tipo == tipo.tipo).count()

    if demandas_qtd == 0:
        db.session.delete(tipo)
        db.session.commit()

        registra_log_auto(usuario_id, None, 'det')

        return 'excluido', tipo, 0

    return 'em_uso', tipo, demandas_qtd


def atualizar_tipo_demanda(id, tipo_novo, relevancia, unidade, usuario_id):
    """
    Atualiza um tipo de demanda e propaga o novo nome para todas as
    demandas que usavam o nome anterior.
    """
    tipo = buscar_tipo(id)
    tipo_ant = tipo.tipo

    tipo.tipo = tipo_novo
    tipo.relevancia = relevancia
    tipo.unidade = unidade

    db.session.commit()

    if tipo_novo != tipo_ant:
        demandas_alterar_tipo = db.session.query(Demanda).filter(Demanda.tipo == tipo_ant).all()
        for demanda in demandas_alterar_tipo:
            demanda.tipo = tipo_novo
        db.session.commit()

    registra_log_auto(usuario_id, None, 'iat')

    return tipo


def criar_tipo_demanda(tipo, relevancia, unidade, usuario_id):
    """Registra um novo tipo de demanda."""
    novo_tipo = Tipos_Demanda(tipo=tipo, relevancia=relevancia, unidade=unidade)

    db.session.add(novo_tipo)
    db.session.commit()

    registra_log_auto(usuario_id, None, 'iat')

    return novo_tipo


def nome_do_tipo(tipo_id):
    """Retorna o nome (texto) de um tipo de demanda a partir do seu ID."""
    return db.session.query(Tipos_Demanda.tipo).filter(Tipos_Demanda.id == tipo_id).first()


def criar_passo_tipo(tipo_id, ordem, passo, desc, usuario_id):
    """
    Registra um novo passo para um tipo de demanda, reordenando os
    passos existentes se o novo passo for inserido no meio da lista.
    """
    passos_qtd = db.session.query(Passos_Tipos.id).filter(Passos_Tipos.tipo_id == tipo_id).count()

    if ordem <= passos_qtd:
        re_order = list(range(ordem, passos_qtd + 1))
        re_order.reverse()

        for o in re_order:
            passo_existente = db.session.query(Passos_Tipos)\
                                        .filter(Passos_Tipos.tipo_id == tipo_id, Passos_Tipos.ordem == o).first()
            passo_existente.ordem = o + 1
            db.session.commit()

    passo_reg = Passos_Tipos(tipo_id=tipo_id, ordem=ordem, passo=passo, desc=desc)
    db.session.add(passo_reg)
    db.session.commit()

    registra_log_auto(usuario_id, None, 'ips')

    return passo_reg


def buscar_passo(id):
    """Busca um passo de tipo de demanda pelo ID, ou levanta 404 se não existir."""
    return Passos_Tipos.query.get_or_404(id)


def atualizar_passo_tipo(id, ordem, passo_novo, desc, usuario_id):
    """
    Atualiza um passo de tipo de demanda, propagando o novo texto do
    passo para providências e despachos que referenciavam o texto
    anterior.
    """
    passo = buscar_passo(id)
    passo_ant = passo.passo

    passo.ordem = ordem
    passo.passo = passo_novo
    passo.desc = desc

    db.session.commit()

    if passo_novo != passo_ant:
        providencias_alterar_passo = db.session.query(Providencia).filter(Providencia.passo == passo_ant).all()
        despachos_alterar_passo = db.session.query(Despacho).filter(Despacho.passo == passo_ant).all()
        for prov in providencias_alterar_passo:
            prov.passo = passo_novo
        for desp in despachos_alterar_passo:
            desp.passo = passo_novo
        db.session.commit()

    registra_log_auto(usuario_id, None, 'aps')

    return passo


def listar_passos_tipo(tipo_id):
    """
    Retorna o nome do tipo e seus passos, ordenados. Renumera os
    passos automaticamente se alguma desordem for encontrada (a
    numeração deveria ser sempre sequencial 1..N).
    """
    tipo = nome_do_tipo(tipo_id)

    passos = db.session.query(Passos_Tipos.id, Passos_Tipos.ordem,
                              Passos_Tipos.passo, Passos_Tipos.desc)\
                       .filter(Passos_Tipos.tipo_id == tipo_id)\
                       .order_by(Passos_Tipos.ordem).all()

    quantidade = len(passos)

    if quantidade > 1 and quantidade != passos[-1].ordem:
        for index, passo in enumerate(passos):
            step = Passos_Tipos.query.get_or_404(passo.id)
            step.ordem = index + 1
            db.session.commit()

        passos = db.session.query(Passos_Tipos.id, Passos_Tipos.ordem,
                                  Passos_Tipos.passo, Passos_Tipos.desc)\
                           .filter(Passos_Tipos.tipo_id == tipo_id)\
                           .order_by(Passos_Tipos.ordem).all()

    return tipo, passos, quantidade


# =============================================================================
# Criação de demanda
# =============================================================================

def tipos_choices(unidade):
    """Retorna a lista de tipos de demanda da unidade (e filhas), formatada para um SelectField."""
    l_unid = _unidades_hierarquia(unidade)

    tipos = db.session.query(Tipos_Demanda.tipo)\
                      .filter(Tipos_Demanda.unidade.in_(l_unid))\
                      .order_by(Tipos_Demanda.tipo)\
                      .all()

    lista_tipos = [(t.tipo, t.tipo) for t in tipos]
    lista_tipos.insert(0, ('', ''))
    return lista_tipos


def atividades_choices(unidade):
    """Retorna a lista de atividades do plano de trabalho da unidade (e filhas), formatada para um SelectField."""
    l_unid = _unidades_hierarquia(unidade)

    atividades = db.session.query(Plano_Trabalho.id, Plano_Trabalho.atividade_sigla)\
                           .filter(Plano_Trabalho.unidade.in_(l_unid))\
                           .order_by(Plano_Trabalho.atividade_sigla).all()

    lista_atividades = [(str(a.id), a.atividade_sigla) for a in atividades]
    lista_atividades.insert(0, ('', ''))
    return lista_atividades


def verificar_demanda_duplicada(sei, tipo):
    """
    Verifica se já existe uma demanda não concluída para o mesmo SEI e
    tipo. Retorna 'OK' se não houver, ou 'KO<id>' com o ID da demanda
    existente.
    """
    verif_demanda = db.session.query(Demanda)\
                              .filter(Demanda.sei == sei, Demanda.tipo == tipo, Demanda.conclu == '0')\
                              .first()

    if verif_demanda is None:
        return 'OK'
    return 'KO' + str(verif_demanda.id)


def formata_sei_para_url(sei):
    """Converte um SEI no formato 'NNNNN.NNNNNN/AAAA-DD' para o formato de URL 'NNNNN.NNNNNN_AAAA-DD'."""
    if '/' in str(sei):
        return str(sei).split('/')[0] + '_' + str(sei).split('/')[1]
    return str(sei)


def formata_sei_de_url(sei_url):
    """Converte um SEI do formato de URL de volta para o formato normal."""
    return str(sei_url).split('_')[0] + '/' + str(sei_url).split('_')[1]


def dados_funcionalidade_sistema():
    """Retorna as flags de funcionalidade de convênio/acordo do sistema."""
    return db.session.query(Sistema.funcionalidade_conv, Sistema.funcionalidade_acordo).first()


def atividade_id_por_programa(prog):
    """
    Busca o ID da atividade do plano de trabalho pela sigla informada
    (prog). Se não encontrar, usa a atividade 'Diversos' como fallback.
    """
    atividade = db.session.query(Plano_Trabalho.id).filter(Plano_Trabalho.atividade_sigla == prog).first()

    if atividade is None:
        atividade = db.session.query(Plano_Trabalho.id).filter(Plano_Trabalho.atividade_sigla == "Diversos").first()

    return atividade


def _notificar_demanda_concluida(demanda, titulo, atividade_id, usuario):
    """Notifica os chefes da coordenação de que uma demanda foi criada já concluída."""
    chefes_emails = db.session.query(User.email)\
                              .filter(or_(User.despacha == 1, User.despacha0 == 1),
                                      User.coord == usuario.coord)

    destino = [e[0] for e in chefes_emails]
    destino.append(usuario.email)

    if len(destino) > 1:
        sistema = db.session.query(Sistema.nome_sistema).first()

        html = render_template('email_demanda_conclu.html', demanda=demanda.id, user=usuario.username,
                                titulo=titulo, sistema=sistema.nome_sistema)

        pt = db.session.query(Plano_Trabalho.atividade_sigla).filter(Plano_Trabalho.id == atividade_id).first()

        send_email('Demanda ' + str(demanda.id) + ' foi concluída (' + pt.atividade_sigla + ')', destino, '', html)

        msg = Msgs_Recebidas(user_id=demanda.user_id, data_hora=datetime.now(),
                             demanda_id=demanda.id, msg='A demanda foi concluída!')
        db.session.add(msg)
        db.session.commit()


def _notificar_necessita_despacho(demanda, titulo, atividade_id, usuario):
    """Notifica os chefes da coordenação de que uma demanda requer despacho."""
    chefes_emails = db.session.query(User.email, User.id)\
                              .filter(or_(User.despacha == 1, User.despacha0 == 1),
                                      User.coord == usuario.coord).all()

    destino = [e[0] for e in chefes_emails]
    destino.append(usuario.email)

    if len(destino) > 1:
        sistema = db.session.query(Sistema.nome_sistema).first()

        html = render_template('email_pede_despacho.html', demanda=demanda.id, user=usuario.username,
                                titulo=titulo, sistema=sistema.nome_sistema)

        pt = db.session.query(Plano_Trabalho.atividade_sigla).filter(Plano_Trabalho.id == atividade_id).first()

        send_email('Demanda ' + str(demanda.id) + ' requer despacho (' + pt.atividade_sigla + ')', destino, '', html)

        for chefe in chefes_emails:
            msg = Msgs_Recebidas(user_id=chefe.id, data_hora=datetime.now(),
                                 demanda_id=demanda.id, msg='Chefia, a demanda está pedindo um despacho!')
            db.session.add(msg)

            msg = Msgs_Recebidas(user_id=usuario.id, data_hora=datetime.now(), demanda_id=demanda.id,
                                 msg='Você marcou a opção -Necessita despacho?- na demanda!')
            db.session.add(msg)

        db.session.commit()


def criar_demanda_via_sei(sei_url, tipo, atividade_id, titulo, desc, necessita_despacho,
                           conclu, urgencia, convenio_data, usuario):
    """
    Cria uma demanda a partir do fluxo de registro livre por SEI.
    Cria também o registro de DadosSEI se um convênio for informado e
    ainda não existir uma associação SEI<->convênio.
    """
    sei = formata_sei_de_url(sei_url)

    if convenio_data:
        verif_sei = db.session.query(DadosSEI).filter(DadosSEI.nr_convenio == str(convenio_data)).first()
        if verif_sei is None:
            dadosSEI = DadosSEI(nr_convenio=str(convenio_data), sei=sei, epe='*', fiscal='')
            db.session.add(dadosSEI)
            db.session.commit()
            registra_log_auto(usuario.id, None, 'sei')

    data_conclu = None
    data_env_despacho = None

    if conclu != '0':
        necessita_despacho = False
        data_conclu = datetime.now()

    if not convenio_data:
        tem_conv = db.session.query(DadosSEI.nr_convenio).filter(DadosSEI.sei == sei).first()
        conv = tem_conv.nr_convenio if tem_conv else ''
    else:
        conv = convenio_data

    desp = 1 if necessita_despacho else 0
    if desp == 1:
        data_env_despacho = datetime.now()

    demanda = Demanda(
        programa=atividade_id, sei=sei, convênio=conv, ano_convênio=None, tipo=tipo,
        data=datetime.now(), user_id=usuario.id, titulo=titulo, desc=desc,
        necessita_despacho=desp, necessita_despacho_cg=0, conclu=conclu,
        data_conclu=data_conclu, urgencia=urgencia, data_env_despacho=data_env_despacho,
        nota=None, data_verific=None,
    )

    db.session.add(demanda)
    db.session.commit()

    registra_log_auto(usuario.id, demanda.id, 'inc')

    if conclu != '0':
        _notificar_demanda_concluida(demanda, titulo, atividade_id, usuario)

    if desp == 1:
        _notificar_necessita_despacho(demanda, titulo, atividade_id, usuario)

    return demanda


def criar_demanda_de_acordo_convenio(sei_url, tipo, atividade_id, conv_param, titulo, desc,
                                       necessita_despacho, conclu, urgencia, convenio_data, usuario):
    """
    Cria uma demanda a partir do fluxo de registro vinculado a um
    acordo ou convênio.
    """
    sei = formata_sei_de_url(sei_url)

    data_conclu = None
    data_env_despacho = None
    conv = conv_param

    if conclu != '0':
        necessita_despacho = False
        data_conclu = datetime.now()
        conv = convenio_data if convenio_data else ''

    desp = 1 if necessita_despacho else 0
    if desp == 1:
        data_env_despacho = datetime.now()

    demanda = Demanda(
        programa=atividade_id, sei=sei, convênio=conv, ano_convênio=None, tipo=tipo,
        data=datetime.now(), user_id=usuario.id, titulo=titulo, desc=desc,
        necessita_despacho=desp, necessita_despacho_cg=0, conclu=conclu,
        data_conclu=data_conclu, urgencia=urgencia, data_env_despacho=data_env_despacho,
        nota=None, data_verific=None,
    )

    db.session.add(demanda)
    db.session.commit()

    registra_log_auto(usuario.id, demanda.id, 'inc')

    if conclu != '0':
        _notificar_demanda_concluida(demanda, titulo, atividade_id, usuario)

    if desp == 1:
        _notificar_necessita_despacho(demanda, titulo, atividade_id, usuario)

    return demanda


# =============================================================================
# Demanda (núcleo)
# =============================================================================

def buscar_dados_demanda(demanda_id):
    """
    Retorna os dados completos de uma demanda (com atividade, coordenação
    e nome do responsável), ou None se não existir. Corrige bug real: o
    código original não checava se a consulta retornou algo antes de
    acessar seus atributos (`.data_conclu`, etc.), quebrando com
    AttributeError para qualquer ID de demanda inexistente.
    """
    return db.session.query(Demanda.id, Demanda.programa, Demanda.sei, Demanda.convênio,
                            Demanda.ano_convênio, Demanda.tipo, Demanda.data, Demanda.user_id,
                            Demanda.titulo, Demanda.desc, Demanda.necessita_despacho,
                            Demanda.conclu, Demanda.data_conclu, Demanda.necessita_despacho_cg,
                            Demanda.urgencia, Demanda.data_env_despacho, Demanda.nota,
                            Plano_Trabalho.atividade_sigla, User.coord, User.username,
                            Demanda.data_verific)\
                     .filter(Demanda.id == demanda_id)\
                     .outerjoin(Plano_Trabalho, Plano_Trabalho.id == Demanda.programa)\
                     .outerjoin(User, User.id == Demanda.user_id)\
                     .first()


def providencias_e_despachos(demanda_id):
    """Retorna as providências e despachos de uma demanda, combinados e ordenados por data (mais recentes primeiro)."""
    providencias = db.session.query(Providencia.demanda_id, Providencia.texto, Providencia.data,
                                    Providencia.user_id, User.username.label('username'),
                                    User.despacha, User.despacha2, Providencia.programada,
                                    Providencia.passo, Providencia.duracao)\
                             .outerjoin(User, Providencia.user_id == User.id)\
                             .filter(Providencia.demanda_id == demanda_id)\
                             .order_by(Providencia.data.desc()).all()

    despachos = db.session.query(Despacho.demanda_id, Despacho.texto, Despacho.data,
                                 Despacho.user_id, (User.username + ' - DESPACHO').label('username'),
                                 User.despacha, User.despacha2, User.despacha0, Despacho.passo)\
                          .filter_by(demanda_id=demanda_id)\
                          .outerjoin(User, Despacho.user_id == User.id)\
                          .order_by(Despacho.data.desc()).all()

    pro_des = providencias + despachos
    pro_des.sort(key=lambda ordem: ordem.data, reverse=True)

    return pro_des


def acordo_relacionado(sei):
    """Retorna o acordo relacionado a um SEI de demanda, se houver."""
    return db.session.query(Acordo.id, Acordo.uf, grupo_programa_cnpq.cod_programa)\
                     .join(grupo_programa_cnpq, grupo_programa_cnpq.id_acordo == Acordo.id)\
                     .filter(Acordo.sei == sei)\
                     .first()


def tipo_id_da_demanda(tipo):
    """Retorna o ID de um tipo de demanda a partir do nome do tipo."""
    return db.session.query(Tipos_Demanda.id).filter(Tipos_Demanda.tipo == tipo).first()


def gerar_pdf_demanda(demanda, pro_des):
    """
    Gera o PDF com o histórico completo de uma demanda (providências e
    despachos) em project/static/demanda.pdf (caminho portável).
    """
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 13)
            self.set_text_color(127, 127, 127)
            self.cell(0, 10, 'Relatório de Demanda - gerado em ' + date.today().strftime('%d/%m/%Y'), 1, 1, 'C')

            if demanda.atividade_sigla is None:
                self.set_text_color(127, 127, 127)
                self.cell(25, 8, 'Demanda: ', 0, 0)
                self.set_text_color(0, 0, 0)
                self.cell(35, 8, str(demanda.id) + ' (' + demanda.coord + ')', 0, 0, 'C')
                self.set_text_color(0, 0, 0)
                self.cell(0, 8, ' Atividade não definida', 0, 1)
            else:
                self.set_text_color(127, 127, 127)
                self.cell(25, 8, 'Demanda: ', 0, 0)
                self.set_text_color(0, 0, 0)
                self.cell(35, 8, str(demanda.id) + ' (' + demanda.coord + ')', 0, 0, 'C')
                self.set_text_color(127, 127, 127)
                self.cell(25, 8, ' Atividade: ', 0, 0)
                self.set_text_color(0, 0, 0)
                self.cell(0, 8, demanda.atividade_sigla, 0, 1)

            self.set_text_color(127, 127, 127)
            self.cell(18, 6, 'Título: ', 0, 0)
            self.set_text_color(0, 0, 0)
            titulo = demanda.titulo.encode('latin-1', 'replace').decode('latin-1')
            tamanho_titulo = self.get_string_width(titulo)
            self.multi_cell(0, 6, titulo)
            if tamanho_titulo <= 100:
                pdf.ln(12)
            else:
                pdf.ln(tamanho_titulo / 10)

            self.set_text_color(127, 127, 127)
            self.cell(12, 8, 'Tipo: ', 0, 0)
            self.set_text_color(0, 0, 0)
            self.cell(90, 8, demanda.tipo, 0, 0)
            self.set_text_color(127, 127, 127)
            self.cell(12, 8, 'SEI: ', 0, 0)
            self.set_text_color(0, 0, 0)
            self.cell(0, 8, demanda.sei, 0, 1)

            self.set_text_color(127, 127, 127)
            self.cell(16, 8, 'Resp.: ', 0, 0)
            self.set_text_color(0, 0, 0)
            self.cell(0, 8, demanda.username, 0, 1)

            if demanda.conclu:
                self.set_text_color(127, 127, 127)
                self.cell(25, 8, 'Criada em: ', 0, 0)
                self.set_text_color(0, 0, 0)
                self.cell(30, 8, demanda.data.strftime('%d/%m/%Y'), 0, 0)
                self.set_text_color(127, 127, 127)
                self.cell(33, 8, 'Finalizada em: ', 0, 0)
                self.set_text_color(0, 0, 0)
                x = lambda x: 'N.I.' if x is None else x.strftime('%d/%m/%Y')
                self.cell(0, 8, x(demanda.data_conclu), 0, 1)
            else:
                self.set_text_color(127, 127, 127)
                self.cell(25, 8, 'Criada em: ', 0, 0)
                self.set_text_color(0, 0, 0)
                self.cell(30, 8, demanda.data.strftime('%d/%m/%Y'), 0, 0)
                self.cell(0, 8, 'Não concluída', 0, 1)

            self.set_text_color(127, 127, 127)
            self.cell(27, 6, 'Descrição: ', 0, 0)
            self.set_text_color(0, 0, 0)
            desc = demanda.desc.encode('latin-1', 'replace').decode('latin-1')
            tamanho_desc = self.get_string_width(desc)
            self.multi_cell(0, 6, desc)
            if tamanho_desc <= 100:
                pdf.ln(6)
            else:
                pdf.ln(tamanho_desc / 12)

            if demanda.necessita_despacho == 1:
                self.cell(0, 10, 'Aguarda despacho', 0, 1)
            if demanda.necessita_despacho_cg == 1:
                self.cell(0, 10, 'Aguarda despacho Coord. Geral ou sup.', 0, 1)

            self.ln(10)
            self.set_text_color(127, 127, 127)
            self.cell(0, 10, 'Providências e Despachos', 1, 1, 'C')

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.set_text_color(127, 127, 127)
            self.cell(0, 10, 'Página ' + str(self.page_no()) + '/{nb}', 0, 0, 'C')

    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_font('Times', '', 12)

    for item in pro_des:
        pdf.set_text_color(0, 0, 0)
        pdf.cell(50, 10, item.username, 0, 0)
        pdf.set_text_color(127, 127, 127)
        pdf.cell(8, 10, 'Em: ', 0, 0)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 10, item.data.strftime('%d/%m/%Y'), 0, 1)
        texto = item.texto.encode('latin-1', 'replace').decode('latin-1')
        tamanho_texto = pdf.get_string_width(texto)
        pdf.multi_cell(0, 5, texto)
        if tamanho_texto <= 100:
            pdf.ln(15)
        else:
            pdf.ln(tamanho_texto / 10)
        pdf.dashed_line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y(), 2, 3)

    # Caminho portável (funciona em qualquer ambiente, não só no container Docker)
    pasta_pdf = os.path.join(app.root_path, 'static', 'demanda.pdf')
    pdf.output(pasta_pdf)


def marcar_verificacao(demanda_id):
    """Registra a data de verificação de uma demanda."""
    demanda = Demanda.query.get_or_404(demanda_id)
    demanda.data_verific = datetime.today()
    db.session.commit()
    return demanda


def atualizar_demanda(demanda_id, atividade, sei, convenio_data, ano_convenio_data, tipo,
                       titulo, desc, tipo_despacho, conclu, urgencia, usuario):
    """
    Atualiza os dados de uma demanda, incluindo a lógica de mudança de
    tipo de despacho e de conclusão (que disparam notificações por
    e-mail quando aplicável).

    Corrige bug real: o código original gravava `demanda.ano_convênio
    = ''` quando o campo de convênio era deixado em branco — a coluna
    é Integer, então isso quebrava com DataError ao salvar.
    """
    demanda = Demanda.query.get_or_404(demanda_id)

    demanda.programa = atividade
    demanda.sei = sei

    if convenio_data == '' or convenio_data is None:
        demanda.convênio = ''
        demanda.ano_convênio = None
    else:
        demanda.convênio = convenio_data
        demanda.ano_convênio = ano_convenio_data

    demanda.tipo = tipo
    demanda.titulo = titulo
    demanda.desc = desc

    if tipo_despacho == '0':
        demanda.necessita_despacho_cg = 0

    if tipo_despacho == '2':
        demanda.necessita_despacho_cg = 1

    if tipo_despacho == '1':

        if demanda.necessita_despacho == 0:
            _notificar_necessita_despacho(demanda, titulo, atividade, usuario)

            demanda.necessita_despacho = 1
            demanda.data_env_despacho = datetime.now()

        demanda.necessita_despacho_cg = 0

    else:
        demanda.necessita_despacho = 0

    if conclu != '0':

        demanda.necessita_despacho = 0
        demanda.necessita_despacho_cg = 0

        if demanda.conclu == '0':
            demanda.data_conclu = datetime.now()
            _notificar_demanda_concluida(demanda, titulo, atividade, usuario)

    else:
        demanda.data_conclu = None

    demanda.conclu = conclu
    demanda.urgencia = urgencia

    db.session.commit()

    registra_log_auto(usuario.id, demanda_id, 'alt')

    return demanda


def transferir_demanda(demanda_id, pessoa_id, usuario):
    """Transfere uma demanda para outra pessoa, registrando uma providência e notificando por e-mail."""
    demanda = Demanda.query.get_or_404(demanda_id)

    demanda.user_id = int(pessoa_id)
    db.session.commit()

    registra_log_auto(usuario.id, demanda_id, 'tra')

    recebedor = db.session.query(User.username, User.email).filter(User.id == int(pessoa_id)).first()

    providencia = Providencia(
        demanda_id=demanda_id, data=datetime.now(),
        texto='DEMANDA TRANSFERIDA para ' + recebedor.username + '!    ',
        user_id=usuario.id, duracao=5, programada=0, passo='',
    )
    db.session.add(providencia)
    db.session.commit()

    sistema = db.session.query(Sistema.nome_sistema).first()

    destino = [recebedor.email, usuario.email]

    html = render_template('email_demanda_transf.html', demanda=demanda_id, user=usuario.username,
                            titulo=demanda.titulo, receb=recebedor.username, sistema=sistema.nome_sistema)

    send_email('A demanda ' + str(demanda_id) + ' foi transferida para você!', destino, '', html)

    msg = Msgs_Recebidas(user_id=demanda.user_id, data_hora=datetime.now(), demanda_id=demanda_id,
                         msg='A demanda foi transferida para você!')
    db.session.add(msg)
    db.session.commit()

    return demanda


def avocar_demanda_service(demanda_id, usuario):
    """Avoca (assume para si) uma demanda de outra pessoa, registrando uma providência."""
    demanda = Demanda.query.get_or_404(demanda_id)

    providencia = Providencia(
        demanda_id=demanda_id, data=datetime.now(),
        texto='DEMANDA AVOCADA! Resp. anterior: ' + demanda.author.username + '.',
        user_id=usuario.id, duracao=5, programada=0, passo='',
    )
    db.session.add(providencia)
    db.session.commit()

    demanda.user_id = usuario.id
    db.session.commit()

    registra_log_auto(usuario.id, demanda_id, 'avo')

    return demanda


def alterar_data_conclusao(demanda_id, nova_data, usuario_id):
    """Permite que o admin altere manualmente a data de conclusão de uma demanda."""
    demanda = Demanda.query.get_or_404(demanda_id)

    demanda.data_conclu = nova_data
    db.session.commit()

    registra_log_auto(usuario_id, demanda_id, 'dat')

    return demanda


def excluir_demanda(demanda_id, usuario_id):
    """Remove uma demanda."""
    demanda = Demanda.query.get_or_404(demanda_id)

    db.session.delete(demanda)
    db.session.commit()

    registra_log_auto(usuario_id, demanda_id, 'del')


# =============================================================================
# Listagens / pesquisa
# =============================================================================

def providencias_e_despachos_todos():
    """Retorna todas as providências e despachos do sistema, combinados e ordenados por data (mais recentes primeiro)."""
    providencias = db.session.query(Providencia.demanda_id, Providencia.texto, Providencia.data,
                                    Providencia.user_id, User.username.label('username'),
                                    Providencia.programada, Providencia.passo)\
                             .outerjoin(User, Providencia.user_id == User.id)\
                             .order_by(Providencia.data.desc()).all()

    despachos = db.session.query(Despacho.demanda_id, Despacho.texto, Despacho.data,
                                 Despacho.user_id, (User.username + ' - DESPACHO').label('username'),
                                 User.despacha, User.despacha2, User.despacha0, Despacho.passo)\
                          .outerjoin(User, Despacho.user_id == User.id)\
                          .order_by(Despacho.data.desc()).all()

    pro_des = providencias + despachos
    pro_des.sort(key=lambda ordem: ordem.data, reverse=True)

    return pro_des


def listar_demandas_paginado(page):
    """Retorna todas as demandas, paginadas (8 por página), mais recentes primeiro."""
    return db.session.query(Demanda.id, Demanda.programa, Demanda.sei, Demanda.convênio,
                            Demanda.ano_convênio, Demanda.tipo, Demanda.data, Demanda.user_id,
                            Demanda.titulo, Demanda.desc, Demanda.necessita_despacho,
                            Demanda.conclu, Demanda.data_conclu, Demanda.necessita_despacho_cg,
                            Demanda.urgencia, Demanda.data_env_despacho, Demanda.nota,
                            Plano_Trabalho.atividade_sigla, User.coord, User.username)\
                     .outerjoin(Plano_Trabalho, Plano_Trabalho.id == Demanda.programa)\
                     .outerjoin(User, User.id == Demanda.user_id)\
                     .order_by(Demanda.data.desc())\
                     .paginate(page=page, per_page=8)


def _vida_media_por_tipo():
    """Calcula a vida média (dias entre criação e conclusão) de cada tipo de demanda já concluído."""
    demandas_conclu_por_tipo = db.session.query(Demanda.tipo, label('qtd', func.count(Demanda.id)))\
                                          .filter(Demanda.conclu == '1')\
                                          .order_by(Demanda.tipo)\
                                          .group_by(Demanda.tipo)

    vida_m_por_tipo_dict = {}

    for tipo in demandas_conclu_por_tipo:
        demandas_datas = db.session.query(Demanda.data, Demanda.data_conclu)\
                                    .filter(Demanda.tipo == tipo.tipo, Demanda.data_conclu != None)

        vida = 0
        for dia in demandas_datas:
            vida += (dia.data_conclu - dia.data).days

        qtd_datas = len(list(demandas_datas))
        vida_m = round(vida / qtd_datas) if qtd_datas > 0 else 0

        vida_m_por_tipo_dict[tipo.tipo] = vida_m

    return vida_m_por_tipo_dict


def priorizar_demandas(peso_r, peso_d, peso_u, coord, resp):
    """
    Lista as demandas não concluídas em ordem de prioridade (lista
    RDU), calculada a partir de relevância do tipo, distância em
    relação à vida média esperada, e urgência marcada na demanda.
    """
    vida_m_por_tipo_dict = _vida_media_por_tipo()

    hoje = datetime.today()

    campos = (Demanda.id, Plano_Trabalho.atividade_sigla, Demanda.sei, Demanda.tipo,
              Demanda.data, Demanda.necessita_despacho, Demanda.necessita_despacho_cg,
              Demanda.urgencia, Demanda.convênio, User.username)

    query = db.session.query(*campos)\
                      .join(User, Demanda.user_id == User.id)\
                      .outerjoin(Plano_Trabalho, Plano_Trabalho.id == Demanda.programa)\
                      .order_by(Demanda.data)

    if coord == '*' and resp == '*':
        demandas = query.filter(Demanda.conclu == '0').all()
    else:
        coord_filtro = '%' if coord == '*' else coord
        resp_filtro = '%' if resp == '*' else resp

        demandas = query.filter(Demanda.conclu == '0',
                                User.coord.like(coord_filtro),
                                User.id.like(resp_filtro)).all()

    quantidade = len(demandas)

    demandas_s = []

    for demanda in demandas:
        # identifica UF
        if demanda.convênio != 0 and demanda.convênio != '':
            uf = db.session.query(Proposta.UF_PROPONENTE)\
                           .filter(Convenio.NR_CONVENIO == demanda.convênio)\
                           .join(Convenio, Proposta.ID_PROPOSTA == Convenio.ID_PROPOSTA)\
                           .first()
        else:
            uf = db.session.query(Acordo.uf).filter_by(sei=demanda.sei).first()
        if uf is None:
            uf = ('*',)

        # identifica relevância
        relev = db.session.query(Tipos_Demanda.relevancia).filter_by(tipo=demanda.tipo).first()

        # calcula distância (momento)
        try:
            alvo = vida_m_por_tipo_dict[demanda.tipo]
        except KeyError:
            alvo = 999

        vigencia = (hoje - demanda.data).days

        if alvo == 0:
            distancia = 1
        else:
            if vigencia / alvo > 1.50:
                distancia = 1
            elif vigencia / alvo < 0.5:
                distancia = 3
            else:
                distancia = 2

        r_relevancia = relev.relevancia if relev else 0

        demanda_s = list(demanda)
        demanda_s.append(float(peso_r) * r_relevancia + float(peso_d) * distancia + float(peso_u) * demanda.urgencia)
        demanda_s.append(str(r_relevancia) + ',' + str(distancia) + ',' + str(demanda.urgencia))
        demanda_s.append(uf)

        demandas_s.append(demanda_s)

    demandas_s.sort(key=lambda x: x[10])

    return demandas_s, quantidade


def demandas_por_tipo_com_ultima_acao(tipo):
    """
    Lista as demandas de um tipo, com a descrição da última
    providência ou despacho de cada uma (o que for mais recente).
    """
    demandas = db.session.query(Demanda.id, Demanda.programa, Demanda.sei, Demanda.convênio,
                                Demanda.ano_convênio, Demanda.tipo, Demanda.data, Demanda.user_id,
                                Demanda.titulo, Demanda.desc, Demanda.necessita_despacho,
                                Demanda.conclu, Demanda.data_conclu, Demanda.necessita_despacho_cg,
                                Demanda.urgencia, Demanda.data_env_despacho, Demanda.nota,
                                Plano_Trabalho.atividade_sigla, Demanda.data_verific,
                                User.username, User.coord)\
                         .join(User, Demanda.user_id == User.id)\
                         .outerjoin(Plano_Trabalho, Plano_Trabalho.id == Demanda.programa)\
                         .filter(Demanda.tipo == tipo)\
                         .order_by(Demanda.id.desc())\
                         .all()

    l_act = {}

    for demanda in demandas:

        prov = db.session.query(Providencia.data, Providencia.texto, Providencia.passo)\
                         .filter(Providencia.demanda_id == demanda.id)\
                         .order_by(Providencia.data.desc()).first()

        desp = db.session.query(Despacho.data, Despacho.texto, Despacho.passo)\
                         .filter(Despacho.demanda_id == demanda.id)\
                         .order_by(Despacho.data.desc()).first()

        if prov is not None and desp is not None:
            ultima = prov if prov.data > desp.data else desp
            prefixo = 'P - ' if ultima is prov else 'D - '
        elif prov is not None:
            ultima = prov
            prefixo = 'P - '
        elif desp is not None:
            ultima = desp
            prefixo = 'D - '
        else:
            l_act[demanda.id] = 'sem registro'
            continue

        if ultima.passo is not None:
            l_act[demanda.id] = prefixo + ultima.passo + ultima.texto
        else:
            l_act[demanda.id] = prefixo + ultima.texto

    return demandas, len(demandas), l_act


def pesquisa_choices():
    """Retorna as 4 listas de opções (coord, tipo, autor, atividade) usadas no formulário de pesquisa."""
    coords = db.session.query(Coords.sigla).order_by(Coords.sigla).all()
    lista_coords = [(c[0], c[0]) for c in coords]
    lista_coords.insert(0, ('', ''))

    tipos = db.session.query(Tipos_Demanda.tipo).order_by(Tipos_Demanda.tipo).all()
    lista_tipos = [(t[0], t[0]) for t in tipos]
    lista_tipos.insert(0, ('', ''))

    pessoas = db.session.query(User.username, User.id).order_by(User.username).all()
    lista_pessoas = [(str(p[1]), p[0]) for p in pessoas]
    lista_pessoas.insert(0, ('', ''))

    atividades = db.session.query(Plano_Trabalho.atividade_sigla, Plano_Trabalho.id)\
                           .order_by(Plano_Trabalho.atividade_sigla).all()
    lista_atividades = [(str(a[1]), a[0]) for a in atividades]
    lista_atividades.insert(0, ('', ''))

    return lista_coords, lista_tipos, lista_pessoas, lista_atividades


def montar_string_pesquisa(sei, titulo, tipo, necessita_despacho, conclu, convenio, autor,
                            demanda_id, atividade, coord, necessita_despacho_cg):
    """
    Monta a string de pesquisa (campos separados por ';') usada para
    passar os critérios de busca pela URL. A '/' do SEI é trocada por
    '_' para não quebrar a URL.
    """
    sei_str = str(sei)
    if sei_str.find('/') != -1:
        sei_str = sei_str.split('/')[0] + '_' + sei_str.split('/')[1]

    return ';'.join([
        sei_str, str(titulo), str(tipo), str(necessita_despacho), str(conclu), str(convenio),
        str(autor), str(demanda_id), str(atividade), str(coord), str(necessita_despacho_cg),
    ])


def executar_pesquisa(pesq, page):
    """
    Executa a busca de demandas a partir da string de critérios (pesq)
    montada por `montar_string_pesquisa`. Retorna as demandas
    (paginadas), a contagem total, e as providências/despachos
    relacionados.
    """
    pesq_l = pesq.split(';')

    sei = pesq_l[0]
    if sei.find('_') != -1:
        sei = str(pesq_l[0]).split('_')[0] + '/' + str(pesq_l[0]).split('_')[1]

    p_tipo_pattern = '' if pesq_l[2] == 'Todos' else pesq_l[2]

    p_n_d = 'Todos'
    if pesq_l[3] == 'Sim':
        p_n_d = '1'
    if pesq_l[3] == 'Não':
        p_n_d = '0'

    p_n_dcg = 'Todos'
    if pesq_l[10] == 'Sim':
        p_n_dcg = '1'
    if pesq_l[10] == 'Não':
        p_n_dcg = '0'

    p_conclu = '' if pesq_l[4] == 'Todos' else pesq_l[4]

    conv = pesq_l[5] if pesq_l[5] != '' else '%'
    autor_id = pesq_l[6] if pesq_l[6] != '' else '%'

    pesq_l[7] = ('%' + str(pesq_l[7]) + '%') if pesq_l[7] == '' else str(pesq_l[7])
    pesq_l[8] = ('%' + str(pesq_l[8]) + '%') if pesq_l[8] == '' else str(pesq_l[8])
    pesq_l[9] = '%' if pesq_l[9] == '' else str(pesq_l[9])

    demandas = db.session.query(Demanda.id, Demanda.programa, Demanda.sei, Demanda.convênio,
                                Demanda.ano_convênio, Demanda.tipo, Demanda.data, Demanda.user_id,
                                Demanda.titulo, Demanda.desc, Demanda.necessita_despacho,
                                Demanda.conclu, Demanda.data_conclu, Demanda.necessita_despacho_cg,
                                Demanda.urgencia, Demanda.data_env_despacho, Demanda.nota,
                                Plano_Trabalho.atividade_sigla, User.coord, User.username)\
                         .join(User, User.id == Demanda.user_id)\
                         .outerjoin(Plano_Trabalho, Plano_Trabalho.id == Demanda.programa)\
                         .filter(Demanda.sei.like('%' + sei + '%'),
                                 func.coalesce(Demanda.convênio, '').like(conv),
                                 Demanda.titulo.like('%' + pesq_l[1] + '%'),
                                 Demanda.tipo.like('%' + p_tipo_pattern + '%'),
                                 cast(Demanda.necessita_despacho, String) != p_n_d,
                                 cast(Demanda.necessita_despacho_cg, String) != p_n_dcg,
                                 cast(Demanda.conclu, String).like('%' + p_conclu + '%'),
                                 cast(Demanda.user_id, String).like(autor_id),
                                 cast(Demanda.id, String).like(pesq_l[7]),
                                 cast(Demanda.programa, String).like(pesq_l[8]),
                                 cast(User.coord, String).like(pesq_l[9]))\
                         .order_by(Demanda.data.desc())\
                         .paginate(page=page, per_page=8)

    demandas_count = demandas.total

    pro_des = providencias_e_despachos_todos()

    return demandas, demandas_count, pro_des, pesq_l


# =============================================================================
# Despacho / providência
# =============================================================================

def passos_choices_do_tipo(tipo_id):
    """Retorna a lista de passos de um tipo de demanda, formatada para um SelectField."""
    passos = db.session.query(Passos_Tipos.passo, Passos_Tipos.ordem)\
                       .filter(Passos_Tipos.tipo_id == tipo_id)\
                       .order_by(Passos_Tipos.ordem).all()

    qtd = len(passos)
    lista_passos = [
        ('(' + str(p[1]) + '/' + str(qtd) + ') ' + p[0], '(' + str(p[1]) + '/' + str(qtd) + ') ' + p[0])
        for p in passos
    ]
    lista_passos.insert(0, ('', ''))
    return lista_passos


def _notificar_despacho_emitido(demanda, atividade_id, usuario):
    """Notifica o responsável pela demanda de que um despacho foi emitido."""
    dono_email = db.session.query(User.email, User.username).filter(User.id == demanda.user_id).first()

    destino = [dono_email.email, usuario.email]

    sistema = db.session.query(Sistema.nome_sistema).first()

    html = render_template('email_despacho_emitido.html', demanda=demanda.id, user=usuario.username,
                            dono=dono_email.username, titulo=demanda.titulo, sistema=sistema.nome_sistema)

    pt = db.session.query(Plano_Trabalho.atividade_sigla).filter(Plano_Trabalho.id == atividade_id).first()

    send_email('Demanda ' + str(demanda.id) + ' recebeu um Despacho (' + pt.atividade_sigla + ')', destino, '', html)

    msg = Msgs_Recebidas(user_id=demanda.user_id, data_hora=datetime.now(), demanda_id=demanda.id,
                         msg='A demanda recebeu um despacho!')
    db.session.add(msg)
    db.session.commit()


def criar_despacho(demanda_id, texto, passo_data, necessita_despacho_cg, conclu, usuario):
    """
    Registra um despacho de chefia para uma demanda. Sempre notifica
    o responsável pela demanda por e-mail, e notifica os chefes se a
    demanda for concluída pelo mesmo ato.

    Corrige bug real: o código original checava `if
    form.necessita_despacho_cg == 1:` (comparando o objeto do campo do
    formulário, não seu valor `.data`) — essa condição nunca era
    verdadeira, então `demanda.data_env_despacho` nunca era atualizado
    nesse ponto.
    """
    demanda = Demanda.query.get_or_404(demanda_id)

    passo = passo_data if passo_data is not None else ''

    despacho = Despacho(data=datetime.now(), user_id=usuario.id, demanda_id=demanda_id,
                        texto=texto, passo=passo)
    db.session.add(despacho)
    db.session.commit()

    registra_log_auto(usuario.id, demanda_id, 'des')

    if necessita_despacho_cg:
        demanda.necessita_despacho_cg = 1
        demanda.data_env_despacho = datetime.now()
    else:
        demanda.necessita_despacho_cg = 0

    if usuario.despacha == 1 or usuario.despacha0 == 1:
        demanda.necessita_despacho = 0

    if usuario.despacha2 == 1 and usuario.despacha == 0:
        demanda.necessita_despacho_cg = 0

    db.session.commit()

    if conclu != '0':
        demanda.necessita_despacho = 0
        demanda.necessita_despacho_cg = 0

        if demanda.conclu == '0':
            _notificar_demanda_concluida(demanda, demanda.titulo, demanda.programa, usuario)

        demanda.conclu = conclu
        demanda.data_conclu = datetime.now()
        db.session.commit()

        registra_log_auto(usuario.id, demanda_id, 'alt')

    else:
        demanda.conclu = '0'
        db.session.commit()

    _notificar_despacho_emitido(demanda, demanda.programa, usuario)

    return demanda


def aferir_demanda(demanda_id, nota, usuario_id):
    """Registra a nota de aferição de uma demanda concluída."""
    demanda = Demanda.query.get_or_404(demanda_id)

    demanda.nota = nota
    db.session.commit()

    registra_log_auto(usuario_id, demanda_id, 'afe')

    return demanda


def _notificar_necessita_despacho_com_dono(demanda, atividade_id, usuario):
    """
    Notifica os chefes, o próprio usuário e o dono da demanda (se
    diferente) de que uma providência marcou a necessidade de
    despacho. Variante de `_notificar_necessita_despacho` usada apenas
    por `criar_providencia`, que também avisa o dono da demanda.
    """
    chefes_emails = db.session.query(User.email, User.id)\
                              .filter(or_(User.despacha == 1, User.despacha0 == 1),
                                      User.coord == usuario.coord)

    dono_email = db.session.query(User.email, User.id).filter(User.id == demanda.user_id).first()

    destino = [e[0] for e in chefes_emails]
    destino.append(usuario.email)
    destino.append(dono_email.email)

    if len(destino) > 1:
        sistema = db.session.query(Sistema.nome_sistema).first()

        html = render_template('email_pede_despacho.html', demanda=demanda.id, user=usuario.username,
                                titulo=demanda.titulo, sistema=sistema.nome_sistema, tipo=demanda.tipo)

        pt = db.session.query(Plano_Trabalho.atividade_sigla).filter(Plano_Trabalho.id == atividade_id).first()

        send_email('Demanda ' + str(demanda.id) + ' requer despacho (' + pt.atividade_sigla + ')', destino, '', html)

        for chefe in chefes_emails:
            msg = Msgs_Recebidas(user_id=chefe.id, data_hora=datetime.now(), demanda_id=demanda.id,
                                 msg='Chefia, a demanda está pedindo um despacho!')
            db.session.add(msg)

        msg = Msgs_Recebidas(user_id=usuario.id, data_hora=datetime.now(), demanda_id=demanda.id,
                             msg='Você marcou a opção -Necessita despacho?- na demanda!')
        db.session.add(msg)

        if dono_email.id != usuario.id:
            msg = Msgs_Recebidas(user_id=dono_email.id, data_hora=datetime.now(), demanda_id=demanda.id,
                                 msg='A opção -Necessita despacho?- foi marcada na sua demanda!')
            db.session.add(msg)

        db.session.commit()


def _notificar_providencia_alheia(demanda, atividade_id, usuario):
    """Notifica o responsável pela demanda de que outra pessoa registrou uma providência nela."""
    dono_email = db.session.query(User.email, User.username).filter(User.id == demanda.user_id).first()

    destino = [dono_email.email, usuario.email]

    if len(destino) > 1:
        sistema = db.session.query(Sistema.nome_sistema).first()

        html = render_template('email_provi_alheia.html', demanda=demanda.id, user=usuario.username,
                                dono=dono_email.username, titulo=demanda.titulo, sistema=sistema.nome_sistema)

        pt = db.session.query(Plano_Trabalho.atividade_sigla).filter(Plano_Trabalho.id == atividade_id).first()

        send_email('Demanda ' + str(demanda.id) + ' com providência alheia (' + pt.atividade_sigla + ')', destino, '', html)

        msg = Msgs_Recebidas(user_id=demanda.user_id, data_hora=datetime.now(), demanda_id=demanda.id,
                             msg='A demanda recebeu uma providência alheia!')
        db.session.add(msg)
        db.session.commit()


def _agendar_no_google_calendar(demanda, data_hora, duracao, texto):
    """
    +---------------------------------------------------------------------------------------+
    | ATENÇÃO — funcionalidade preservada como estava, mas NÃO FUNCIONAL num servidor web:  |
    | `flow.run_console()` implementa um fluxo OAuth interativo por linha de comando, que    |
    | não tem como funcionar dentro de uma requisição HTTP de um servidor Flask (não há      |
    | console para o usuário interagir). Mantido sem alteração — corrigir isso exigiria      |
    | trocar para um fluxo OAuth web completo, o que é uma mudança de funcionalidade, não     |
    | uma correção de bug simples. O caminho '/temp/token.pkl' também tem o mesmo problema    |
    | de portabilidade já visto em outros pontos do sistema ('/temp' não é '/tmp').           |
    +---------------------------------------------------------------------------------------+
    """
    scopes = ['https://www.googleapis.com/auth/calendar.events']

    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
        client_file = os.path.join(base_path, 'client.json')
    else:
        client_file = 'client.json'

    flow = InstalledAppFlow.from_client_secrets_file(client_file, scopes=scopes)

    pasta_token_antiga = os.path.normpath('/temp/token.pkl')
    pasta_token = os.path.normpath('/temp/token/token.pkl')

    if os.path.exists(pasta_token_antiga):
        os.makedirs(os.path.normpath('/temp/token/'))
        os.system('copy ' + pasta_token_antiga + ' ' + pasta_token)
        os.remove(pasta_token_antiga)

    if os.path.exists(pasta_token):
        credentials = pickle.load(open(pasta_token, "rb"))
    else:
        credentials = flow.run_console()
        pickle.dump(credentials, open(pasta_token, "wb"))

    service = build("calendar", "v3", credentials=credentials)

    ini = data_hora
    fim = ini + timedelta(minutes=duracao)
    timezone = 'America/Sao_Paulo'

    event = {
        'summary': 'Demanda ' + str(demanda.id) + ' - Providência agendada',
        'location': 'CNPq',
        'description': texto,
        'start': {'dateTime': ini.strftime("%Y-%m-%dT%H:%M:%S"), 'timeZone': timezone},
        'end': {'dateTime': fim.strftime("%Y-%m-%dT%H:%M:%S"), 'timeZone': timezone},
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'email', 'minutes': 24 * 60},
                {'method': 'popup', 'minutes': 15},
            ],
        },
    }

    service.events().insert(calendarId='primary', body=event).execute()


def criar_providencia(demanda_id, data_hora, texto, duracao, passo_data, necessita_despacho,
                       conclu, agenda, usuario):
    """
    Registra uma providência para uma demanda, com toda a lógica de
    notificação por e-mail e (opcionalmente) agendamento no Google
    Calendar. Retorna uma tupla (demanda, agendada).
    """
    demanda = Demanda.query.get_or_404(demanda_id)

    programada = 1 if data_hora > datetime.now() else 0
    passo = passo_data if passo_data is not None else ''

    providencia = Providencia(demanda_id=demanda_id, data=data_hora, texto=texto, user_id=usuario.id,
                              duracao=duracao, programada=programada, passo=passo)
    db.session.add(providencia)
    db.session.commit()

    if programada == 1:
        registra_log_auto(usuario.id, demanda_id, 'age', demanda.programa, duracao)
    else:
        registra_log_auto(usuario.id, demanda_id, 'pro', demanda.programa, duracao)

    # para o caso da providência exigir um despacho
    if necessita_despacho:
        if demanda.necessita_despacho == 0:
            _notificar_necessita_despacho_com_dono(demanda, demanda.programa, usuario)

        demanda.necessita_despacho = 1
        demanda.necessita_despacho_cg = 0
        demanda.data_env_despacho = datetime.now()
    else:
        demanda.necessita_despacho = 0

    if demanda.user_id == usuario.id:
        if conclu != '0':
            if demanda.conclu == '0':
                demanda.conclu = conclu
                demanda.data_conclu = datetime.now()
                demanda.necessita_despacho = 0
                demanda.necessita_despacho_cg = 0

                _notificar_demanda_concluida(demanda, demanda.titulo, demanda.programa, usuario)

                registra_log_auto(usuario.id, demanda_id, 'alt')
        else:
            demanda.conclu = '0'
            demanda.data_conclu = None

    db.session.commit()

    if demanda.user_id != usuario.id:
        _notificar_providencia_alheia(demanda, demanda.programa, usuario)

    agendada = False
    if programada == 1 and agenda:
        _agendar_no_google_calendar(demanda, data_hora, duracao, texto)
        agendada = True

    return demanda, agendada


# =============================================================================
# Resumo / números
# =============================================================================

def resumo_demandas(coord):
    """
    Agrega informações básicas de todas as demandas de uma
    coordenação: contagem por tipo, vida média, prazo médio de
    despacho, percentual de conclusão, e médias mensais dos últimos
    12 meses (demandas, providências, despachos).
    """
    hoje = date.today()

    ## conta demandas por tipo, destacando a quantidade concluída e a vida média
    demandas_count = db.session.query(Demanda, User.coord)\
                               .join(User, Demanda.user_id == User.id)\
                               .filter(User.coord.like(coord))\
                               .count()

    demandas_por_tipo = db.session.query(Demanda.tipo, label('qtd_por_tipo', func.count(Demanda.id)))\
                                  .join(User, Demanda.user_id == User.id)\
                                  .order_by(func.count(Demanda.id).desc())\
                                  .filter(User.coord.like(coord))\
                                  .group_by(Demanda.tipo)

    demandas_por_tipo_ano_anterior = db.session.query(Demanda.tipo, label('qtd_por_tipo', func.count(Demanda.id)))\
                                               .join(User, Demanda.user_id == User.id)\
                                               .filter(Demanda.data >= str(hoje.year - 1) + '-1-1',
                                                       Demanda.data <= str(hoje.year - 1) + '-12-31',
                                                       User.coord.like(coord))\
                                               .group_by(Demanda.tipo)

    demandas_por_tipo_ano_corrente = db.session.query(Demanda.tipo, label('qtd_por_tipo', func.count(Demanda.id)))\
                                               .join(User, Demanda.user_id == User.id)\
                                               .filter(Demanda.data >= str(hoje.year) + '-1-1',
                                                       User.coord.like(coord))\
                                               .group_by(Demanda.tipo)

    m_top = hoje.month
    y_top = hoje.year
    m_ini = m_top - 11
    y_ini = y_top
    if m_ini < 1:
        m_ini += 12
        y_ini -= 1
    s_m_ini = str(m_ini)
    s_y_ini = str(y_ini)
    s_m_top = str(m_top)
    s_y_top = str(y_top)

    demandas_por_tipo_12meses = db.session.query(Demanda.tipo, label('qtd_por_tipo', func.count(Demanda.id)))\
                                          .join(User, Demanda.user_id == User.id)\
                                          .filter(Demanda.data >= s_y_ini + '-' + s_m_ini + '-1',
                                                  Demanda.data <= s_y_top + '-' + s_m_top + '-' + str(monthrange(y_top, m_top)[1]),
                                                  User.coord.like(coord))\
                                          .group_by(Demanda.tipo)

    demandas_tipos = db.session.query(Tipos_Demanda.tipo)\
                               .filter(Tipos_Demanda.unidade.like(coord))\
                               .order_by(Tipos_Demanda.tipo).all()

    ## calcula a vida média das demandas por tipo
    vida_m_por_tipo = []

    for demanda in demandas_por_tipo:
        demandas_datas = db.session.query(Demanda.data, Demanda.data_conclu)\
                                    .join(User, Demanda.user_id == User.id)\
                                    .filter(Demanda.tipo == demanda.tipo,
                                            Demanda.conclu == '1',
                                            Demanda.data_conclu != None,
                                            User.coord.like(coord))

        demandas_conclu_por_tipo = db.session.query(Demanda.tipo, label('qtd_conclu', func.count(Demanda.id)))\
                                             .join(User, Demanda.user_id == User.id)\
                                             .filter(Demanda.tipo == demanda.tipo,
                                                     Demanda.conclu == '1',
                                                     User.coord.like(coord))\
                                             .group_by(Demanda.tipo)

        vida = 0
        for dia in demandas_datas:
            vida += (dia.data_conclu - dia.data).days

        qtd_datas = len(list(demandas_datas))
        vida_m = round(vida / qtd_datas) if qtd_datas > 0 else 0

        if len(demandas_conclu_por_tipo.all()) != 0:
            vida_m_por_tipo.append([demanda.tipo, demandas_conclu_por_tipo[0][1], vida_m])

    ## calcula a vida média das demandas (geral)
    demandas_datas = db.session.query(Demanda.data, Demanda.data_conclu)\
                               .join(User, Demanda.user_id == User.id)\
                               .filter(Demanda.conclu == '1',
                                       Demanda.data_conclu != None,
                                       User.coord.like(coord))

    vida = 0
    for dia in demandas_datas:
        vida += (dia.data_conclu - dia.data).days

    qtd_datas = len(list(demandas_datas))
    vida_m = round(vida / qtd_datas) if qtd_datas > 0 else 0

    ## calcula a vida média das demandas (ano corrente)
    inic_ano = str(hoje.year) + '-01-01'

    demandas_ano = db.session.query(Demanda.data, Demanda.data_conclu)\
                             .join(User, Demanda.user_id == User.id)\
                             .filter(Demanda.conclu == '1',
                                     Demanda.data > inic_ano,
                                     User.coord.like(coord))
    vida = 0
    for dia in demandas_ano:
        vida += (dia.data_conclu - dia.data).days

    qtd_ano = len(list(demandas_ano))
    vida_m_ano = round(vida / qtd_ano) if qtd_ano > 0 else 0

    ## calcula o prazo médio dos despachos
    despachos = db.session.query(label('c_data', Despacho.data), Despacho.demanda_id,
                                 Demanda.id, label('i_data', Demanda.data))\
                          .join(User, Despacho.user_id == User.id)\
                          .outerjoin(Demanda, Despacho.demanda_id == Demanda.id)\
                          .filter(User.coord.like(coord))\
                          .all()

    desp = 0
    for despacho in despachos:
        desp += (despacho.c_data - despacho.i_data).days

    qtd_despachos = len(list(despachos))
    desp_m = round(desp / qtd_despachos) if qtd_despachos > 0 else 0

    # porcentagem de conclusão das demandas
    demandas_total = demandas_count

    demandas_conclu = db.session.query(Demanda, User.coord)\
                                .join(User, Demanda.user_id == User.id)\
                                .filter(Demanda.conclu == '1',
                                        User.coord.like(coord))\
                                .count()

    percent_conclu = round((demandas_conclu / demandas_total) * 100) if demandas_total != 0 else 0

    # média, maior quantidade e menor quantidade de demandas por colaborador ativo.
    colaborador_demandas = db.session.query(Demanda.user_id, label('qtd', func.count(Demanda.user_id)))\
                                     .join(User, Demanda.user_id == User.id)\
                                     .filter(User.coord.like(coord))\
                                     .group_by(Demanda.user_id)

    pessoas = db.session.query(User.id, User.ativo).filter(User.coord.like(coord)).all()

    qtd_demandas = []
    for c_d in colaborador_demandas:
        for p in pessoas:
            if c_d.user_id == p.id:
                if p.ativo == 1:
                    qtd_demandas.append(c_d.qtd)

    if len(qtd_demandas) > 0:
        qtd_demandas_max = max(qtd_demandas)
        qtd_demandas_min = min(qtd_demandas)
        qtd_demandas_avg = round(sum(qtd_demandas) / len(qtd_demandas))
    else:
        qtd_demandas_max = 0
        qtd_demandas_min = 0
        qtd_demandas_avg = 0

    # média de demandas, providências e despachos por mês nos últimos 12 meses
    meses = []
    for i in range(12):
        m = hoje.month - i
        y = hoje.year
        if m < 1:
            m += 12
            y -= 1
        if m >= 0 and m < 10:
            m = '0' + str(m)
        meses.append((str(m), str(y)))

    demandas_12meses = [db.session.query(Demanda)
                              .join(User, Demanda.user_id == User.id)
                              .filter(Demanda.data >= mes[1] + '-' + mes[0] + '-01',
                                      Demanda.data <= mes[1] + '-' + mes[0] + '-' + str(monthrange(int(mes[1]), int(mes[0]))[1]),
                                      User.coord.like(coord))
                              .count()
                        for mes in meses]

    med_dm = round(sum(demandas_12meses) / len(demandas_12meses))
    max_dm = max(demandas_12meses)
    min_dm = min(demandas_12meses)
    if med_dm != 0:
        mes_max_dm = meses[demandas_12meses.index(max_dm)]
        mes_min_dm = meses[demandas_12meses.index(min_dm)]
    else:
        mes_max_dm = 0
        mes_min_dm = 0

    providencias_12meses = [db.session.query(Providencia)
                                  .join(User, Providencia.user_id == User.id)
                                  .filter(Providencia.data >= mes[1] + '-' + mes[0] + '-01',
                                          Providencia.data <= mes[1] + '-' + mes[0] + '-' + str(monthrange(int(mes[1]), int(mes[0]))[1]),
                                          User.coord.like(coord))
                                  .count()
                            for mes in meses]

    med_pr = round(sum(providencias_12meses) / len(providencias_12meses))
    max_pr = max(providencias_12meses)
    min_pr = min(providencias_12meses)
    if med_pr != 0:
        mes_max_pr = meses[providencias_12meses.index(max_pr)]
        mes_min_pr = meses[providencias_12meses.index(min_pr)]
    else:
        mes_max_pr = 0
        mes_min_pr = 0

    despachos_12meses = [db.session.query(Despacho)
                               .join(User, Despacho.user_id == User.id)
                               .filter(Despacho.data >= mes[1] + '-' + mes[0] + '-01',
                                       Despacho.data <= mes[1] + '-' + mes[0] + '-' + str(monthrange(int(mes[1]), int(mes[0]))[1]),
                                       User.coord.like(coord))
                               .count()
                         for mes in meses]

    med_dp = round(sum(despachos_12meses) / len(despachos_12meses))
    max_dp = max(despachos_12meses)
    min_dp = min(despachos_12meses)
    if med_dp != 0:
        mes_max_dp = meses[despachos_12meses.index(max_dp)]
        mes_min_dp = meses[despachos_12meses.index(min_dp)]
    else:
        mes_max_dp = 0
        mes_min_dp = 0

    return {
        'demandas_count': demandas_count,
        'demandas_por_tipo': demandas_por_tipo,
        'demandas_por_tipo_ano_anterior': demandas_por_tipo_ano_anterior,
        'demandas_por_tipo_ano_corrente': demandas_por_tipo_ano_corrente,
        'demandas_por_tipo_12meses': demandas_por_tipo_12meses,
        'demandas_tipos': demandas_tipos,
        'vida_m_por_tipo': vida_m_por_tipo,
        'vida_m': vida_m,
        'desp_m': desp_m,
        'percent_conclu': percent_conclu,
        'vida_m_ano': vida_m_ano,
        'qtd_demandas_max': qtd_demandas_max,
        'qtd_demandas_min': qtd_demandas_min,
        'qtd_demandas_avg': qtd_demandas_avg,
        'med_dm': med_dm, 'max_dm': max_dm, 'mes_max_dm': mes_max_dm, 'min_dm': min_dm, 'mes_min_dm': mes_min_dm,
        'med_pr': med_pr, 'max_pr': max_pr, 'mes_max_pr': mes_max_pr, 'min_pr': min_pr, 'mes_min_pr': mes_min_pr,
        'med_dp': med_dp, 'max_dp': max_dp, 'mes_max_dp': mes_max_dp, 'min_dp': min_dp, 'mes_min_dp': mes_min_dp,
    }


def estatisticas_usuario(usu):
    """
    Calcula as estatísticas de um usuário específico: quantidade de
    demandas, taxa de conclusão, vida média, prazo médio de despacho,
    e médias mensais/semanais de dedicação.

    Corrige bug real (mesmo padrão já corrigido em
    users/services.py:calcular_estatisticas_conta): as consultas
    `user_demandas`/`user_demandas_conclu` usam GROUP BY, que retorna
    uma lista VAZIA (não uma linha com contagem 0) quando o usuário
    não tem nenhuma demanda — acessar `[0][1]` diretamente quebrava
    com IndexError para qualquer usuário sem demandas.
    """
    hoje = date.today()

    usuario = db.session.query(User).filter(User.id == usu).first()

    user_demandas = db.session.query(Demanda.user_id, func.count(Demanda.user_id))\
                              .filter(Demanda.user_id == usu)\
                              .group_by(Demanda.user_id).first()

    qtd_demandas = user_demandas[1] if user_demandas else 0

    user_demandas_conclu = db.session.query(Demanda.user_id, func.count(Demanda.user_id))\
                                     .filter(Demanda.user_id == usu, Demanda.conclu == '1')\
                                     .group_by(Demanda.user_id).first()

    qtd_demandas_conclu = user_demandas_conclu[1] if user_demandas_conclu else 0

    percent_conclu = round((qtd_demandas_conclu / qtd_demandas) * 100) if qtd_demandas != 0 else 0

    ## calcula a vida média das demandas do usuário
    demandas_datas = db.session.query(Demanda.data, Demanda.data_conclu)\
                               .filter(Demanda.conclu == '1', Demanda.data_conclu != None, Demanda.user_id == usu)

    vida = 0
    for dia in demandas_datas:
        vida += (dia.data_conclu - dia.data).days

    qtd_datas = len(list(demandas_datas))
    vida_m = round(vida / qtd_datas) if qtd_datas > 0 else 0

    ## calcula o prazo médio dos despachos
    despachos = db.session.query(label('c_data', Despacho.data), Despacho.demanda_id,
                                 Demanda.id, label('i_data', Demanda.data))\
                          .outerjoin(Demanda, Despacho.demanda_id == Demanda.id)\
                          .filter(Demanda.user_id == usu)\
                          .all()

    desp = 0
    for despacho in despachos:
        desp += (despacho.c_data - despacho.i_data).days

    qtd_despachos = len(list(despachos))
    desp_m = round(desp / qtd_despachos) if qtd_despachos > 0 else 0

    ## média de demandas, providências e despachos por mês nos últimos 12 meses
    meses = []
    for i in range(12):
        m = hoje.month - i - 1
        y = hoje.year
        if m < 1:
            m += 12
            y -= 1
        if m >= 0 and m < 10:
            m = '0' + str(m)
        meses.append((str(m), str(y)))

    demandas_12meses = [Demanda.query.filter(Demanda.data >= mes[1] + '-' + mes[0] + '-01',
                                             Demanda.data <= mes[1] + '-' + mes[0] + '-' + str(monthrange(int(mes[1]), int(mes[0]))[1]),
                                             Demanda.user_id == usu).count()
                                             for mes in meses]

    med_dm = round(sum(demandas_12meses) / len(demandas_12meses))
    max_dm = max(demandas_12meses)
    mes_max_dm = meses[demandas_12meses.index(max_dm)]
    min_dm = min(demandas_12meses)
    mes_min_dm = meses[demandas_12meses.index(min_dm)]

    providencias_12meses = [Providencia.query.filter(Providencia.data >= mes[1] + '-' + mes[0] + '-01',
                                             Providencia.data <= mes[1] + '-' + mes[0] + '-' + str(monthrange(int(mes[1]), int(mes[0]))[1]),
                                             Providencia.user_id == usu).count()
                                             for mes in meses]

    med_pr = round(sum(providencias_12meses) / len(providencias_12meses))
    max_pr = max(providencias_12meses)
    mes_max_pr = meses[providencias_12meses.index(max_pr)]
    min_pr = min(providencias_12meses)
    mes_min_pr = meses[providencias_12meses.index(min_pr)]

    minutos_dedicados_12meses = [db.session.query(func.sum(Providencia.duracao)).filter(Providencia.data >= mes[1] + '-' + mes[0] + '-01',
                                             Providencia.data <= mes[1] + '-' + mes[0] + '-' + str(monthrange(int(mes[1]), int(mes[0]))[1]),
                                             Providencia.user_id == usu).all()
                                             for mes in meses]

    minutos_log_man_12meses = [db.session.query(func.sum(Log_Auto.duracao)).filter(Log_Auto.data_hora >= mes[1] + '-' + mes[0] + '-01',
                                             Log_Auto.data_hora <= mes[1] + '-' + mes[0] + '-' + str(monthrange(int(mes[1]), int(mes[0]))[1]),
                                             Log_Auto.user_id == usu).all()
                                             for mes in meses]

    hd_p = [m[0][0] if m[0][0] is not None else 0 for m in minutos_dedicados_12meses]
    hd_l = [m[0][0] if m[0][0] is not None else 0 for m in minutos_log_man_12meses]
    hd = [x + y for (x, y) in zip(hd_p, hd_l)]

    med_hd = round((sum(hd) / len(hd)) / 60)
    max_hd = round(max(hd) / 60)
    mes_max_hd = meses[hd.index(max(hd))]
    min_hd = round(min(hd) / 60)
    mes_min_hd = meses[hd.index(min(hd))]

    start = hoje - timedelta(days=hoje.weekday())
    end = start + timedelta(days=6)

    minutos_dedicados_semana_p = db.session.query(func.sum(Providencia.duracao)).filter(Providencia.data >= start,
                                             Providencia.data <= end,
                                             Providencia.user_id == usu).all()

    minutos_dedicados_semana_l = db.session.query(func.sum(Log_Auto.duracao)).filter(Log_Auto.data_hora >= start,
                                          Log_Auto.data_hora <= end,
                                          Log_Auto.user_id == usu).all()

    md_p = minutos_dedicados_semana_p[0][0] or 0
    md_l = minutos_dedicados_semana_l[0][0] or 0

    horas_dedicadas_semana = round((md_p + md_l) / 60)

    return {
        'usuario': usuario,
        'qtd_demandas': qtd_demandas,
        'qtd_demandas_conclu': qtd_demandas_conclu,
        'percent_conclu': percent_conclu,
        'vida_m': vida_m,
        'desp_m': desp_m,
        'med_dm': med_dm, 'max_dm': max_dm, 'mes_max_dm': mes_max_dm, 'min_dm': min_dm, 'mes_min_dm': mes_min_dm,
        'med_pr': med_pr, 'max_pr': max_pr, 'mes_max_pr': mes_max_pr, 'min_pr': min_pr, 'mes_min_pr': mes_min_pr,
        'med_hd': med_hd, 'max_hd': max_hd, 'mes_max_hd': mes_max_hd, 'min_hd': min_hd, 'mes_min_hd': mes_min_hd,
        'horas': horas_dedicadas_semana,
    }
