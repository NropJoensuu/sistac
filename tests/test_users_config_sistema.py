# test_users_config_sistema.py
#
# Testes dos dois interruptores de sistema por módulo (Convênios, Acordos,
# TED): "Gestão habilitada?" (controla a permissão individual trab_X,
# concedida pelo admin comum por usuário, com cascade-remove quando
# desabilitada) e "BI habilitado?" (novo, só admin master, sistema
# inteiro, sem granularidade por usuário — BI é rota pública, sem login).
#
# Sistema é uma tabela de linha única e persistente (banco de dev), então
# todo teste que altera um campo de Sistema restaura o valor original no
# final (try/finally), para não vazar estado entre testes/execuções.
#
# Nota: nas chamadas a atualizar_config_sistema() abaixo, funcionalidade_conv/
# acordo/instru vão sempre hardcoded em 1, nunca threadadas de 'original' —
# se o ambiente já estiver com algum desses em 0 (outro teste do módulo users
# desabilitou e não restaurou), threadar o valor original faria o
# cascade-remove da própria função zerar trab_conv/trab_acordo/trab_instru de
# TODO usuário do banco, um efeito colateral bem maior que o testado aqui.

from project import db
from project.models import User, Sistema
from project.users import services


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


def _usuario(app, email, username, role='user', coord='DPI', trab_ted=0):
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if user is None:
            user = User(
                email=email, username=username,
                plaintext_password='senha123', coord=coord, role=role,
                ativo=1, sversion=1, cargo_func='teste',
                trab_conv=1, trab_acordo=1, trab_instru=1, trab_ted=trab_ted,
                despacha0=0, despacha=0, despacha2=0,
            )
            db.session.add(user)
            db.session.commit()
        else:
            user.role = role
            user.coord = coord
            user.trab_ted = trab_ted
            db.session.commit()
        return user.id


def _config_atual(app):
    with app.app_context():
        sistema, inst = services.dados_config_sistema()
        return dict(
            nome_sistema=sistema.nome_sistema, descritivo=sistema.descritivo,
            funcionalidade_conv=sistema.funcionalidade_conv,
            funcionalidade_acordo=sistema.funcionalidade_acordo,
            funcionalidade_instru=sistema.funcionalidade_instru,
            funcionalidade_ted=sistema.funcionalidade_ted,
            bi_conv=sistema.bi_conv, bi_acordo=sistema.bi_acordo, bi_ted=sistema.bi_ted,
            cod_inst=inst.cod_inst, carga_auto=sistema.carga_auto,
        )


def test_cascade_remove_trab_ted_ao_desabilitar_gestao_ted(app):
    """
    Ao desligar a Gestão de TED no sistema, todo usuário que tinha
    trab_ted concedido perde a permissão — mesmo padrão já usado para
    trab_conv/trab_acordo em atualizar_config_sistema.
    """
    with app.app_context():
        original = _config_atual(app)
        admin_id = _usuario(app, 'admin.cascadeted@teste.com', 'admincascadeted', role='admin_master', coord='COPES')
        user_id = _usuario(app, 'user.cascadeted@teste.com', 'usercascadeted', trab_ted=1)
        assert User.query.get(user_id).trab_ted == 1

        try:
            services.atualizar_config_sistema(
                nome_sistema=original['nome_sistema'], descritivo=original['descritivo'],
                # forçado a 1 (não threadado de 'original' — ver nota no topo do arquivo)
                funcionalidade_conv=1, funcionalidade_acordo=1, funcionalidade_instru=1,
                cod_inst=original['cod_inst'], carga_auto=original['carga_auto'],
                usuario_id=admin_id,
                funcionalidade_ted=0,
                bi_conv=original['bi_conv'], bi_acordo=original['bi_acordo'], bi_ted=original['bi_ted'],
            )
            assert User.query.get(user_id).trab_ted == 0
        finally:
            services.atualizar_config_sistema(
                nome_sistema=original['nome_sistema'], descritivo=original['descritivo'],
                # forçado a 1 (não threadado de 'original' — ver nota no topo do arquivo)
                funcionalidade_conv=1, funcionalidade_acordo=1, funcionalidade_instru=1,
                cod_inst=original['cod_inst'], carga_auto=original['carga_auto'],
                usuario_id=admin_id,
                funcionalidade_ted=original['funcionalidade_ted'],
                bi_conv=original['bi_conv'], bi_acordo=original['bi_acordo'], bi_ted=original['bi_ted'],
            )


