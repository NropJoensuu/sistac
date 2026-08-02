"""adiciona tabelas do modulo TED

Revision ID: 1d4f6a7c9e21
Revises: bac5c0bbc4a5
Create Date: 2026-08-02 00:00:00.000000

Migração escrita à mão (mesmo motivo da migração anterior,
bac5c0bbc4a5): o histórico do alembic está fora de sincronia com o
schema real, e o autogenerate tenta recriar tabelas dem.* já
existentes, fora do escopo desta mudança.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1d4f6a7c9e21'
down_revision = 'bac5c0bbc4a5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ted_programa',
        sa.Column('id', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('codigo_programa', sa.String(), nullable=True),
        sa.Column('nome', sa.String(), nullable=True),
        sa.Column('unidade_descentralizadora', sa.String(), nullable=True),
        sa.Column('ano', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'ted_plano_acao',
        sa.Column('id', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('numero_ted', sa.String(), nullable=True),
        sa.Column('id_programa', sa.Integer(), nullable=True),
        sa.Column('unidade_descentralizada', sa.String(), nullable=True),
        sa.Column('situacao_plano', sa.String(), nullable=True),
        sa.Column('objeto', sa.Text(), nullable=True),
        sa.Column('valor_beneficiario_especifico', sa.Float(), nullable=True),
        sa.Column('valor_chamamento_publico', sa.Float(), nullable=True),
        sa.Column('vigencia_inicio', sa.Date(), nullable=True),
        sa.Column('vigencia_fim', sa.Date(), nullable=True),
        sa.Column('ano', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'ted_termo_execucao',
        sa.Column('id', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('id_plano_acao', sa.Integer(), nullable=True),
        sa.Column('situacao_termo', sa.String(), nullable=True),
        sa.Column('data_assinatura', sa.Date(), nullable=True),
        sa.Column('numero_ns_termo', sa.String(), nullable=True),
        sa.Column('referencia_externa', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'ted_execucao_interna',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('id_plano_acao', sa.Integer(), nullable=True),
        sa.Column('coordenacao', sa.String(), nullable=True),
        sa.Column('sei_cnpq', sa.String(), nullable=True),
        sa.Column('observacao', sa.String(), nullable=True),
        sa.Column('usuario_curador_id', sa.Integer(), nullable=True),
        sa.Column('data_registro', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'ted_vinculo_programa_cnpq',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('id_plano_acao', sa.Integer(), nullable=True),
        sa.Column('id_programa_cnpq', sa.Integer(), nullable=True),
        sa.Column('tipo_evidencia', sa.String(), nullable=True),
        sa.Column('usuario_curador_id', sa.Integer(), nullable=True),
        sa.Column('data_vinculo', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'ted_vinculo_instrumento',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('id_plano_acao', sa.Integer(), nullable=True),
        sa.Column('tipo_instrumento', sa.String(), nullable=True),
        sa.Column('nr_convenio', sa.String(), nullable=True),
        sa.Column('id_acordo', sa.Integer(), nullable=True),
        sa.Column('usuario_curador_id', sa.Integer(), nullable=True),
        sa.Column('data_vinculo', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('ted_vinculo_instrumento')
    op.drop_table('ted_vinculo_programa_cnpq')
    op.drop_table('ted_execucao_interna')
    op.drop_table('ted_termo_execucao')
    op.drop_table('ted_plano_acao')
    op.drop_table('ted_programa')
