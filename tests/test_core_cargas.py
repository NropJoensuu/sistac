# test_core_cargas.py
#
# Testes de characterization do grupo Cargas de arquivo do módulo
# core (carregaPDCTR, carregaMSG). Cobre um bug real: a tela de
# upload de folha de pagamento quebrava com erro 500 numa instalação
# sem nenhuma carga PDCTR anterior, porque o template chamava
# .strftime() diretamente num valor None.
#
# Também cobre a migração de cargaPDCTR de .xls (xlrd) para .xlsx
# (openpyxl): a planilha real usada por Igor não tem a coluna "Sexo
# Proc. Filho" (fonte de dados diferente da COSAO original), então
# esse campo virou opcional — ausente, grava None em vez de abortar a
# carga com erro, que é o comportamento ainda esperado para qualquer
# outro campo obrigatório faltando.
#
# E mais um bug real, encontrado ao rodar a carga com o arquivo real
# de Igor (53 mil linhas): Processo_Mae(...) na fase de agregação
# estava faltando 4 argumentos obrigatórios (id_chamada, pago_capital,
# pago_custeio, pago_bolsas), quebrando com TypeError sempre que a
# planilha trazia um processo mãe ainda não cadastrado — o que sempre
# acontece na primeira carga de uma fonte de dados nova. Corrigido
# passando os mesmos valores "sem dado disponível aqui" (None/0) já
# usados em acordos/services.py:incluir_processo_mae_manual.

import datetime

import openpyxl

from project import db
from project.core import services
from project.models import User, PagamentosPDCTR, RefCargaPDCTR, Processo_Mae, Processo_Filho


CAMPOS_PDCTR = [
    'Processo', 'Nome', 'Sexo Proc. Filho', 'CPF', 'Sit Filho', 'Data da Situação Filho', 'Inicio Filho',
    'Termino Filho', 'Processo Mãe', 'Coordenador', 'Inicio Mãe', 'Termino Mãe', 'Titulo do Processo Filho',
    'Nome Chamada', 'Modalidade', 'Cat Nivel', 'Cod Programa', 'Grande Área', 'Área de Conhecimento',
    'Sigla Instituição', 'UF Instituição', 'Cidade Instituição', 'Data do Pagamento', 'Tipo de Pagamento',
    'Valor Pago', 'Sit Mãe',
]


def _gera_xlsx_pdctr(caminho, linha_valores, omitir_campos=None):
    """
    Gera um .xlsx mínimo no formato esperado por cargaPDCTR: cabeçalho
    na linha 0 (mesmo formato da planilha real de Igor — sem linhas de
    título antes), com uma linha de dados. `omitir_campos` remove
    colunas do cabeçalho (e do valor correspondente), simulando um
    campo ausente na planilha de origem.
    """
    omitir_campos = omitir_campos or []
    campos = [c for c in CAMPOS_PDCTR if c not in omitir_campos]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(campos)
    ws.append([linha_valores[campo] for campo in campos])
    wb.save(caminho)


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


def test_carregaPDCTR_get_sem_carga_anterior_nao_quebra(client, app):
    """
    Regressão do bug: a tela de upload da folha de pagamento deve
    carregar normalmente mesmo sem nenhuma carga PDCTR anterior
    (data_ref None).
    """
    user_id = _usuario(app, 'teste.cargapdctr@teste.com', 'usuariocargapdctrteste')
    _login(client, user_id)
    resp = client.get("/carregaPDCTR")
    assert resp.status_code == 200


def test_carregaMSG_get_responde_200(client, app):
    user_id = _usuario(app, 'teste.cargamsg@teste.com', 'usuariocargamsgteste')
    _login(client, user_id)
    resp = client.get("/carregaMSG")
    assert resp.status_code == 200


