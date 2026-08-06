"""adiciona ted_programa.sigla_unidade_descentralizadora

Revision ID: b7e3d9f4a218
Revises: 4d8b2f6a1c73
Create Date: 2026-08-05 00:00:00.000000

Migracao escrita a mao (mesmo motivo das anteriores nesta branch):
historico do alembic fora de sincronia com o schema real, autogenerate
tenta recriar tabelas dem.* ja existentes.

Sigla do orgao de origem do TED (ex: "MCTI"), que a API do
TransfereGov ja fornece num campo separado do nome por extenso
(sigla_unidade_descentralizadora) mas que a carga nao capturava.
Usada na exibicao da Gestao de TED (item A5 do backlog), com fallback
pro nome completo quando vier vazia.

A tabela e recarregada inteira a cada cargaTED() (delete-and-reload),
entao a coluna nova e populada na proxima carga -- nao precisa de
UPDATE de backfill aqui.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7e3d9f4a218'
down_revision = '4d8b2f6a1c73'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('ted_programa', sa.Column('sigla_unidade_descentralizadora', sa.String(), nullable=True))


def downgrade():
    op.drop_column('ted_programa', 'sigla_unidade_descentralizadora')
