"""adiciona convenio_programa_cnpq

Revision ID: bac5c0bbc4a5
Revises: 56fc27e9c1ad
Create Date: 2026-08-02 00:30:07.962912

Migração escrita à mão (não pelo autogenerate do alembic): o
autogenerate detectou o histórico de migração como desatualizado em
relação ao schema real (tentou recriar dezenas de tabelas `dem.*` que
já existem, fora do escopo desta mudança) — então só a criação da
tabela nova está aqui, isolada.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bac5c0bbc4a5'
down_revision = '56fc27e9c1ad'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'convenio_programa_cnpq',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nr_convenio', sa.String(), nullable=True),
        sa.Column('id_programa', sa.Integer(), nullable=True),
        sa.Column('cod_programa', sa.String(), nullable=True),
        sa.Column('programa_estrategico', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('convenio_programa_cnpq')
