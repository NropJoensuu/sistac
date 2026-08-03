"""adiciona interruptores de Gestao e BI (TED, Convenios, Acordos)

Revision ID: 2f8e1a9c4d33
Revises: 1d4f6a7c9e21
Create Date: 2026-08-02 00:00:00.000000

Migracao escrita a mao (mesmo motivo das anteriores, bac5c0bbc4a5 e
1d4f6a7c9e21): o historico do alembic esta fora de sincronia com o
schema real, e o autogenerate tenta recriar tabelas dem.* ja
existentes, fora do escopo desta mudanca.

Adiciona os 2 interruptores por modulo (Gestao habilitada / BI
habilitado) para Convenios, Acordos e TED: 4 colunas novas em
dem.sistema (funcionalidade_ted, bi_conv, bi_acordo, bi_ted) e 1
coluna nova em dem.users (trab_ted, a permissao individual "trabalha
com TED", analoga a trab_conv/trab_acordo).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2f8e1a9c4d33'
down_revision = '1d4f6a7c9e21'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('sistema', sa.Column('funcionalidade_ted', sa.Integer(), server_default='0', nullable=True))
    op.add_column('sistema', sa.Column('bi_conv', sa.Integer(), server_default='1', nullable=True))
    op.add_column('sistema', sa.Column('bi_acordo', sa.Integer(), server_default='1', nullable=True))
    op.add_column('sistema', sa.Column('bi_ted', sa.Integer(), server_default='1', nullable=True))
    op.add_column('users', sa.Column('trab_ted', sa.Integer(), server_default='0', nullable=True))


def downgrade():
    op.drop_column('users', 'trab_ted')
    op.drop_column('sistema', 'bi_ted')
    op.drop_column('sistema', 'bi_acordo')
    op.drop_column('sistema', 'bi_conv')
    op.drop_column('sistema', 'funcionalidade_ted')
