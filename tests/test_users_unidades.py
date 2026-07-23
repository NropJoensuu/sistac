# test_users_unidades.py
#
# Testes do CRUD de unidades (Coords) restrito ao admin master, e da
# função de transferência de unidade (alternativa deliberada à
# exclusão direta, que poderia deixar registros órfãos já que a sigla
# da coordenação é salva como texto solto em várias tabelas, não como
# chave estrangeira).

from datetime import date
from project import db
from project.models import User, Coords, Tipos_Demanda, Plano_Trabalho, Acordo
from project.users import services


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


def _admin_comum(app):
    with app.app_context():
        user = User.query.filter_by(email='teste.unidadesadmincomum@teste.com').first()
        if user is None:
            user = User(
                email='teste.unidadesadmincomum@teste.com', username='usuariounidadesadmincomumteste',
                plaintext_password='senha123', coord='DPI', role='admin',
                ativo=1, sversion=1, cargo_func='teste',
                trab_conv=1, trab_acordo=1, trab_instru=1,
                despacha0=0, despacha=0, despacha2=0,
            )
            db.session.add(user)
            db.session.commit()
        return user.id


def _admin_master(app):
    with app.app_context():
        user = User.query.filter_by(email='teste.unidadesadminmaster@teste.com').first()
        if user is None:
            user = User(
                email='teste.unidadesadminmaster@teste.com', username='usuariounidadesadminmasterteste',
                plaintext_password='senha123', coord='COPES', role='admin_master',
                ativo=1, sversion=1, cargo_func='teste',
                trab_conv=1, trab_acordo=1, trab_instru=1,
                despacha0=0, despacha=0, despacha2=0,
            )
            db.session.add(user)
            db.session.commit()
        return user.id


def _unidades_teste(app):
    with app.app_context():
        for sigla in ['UNIDORIGEMTESTE', 'UNIDDESTINOTESTE']:
            if not Coords.query.filter_by(sigla=sigla).first():
                db.session.add(Coords(sigla=sigla, pai=''))
        db.session.commit()


def test_admin_insere_coord_bloqueado_para_admin_comum(client, app):
    user_id = _admin_comum(app)
    _login(client, user_id)
    resp = client.get("/admin_insere_coord")
    assert resp.status_code == 403


def test_admin_insere_coord_permitido_para_admin_master(client, app):
    user_id = _admin_master(app)
    _login(client, user_id)
    resp = client.get("/admin_insere_coord")
    assert resp.status_code == 200


def test_admin_view_coords_continua_liberado_para_admin_comum(client, app):
    """A visualização das unidades continua aberta para admin comum — só o CRUD é restrito."""
    user_id = _admin_comum(app)
    _login(client, user_id)
    resp = client.get("/admin_view_coords")
    assert resp.status_code == 200


def test_admin_transfere_unidade_bloqueado_para_admin_comum(client, app):
    user_id = _admin_comum(app)
    _login(client, user_id)
    resp = client.get("/admin_transfere_unidade")
    assert resp.status_code == 403


def test_transferir_unidade_move_registros_de_varias_tabelas(app):
    """
    Regressão: transferir uma unidade deve mover as referências em
    TODAS as tabelas que guardam a sigla da coordenação como texto
    (usuários, tipos de demanda, plano de trabalho, acordos, unidades-
    filhas), e excluir a unidade de origem ao final.
    """
    admin_master_id = _admin_master(app)
    _unidades_teste(app)

    with app.app_context():
        if not Coords.query.filter_by(sigla='UNIDFILHATESTE2').first():
            db.session.add(Coords(sigla='UNIDFILHATESTE2', pai='UNIDORIGEMTESTE'))

        if not User.query.filter_by(email='teste.transferencia2@teste.com').first():
            db.session.add(User(
                email='teste.transferencia2@teste.com', username='usuariotransferencia2teste',
                plaintext_password='senha123', coord='UNIDORIGEMTESTE', role='user',
                ativo=1, sversion=1, cargo_func='teste',
                trab_conv=1, trab_acordo=1, trab_instru=1, despacha0=0, despacha=0, despacha2=0,
            ))

        if not Tipos_Demanda.query.filter_by(tipo='Tipo Teste Transferencia2').first():
            db.session.add(Tipos_Demanda(tipo='Tipo Teste Transferencia2', relevancia=1, unidade='UNIDORIGEMTESTE'))

        if not Plano_Trabalho.query.filter_by(atividade_sigla='ATVTRANSFERENCIA2').first():
            db.session.add(Plano_Trabalho(
                atividade_sigla='ATVTRANSFERENCIA2', atividade_desc='teste', natureza='Finalística',
                meta=10, situa='Ativa', unidade='UNIDORIGEMTESTE',
            ))

        if not Acordo.query.filter_by(sei='00000.000000/2024-50').first():
            db.session.add(Acordo(
                nome='Acordo Teste Transferencia', desc='teste', sei='00000.000000/2024-50', epe='EPE',
                uf='DF', data_inicio=date(2024, 1, 1), data_fim=date(2026, 12, 31), valor_cnpq=1000.0,
                valor_epe=1000.0, unidade_cnpq='UNIDORIGEMTESTE', situ='Assinado', capital=0.0,
                custeio=0.0, bolsas=0.0, siafi='999',
            ))

        db.session.commit()

        resultado, erro = services.transferir_unidade('UNIDORIGEMTESTE', 'UNIDDESTINOTESTE', admin_master_id)

        assert erro is None
        assert Coords.query.filter_by(sigla='UNIDORIGEMTESTE').first() is None
        assert User.query.filter_by(email='teste.transferencia2@teste.com').first().coord == 'UNIDDESTINOTESTE'
        assert Tipos_Demanda.query.filter_by(tipo='Tipo Teste Transferencia2').first().unidade == 'UNIDDESTINOTESTE'
        assert Plano_Trabalho.query.filter_by(atividade_sigla='ATVTRANSFERENCIA2').first().unidade == 'UNIDDESTINOTESTE'
        assert Acordo.query.filter_by(sei='00000.000000/2024-50').first().unidade_cnpq == 'UNIDDESTINOTESTE'
        assert Coords.query.filter_by(sigla='UNIDFILHATESTE2').first().pai == 'UNIDDESTINOTESTE'


def test_transferir_unidade_recusa_origem_igual_destino(app):
    admin_master_id = _admin_master(app)
    _unidades_teste(app)

    with app.app_context():
        resultado, erro = services.transferir_unidade('UNIDORIGEMTESTE', 'UNIDORIGEMTESTE', admin_master_id)
        assert erro is not None
