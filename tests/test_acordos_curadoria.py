# test_acordos_curadoria.py
#
# Testes da curadoria do vínculo Processo-Mãe <-> Acordo (Acordo_ProcMae
# com os novos campos de auditoria tipo_evidencia/usuario_curador_id/
# data_vinculo): classificação nos 4 níveis, vínculo automático restrito
# a alta/média, confirmação manual (curadoria) e marcação de "sem Acordo
# correspondente". Usa dados sintéticos com identificadores facilmente
# reconhecíveis (sei/proc_mae/epe com o padrão "TESTECURADORIA"), mesmo
# padrão já usado em test_acordos_bi.py/test_acordos_dashboards.py —
# fixtures idempotentes (get-or-create), não precisam de limpeza.
#
# A suíte roda contra o banco de estudo compartilhado (sistac_dev, ver
# conftest.py). classificar_e_vincular_processos_mae() varre TODOS os
# processos-mãe ainda sem tratamento, então, como efeito colateral real
# (e intencional: é a própria funcionalidade), também vincula os
# processos-mãe reais já carregados que baterem os critérios de alta/
# média -- operação aditiva e idempotente (só cria Acordo_ProcMae que
# ainda não existem), no mesmo espírito do rebuild aditivo de
# Processo_Filho em cargaPDCTR. Por isso não precisa de restauração de
# estado, ao contrário das mutações em Sistema/trab_* (essas sim,
# restauradas manualmente após a suíte, convenção já estabelecida).

from datetime import date
from project import db
from project.acordos import services
from project.models import User, Acordo, Processo_Mae, PagamentosPDCTR, Acordo_ProcMae


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


def _acordo(sei, nome, epe, uf):
    acordo = Acordo.query.filter_by(sei=sei).first()
    if acordo is None:
        acordo = Acordo(
            nome=nome, sei=sei, epe=epe, uf=uf,
            data_inicio=date(2024, 1, 1), data_fim=date(2026, 12, 31), valor_cnpq=100000.0,
            valor_epe=50000.0, unidade_cnpq='DPI', situ='Vigente-Z', desc='teste curadoria',
            capital=0.0, custeio=0.0, bolsas=100000.0, siafi='123',
        )
        db.session.add(acordo)
        db.session.commit()
    return acordo


def _processo_mae(proc_mae, nome_chamada):
    mae = Processo_Mae.query.filter_by(proc_mae=proc_mae).first()
    if mae is None:
        mae = Processo_Mae(
            cod_programa=None, nome_chamada=nome_chamada, proc_mae=proc_mae,
            inic_mae=date(2024, 1, 1), term_mae=date(2026, 12, 31), coordenador='Teste',
            situ_mae='Vigente-Z', id_chamada=None, pago_capital=0, pago_custeio=0, pago_bolsas=0,
        )
        db.session.add(mae)
        db.session.commit()
    return mae


def _pagamento(proc_mae, sigla_inst, uf_inst):
    existente = PagamentosPDCTR.query.filter_by(processo=proc_mae + '_filho', proc_mae=proc_mae).first()
    if existente is None:
        existente = PagamentosPDCTR(
            processo=proc_mae + '_filho', nome='Bolsista Teste', sexo_proc_filho=None, cpf='00000000000',
            situ_filho='Vigente', data_situ_filho=date(2024, 1, 1), inic_filho=date(2024, 1, 1),
            term_filho=date(2026, 12, 31), proc_mae=proc_mae, coordenador='Teste',
            inic_mae=date(2024, 1, 1), term_mae=date(2026, 12, 31), titu_proc_filho='Bolsa Teste',
            nome_chamada='irrelevante', modalidade='DR', nivel='Doutorado', cod_programa=None,
            grande_area=None, area_conhecimento=None, sigla_inst=sigla_inst, uf_inst=uf_inst,
            cidade_inst='Cidade Teste', data_pagamento=date(2024, 6, 1), tipo_pagamento='Mensalidade',
            valor_pago=3000.0, situ_mae='Vigente-Z',
        )
        db.session.add(existente)
        db.session.commit()
    return existente


