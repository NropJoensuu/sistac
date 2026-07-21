# test_demandas_resumo.py
#
# Testes de characterization do grupo Resumo/números do módulo
# demandas — último grupo do maior módulo do projeto, fecha a
# refatoração completa da Fase 2. Cobre um bug real: numeros_usu
# quebrava com IndexError para qualquer usuário sem nenhuma demanda
# (mesmo padrão já corrigido em users/services.py).

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


def test_demandas_resumo_responde_200(client):
    resp = client.get("/demandas/*/demandas_resumo")
    assert resp.status_code == 200


def test_numeros_usu_sem_demandas_nao_quebra(client, app):
    """
    Regressão do bug: a tela de números do usuário deve carregar
    normalmente mesmo para um usuário que nunca registrou nenhuma
    demanda (antes quebrava com IndexError).
    """
    admin_id, _ = None, None
    with app.app_context():
        admin = User.query.filter_by(email='admin@teste.com').first()
        admin_id = admin.id

    user_id = _usuario(app, 'teste.numerosususemdemandas@teste.com', 'usuarionumerosusuteste')
    _login(client, admin_id)

    resp = client.get(f"/demandas/{user_id}/numeros_usu")
    assert resp.status_code == 200
