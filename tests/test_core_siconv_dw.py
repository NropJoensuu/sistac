# test_core_siconv_dw.py
#
# Testes de characterization do grupo Integração SICONV/DW do módulo
# core (último grupo, fecha a refatoração completa do core).
#
# Não é possível testar consultaDW/chamadas_DW/cargaSICONV de ponta a
# ponta neste ambiente, pois dependem de acesso real a um Oracle DW e
# ao portal do SICONV (infraestrutura de produção, não disponível em
# testes automatizados). Os testes abaixo cobrem o que É possível
# validar sem essas dependências externas: dois bugs reais de
# encadeamento/contexto encontrados durante a refatoração.

import time
from project import db, app as flask_app
from project.core import services
from project.models import User


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


def test_thread_cargaSICONV_propaga_contexto_de_aplicacao(monkeypatch, app):
    """
    Regressão do bug: o "with app.app_context()" original só envolvia
    a criação da thread, não a execução de cargaSICONV() dentro dela.
    Isso fazia QUALQUER acesso ao banco dentro da thread quebrar com
    "RuntimeError: Working outside of application context".

    Aqui substituímos cargaSICONV por uma função de teste que só faz
    uma consulta ao banco — se o contexto não se propagar, essa
    consulta levanta RuntimeError dentro da thread.
    """
    erro_na_thread = []

    def cargaSICONV_de_teste():
        try:
            db.session.query(User).first()
        except Exception as e:
            erro_na_thread.append(e)

    monkeypatch.setattr(services, 'cargaSICONV', cargaSICONV_de_teste)

    services.thread_cargaSICONV()
    time.sleep(0.5)

    assert erro_na_thread == [], f"Erro dentro da thread: {erro_na_thread}"


def test_carregaSICONV_get_nao_quebra_a_requisicao(client, app):
    """
    A requisição HTTP em si (disparar a carga assíncrona) não deve
    quebrar mesmo que a carga real falhe em background por falta de
    configuração de ambiente (URL_SICONV, Oracle) — isso é esperado
    fora de produção.
    """
    user_id = _usuario(app, 'teste.carregasiconv@teste.com', 'usuariocarregasiconvteste')
    _login(client, user_id)
    resp = client.get("/carregaSICONV")
    assert resp.status_code == 302
