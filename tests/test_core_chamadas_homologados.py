# test_core_chamadas_homologados.py
#
# Testes de characterization do grupo Chamadas/Homologados do módulo
# core.

from project import db
from project.models import User, Chamadas


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


def _chamada(app):
    with app.app_context():
        chamada = Chamadas.query.filter_by(chamada='Chamada Teste Grupo D').first()
        if chamada is None:
            chamada = Chamadas(
                sei='00000.000000/2024-00', chamada='Chamada Teste Grupo D',
                qtd_projetos=10, vl_total_chamada=1000.0, doc_sei='doc1',
                obs='teste', id_relaciona='', qtd_processos=0,
            )
            db.session.add(chamada)
            db.session.commit()
        return chamada.id


def test_update_chamada_get_responde_200(client, app):
    user_id = _usuario(app, 'teste.updchamada@teste.com', 'usuarioupdchamadateste')
    chamada_id = _chamada(app)
    _login(client, user_id)
    resp = client.get(f"/{chamada_id}/update_chamada")
    assert resp.status_code == 200


def test_lista_homologados_responde_200(client, app):
    chamada_id = _chamada(app)
    resp = client.get(f"/{chamada_id}/homologados")
    assert resp.status_code == 200


def test_edita_homologado_novo_responde_200(client, app):
    user_id = _usuario(app, 'teste.editahomologado@teste.com', 'usuarioeditahomologadoteste')
    chamada_id = _chamada(app)
    _login(client, user_id)
    resp = client.get(f"/{chamada_id}/0/edita_homologado")
    assert resp.status_code == 200


def test_cria_chamada_get_responde_200(client, app):
    user_id = _usuario(app, 'teste.criachamada@teste.com', 'usuariocriachamadateste')
    _login(client, user_id)
    resp = client.get("/1/criar_chamada")
    assert resp.status_code == 200
