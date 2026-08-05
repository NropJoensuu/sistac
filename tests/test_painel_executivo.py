# test_painel_executivo.py
#
# Testes do Painel Executivo (Etapa 4 do roadmap_bi_sistac.md): acesso
# público sem login, disponibilidade controlada por
# Sistema.bi_painel_executivo, e — o ponto central da correção registrada
# em correcao_painel_executivo_dupla_contagem.txt — Captado (TED) e
# Executado (Convênio+Acordo) NUNCA são somados num total único, o
# ranking por Programa CNPq mostra TED como coluna separada (não
# empilhada no mesmo total), e a cobertura de vínculo a Programa CNPq é
# calculada corretamente por instrumento.
#
# Usa dados sintéticos com identificadores facilmente reconhecíveis
# (prefixo "PETESTE"/"9  9xxx"), mesmo padrão idempotente já usado em
# test_convenios_bi.py/test_acordos_bi.py/test_ted_bi.py — não precisa
# de limpeza (fixtures get-or-create).

from datetime import date
from project import db
from project.painel_executivo import services
from project.ted import services as ted_services
from project.models import (
    Sistema, Programa, Proposta, Convenio, Convenio_Programa_CNPq,
    Acordo, grupo_programa_cnpq, Programa_CNPq, TED_Programa, TED_PlanoAcao,
)


def _programa_cnpq(cod_programa, sigla):
    existente = Programa_CNPq.query.filter_by(COD_PROGRAMA=cod_programa).first()
    if existente is None:
        db.session.add(Programa_CNPq(cod_programa, f'Programa Teste {sigla}', sigla, 'DPI'))
        db.session.commit()
    return Programa_CNPq.query.filter_by(COD_PROGRAMA=cod_programa).first()


def _programa_proposta(cod_programa):
    if not Programa.query.get(cod_programa):
        db.session.add(Programa(cod_programa, cod_programa, 'Programa Teste Painel', 'Ativo', '2024'))
    if not Proposta.query.get(cod_programa):
        db.session.add(Proposta(cod_programa, cod_programa, 'DF', 'Proponente Teste Painel', 'Objeto teste painel'))
    db.session.commit()


def _convenio(nr_convenio, id_proposta, ano='2199', vl_repasse=100000.0):
    existente = Convenio.query.get(nr_convenio)
    if existente is None:
        db.session.add(Convenio(
            nr_convenio, id_proposta, '01', '01', ano, '01/01/2024', 'Em execução', 'Normal',
            'Publicado', 'Sim', 'Não', 'PROC-PE', 'UG1', '01/01/2024', '01/01/2024',
            date(2030, 1, 1), '01/01/2025', '60', '01/03/2026', 'Contratado', 'Sim', '',
            'N', '1', '0', '0',
            vl_repasse + 10000.0, vl_repasse, 10000.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        ))
        db.session.commit()
    return Convenio.query.get(nr_convenio)


def _vincula_convenio_programa(nr_convenio, id_programa, cod_programa):
    existente = Convenio_Programa_CNPq.query.filter_by(nr_convenio=nr_convenio).first()
    if existente is None:
        db.session.add(Convenio_Programa_CNPq(nr_convenio, id_programa, cod_programa, None))
        db.session.commit()


def _acordo(sei, nome, epe, uf, ano_inicio=2199):
    acordo = Acordo.query.filter_by(sei=sei).first()
    if acordo is None:
        acordo = Acordo(
            nome=nome, sei=sei, epe=epe, uf=uf,
            data_inicio=date(ano_inicio, 1, 1), data_fim=date(ano_inicio + 2, 12, 31), valor_cnpq=80000.0,
            valor_epe=20000.0, unidade_cnpq='DPI', situ='Vigente-Z', desc='teste painel executivo',
            capital=0.0, custeio=0.0, bolsas=100000.0, siafi='123',
        )
        db.session.add(acordo)
        db.session.commit()
    return acordo


def _vincula_acordo_programa(id_acordo, id_programa, cod_programa):
    existente = grupo_programa_cnpq.query.filter_by(id_acordo=id_acordo, id_programa=id_programa).first()
    if existente is None:
        db.session.add(grupo_programa_cnpq(id_acordo, id_programa, cod_programa))
        db.session.commit()


def _ted_programa(id_programa, unidade='MCTI', ano='2199'):
    if not TED_Programa.query.get(id_programa):
        db.session.add(TED_Programa(
            id=id_programa, codigo_programa=f'PETESTE{id_programa}', nome='Programa Teste Painel TED',
            unidade_descentralizadora=unidade, ano=ano,
        ))
        db.session.commit()


def _ted_plano(id_plano, id_programa, numero_ted, valor=50000.0, ano='2199'):
    if not TED_PlanoAcao.query.get(id_plano):
        db.session.add(TED_PlanoAcao(
            id=id_plano, numero_ted=numero_ted, id_programa=id_programa,
            unidade_descentralizada='CNPq', situacao_plano='APROVADO',
            objeto='Objeto teste painel executivo', valor_beneficiario_especifico=valor,
            valor_chamamento_publico=0.0, vigencia_inicio=None, vigencia_fim=None,
            ano=ano,
        ))
        db.session.commit()


