# test_demandas_criacao.py
#
# Testes de characterization do grupo Criação de demanda do módulo
# demandas. Cobre um bug real e severo, pré-existente no código
# original: ano_convênio='' era inserido numa coluna Integer,
# quebrando com DataError toda vez que uma demanda era criada pelo
# fluxo principal (tanto via SEI livre quanto via acordo/convênio).

from project import db
from project.models import User, Tipos_Demanda, Plano_Trabalho


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
                despacha0=1, despacha=1, despacha2=1,
            )
            db.session.add(user)
            db.session.commit()
        return user.id, user.coord


def _tipo_e_atividade(app, coord):
    with app.app_context():
        tipo = Tipos_Demanda.query.filter_by(tipo='Tipo Teste Criacao').first()
        if tipo is None:
            tipo = Tipos_Demanda(tipo='Tipo Teste Criacao', relevancia=1, unidade=coord)
            db.session.add(tipo)
            db.session.commit()

        ativ = Plano_Trabalho.query.filter_by(atividade_sigla='ATVTESTECRIACAO').first()
        if ativ is None:
            ativ = Plano_Trabalho(
                atividade_sigla='ATVTESTECRIACAO', atividade_desc='Atividade Teste Criacao',
                natureza='Finalística', meta=10, situa='Ativa', unidade=coord,
            )
            db.session.add(ativ)
            db.session.commit()

        return tipo.tipo, ativ.id


def test_cria_demanda_get_responde_200(client, app):
    user_id, coord = _usuario(app, 'teste.criademanda@teste.com', 'usuariocriademandateste')
    _login(client, user_id)
    resp = client.get("/demandas/criar")
    assert resp.status_code == 200


def test_confirma_cria_demanda_get_responde_200(client, app):
    user_id, coord = _usuario(app, 'teste.confirmacriademanda@teste.com', 'usuarioconfirmacriademandateste')
    tipo, ativ_id = _tipo_e_atividade(app, coord)
    _login(client, user_id)
    resp = client.get(f"/demandas/00000.000000_2024-90/{tipo}/OK/confirma_criar")
    assert resp.status_code == 200


def test_criar_demanda_concluida_nao_quebra(client, app):
    """
    Regressão do bug: criar uma demanda já marcada como concluída
    (que dispara a notificação de e-mail) não deve quebrar com
    DataError por causa de ano_convênio=''.
    """
    user_id, coord = _usuario(app, 'teste.demandaconcluida@teste.com', 'usuariodemandaconcluidateste')
    tipo, ativ_id = _tipo_e_atividade(app, coord)
    _login(client, user_id)

    resp = client.post(f"/demandas/00000.000000_2024-89/{tipo}/OK/confirma_criar", data={
        'atividade': str(ativ_id), 'titulo': 'Demanda Teste Concluida', 'desc': 'teste',
        'conclu': '1', 'urgencia': '3', 'necessita_despacho': '', 'convênio': '',
    })
    assert resp.status_code == 302


def test_criar_demanda_necessita_despacho_nao_quebra(client, app):
    """
    Regressão do bug: criar uma demanda que necessita despacho (que
    dispara a notificação de e-mail) não deve quebrar.
    """
    user_id, coord = _usuario(app, 'teste.demandadespacho@teste.com', 'usuariodemandadespachoteste')
    tipo, ativ_id = _tipo_e_atividade(app, coord)
    _login(client, user_id)

    resp = client.post(f"/demandas/00000.000000_2024-88/{tipo}/OK/confirma_criar", data={
        'atividade': str(ativ_id), 'titulo': 'Demanda Teste Despacho', 'desc': 'teste',
        'conclu': '0', 'urgencia': '3', 'necessita_despacho': 'y', 'convênio': '',
    })
    assert resp.status_code == 302


def test_acordo_convenio_demanda_get_responde_200(client, app):
    user_id, coord = _usuario(app, 'teste.acordoconveniodemanda@teste.com', 'usuarioacordoconveniodemandateste')
    tipo, ativ_id = _tipo_e_atividade(app, coord)
    _login(client, user_id)
    resp = client.get("/demandas/ATVTESTECRIACAO/00000.000000_2024-87/0/2024/criar")
    assert resp.status_code == 200
