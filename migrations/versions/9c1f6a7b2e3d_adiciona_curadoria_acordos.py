"""adiciona campos de curadoria a acordo_procmae e processo_mae

Revision ID: 9c1f6a7b2e3d
Revises: 7a4c2e9f1b06
Create Date: 2026-08-04 00:00:00.000000

Migracao escrita a mao (mesmo motivo das anteriores nesta branch):
historico do alembic fora de sincronia com o schema real, autogenerate
tenta recriar tabelas dem.* ja existentes.

Adiciona campos de auditoria a acordo_procmae (tipo_evidencia,
usuario_curador_id, data_vinculo) para registrar como cada vinculo
Processo_Mae <-> Acordo foi estabelecido (match automatico por FAP/UF,
ou confirmacao manual do curador), e um flag em processo_mae
(sem_acordo_confirmado) para o curador marcar explicitamente que um
processo-mae nao tem Acordo correspondente, sem precisar de um
acordo_id nulo na tabela de vinculo.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9c1f6a7b2e3d'
down_revision = '7a4c2e9f1b06'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('acordo_procmae', sa.Column('tipo_evidencia', sa.String(), nullable=True))
    op.add_column('acordo_procmae', sa.Column('usuario_curador_id', sa.Integer(), nullable=True))
    op.add_column('acordo_procmae', sa.Column('data_vinculo', sa.DateTime(), nullable=True))
    op.add_column('processo_mae', sa.Column('sem_acordo_confirmado', sa.Integer(), nullable=True, server_default='0'))


def downgrade():
    op.drop_column('processo_mae', 'sem_acordo_confirmado')
    op.drop_column('acordo_procmae', 'data_vinculo')
    op.drop_column('acordo_procmae', 'usuario_curador_id')
    op.drop_column('acordo_procmae', 'tipo_evidencia')
