# test_core_static.py
#
# Regressão: static_folder era um caminho absoluto fixo do container
# Docker de produção ('/app/project/static'), incompatível com qualquer
# outro ambiente (Codespace etc.) — arquivos em project/static/ existiam
# de verdade no disco, mas qualquer link /static/arquivo respondia 404.
# Corrigido em project/__init__.py pra um caminho relativo ao pacote
# (os.path.join(os.path.dirname(__file__), 'static')). Este teste evita
# que o bug volte se alguém reintroduzir um caminho fixo por engano.

from project import app


def test_arquivo_estatico_conhecido_responde_200(client):
    """coop_nac.png (logo do CNPq, usado no menu) e favicon.ico estão
    versionados em project/static/ — se o static_folder estiver
    configurado errado, essas rotas voltam a responder 404."""
    resp = client.get('/static/coop_nac.png')
    assert resp.status_code == 200
    assert resp.content_type == 'image/png'

    resp_favicon = client.get('/static/favicon.ico')
    assert resp_favicon.status_code == 200


def test_static_folder_aponta_para_pasta_real_do_pacote():
    """static_folder deve resolver pra um caminho que existe no disco,
    não um caminho fixo de container Docker que só existe em produção."""
    import os
    assert os.path.isdir(app.static_folder)
    assert app.static_folder.endswith(os.path.join('project', 'static'))
