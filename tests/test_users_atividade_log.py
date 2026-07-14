# test_users_atividade_log.py
#
# Testes de characterization do grupo Atividade/log do módulo users
# (último grupo da refatoração completa do módulo).

import pytest
from project import db
from project.models import User


@pytest.fixture()
def usuario_qualquer(app):
    with app.app_context():
        user = User.query.filter_by(email='teste.log@teste.com').first()
        if user is None:
            user = User(
                email='teste.log@teste.com', username='usuariologteste',
                plaintext_password='senha123', coord='TESTE', role='user',
                ativo=1, sversion=1, cargo_func='teste',
                trab_conv=1, trab_acordo=1, trab_instru=1,
                despacha0=0, despacha=0, despacha2=0,
            )
            db.session.add(user)
            db.session.commit()
        return user.id


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


def test_user_log_responde_200(client, usuario_qualquer):
    _login(client, usuario_qualquer)
    resp = client.get("/*/user_log")
    assert resp.status_code == 200


def test_user_msgs_recebidas_responde_200(client, usuario_qualquer):
    _login(client, usuario_qualquer)
    resp = client.get("/user_msgs_recebidas")
    assert resp.status_code == 200


def test_coord_view_users_bloqueado_para_quem_nao_despacha(client, usuario_qualquer):
    """
    Um usuário sem permissão de despacho (despacha=0, despacha0=0) e
    que não é admin não deve conseguir acessar a lista de usuários da
    coordenação para atribuir atividades.
    """
    _login(client, usuario_qualquer)
    resp = client.get("/coord_view_users")
    assert resp.status_code == 403
