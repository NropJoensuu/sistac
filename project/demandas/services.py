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

from flask_mail import Message

import os
from datetime import date

from fpdf import FPDF
from sqlalchemy import func

from project import db, mail, app
from project.models import (
    Log_Auto, Plano_Trabalho, Ativ_Usu, User, Coords, Tipos_Demanda,
    Passos_Tipos, Demanda, Providencia, Despacho,
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