def test_classifica_alta_quando_fap_e_texto_batem(app):
    with app.app_context():
        acordo = _acordo('00000.000000/2024-91', 'Programa Teste Curadoria Alfa', 'EPETESTECURADORIAALTA', 'DF')
        mae = _processo_mae('00000.000000/2024-91', 'Programa Teste Curadoria Alfa - Edição 2024')
        _pagamento('00000.000000/2024-91', 'EPETESTECURADORIAALTA', 'DF')

        nivel, acordo_escolhido, candidatos = services.classificar_processo_mae(mae, [acordo])

        assert nivel == 'alta'
        assert acordo_escolhido.id == acordo.id
        assert candidatos == []


def test_classifica_media_quando_so_fap_bate(app):
    with app.app_context():
        acordo = _acordo('00000.000000/2024-92', 'Nome Sem Relação Nenhuma Aqui', 'EPETESTECURADORIAMEDIA', 'DF')
        mae = _processo_mae('00000.000000/2024-92', 'Chamada Totalmente Distinta Beta')
        _pagamento('00000.000000/2024-92', 'EPETESTECURADORIAMEDIA', 'DF')

        nivel, acordo_escolhido, candidatos = services.classificar_processo_mae(mae, [acordo])

        assert nivel == 'media'
        assert acordo_escolhido.id == acordo.id


def test_classifica_media_uf_ambigua_quando_so_uf_bate(app):
    with app.app_context():
        acordo = _acordo('00000.000000/2024-93', 'Nome Sem Relação Gama', 'EPEOUTRAINSTITUICAO', 'TO')
        mae = _processo_mae('00000.000000/2024-93', 'Chamada Totalmente Distinta Gama')
        _pagamento('00000.000000/2024-93', 'INSTITUICAO_DO_BOLSISTA_DIFERENTE', 'TO')

        nivel, acordo_escolhido, candidatos = services.classificar_processo_mae(mae, [acordo])

        assert nivel == 'media_uf_ambigua'
        assert acordo_escolhido is None
        assert any(c.id == acordo.id for c in candidatos)


def test_classifica_sem_match_quando_nada_bate(app):
    with app.app_context():
        acordo = _acordo('00000.000000/2024-94', 'Nome Sem Relação Delta', 'EPEQUALQUERCOISA', 'DF')
        mae = _processo_mae('00000.000000/2024-94', 'Chamada Totalmente Distinta Delta')
        _pagamento('00000.000000/2024-94', 'INSTITUICAO_SEM_RELACAO', 'ZZ')

        nivel, acordo_escolhido, candidatos = services.classificar_processo_mae(mae, [acordo])

        assert nivel == 'sem_match'
        assert acordo_escolhido is None
        assert candidatos == []


def test_classificar_e_vincular_liga_automaticamente_alta_e_media(app):
    with app.app_context():
        acordo_alta = _acordo('00000.000000/2024-95', 'Programa Teste Curadoria Epsilon', 'EPETESTECURADORIAEPSILON', 'DF')
        mae_alta = _processo_mae('00000.000000/2024-95', 'Programa Teste Curadoria Epsilon - Edição 2024')
        _pagamento('00000.000000/2024-95', 'EPETESTECURADORIAEPSILON', 'DF')

        acordo_media = _acordo('00000.000000/2024-96', 'Nome Sem Relação Zeta', 'EPETESTECURADORIAZETA', 'DF')
        mae_media = _processo_mae('00000.000000/2024-96', 'Chamada Totalmente Distinta Zeta')
        _pagamento('00000.000000/2024-96', 'EPETESTECURADORIAZETA', 'DF')

        services.classificar_e_vincular_processos_mae(usuario_id=None)

        vinculo_alta = Acordo_ProcMae.query.filter_by(proc_mae_id=mae_alta.id).first()
        vinculo_media = Acordo_ProcMae.query.filter_by(proc_mae_id=mae_media.id).first()

        assert vinculo_alta is not None
        assert vinculo_alta.acordo_id == acordo_alta.id
        assert vinculo_alta.tipo_evidencia == 'auto_alta'
        assert vinculo_alta.usuario_curador_id is None

        assert vinculo_media is not None
        assert vinculo_media.acordo_id == acordo_media.id
        assert vinculo_media.tipo_evidencia == 'auto_media'


