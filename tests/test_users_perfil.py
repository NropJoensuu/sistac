# test_users_perfil.py
#
# Testes de characterization do grupo Perfil/conta do módulo users.
# Cobre um bug real encontrado durante a refatoração: a tela de conta
# (/account) travava com erro 500 para qualquer usuário que ainda não
# tivesse nenhuma demanda registrada (IndexError em uma query GROUP BY
# que assumia pelo menos 1 linha de resultado).

import pytest
from project import db
from project.models import User


@pytest.fixture()
def usuario_sem_demandas(app):
    with app.app_context():
        user = User.query.filter_by(email='teste.perfil@teste.com').first()
        if user is None:
            user = User(
                email='teste.perfil@teste.com', username='usuarioperfilsemdemandas',
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


def test_account_nao_quebra_para_usuario_sem_demandas(client, usuario_sem_demandas):
    """
    A tela de conta deve carregar normalmente mesmo para um usuário
    que nunca registrou nenhuma demanda (regressão do bug de IndexError).
    """
    _login(client, usuario_sem_demandas)
    resp = client.get("/account")
    assert resp.status_code == 200


def test_user_posts_todos_responde_200(client):
    resp = client.get("/user_posts/todos/todos")
    assert resp.status_code == 200