def test_desligar_bi_conv_nao_afeta_permissao_individual_trab_conv(app):
    """
    Distinção-chave da nota: bi_conv é um interruptor só de sistema, sem
    permissão individual — desligá-lo não cascade-remove trab_conv de
    ninguém (ao contrário de funcionalidade_conv, que é a Gestão).
    """
    with app.app_context():
        original = _config_atual(app)
        admin_id = _usuario(app, 'admin.bicascade@teste.com', 'adminbicascade', role='admin_master', coord='COPES')
        user_id = _usuario(app, 'user.bicascade@teste.com', 'userbicascade')
        assert User.query.get(user_id).trab_conv == 1

        try:
            services.atualizar_config_sistema(
                nome_sistema=original['nome_sistema'], descritivo=original['descritivo'],
                # forçado a 1 (não threadado de 'original' — ver nota no topo do arquivo)
                funcionalidade_conv=1, funcionalidade_acordo=1, funcionalidade_instru=1,
                cod_inst=original['cod_inst'], carga_auto=original['carga_auto'],
                usuario_id=admin_id,
                funcionalidade_ted=original['funcionalidade_ted'],
                bi_conv=0, bi_acordo=original['bi_acordo'], bi_ted=original['bi_ted'],
            )
            assert User.query.get(user_id).trab_conv == 1
        finally:
            services.atualizar_config_sistema(
                nome_sistema=original['nome_sistema'], descritivo=original['descritivo'],
                # forçado a 1 (não threadado de 'original' — ver nota no topo do arquivo)
                funcionalidade_conv=1, funcionalidade_acordo=1, funcionalidade_instru=1,
                cod_inst=original['cod_inst'], carga_auto=original['carga_auto'],
                usuario_id=admin_id,
                funcionalidade_ted=original['funcionalidade_ted'],
                bi_conv=original['bi_conv'], bi_acordo=original['bi_acordo'], bi_ted=original['bi_ted'],
            )


def test_admin_comum_so_concede_trab_ted_com_gestao_ted_habilitada(app):
    """
    atualizar_usuario_admin só grava trab_ted quando
    Sistema.funcionalidade_ted == 1 (mesmo guard de trab_conv/trab_acordo/
    trab_instru) — o admin comum nunca controla isso além desse limite.
    """
    with app.app_context():
        original = _config_atual(app)
        admin_id = _usuario(app, 'admin.guardted@teste.com', 'adminguardted', role='admin', coord='DPI')
        alvo_id = _usuario(app, 'alvo.guardted@teste.com', 'alvoguardted', coord='DPI')

        try:
            # com Gestão de TED desligada no sistema, tentar conceder trab_ted é ignorado
            services.atualizar_config_sistema(
                nome_sistema=original['nome_sistema'], descritivo=original['descritivo'],
                # forçado a 1 (não threadado de 'original' — ver nota no topo do arquivo)
                funcionalidade_conv=1, funcionalidade_acordo=1, funcionalidade_instru=1,
                cod_inst=original['cod_inst'], carga_auto=original['carga_auto'],
                usuario_id=admin_id, funcionalidade_ted=0,
                bi_conv=original['bi_conv'], bi_acordo=original['bi_acordo'], bi_ted=original['bi_ted'],
            )
            admin = User.query.get(admin_id)
            services.atualizar_usuario_admin(
                user_id=alvo_id, coord='DPI', despacha0=0, despacha=0, despacha2=0, ativo=1,
                role='user', cargo_func='teste', trab_conv=1, trab_acordo=1, trab_instru=1,
                admin_atual=admin, trab_ted=1,
            )
            assert User.query.get(alvo_id).trab_ted != 1

            # com Gestão de TED ligada, a concessão passa a funcionar
            services.atualizar_config_sistema(
                nome_sistema=original['nome_sistema'], descritivo=original['descritivo'],
                # forçado a 1 (não threadado de 'original' — ver nota no topo do arquivo)
                funcionalidade_conv=1, funcionalidade_acordo=1, funcionalidade_instru=1,
                cod_inst=original['cod_inst'], carga_auto=original['carga_auto'],
                usuario_id=admin_id, funcionalidade_ted=1,
                bi_conv=original['bi_conv'], bi_acordo=original['bi_acordo'], bi_ted=original['bi_ted'],
            )
            admin = User.query.get(admin_id)
            services.atualizar_usuario_admin(
                user_id=alvo_id, coord='DPI', despacha0=0, despacha=0, despacha2=0, ativo=1,
                role='user', cargo_func='teste', trab_conv=1, trab_acordo=1, trab_instru=1,
                admin_atual=admin, trab_ted=1,
            )
            assert User.query.get(alvo_id).trab_ted == 1
        finally:
            services.atualizar_config_sistema(
                nome_sistema=original['nome_sistema'], descritivo=original['descritivo'],
                # forçado a 1 (não threadado de 'original' — ver nota no topo do arquivo)
                funcionalidade_conv=1, funcionalidade_acordo=1, funcionalidade_instru=1,
                cod_inst=original['cod_inst'], carga_auto=original['carga_auto'],
                usuario_id=admin_id,
                funcionalidade_ted=original['funcionalidade_ted'],
                bi_conv=original['bi_conv'], bi_acordo=original['bi_acordo'], bi_ted=original['bi_ted'],
            )


