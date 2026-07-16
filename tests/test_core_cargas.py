# test_core_cargas.py
#
# Testes de characterization do grupo Cargas de arquivo do módulo
# core (carregaPDCTR, carregaMSG). Cobre um bug real: a tela de
# upload de folha de pagamento quebrava com erro 500 numa instalação
# sem nenhuma carga PDCTR anterior, porque o template chamava
# .strftime() diretamente num valor None.

from project import db
from project.models import User


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


def _usuario(app, email, username):
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if user is None:
            user = User(
                email=email, username=username,
                plaintext_password='senha123', coord='DPI', role='user',
                ativo=1, sversion=1, cargo_func='teste',
                trab_conv=1, trab_acordo=1, trab_instru=1,
                despacha0=0, despacha=0, despacha2=0,
            )
            db.session.add(user)
            db.session.commit()
        return user.id


def test_carregaPDCTR_get_sem_carga_anterior_nao_quebra(client, app):
    """
    Regressão do bug: a tela de upload da folha de pagamento deve
    carregar normalmente mesmo sem nenhuma carga PDCTR anterior
    (data_ref None).
    """
    user_id = _usuario(app, 'teste.cargapdctr@teste.com', 'usuariocargapdctrteste')
    _login(client, user_id)
    resp = client.get("/carregaPDCTR")
    assert resp.status_code == 200


def test_carregaMSG_get_responde_200(client, app):
    user_id = _usuario(app, 'teste.cargamsg@teste.com', 'usuariocargamsgteste')
    _login(client, user_id)
    resp = client.get("/carregaMSG")
    assert resp.status_code == 200
