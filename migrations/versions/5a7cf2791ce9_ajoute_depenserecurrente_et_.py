"""ajoute depenserecurrente et lignedepense.depense_recurrente_id

Revision ID: 5a7cf2791ce9
Revises: 6ace57ecce26
Create Date: 2026-10-28 14:59:21.400214

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '5a7cf2791ce9'
down_revision: Union[str, Sequence[str], None] = '6ace57ecce26'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'depenserecurrente',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('bien_id', sa.Integer(), nullable=False),
        sa.Column('unite_locative_id', sa.Integer(), nullable=True),
        sa.Column('categorie', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('libelle', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('montant', sa.Float(), nullable=False),
        sa.Column('frequence', sa.Enum('MENSUELLE', 'TRIMESTRIELLE', 'ANNUELLE', name='frequencedepense'), nullable=False),
        sa.Column('date_debut', sa.Date(), nullable=False),
        sa.Column('date_fin', sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(['bien_id'], ['bien.id'], ),
        sa.ForeignKeyConstraint(['unite_locative_id'], ['unitelocative.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )

    with op.batch_alter_table('lignedepense', schema=None) as batch_op:
        batch_op.add_column(sa.Column('depense_recurrente_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_lignedepense_depense_recurrente_id', 'depenserecurrente', ['depense_recurrente_id'], ['id']
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('lignedepense', schema=None) as batch_op:
        batch_op.drop_constraint('fk_lignedepense_depense_recurrente_id', type_='foreignkey')
        batch_op.drop_column('depense_recurrente_id')

    op.drop_table('depenserecurrente')