def test_bi_convenios_acessivel_sem_login_quando_habilitado(client, app):
    """
    Sistema é linha única persistente (banco de dev) — outros testes do
    módulo users (ex: test_users_admin.py) podem ter deixado bi_conv
    desligado antes deste rodar, então o estado é forçado aqui, não
    assumido, e restaurado ao final.
    """
    with app.app_context():
        sistema = Sistema.query.first()
        original = sistema.bi_conv
        sistema.bi_conv = 1
        db.session.commit()
    try:
        resp = client.get('/convenios/bi_convenios')
        assert resp.status_code == 200
    finally:
        with app.app_context():
            sistema = Sistema.query.first()
            sistema.bi_conv = original
            db.session.commit()


def test_bi_acordos_acessivel_sem_login_quando_habilitado(client, app):
    with app.app_context():
        sistema = Sistema.query.first()
        original = sistema.bi_acordo
        sistema.bi_acordo = 1
        db.session.commit()
    try:
        resp = client.get('/acordos/bi_acordos')
        assert resp.status_code == 200
    finally:
        with app.app_context():
            sistema = Sistema.query.first()
            sistema.bi_acordo = original
            db.session.commit()


def test_bi_convenios_indisponivel_sem_login_quando_desabilitado(app):
    with app.app_context():
        sistema = Sistema.query.first()
        original = sistema.bi_conv
        sistema.bi_conv = 0
        db.session.commit()
    try:
        with app.test_client() as client_sem_sessao:
            resp = client_sem_sessao.get('/convenios/bi_convenios')
            assert resp.status_code == 200
            assert 'indispon' in resp.get_data(as_text=True).lower()
    finally:
        with app.app_context():
            sistema = Sistema.query.first()
            sistema.bi_conv = original
            db.session.commit()


def test_bi_acordos_indisponivel_sem_login_quando_desabilitado(app):
    with app.app_context():
        sistema = Sistema.query.first()
        original = sistema.bi_acordo
        sistema.bi_acordo = 0
        db.session.commit()
    try:
        with app.test_client() as client_sem_sessao:
            resp = client_sem_sessao.get('/acordos/bi_acordos')
            assert resp.status_code == 200
            assert 'indispon' in resp.get_data(as_text=True).lower()
    finally:
        with app.app_context():
            sistema = Sistema.query.first()
            sistema.bi_acordo = original
            db.session.commit()


def test_admin_reg_ver_exige_admin_master_mesmo_para_os_toggles_de_bi(client, app):
    """
    Confirma que os campos novos (funcionalidade_ted, bi_conv, bi_acordo,
    bi_ted) vivem só na tela restrita a admin_master — admin comum
    continua barrado, igual já valia para os campos existentes.
    """
    user_id = _usuario(app, 'teste.regverbi@teste.com', 'usuarioregverbi', role='admin')
    _login(client, user_id)
    resp = client.get('/admin_reg_ver')
    assert resp.status_code == 403


def test_nenhuma_rota_de_bi_depende_de_sessao_de_usuario(app):
    """BI não exige login — confirma que uma requisição totalmente sem
    sessão (nenhum cookie, nenhum usuário) chega às duas rotas de BI."""
    with app.test_client() as client_anonimo:
        assert client_anonimo.get('/convenios/bi_convenios').status_code == 200
        assert client_anonimo.get('/acordos/bi_acordos').status_code == 200
