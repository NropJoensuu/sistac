# test_acordos_bi.py
#
# Testes da tela de BI Acordos (Etapa 2 do roadmap_bi_sistac.md):
# rota básica, filtros via querystring, e contagem de acordos com
# vigência a vencer. Segue o padrão de test_acordos_dashboards.py.

from datetime import date, timedelta
from project import db
from project.acordos import services
from project.models import User, Acordo


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


def _acordo(sei, situ='Vigente-Z', uf='DF', ano_inicio=2024, data_fim=None):
    if data_fim is None:
        data_fim = date(2030, 1, 1)
    existente = Acordo.query.filter_by(sei=sei).first()
    if existente is None:
        db.session.add(Acordo(
            nome='Acordo Teste BI', sei=sei, epe='EPE Teste', uf=uf,
            data_inicio=date(ano_inicio, 1, 1), data_fim=data_fim,
            valor_cnpq=100000.0, valor_epe=50000.0, unidade_cnpq='DPI',
            situ=situ, desc='teste', capital=0.0, custeio=0.0,
            bolsas=100000.0, siafi='123',
        ))
    else:
        existente.data_fim = data_fim
    db.session.commit()


def test_bi_acordos_sem_login_redireciona(client):
    resp = client.get("/acordos/bi_acordos")
    assert resp.status_code == 302


def test_bi_acordos_logado_responde_200(client, app):
    user_id = _usuario(app, 'teste.biacordos@teste.com', 'usuariobiacordosteste')
    with app.app_context():
        _acordo('00000.000000/2024-51')
    _login(client, user_id)
    resp = client.get("/acordos/bi_acordos")
    assert resp.status_code == 200


def test_bi_acordos_com_filtros_responde_200(client, app):
    user_id = _usuario(app, 'teste.biacordosfiltro@teste.com', 'usuariobiacordosfiltro')
    with app.app_context():
        _acordo('00000.000000/2024-52', situ='Expirado (sem RTF)', uf='SP', ano_inicio=2023)
    _login(client, user_id)
    resp = client.get(
        "/acordos/bi_acordos",
        query_string={'uf': 'SP', 'situacao': 'Expirado (sem RTF)', 'ano': '2023'},
    )
    assert resp.status_code == 200


def test_bi_acordos_vigencia_a_vencer(app):
    """
    Confere que a contagem de "vigência a vencer em 3 meses" inclui um
    acordo cujo fim de vigência está dentro da janela.
    """
    with app.app_context():
        hoje = date.today()
        _acordo('00000.000000/2024-53', data_fim=hoje + timedelta(days=30))

        dados = services.bi_acordos()

        assert dados['vigencia_a_vencer']['3_meses'] >= 1