def test_classificar_e_vincular_nao_liga_uf_ambigua_nem_sem_match(app):
    with app.app_context():
        _acordo('00000.000000/2024-97', 'Nome Sem Relação Eta', 'EPEOUTRAINSTITUICAOETA', 'RO')
        mae_ambigua = _processo_mae('00000.000000/2024-97', 'Chamada Totalmente Distinta Eta')
        _pagamento('00000.000000/2024-97', 'INSTITUICAO_DO_BOLSISTA_ETA', 'RO')

        mae_sem_match = _processo_mae('00000.000000/2024-98', 'Chamada Totalmente Distinta Theta')
        _pagamento('00000.000000/2024-98', 'INSTITUICAO_SEM_RELACAO_THETA', 'ZZ')

        services.classificar_e_vincular_processos_mae(usuario_id=None)

        assert Acordo_ProcMae.query.filter_by(proc_mae_id=mae_ambigua.id).first() is None
        assert Acordo_ProcMae.query.filter_by(proc_mae_id=mae_sem_match.id).first() is None


def test_curadoria_processo_mae_lista_pendentes_e_progresso(client, app):
    with app.app_context():
        user_id = _usuario(app, 'teste.curadoria@teste.com', 'usuariocuradoriateste')
        _acordo('00000.000000/2024-99', 'Nome Sem Relação Iota', 'EPEOUTRAINSTITUICAOIOTA', 'AC')
        mae_pendente = _processo_mae('00000.000000/2024-99', 'Chamada Totalmente Distinta Iota')
        _pagamento('00000.000000/2024-99', 'INSTITUICAO_DO_BOLSISTA_IOTA', 'AC')
        mae_id = mae_pendente.id

    _login(client, user_id)
    resp = client.get('/acordos/curadoria_processo_mae')
    assert resp.status_code == 200

    with app.app_context():
        dados = services.fila_curadoria_processos_mae()
        assert dados['total'] >= dados['concluidos']
        assert any(item['processo_mae'].id == mae_id for item in dados['fila'])


def test_vincula_curadoria_confirma_vinculo_manual(client, app):
    with app.app_context():
        user_id = _usuario(app, 'teste.curadoria2@teste.com', 'usuariocuradoriateste2')
        acordo = _acordo('00000.000000/2024-01', 'Nome Sem Relação Kapa', 'EPEOUTRAINSTITUICAOKAPA', 'AC')
        mae = _processo_mae('00000.001000/2024-01', 'Chamada Totalmente Distinta Kapa')
        mae_id, acordo_id = mae.id, acordo.id

    _login(client, user_id)
    resp = client.post(f'/acordos/{mae_id}/vincula_curadoria', data={'acordo_id': str(acordo_id)}, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        vinculo = Acordo_ProcMae.query.filter_by(proc_mae_id=mae_id, acordo_id=acordo_id).first()
        assert vinculo is not None
        assert vinculo.tipo_evidencia == 'manual_curadoria'
        assert vinculo.usuario_curador_id == user_id


def test_sem_acordo_curadoria_marca_confirmado_e_some_da_fila(client, app):
    with app.app_context():
        user_id = _usuario(app, 'teste.curadoria3@teste.com', 'usuariocuradoriateste3')
        mae = _processo_mae('00000.001000/2024-02', 'Chamada Totalmente Distinta Lambda')
        mae_id = mae.id

    _login(client, user_id)
    resp = client.post(f'/acordos/{mae_id}/sem_acordo_curadoria', follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        mae_atualizado = Processo_Mae.query.get(mae_id)
        assert mae_atualizado.sem_acordo_confirmado == 1

        dados = services.fila_curadoria_processos_mae()
        assert all(item['processo_mae'].id != mae_id for item in dados['fila'])
