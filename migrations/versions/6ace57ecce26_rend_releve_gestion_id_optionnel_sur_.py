"""rend releve_gestion_id optionnel sur lignedepense pour la saisie manuelle

Revision ID: 6ace57ecce26
Revises: a8ffbde12193
Create Date: 2026-10-28 11:29:16.489136

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '6ace57ecce26'
down_revision: Union[str, Sequence[str], None] = 'a8ffbde12193'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Une dépense peut désormais être saisie manuellement (taxe foncière,
    # assurance propriétaire...) sans être rattachée à un relevé de gestion.
    with op.batch_alter_table('lignedepense', schema=None) as batch_op:
        batch_op.alter_column('releve_gestion_id', existing_type=sa.INTEGER(), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('lignedepense', schema=None) as batch_op:
        batch_op.alter_column('releve_gestion_id', existing_type=sa.INTEGER(), nullable=False)
