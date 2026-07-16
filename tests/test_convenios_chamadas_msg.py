# test_convenios_chamadas_msg.py
#
# Testes de characterization do grupo chamadas/natureza de despesa/
# SEI_demandas/msg_siconv do módulo convenios. Cobre um bug real: a
# rota msg_siconv quebrava com IndexError quando não havia nenhuma
# mensagem SICONV carregada.

from datetime import date
from project import db
from project.models import User, Programa, Proposta, Convenio


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


def _convenio_teste(app):
    with app.app_context():
        if not Programa.query.get('9002'):
            db.session.add(Programa('9002', '9002', 'Programa Teste 2', 'Ativo', '2024'))
        if not Proposta.query.get('9002'):
            db.session.add(Proposta('9002', '9002', 'DF', 'Proponente Teste 2', 'Objeto teste'))
        db.session.commit()

        if not Convenio.query.get('CONVTESTE002'):
            db.session.add(Convenio(
                'CONVTESTE002', '9002', '01', '01', '2024', '01/01/2024', 'Em execução', 'Normal',
                'Publicado', 'Sim', 'Não', 'PROC002', 'UG1', '01/01/2024', '01/01/2024',
                date(2025, 12, 31), '01/01/2025', '60', '01/03/2026', 'Contratado', 'Sim', '',
                'N', '1', '0', '0',
                100000.0, 90000.0, 10000.0, 50000.0, 20000.0, 0.0, 0.0, 500.0, 0.0, 0.0, 90000.0,
            ))
        db.session.commit()

        return 'CONVTESTE002'


def test_msg_siconv_sem_mensagens_nao_quebra(client, app):
    """
    Regressão do bug de IndexError: a listagem de mensagens SICONV
    deve carregar normalmente mesmo quando não há nenhuma mensagem
    carregada no banco.
    """
    user_id = _usuario(app, 'teste.msgsiconv@teste.com', 'usuariomsgsiconvteste')
    _login(client, user_id)
    resp = client.get("/convenios/msg_siconv")
    assert resp.status_code == 200


def test_associa_chamada_get_responde_200(client, app):
    user_id = _usuario(app, 'teste.associachamada@teste.com', 'usuarioassociachamadateste')
    conv = _convenio_teste(app)
    _login(client, user_id)
    resp = client.get(f"/convenios/associa_chamada/{conv}")
    assert resp.status_code == 200
