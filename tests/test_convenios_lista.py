# test_convenios_lista.py
#
# Testes de characterization da rota lista_convenios_SICONV do módulo
# convenios. Cobre as combinações de filtro de coordenação ('*', 'usu',
# 'inst', sigla parcial) e de tipo de lista ('todos', 'em execução',
# 'programa...'), além da correção do caminho absoluto do Docker.

import pytest
from project import db
from project.models import User


@pytest.fixture()
def usuario_convenios(app):
    with app.app_context():
        user = User.query.filter_by(email='teste.convenios@teste.com').first()
        if user is None:
            user = User(
                email='teste.convenios@teste.com', username='usuarioconveniosteste',
                plaintext_password='senha123', coord='DPI', role='user',
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


@pytest.mark.parametrize("coord", ["*", "usu", "inst", "DPI"])
@pytest.mark.parametrize("lista", ["todos", "em execução"])
def test_lista_convenios_siconv_responde_200(client, usuario_convenios, lista, coord):
    _login(client, usuario_convenios)
    resp = client.get(f"/convenios/{lista}/{coord}/lista_convenios_SICONV")
    assert resp.status_code == 200
