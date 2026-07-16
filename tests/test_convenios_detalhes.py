# test_convenios_detalhes.py
#
# Testes de characterization da rota convenio_detalhes do módulo
# convenios. Cobre um bug real encontrado durante a refatoração: um
# POST com dados de formulário inválidos caía fora dos dois branches
# (if/elif) da função original, chegando na geração do PDF com
# variáveis nunca definidas (UnboundLocalError / NameError).

import pytest
from datetime import date
from project import db
from project.models import User, Programa, Proposta, Convenio


@pytest.fixture()
def convenio_teste(app):
    with app.app_context():
        if not Programa.query.get('9001'):
            db.session.add(Programa('9001', '9001', 'Programa Teste', 'Ativo', '2024'))
        if not Proposta.query.get('9001'):
            db.session.add(Proposta('9001', '9001', 'DF', 'Proponente Teste', 'Objeto teste'))
        db.session.commit()

        if not Convenio.query.get('CONVTESTE001'):
            db.session.add(Convenio(
                'CONVTESTE001', '9001', '01', '01', '2024', '01/01/2024', 'Em execução', 'Normal',
                'Publicado', 'Sim', 'Não', 'PROC001', 'UG1', '01/01/2024', '01/01/2024',
                date(2025, 12, 31), '01/01/2025', '60', '01/03/2026', 'Contratado', 'Sim', '',
                'N', '1', '0', '0',
                100000.0, 90000.0, 10000.0, 50000.0, 20000.0, 0.0, 0.0, 500.0, 0.0, 0.0, 90000.0,
            ))
        db.session.commit()

        return 'CONVTESTE001'


@pytest.fixture()
def usuario_convenios_detalhes(app):
    with app.app_context():
        user = User.query.filter_by(email='teste.convdet@teste.com').first()
        if user is None:
            user = User(
                email='teste.convdet@teste.com', username='usuarioconvdetteste',
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


def test_convenio_detalhes_get_responde_200(client, usuario_convenios_detalhes, convenio_teste):
    _login(client, usuario_convenios_detalhes)
    resp = client.get(f"/convenios/{convenio_teste}/convenio_detalhes")
    assert resp.status_code == 200


def test_convenio_detalhes_post_invalido_nao_quebra(client, usuario_convenios_detalhes, convenio_teste):
    """
    Regressão do bug de UnboundLocalError: submeter o form de SEI com
    dados inválidos não deve derrubar a página com erro 500.
    """
    _login(client, usuario_convenios_detalhes)
    resp = client.post(f"/convenios/{convenio_teste}/convenio_detalhes", data={
        "sei": "", "epe": "", "fiscal": "",
    })
    assert resp.status_code == 200
