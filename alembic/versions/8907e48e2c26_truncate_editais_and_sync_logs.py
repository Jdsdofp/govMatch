"""truncate_editais_and_sync_logs

Revision ID: 8907e48e2c26
Revises: d67cf076716b
Create Date: 2026-06-25 18:01:50.002023

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8907e48e2c26'
down_revision: Union[str, None] = 'd67cf076716b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Limpa dados inseridos antes do campo `fonte` existir no schema de resposta
    op.execute("TRUNCATE TABLE alertas_monitoramento, sync_logs, editais RESTART IDENTITY CASCADE")


def downgrade() -> None:
    pass
