"""initial schema with fonte field

Revision ID: a32546c008ea
Revises:
Create Date: 2026-06-24 16:36:38.575399

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a32546c008ea'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'editais',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('numero_controle', sa.String(length=100), nullable=False),
        sa.Column('orgao', sa.String(length=300), nullable=False),
        sa.Column('uasg', sa.String(length=20), nullable=True),
        sa.Column('objeto', sa.Text(), nullable=False),
        sa.Column('modalidade', sa.String(length=80), nullable=False),
        sa.Column('valor_estimado', sa.Float(), nullable=True),
        sa.Column('data_abertura', sa.DateTime(timezone=True), nullable=True),
        sa.Column('data_encerramento', sa.DateTime(timezone=True), nullable=True),
        sa.Column('link_edital', sa.Text(), nullable=True),
        sa.Column('link_pdf', sa.Text(), nullable=True),
        sa.Column('exclusivo_me', sa.Boolean(), nullable=False),
        sa.Column('estado', sa.String(length=2), nullable=True),
        sa.Column('municipio', sa.String(length=150), nullable=True),
        sa.Column('fonte', sa.String(length=50), nullable=True),
        sa.Column('status', sa.Enum(
            'publicado', 'aberto', 'em_andamento', 'disputa_aberta',
            'homologado', 'cancelado', 'encerrado', name='editalstatus'
        ), nullable=False),
        sa.Column('texto_extraido', sa.Text(), nullable=True),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_editais_id'), 'editais', ['id'], unique=False)
    op.create_index(op.f('ix_editais_numero_controle'), 'editais', ['numero_controle'], unique=True)
    op.create_index(op.f('ix_editais_fonte'), 'editais', ['fonte'], unique=False)
    op.create_index(op.f('ix_editais_status'), 'editais', ['status'], unique=False)

    op.create_table(
        'alertas_monitoramento',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('edital_id', sa.Integer(), nullable=False),
        sa.Column('dispositivo_token', sa.String(length=500), nullable=True),
        sa.Column('ativo', sa.Boolean(), nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_alertas_monitoramento_id'), 'alertas_monitoramento', ['id'], unique=False)
    op.create_index(op.f('ix_alertas_monitoramento_edital_id'), 'alertas_monitoramento', ['edital_id'], unique=False)

    op.create_table(
        'sync_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('iniciado_em', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('finalizado_em', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_encontrados', sa.Integer(), nullable=False),
        sa.Column('total_novos', sa.Integer(), nullable=False),
        sa.Column('erro', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('fonte', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_sync_logs_id'), 'sync_logs', ['id'], unique=False)


def downgrade() -> None:
    op.drop_table('sync_logs')
    op.drop_table('alertas_monitoramento')
    op.drop_index(op.f('ix_editais_status'), table_name='editais')
    op.drop_index(op.f('ix_editais_fonte'), table_name='editais')
    op.drop_index(op.f('ix_editais_numero_controle'), table_name='editais')
    op.drop_index(op.f('ix_editais_id'), table_name='editais')
    op.drop_table('editais')
    op.execute("DROP TYPE IF EXISTS editalstatus")
