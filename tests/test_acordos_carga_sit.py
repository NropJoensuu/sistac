# test_acordos_carga_sit.py
#
# Testes de characterization da carga de situações via SIGEF
# (cargaSit(), rota carrega_sit_sigef) do módulo acordos.
#
# Cobre a migração de cargaSit() de .xls (xlrd) para .xlsx (openpyxl) —
# mesmo bug já corrigido em cargaPDCTR (ver test_core_cargas.py):
# xlrd só lê o formato antigo .xls, e a planilha exportada pelo SIGEF é
# .xlsx.
#
# Também cobre dois bugs reais encontrados ao revisar a rota
# carrega_sit_sigef: faltava @login_required (mas current_user.id era
# usado incondicionalmente no registra_log_auto — mesmo padrão de bug já
# visto em lista_acordos/Convênios-B13), e a rota exigia proc_mae/edic/
# epe/uf na URL sem nunca usar edic/epe/uf no corpo da função — parâmetros
# mortos que impediam a rota de ser exposta direto no menu Carga.

import openpyxl

from project import db
from project.acordos import services
from project.models import User, Processo_Filho, PagamentosPDCTR


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


def _usuario(app, email, username, trab_acordo=1):
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if user is None:
            user = User(
                email=email, username=username,
                plaintext_password='senha123', coord='DPI', role='user',
                ativo=1, sversion=1, cargo_func='teste',
                trab_conv=1, trab_acordo=trab_acordo, trab_instru=1,
                despacha0=0, despacha=0, despacha2=0,
            )
            db.session.add(user)
            db.session.commit()
        return user.id


def _gera_xlsx_sit(caminho, linhas):
    """
    Gera um .xlsx mínimo no formato esperado por cargaSit: cabeçalho com
    "Processo" e "Situação" na linha 0, uma linha por item de `linhas`
    (lista de tuplas (processo, situacao)).
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(['Processo', 'Situação'])
    for processo, situacao in linhas:
        ws.append([processo, situacao])
    wb.save(caminho)


def test_cargaSit_le_xlsx_e_atualiza_situacao(app, tmp_path):
    """
    Regressão: cargaSit() usava xlrd.open_workbook(), que só lê .xls —
    quebraria ao receber a planilha .xlsx real exportada pelo SIGEF.
    Migrada pra openpyxl, mesmo padrão já usado em cargaPDCTR.
    """
    caminho = str(tmp_path / 'sigef_teste.xlsx')
    _gera_xlsx_sit(caminho, [('SIGEFPROC001', 'Concluído')])

    with app.app_context():
        Processo_Filho.query.filter_by(processo='SIGEFPROC001').delete()
        PagamentosPDCTR.query.filter_by(processo='SIGEFPROC001').delete()
        db.session.commit()

        filho = Processo_Filho(
            cod_programa='PROG', nome_chamada='Chamada Teste', proc_mae='SIGEFMAETESTE001',
            processo='SIGEFPROC001', nome='Fulano Teste', cpf='11111111111', modalidade='MOD',
            nivel='A', situ_filho='Em andamento', inic_filho=None, term_filho=None,
            mens_pagas=0, pago_total=0.0, valor_apagar=0.0, mens_apagar=0, dt_ult_pag=None,
        )
        db.session.add(filho)
        db.session.commit()

        services.cargaSit(caminho)

        filho_atualizado = Processo_Filho.query.filter_by(processo='SIGEFPROC001').first()
        assert filho_atualizado is not None
        assert filho_atualizado.situ_filho == 'Concluído'


def test_carrega_sit_sigef_exige_login(client):
    """
    Regressão: a rota usava current_user.id incondicionalmente (no
    registra_log_auto do POST) mas não tinha @login_required — um acesso
    anônimo quebraria com AttributeError em vez de redirecionar pro login.
    """
    resp = client.get('/acordos/carrega_sit_sigef')
    assert resp.status_code in (301, 302)
    assert '/login' in resp.headers['Location']


def test_carrega_sit_sigef_responde_200_sem_parametros_na_url(client, app):
    """
    Regressão/simplificação: a rota exigia proc_mae/edic/epe/uf na URL,
    mas edic/epe/uf nunca eram usados no corpo da função e cargaSit() não
    é filtrada por proc_mae (atualiza todos os processos-filho encontrados
    na planilha) — os parâmetros foram removidos pra permitir o acesso
    direto pelo menu Carga.
    """
    user_id = _usuario(app, 'teste.cargasit@teste.com', 'usuariocargasitteste')
    _login(client, user_id)
    resp = client.get('/acordos/carrega_sit_sigef')
    assert resp.status_code == 200
