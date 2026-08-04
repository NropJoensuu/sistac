# test_acordos_dashboards.py
#
# Testes de characterization do grupo Dashboards/mapas do módulo
# acordos. resumo_acordos/brasil_acordos/quadro_acordos foram
# desativadas em favor do BI Acordos (ver proposta_melhorias.md) — os
# testes correspondentes foram removidos junto (o bug de
# current_user.coord sem @login_required que o primeiro teste cobria
# não se aplica mais, já que a rota nem existe ativa). gasto_mes segue
# ativa e seu teste foi mantido.

from datetime import date
from project import db
from project.models import Acordo


def _acordo(app):
    with app.app_context():
        acordo = Acordo.query.filter_by(sei='00000.000000/2024-44').first()
        if acordo is None:
            acordo = Acordo(
                nome='Acordo Teste Dashboards', sei='00000.000000/2024-44', epe='EPE Teste', uf='DF',
                data_inicio=date(2024, 1, 1), data_fim=date(2026, 12, 31), valor_cnpq=100000.0,
                valor_epe=50000.0, unidade_cnpq='DPI', situ='Em execução', desc='teste',
                capital=0.0, custeio=0.0, bolsas=100000.0, siafi='123',
            )
            db.session.add(acordo)
            db.session.commit()
        return acordo.id


def test_gasto_mes_sem_processos_mae_nao_quebra(client, app):
    acordo_id = _acordo(app)
    resp = client.get(f"/acordos/{acordo_id}/2024/EPE/DF/gasto_mes")
    assert resp.status_code == 200
