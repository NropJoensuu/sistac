# test_convenios_dashboards.py
#
# Testes de characterization do grupo dashboards/mapas do módulo
# convenios (último grupo, fecha a refatoração completa do módulo).
# Cobre um bug real: resumo_convenios quebrava com IndexError sempre
# que um convênio tinha VL_REPASSE_CONV ou VL_CONTRAPARTIDA_CONV
# zerados, porque o código pulava o append dos percentuais em vez de
# gravar 0 — e o template acessa essas posições incondicionalmente.

from datetime import date
from project import db
from project.models import User, Programa, Proposta, Convenio


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


def _usuario(app, email, username, coord='DPI'):
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if user is None:
            user = User(
                email=email, username=username,
                plaintext_password='senha123', coord=coord, role='user',
                ativo=1, sversion=1, cargo_func='teste',
                trab_conv=1, trab_acordo=1, trab_instru=1,
                despacha0=0, despacha=0, despacha2=0,
            )
            db.session.add(user)
            db.session.commit()
        return user.id


def _convenio_repasse_zero(app):
    with app.app_context():
        if not Programa.query.get('9004'):
            db.session.add(Programa('9004', '9004', 'Programa Repasse Zero', 'Ativo', '2024'))
        if not Proposta.query.get('9004'):
            db.session.add(Proposta('9004', '9004', 'DF', 'Proponente Teste', 'Objeto teste'))
        db.session.commit()

        if not Convenio.query.get('CONVZERO002'):
            db.session.add(Convenio(
                'CONVZERO002', '9004', '01', '01', '2024', '01/01/2024', 'Em execução', 'Normal',
                'Publicado', 'Sim', 'Não', 'PROC004', 'UG1', '01/01/2024', '01/01/2024',
                date(2025, 12, 31), '01/01/2025', '60', '01/03/2026', 'Contratado', 'Sim', '',
                'N', '1', '0', '0',
                # VL_REPASSE_CONV e VL_CONTRAPARTIDA_CONV zerados de propósito
                100000.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            ))
        db.session.commit()


def test_quadro_convenios_responde_200(client, app):
    user_id = _usuario(app, 'teste.quadro@teste.com', 'usuarioquadroteste')
    _login(client, user_id)
    resp = client.get("/convenios/quadro_convenios")
    assert resp.status_code == 200


def test_brasil_convenios_responde_200(client, app):
    user_id = _usuario(app, 'teste.brasil@teste.com', 'usuariobrasilteste')
    _login(client, user_id)
    resp = client.get("/convenios/brasil_convenios")
    assert resp.status_code == 200


def test_resumo_convenios_com_repasse_zero_nao_quebra(client, app):
    """
    Regressão do bug de IndexError: um convênio com VL_REPASSE_CONV e
    VL_CONTRAPARTIDA_CONV zerados não deve derrubar a página de resumo.
    """
    user_id = _usuario(app, 'teste.resumo@teste.com', 'usuarioresumoteste', coord='DPI')
    _convenio_repasse_zero(app)
    _login(client, user_id)
    resp = client.get("/convenios/resumo_convenios")
    assert resp.status_code == 200
