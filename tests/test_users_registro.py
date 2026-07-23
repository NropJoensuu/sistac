# test_users_registro.py
#
# Testes de dois achados reais na tela de registro:
#
# 1. BUG GRAVE (corrigido): a rota register() passava o OBJETO do
#    campo (form.despacha0), não o valor marcado (form.despacha0.data),
#    para o serviço de criação. Como um objeto de campo do WTForms é
#    sempre "verdadeiro" em Python, TODO usuário que já se registrou
#    pelo sistema recebeu despacha0=1, despacha=1, despacha2=1
#    automaticamente, independente do que marcou no formulário.
#
# 2. Nova funcionalidade: se o e-mail já existe mas ainda não foi
#    confirmado, o registro não bloqueia mais — atualiza o cadastro
#    existente e reenvia a confirmação com um link novo. Isso permite
#    que a pessoa tente de novo sozinha, sem depender de um admin,
#    mesmo que o primeiro link tenha expirado (caso real: usuário Yuri).

from project import db
from project.models import User


def test_registro_sem_marcar_despacho_nao_concede_despacho(client, app):
    """Regressão do bug grave: nenhum despacho deve ser concedido se não foi marcado."""
    with app.app_context():
        User.query.filter_by(email='teste.regsemdespacho@teste.com').delete()
        db.session.commit()

    resp = client.post("/register", data={
        'email': 'teste.regsemdespacho@teste.com', 'username': 'usuarioregsemdespachoteste',
        'password': 'senha123', 'pass_confirm': 'senha123', 'coord': 'DPI',
    })
    assert resp.status_code == 302

    with app.app_context():
        user = User.query.filter_by(email='teste.regsemdespacho@teste.com').first()
        assert user.despacha0 == 0
        assert user.despacha == 0
        assert user.despacha2 == 0


def test_registro_marcando_so_um_despacho_concede_so_esse(client, app):
    with app.app_context():
        User.query.filter_by(email='teste.regumdespacho@teste.com').delete()
        db.session.commit()

    resp = client.post("/register", data={
        'email': 'teste.regumdespacho@teste.com', 'username': 'usuarioregumdespachoteste',
        'password': 'senha123', 'pass_confirm': 'senha123', 'coord': 'DPI', 'despacha0': 'y',
    })
    assert resp.status_code == 302

    with app.app_context():
        user = User.query.filter_by(email='teste.regumdespacho@teste.com').first()
        assert user.despacha0 == 1
        assert user.despacha == 0
        assert user.despacha2 == 0


def test_reregistro_com_email_nao_confirmado_atualiza_em_vez_de_bloquear(client, app):
    """
    Regressão: caso real do usuário Yuri, que não confirmou a tempo e
    não tinha admin disponível para ajudar. Tentar de novo com o
    mesmo e-mail (ainda não confirmado) deve atualizar o cadastro
    existente, não bloquear.
    """
    with app.app_context():
        User.query.filter_by(email='teste.reregistro@teste.com').delete()
        db.session.commit()

    resp1 = client.post("/register", data={
        'email': 'teste.reregistro@teste.com', 'username': 'usuarioreregistrov1teste',
        'password': 'senhaoriginal', 'pass_confirm': 'senhaoriginal', 'coord': 'COPES',
    })
    assert resp1.status_code == 302

    with app.app_context():
        id_original = User.query.filter_by(email='teste.reregistro@teste.com').first().id

    resp2 = client.post("/register", data={
        'email': 'teste.reregistro@teste.com', 'username': 'usuarioreregistrov2teste',
        'password': 'senhanova', 'pass_confirm': 'senhanova', 'coord': 'COPES',
    })
    assert resp2.status_code == 302

    with app.app_context():
        contas = User.query.filter_by(email='teste.reregistro@teste.com').all()
        assert len(contas) == 1
        assert contas[0].id == id_original
        assert contas[0].username == 'usuarioreregistrov2teste'
        assert contas[0].check_password('senhanova')


def test_reregistro_com_email_ja_confirmado_continua_bloqueado(client, app):
    """Regressão: a nova regra não deve afetar o bloqueio de e-mails já confirmados."""
    with app.app_context():
        user = User.query.filter_by(email='teste.jaconfirmadoregistro@teste.com').first()
        if user is None:
            user = User(
                email='teste.jaconfirmadoregistro@teste.com', username='usuariojaconfirmadoregistroteste',
                plaintext_password='senha123', coord='DPI', role='user',
                ativo=1, sversion=1, cargo_func='teste',
                trab_conv=1, trab_acordo=1, trab_instru=1, despacha0=0, despacha=0, despacha2=0,
            )
            db.session.add(user)
            db.session.commit()
        user.email_confirmed = 1
        db.session.commit()

    resp = client.post("/register", data={
        'email': 'teste.jaconfirmadoregistro@teste.com', 'username': 'outronome',
        'password': 'senha123', 'pass_confirm': 'senha123', 'coord': 'DPI',
    }, follow_redirects=True)

    assert 'já foi registrado'.encode() in resp.data
