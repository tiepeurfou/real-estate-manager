"""ajoute residence_principale au type de bien

Revision ID: 311f4d167b1d
Revises: 5a7cf2791ce9
Create Date: 2026-10-28 15:59:18.719447

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '311f4d167b1d'
down_revision: Union[str, Sequence[str], None] = '5a7cf2791ce9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Autogenerate propose un op.alter_column non batché, qui casse sur
    # SQLite (ALTER COLUMN TYPE non supporté nativement). En pratique SQLite
    # ne matérialise aucune contrainte sur ce type (toujours stocké en texte
    # libre) : il s'agit juste d'aligner la longueur VARCHAR connue
    # d'Alembic avec la nouvelle valeur d'enum, sans ajouter de contrainte.
    with op.batch_alter_table('bien', schema=None) as batch_op:
        batch_op.alter_column(
            'type',
            existing_type=sa.VARCHAR(length=17),
            type_=sqlmodel.sql.sqltypes.AutoString(length=20),
            existing_nullable=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('bien', schema=None) as batch_op:
        batch_op.alter_column(
            'type',
            existing_type=sqlmodel.sql.sqltypes.AutoString(length=20),
            type_=sa.VARCHAR(length=17),
            existing_nullable=False,
        )
