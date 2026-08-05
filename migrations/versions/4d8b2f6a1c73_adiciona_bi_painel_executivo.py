"""adiciona sistema.bi_painel_executivo

Revision ID: 4d8b2f6a1c73
Revises: 9c1f6a7b2e3d
Create Date: 2026-08-04 00:00:00.000000

Migracao escrita a mao (mesmo motivo das anteriores nesta branch):
historico do alembic fora de sincronia com o schema real, autogenerate
tenta recriar tabelas dem.* ja existentes.

Interruptor de sistema pro Painel Executivo (Etapa 4 do roadmap de BI),
mesmo padrao de bi_conv/bi_acordo/bi_ted -- controla a visibilidade da
tela publica (sem login) que consolida Convenio+Acordo+TED por Programa
CNPq.

Ao contrario da migracao anterior que mexeu em dem.sistema
(2f8e1a9c4d33), aqui o nome da tabela e qualificado com schema='dem'
explicitamente -- o search_path da conexao atual (\"$user\", public) nao
inclui dem, entao a forma sem qualificar so funcionaria se o
search_path da role tivesse sido ajustado em algum momento anterior
(nao e mais o caso).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4d8b2f6a1c73'
down_revision = '9c1f6a7b2e3d'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('sistema', sa.Column('bi_painel_executivo', sa.Integer(), server_default='1', nullable=True), schema='dem')


def downgrade():
    op.drop_column('sistema', 'bi_painel_executivo', schema='dem')
