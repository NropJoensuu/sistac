# conftest.py
#
# Fixtures compartilhadas pelos testes. Por enquanto, os testes rodam
# contra o banco de estudo local (sistac_dev) já criado via migrations.
# Isso é intencional nesta fase inicial (Fase 1): o objetivo é criar uma
# "rede de segurança" que confirme o comportamento atual da aplicação,
# antes de qualquer refatoração. Uma evolução futura (Fase 2+) será usar
# um banco de teste isolado/efêmero em vez do banco de desenvolvimento.

import pytest
from project import app as flask_app


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