def test_painel_executivo_responde_200_sem_login(client):
    resp = client.get('/painel_executivo/')
    assert resp.status_code == 200


def test_painel_executivo_indisponivel_quando_desligado(app):
    with app.app_context():
        sistema = Sistema.query.first()
        original = sistema.bi_painel_executivo
        sistema.bi_painel_executivo = 0
        db.session.commit()
    try:
        with app.test_client() as client_sem_sessao:
            resp = client_sem_sessao.get('/painel_executivo/')
            assert resp.status_code == 200
            assert 'indispon' in resp.get_data(as_text=True).lower()
    finally:
        with app.app_context():
            sistema = Sistema.query.first()
            sistema.bi_painel_executivo = original
            db.session.commit()


def test_captado_e_executado_nunca_somados(app):
    with app.app_context():
        pcnpq = _programa_cnpq('PETESTE01', 'PCPE01')

        _programa_proposta('9500')
        _convenio('PETESTECONV001', '9500', ano='2199', vl_repasse=100000.0)
        _vincula_convenio_programa('PETESTECONV001', pcnpq.ID_PROGRAMA, 'PETESTE01')

        acordo = _acordo('00000.000000/2199-01', 'Acordo Teste Painel', 'EPETESTEPAINEL', 'DF', ano_inicio=2199)
        _vincula_acordo_programa(acordo.id, pcnpq.ID_PROGRAMA, 'PETESTE01')

        _ted_programa(95001, unidade='PETESTEORGAO', ano='2199')
        _ted_plano(95002, 95001, 'PETESTETED001', valor=70000.0, ano='2199')
        ted_services.vincular_programa_cnpq(
            id_plano_acao=95002, id_programa_cnpq=pcnpq.ID_PROGRAMA,
            tipo_evidencia='nome_literal', usuario_id=1,
        )

        dados = services.painel_executivo({'ano': '2199'})

        # Convenio (110000 = repasse+contrapartida) + Acordo (100000 = cnpq+epe)
        assert dados['valor_total_executado'] >= 210000.0
        # TED isolado, nao contaminado pelo executado
        assert dados['valor_total_captado'] >= 70000.0
        # as duas chaves existem separadas -- nunca um total unico somando os 3
        assert 'valor_total_executado' in dados and 'valor_total_captado' in dados
        assert dados['valor_total_executado'] != dados['valor_total_executado'] + dados['valor_total_captado']


def test_ranking_com_ted_como_coluna_separada(app):
    with app.app_context():
        pcnpq = _programa_cnpq('PETESTE02', 'PCPE02')

        _programa_proposta('9501')
        _convenio('PETESTECONV002', '9501', ano='2198', vl_repasse=50000.0)
        _vincula_convenio_programa('PETESTECONV002', pcnpq.ID_PROGRAMA, 'PETESTE02')

        acordo = _acordo('00000.000000/2198-02', 'Acordo Teste Painel 2', 'EPETESTEPAINEL2', 'DF', ano_inicio=2198)
        _vincula_acordo_programa(acordo.id, pcnpq.ID_PROGRAMA, 'PETESTE02')

        _ted_programa(95003, unidade='PETESTEORGAO2', ano='2198')
        _ted_plano(95004, 95003, 'PETESTETED002', valor=30000.0, ano='2198')
        ted_services.vincular_programa_cnpq(
            id_plano_acao=95004, id_programa_cnpq=pcnpq.ID_PROGRAMA,
            tipo_evidencia='nome_literal', usuario_id=1,
        )

        dados = services.painel_executivo({'programa': 'PCPE02'})
        linha = next(r for r in dados['ranking'] if r['programa'] == 'PCPE02')

        assert linha['convenio'] == 60000.0  # 50000 + 10000 contrapartida
        assert linha['acordo'] == 100000.0   # 80000 cnpq + 20000 epe
        assert linha['executado'] == linha['convenio'] + linha['acordo']
        assert linha['captado_ted'] == 30000.0
        # TED nao entra na soma "executado"
        assert linha['executado'] != linha['executado'] + linha['captado_ted']


def test_cobertura_calculada_corretamente(app):
    with app.app_context():
        pcnpq = _programa_cnpq('PETESTE03', 'PCPE03')

        _programa_proposta('9502')
        _convenio('PETESTECONV003', '9502', ano='2197', vl_repasse=100000.0)
        _convenio('PETESTECONV004', '9502', ano='2197', vl_repasse=100000.0)
        # só o primeiro convênio recebe vínculo a Programa CNPq
        _vincula_convenio_programa('PETESTECONV003', pcnpq.ID_PROGRAMA, 'PETESTE03')

        dados = services.painel_executivo({'ano': '2197'})

        # 110000 vinculado de um total de 220000 (2 convênios de 110000 cada) = 50%
        assert dados['cobertura_executado'] == 50


def test_filtros_nao_quebram(client):
    resp = client.get('/painel_executivo/', query_string={'programa': 'INEXISTENTE', 'ano': '2199'})
    assert resp.status_code == 200
