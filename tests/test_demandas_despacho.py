# test_demandas_despacho.py
#
# Testes de characterization do grupo Despacho/providência do módulo
# demandas. Cobre um bug real: cria_despacho checava
# `form.necessita_despacho_cg == 1` (comparando o objeto do campo, não
# `.data`) — data_env_despacho nunca era atualizado nesse ponto.

from datetime import datetime
from project import db
from project.models import User, Demanda, Tipos_Demanda, Plano_Trabalho


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


def _usuario(app, email, username, despacha=1):
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if user is None:
            user = User(
                email=email, username=username,
                plaintext_password='senha123', coord='DPI', role='user',
                ativo=1, sversion=1, cargo_func='teste',
                trab_conv=1, trab_acordo=1, trab_instru=1,
                despacha0=despacha, despacha=despacha, despacha2=despacha,
            )
            db.session.add(user)
            db.session.commit()
        return user.id, user.coord


def _demanda_do_usuario(app, user_id, coord, sei):
    with app.app_context():
        demanda = Demanda.query.filter_by(sei=sei).first()
        if demanda is not None:
            return demanda.id

        tipo = Tipos_Demanda.query.filter_by(tipo='Tipo Teste Despacho').first()
        if tipo is None:
            tipo = Tipos_Demanda(tipo='Tipo Teste Despacho', relevancia=1, unidade=coord)
            db.session.add(tipo)
            db.session.commit()

        ativ = Plano_Trabalho.query.filter_by(atividade_sigla='ATVTESTEDESPACHO').first()
        if ativ is None:
            ativ = Plano_Trabalho(
                atividade_sigla='ATVTESTEDESPACHO', atividade_desc='Atividade Teste Despacho',
                natureza='Finalística', meta=10, situa='Ativa', unidade=coord,
            )
            db.session.add(ativ)
            db.session.commit()

        demanda = Demanda(
            programa=ativ.id, sei=sei, convênio='', ano_convênio=None, tipo=tipo.tipo,
            data=datetime.now(), user_id=user_id, titulo='Demanda Teste Despacho', desc='teste',
            necessita_despacho=0, necessita_despacho_cg=0, conclu='0', data_conclu=None,
            urgencia='3', data_env_despacho=None, nota=None, data_verific=None,
        )
        db.session.add(demanda)
        db.session.commit()

        return demanda.id


def test_cria_despacho_get_responde_200(client, app):
    user_id, coord = _usuario(app, 'teste.criadespacho@teste.com', 'usuariocriadespachoteste')
    demanda_id = _demanda_do_usuario(app, user_id, coord, '00000.000000/2024-60')
    _login(client, user_id)
    resp = client.get(f"/demandas/{demanda_id}/cria_despacho")
    assert resp.status_code == 200


def test_cria_despacho_atualiza_data_env_despacho(client, app):
    """
    Regressão do bug: marcar 'necessita_despacho_cg' ao criar um
    despacho deve preencher data_env_despacho (antes nunca acontecia,
    por causa da comparação sem '.data').
    """
    user_id, coord = _usuario(app, 'teste.despachocgbug@teste.com', 'usuariodespachocgbugteste')
    demanda_id = _demanda_do_usuario(app, user_id, coord, '00000.000000/2024-61')
    _login(client, user_id)

    resp = client.post(f"/demandas/{demanda_id}/cria_despacho", data={
        'texto': 'Despacho de teste', 'necessita_despacho_cg': 'y', 'conclu': '0', 'passo': '',
    })
    assert resp.status_code == 302

    with app.app_context():
        demanda = Demanda.query.get(demanda_id)
        assert demanda.necessita_despacho_cg == 1
        assert demanda.data_env_despacho is not None


def test_afere_demanda_get_responde_200(client, app):
    user_id, coord = _usuario(app, 'teste.aferedemanda@teste.com', 'usuarioaferedemandateste')
    demanda_id = _demanda_do_usuario(app, user_id, coord, '00000.000000/2024-62')
    _login(client, user_id)
    resp = client.get(f"/demandas/{demanda_id}/afere_demanda")
    assert resp.status_code == 200


def test_cria_providencia_get_responde_200(client, app):
    user_id, coord = _usuario(app, 'teste.criaprovidencia@teste.com', 'usuariocriaprovidenciateste')
    demanda_id = _demanda_do_usuario(app, user_id, coord, '00000.000000/2024-63')
    _login(client, user_id)
    resp = client.get(f"/demandas/{demanda_id}/cria_providencia")
    assert resp.status_code == 200


def test_cria_providencia_post_nao_quebra(client, app):
    user_id, coord = _usuario(app, 'teste.postprovidencia@teste.com', 'usuariopostprovidenciateste')
    demanda_id = _demanda_do_usuario(app, user_id, coord, '00000.000000/2024-64')
    _login(client, user_id)

    resp = client.post(f"/demandas/{demanda_id}/cria_providencia", data={
        'data_hora': datetime.now().strftime('%d/%m/%Y %H:%M:%S'), 'texto': 'Providencia teste',
        'duracao': '15', 'passo': '', 'necessita_despacho': '', 'conclu': '0', 'agenda': '',
    })
    assert resp.status_code == 302