def _linha_pdctr_teste(processo='PDCTRTESTE001'):
    return {
        'Processo': processo,
        'Nome': 'Fulano de Tal Teste',
        'Sexo Proc. Filho': 'M',
        'CPF': '11111111111',
        'Sit Filho': '10',
        'Data da Situação Filho': '01/01/2024',
        'Inicio Filho': '01/01/2023',
        'Termino Filho': '31/12/2024',
        'Processo Mãe': 'PDCTRMAETESTE001',
        'Coordenador': 'Coordenador Teste',
        'Inicio Mãe': '01/01/2022',
        'Termino Mãe': '31/12/2025',
        'Titulo do Processo Filho': 'Titulo Teste',
        'Nome Chamada': 'Chamada Teste',
        'Modalidade': 'MOD',
        'Cat Nivel': 'A',
        'Cod Programa': 'PDCTRPROGTESTE001',
        'Grande Área': 'Área Teste',
        'Área de Conhecimento': 'Conhecimento Teste',
        'Sigla Instituição': 'INSTTESTE',
        'UF Instituição': 'DF',
        'Cidade Instituição': 'Brasília',
        'Data do Pagamento': datetime.datetime(2024, 1, 15),
        'Tipo de Pagamento': 'Normal',
        'Valor Pago': 1000.0,
        'Sit Mãe': '10',
    }


def test_cargaPDCTR_le_xlsx_e_grava_campo_opcional_ausente_como_none(app, tmp_path):
    """
    Regressão: cargaPDCTR foi migrada de .xls (xlrd) para .xlsx
    (openpyxl) para ler a planilha real de Igor, que não tem a coluna
    "Sexo Proc. Filho" (fonte diferente da COSAO original). Esse campo
    virou opcional — ausente na planilha, deve gravar None e seguir a
    carga normalmente, sem abortar como acontecia (e ainda acontece,
    ver teste abaixo) para um campo obrigatório ausente.
    """
    caminho = str(tmp_path / 'pdctr_teste.xlsx')
    _gera_xlsx_pdctr(caminho, _linha_pdctr_teste('PDCTROPCIONAL001'), omitir_campos=['Sexo Proc. Filho'])

    with app.app_context():
        # limpa resquício de execuções anteriores da suíte (banco de dev
        # persistente) antes de checar o estado "depois"
        PagamentosPDCTR.query.filter_by(processo='PDCTROPCIONAL001').delete()
        Processo_Mae.query.filter_by(proc_mae='PDCTRMAETESTE001').delete()
        db.session.commit()

        services.cargaPDCTR(caminho)

        pagamento = PagamentosPDCTR.query.filter_by(processo='PDCTROPCIONAL001').first()
        assert pagamento is not None
        assert pagamento.sexo_proc_filho is None
        assert pagamento.nome == 'Fulano de Tal Teste'
        assert pagamento.data_pagamento == datetime.date(2024, 1, 15)
        assert pagamento.inic_filho == datetime.date(2023, 1, 1)
        assert pagamento.valor_pago == 1000.0

        assert RefCargaPDCTR.query.first() is not None

        # Regressão: Processo_Mae(...) na fase de agregação quebrava com
        # TypeError (faltavam id_chamada/pago_capital/pago_custeio/
        # pago_bolsas) sempre que um processo mãe novo aparecia — sem
        # essa correção, este teste já falharia aqui, na chamada acima.
        mae = Processo_Mae.query.filter_by(proc_mae='PDCTRMAETESTE001').first()
        assert mae is not None
        assert mae.pago_capital == 0
        assert mae.pago_custeio == 0
        assert mae.pago_bolsas == 0
        assert mae.id_chamada is None

        filho = Processo_Filho.query.filter_by(processo='PDCTROPCIONAL001').first()
        assert filho is not None
        assert filho.pago_total == 1000.0


def test_cargaPDCTR_campo_obrigatorio_ausente_ainda_bloqueia(app, tmp_path):
    """
    Confirma que só "Sexo Proc. Filho" virou opcional — qualquer outro
    campo obrigatório ausente na planilha ainda bloqueia a carga (não
    grava nada), mesmo comportamento de antes da migração pra .xlsx.
    """
    caminho = str(tmp_path / 'pdctr_teste_sem_processo.xlsx')
    _gera_xlsx_pdctr(caminho, _linha_pdctr_teste('PDCTROBRIGATORIO001'), omitir_campos=['Cod Programa'])

    with app.app_context():
        with app.test_request_context():
            services.cargaPDCTR(caminho)

        assert PagamentosPDCTR.query.filter_by(processo='PDCTROBRIGATORIO001').first() is None
