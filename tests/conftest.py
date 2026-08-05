# conftest.py
#
# Fixtures compartilhadas pelos testes. Por enquanto, os testes rodam
# contra o banco de estudo local (sistac_dev) já criado via migrations.
# Isso é intencional nesta fase inicial (Fase 1): o objetivo é criar uma
# "rede de segurança" que confirme o comportamento atual da aplicação,
# antes de qualquer refatoração. Uma evolução futura (Fase 2+) será usar
# um banco de teste isolado/efêmero em vez do banco de desenvolvimento.
#
# Infraestrutura de proteção contra efeito colateral em dado
# persistente/singleton (ver proposta_melhorias.md, item 8): já
# aconteceu de verdade um teste zerar Gestão/BI e permissões da conta
# real `igorc@cnpq.br` (POST minimalista em admin_reg_ver deixando todo
# BooleanField desmarcado), e cargaTED() (chamada de verdade nos testes
# de carga, só a requisição HTTP é mockada) apagar os TEDs reais e
# substituir por dado de teste a cada rodada da suíte. As duas fixtures
# abaixo (`protege_dados_persistentes_singleton`, autouse, e
# `preserva_tabelas_ted`, opt-in) tiram um snapshot antes e restauram
# depois, independente do teste ter passado ou falhado.

import pytest
from project import app as flask_app, db
from project.models import Sistema, RefSICONV, User, TED_PlanoAcao, TED_Programa, TED_TermoExecucao


@pytest.fixture()
def app():
    flask_app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
    })
    yield flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


def _snapshot_row(instancia):
    """Copia todas as colunas de uma linha (modelo SQLAlchemy) num dict simples, pra restaurar depois."""
    return {c.name: getattr(instancia, c.name) for c in instancia.__table__.columns}


def _restaura_row(instancia, snapshot):
    for campo, valor in snapshot.items():
        setattr(instancia, campo, valor)


# Conta real usada como "usuário admin master" em vários testes de
# characterization — precisa existir com role/permissões corretas pra
# esses testes funcionarem, mas seus campos já foram zerados por engano
# no passado por um teste que não restaurava o estado.
_EMAIL_USUARIO_REAL_PROTEGIDO = 'igorc@cnpq.br'


@pytest.fixture(autouse=True)
def protege_dados_persistentes_singleton():
    """
    Protege a linha única de Sistema, a linha única de RefSICONV, e a
    conta real `igorc@cnpq.br` contra efeito colateral de testes que
    escrevem nesses registros sem restaurar o estado original (ver
    proposta_melhorias.md, item 8).

    Autouse: roda ao redor de todo teste. Os testes que legitimamente
    querem alterar esses dados durante a execução (ex:
    test_users_config_sistema.py) continuam funcionando normalmente —
    só o estado final é que sempre volta ao original, mesmo se o teste
    falhar no meio.
    """
    with flask_app.app_context():
        sistema = Sistema.query.first()
        snap_sistema = _snapshot_row(sistema) if sistema else None

        ref_siconv = RefSICONV.query.first()
        snap_ref_siconv = _snapshot_row(ref_siconv) if ref_siconv else None

        usuario_real = User.query.filter_by(email=_EMAIL_USUARIO_REAL_PROTEGIDO).first()
        snap_usuario_real = _snapshot_row(usuario_real) if usuario_real else None

    yield

    with flask_app.app_context():
        if snap_sistema is not None:
            sistema = Sistema.query.first()
            if sistema is not None:
                _restaura_row(sistema, snap_sistema)

        if snap_ref_siconv is not None:
            ref_siconv = RefSICONV.query.first()
            if ref_siconv is not None:
                _restaura_row(ref_siconv, snap_ref_siconv)

        if snap_usuario_real is not None:
            usuario_real = User.query.filter_by(email=_EMAIL_USUARIO_REAL_PROTEGIDO).first()
            if usuario_real is not None:
                _restaura_row(usuario_real, snap_usuario_real)

        db.session.commit()


@pytest.fixture()
def preserva_tabelas_ted():
    """
    Snapshot e restauração das 3 tabelas-espelho de TED (TED_PlanoAcao,
    TED_Programa, TED_TermoExecucao), pra uso em testes que chamam
    cargaTED() de verdade (só a chamada HTTP é mockada — a função em si
    faz delete-and-reload real nessas tabelas). Sem isso, cada rodada
    da suíte apaga os TEDs reais carregados da API do TransfereGov e
    substitui por dado de teste (ver proposta_melhorias.md, item 8).

    Não é autouse (ao contrário de protege_dados_persistentes_singleton)
    porque snapshot/restore de 3 tabelas inteiras é mais caro que as
    poucas linhas únicas protegidas ali — só os testes que realmente
    chamam cargaTED() de verdade precisam pedir esta fixture
    explicitamente.
    """
    with flask_app.app_context():
        snap_programas = [_snapshot_row(p) for p in TED_Programa.query.all()]
        snap_planos = [_snapshot_row(p) for p in TED_PlanoAcao.query.all()]
        snap_termos = [_snapshot_row(t) for t in TED_TermoExecucao.query.all()]

    yield

    with flask_app.app_context():
        TED_TermoExecucao.query.delete()
        TED_PlanoAcao.query.delete()
        TED_Programa.query.delete()
        db.session.commit()

        for dados in snap_programas:
            db.session.add(TED_Programa(**dados))
        db.session.commit()

        for dados in snap_planos:
            db.session.add(TED_PlanoAcao(**dados))
        db.session.commit()

        for dados in snap_termos:
            db.session.add(TED_TermoExecucao(**dados))
        db.session.commit()
