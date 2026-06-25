"""fix_editalstatus_enum_case

Revision ID: d67cf076716b
Revises: a32546c008ea
Create Date: 2026-06-25 17:41:04.103611

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd67cf076716b'
down_revision: Union[str, None] = 'a32546c008ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Converte para VARCHAR, recria o enum com nomes em maiúsculas
    # (SQLAlchemy envia o .name do enum, não o .value)
    op.execute("ALTER TABLE editais ALTER COLUMN status TYPE VARCHAR(50)")
    op.execute("DROP TYPE editalstatus")
    op.execute(
        "CREATE TYPE editalstatus AS ENUM "
        "('PUBLICADO', 'ABERTO', 'EM_ANDAMENTO', 'DISPUTA_ABERTA', "
        "'HOMOLOGADO', 'CANCELADO', 'ENCERRADO')"
    )
    op.execute(
        "ALTER TABLE editais ALTER COLUMN status TYPE editalstatus "
        "USING status::editalstatus"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE editais ALTER COLUMN status TYPE VARCHAR(50)")
    op.execute("DROP TYPE editalstatus")
    op.execute(
        "CREATE TYPE editalstatus AS ENUM "
        "('publicado', 'aberto', 'em_andamento', 'disputa_aberta', "
        "'homologado', 'cancelado', 'encerrado')"
    )
    op.execute(
        "ALTER TABLE editais ALTER COLUMN status TYPE editalstatus "
        "USING status::editalstatus"
    )
