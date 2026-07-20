# test_acordos_nucleo.py
#
# Testes de characterization do grupo Acordo (núcleo) do módulo
# acordos — último grupo, fecha a refatoração completa do módulo.
#
# Cobre bugs reais encontrados durante a refatoração:
# 1. lista_acordos quebrava com TypeError ao comparar/subtrair
#    datetime.date com datetime.datetime ("hoje" era construído com
#    dt.today() em vez de date.today()) — bug relatado pelo usuário ao
#    tentar registrar um acordo.
# 2. criar_acordo gravava valor_epe = valor_cnpq (erro de copiar-colar),
#    fazendo o valor da EPE ser sempre sobrescrito.
# 3. excluir_acordo quebrava ao excluir um acordo com programas ou
#    capital/custeio associados (db.session.delete() chamado com uma
#    lista em vez de um único objeto).
# 4. acordo_demandas quebrava com AttributeError para acordo inexistente.

from datetime import date
from project import db
from project.models import User, Acordo, Programa_CNPq
from project.acordos import services


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


def _acordo(app):
    with app.app_context():
        acordo = Acordo.query.filter_by(sei='00000.000000/2024-22').first()
        if acordo is None:
            acordo = Acordo(
                nome='Acordo Teste Nucleo', sei='00000.000000/2024-22', epe='EPE Teste', uf='DF',
                data_inicio=date(2024, 1, 1), data_fim=date(2026, 12, 31), valor_cnpq=100000.0,
                valor_epe=50000.0, unidade_cnpq='DPI', situ='Em execução', desc='teste',
                capital=0.0, custeio=0.0, bolsas=100000.0, siafi='123',
            )
            db.session.add(acordo)
            db.session.commit()
        return acordo.id


def test_lista_acordos_todos_nao_quebra(client, app):
    """Regressão do bug relatado: TypeError ao subtrair date de datetime."""
    user_id = _usuario(app, 'teste.listaacordos@teste.com', 'usuariolistaacordosteste')
    _acordo(app)
    _login(client, user_id)
    resp = client.get("/acordos/todos/*/lista_acordos")
    assert resp.status_code == 200


def test_lista_acordos_em_execucao_nao_quebra(client, app):
    user_id = _usuario(app, 'teste.listaacordos2@teste.com', 'usuariolistaacordos2teste')
    _login(client, user_id)
    resp = client.get("/acordos/em execução/*/lista_acordos")
    assert resp.status_code == 200


def test_criar_acordo_nao_confunde_valor_epe_com_cnpq(app):
    """Regressão do bug de copiar-colar: valor_epe não pode ser igual a valor_cnpq quando são diferentes."""
    with app.app_context():
        user = User.query.filter_by(email='admin@teste.com').first()
        if user is None:
            user = User(
                email='admin@teste.com', username='adminteste',
                plaintext_password='senha123', coord='DPI', role='admin',
                ativo=1, sversion=1, cargo_func='teste',
                trab_conv=1, trab_acordo=1, trab_instru=1,
                despacha0=0, despacha=0, despacha2=0,
            )
            db.session.add(user)
            db.session.commit()

        acordo, _ = services.criar_acordo(
            nome='Acordo Teste ValorEPE Regressao', desc='teste', sei='00000.000000/2024-11',
            epe='EPE', uf='DF', data_inicio=date(2024, 1, 1), data_fim=date(2026, 12, 31),
            valor_cnpq_str='100.000,00', valor_epe_str='50.000,00', unid='DPI',
            situacao='Assinado', capital_str='0,00', custeio_str='0,00', bolsas_str='0,00',
            siafi='888', usuario_id=user.id,
        )

        assert acordo.valor_cnpq == 100000.0
        assert acordo.valor_epe == 50000.0


def test_excluir_acordo_com_programa_associado_nao_quebra(app):
    """Regressão do bug: db.session.delete() com lista em vez de objeto único."""
    with app.app_context():
        user = User.query.filter_by(email='admin@teste.com').first()

        acordo = Acordo(
            nome='Acordo Teste Exclusao', desc='teste', sei='00000.000000/2024-00',
            epe='EPE', uf='DF', data_inicio=date(2024, 1, 1), data_fim=date(2026, 12, 31),
            valor_cnpq=1000.0, valor_epe=1000.0, unidade_cnpq='DPI', situ='Assinado',
            capital=0.0, custeio=0.0, bolsas=0.0, siafi='777',
        )
        db.session.add(acordo)
        db.session.commit()

        prog = Programa_CNPq.query.filter_by(COD_PROGRAMA='PRGEXCLUSAOTESTE').first()
        if prog is None:
            prog = Programa_CNPq(
                COD_PROGRAMA='PRGEXCLUSAOTESTE', NOME_PROGRAMA='Programa Exclusao Teste',
                SIGLA_PROGRAMA='PET', COORD='DPI',
            )
            db.session.add(prog)
            db.session.commit()

        services.associar_programas_ao_acordo(acordo.id, [str(prog.ID_PROGRAMA)])

        # não deve levantar exceção
        services.excluir_acordo(acordo.id, user.id)

        assert Acordo.query.get(acordo.id) is None


def test_acordo_demandas_inexistente_retorna_404(client):
    """Regressão do bug: acordo inexistente deve retornar 404, não quebrar."""
    resp = client.get("/acordos/999999/acordo_demandas")
    assert resp.status_code == 404


def test_acordo_demandas_existente_responde_200(client, app):
    acordo_id = _acordo(app)
    resp = client.get(f"/acordos/{acordo_id}/acordo_demandas")
    assert resp.status_code == 200


def test_update_acordo_responde_200(client, app):
    user_id = _usuario(app, 'teste.updateacordo@teste.com', 'usuarioupdateacordoteste')
    acordo_id = _acordo(app)
    _login(client, user_id)
    resp = client.get(f"/acordos/{acordo_id}/todos/update")
    assert resp.status_code == 200


def test_cria_acordo_get_responde_200(client, app):
    user_id = _usuario(app, 'teste.criaacordo@teste.com', 'usuariocriaacordoteste')
    _login(client, user_id)
    resp = client.get("/acordos/criar")
    assert resp.status_code == 200
