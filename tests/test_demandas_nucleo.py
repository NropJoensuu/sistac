# test_demandas_nucleo.py
#
# Testes de characterization do grupo Demanda (núcleo) do módulo
# demandas — o maior grupo do maior módulo do projeto. Cobre dois
# bugs reais:
# 1. demanda() quebrava com AttributeError para qualquer ID de
#    demanda inexistente (a consulta não checava se retornou None).
# 2. update_demanda gravava ano_convênio='' quando o campo de
#    convênio era deixado em branco — a coluna é Integer, então
#    quebrava com DataError ao salvar.

from datetime import datetime
from project import db
from project.models import User, Demanda, Tipos_Demanda, Plano_Trabalho


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
                despacha0=1, despacha=1, despacha2=1,
            )
            db.session.add(user)
            db.session.commit()
        return user.id, user.coord


def _demanda_do_usuario(app, user_id, coord, sei):
    with app.app_context():
        demanda = Demanda.query.filter_by(sei=sei).first()
        if demanda is not None:
            return demanda.id, demanda.programa, demanda.tipo

        tipo = Tipos_Demanda.query.filter_by(tipo='Tipo Teste Nucleo').first()
        if tipo is None:
            tipo = Tipos_Demanda(tipo='Tipo Teste Nucleo', relevancia=1, unidade=coord)
            db.session.add(tipo)
            db.session.commit()

        ativ = Plano_Trabalho.query.filter_by(atividade_sigla='ATVTESTENUCLEO').first()
        if ativ is None:
            ativ = Plano_Trabalho(
                atividade_sigla='ATVTESTENUCLEO', atividade_desc='Atividade Teste Nucleo',
                natureza='Finalística', meta=10, situa='Ativa', unidade=coord,
            )
            db.session.add(ativ)
            db.session.commit()

        demanda = Demanda(
            programa=ativ.id, sei=sei, convênio='', ano_convênio=None, tipo=tipo.tipo,
            data=datetime.now(), user_id=user_id, titulo='Demanda Teste Núcleo', desc='teste',
            necessita_despacho=0, necessita_despacho_cg=0, conclu='0', data_conclu=None,
            urgencia='3', data_env_despacho=None, nota=None, data_verific=None,
        )
        db.session.add(demanda)
        db.session.commit()

        return demanda.id, ativ.id, tipo.tipo


def test_demanda_inexistente_retorna_404(client):
    """Regressão do bug: demanda inexistente deve retornar 404, não quebrar."""
    resp = client.get("/demandas/demanda/999999")
    assert resp.status_code == 404


def test_demanda_existente_responde_200(client, app):
    user_id, coord = _usuario(app, 'teste.demandanucleo@teste.com', 'usuariodemandanucleoteste')
    demanda_id, _, _ = _demanda_do_usuario(app, user_id, coord, '00000.000000/2024-70')
    resp = client.get(f"/demandas/demanda/{demanda_id}")
    assert resp.status_code == 200


def test_verifica_redireciona(client, app):
    user_id, coord = _usuario(app, 'teste.verificademanda@teste.com', 'usuarioverificademandateste')
    demanda_id, _, _ = _demanda_do_usuario(app, user_id, coord, '00000.000000/2024-71')
    resp = client.get(f"/demandas/{demanda_id}/verifica")
    assert resp.status_code == 302


def test_update_demanda_com_convenio_em_branco_nao_quebra(client, app):
    """
    Regressão do bug: atualizar uma demanda com o campo de convênio em
    branco não deve quebrar com DataError (ano_convênio='' numa
    coluna Integer).
    """
    user_id, coord = _usuario(app, 'teste.updatedemandanucleo@teste.com', 'usuarioupdatedemandanucleoteste')
    demanda_id, ativ_id, tipo = _demanda_do_usuario(app, user_id, coord, '00000.000000/2024-72')
    _login(client, user_id)

    resp = client.post(f"/demandas/{demanda_id}/update_demanda", data={
        'atividade': str(ativ_id), 'sei': '00000.000000/2024-72', 'convênio': '', 'ano_convênio': '',
        'tipo': tipo, 'titulo': 'Titulo Atualizado', 'desc': 'desc atualizada',
        'tipo_despacho': '0', 'conclu': '0', 'urgencia': '3',
    })
    assert resp.status_code == 302


def test_transfer_demanda_get_responde_200(client, app):
    user_id, coord = _usuario(app, 'teste.transferdemanda@teste.com', 'usuariotransferdemandateste')
    demanda_id, _, _ = _demanda_do_usuario(app, user_id, coord, '00000.000000/2024-73')
    _login(client, user_id)
    resp = client.get(f"/demandas/{demanda_id}/transfer_demanda")
    assert resp.status_code == 200


def test_admin_altera_demanda_get_responde_200(client, app):
    with app.app_context():
        admin = User.query.filter_by(email='admin@teste.com').first()
        admin_id = admin.id
        coord = admin.coord

    demanda_id, _, _ = _demanda_do_usuario(app, admin_id, coord, '00000.000000/2024-74')
    _login(client, admin_id)
    resp = client.get(f"/demandas/{demanda_id}/admin_altera_demanda")
    assert resp.status_code == 200
