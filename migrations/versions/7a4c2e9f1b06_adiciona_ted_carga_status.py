"""adiciona ted_carga_status

Revision ID: 7a4c2e9f1b06
Revises: 2f8e1a9c4d33
Create Date: 2026-08-02 00:00:00.000000

Migracao escrita a mao (mesmo motivo das anteriores nesta branch): o
historico do alembic esta fora de sincronia com o schema real, e o
autogenerate tenta recriar tabelas dem.* ja existentes, fora do
escopo desta mudanca.

Tabela de linha unica com a data/hora da ultima carga de TED
bem-sucedida (mesmo papel de RefSICONV.data_ref para o SICONV), usada
pela tela de Gestao de TED para exibir "Dados atualizados em: ...".
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7a4c2e9f1b06'
down_revision = '2f8e1a9c4d33'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ted_carga_status',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('data_ultima_carga', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('ted_carga_status')
