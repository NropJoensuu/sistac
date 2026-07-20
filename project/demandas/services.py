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

from project import db, mail, app
from project.models import Log_Auto, Plano_Trabalho, Ativ_Usu, User, Coords


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
