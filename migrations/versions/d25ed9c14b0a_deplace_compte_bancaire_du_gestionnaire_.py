"""deplace compte_bancaire du gestionnaire vers le mandat

Revision ID: d25ed9c14b0a
Revises: 5ac4f897e51f
Create Date: 2026-10-28 10:55:51.715881

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'd25ed9c14b0a'
down_revision: Union[str, Sequence[str], None] = '5ac4f897e51f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Un même gestionnaire peut verser sur des comptes différents selon le
    # bien géré : le compte bancaire devient un attribut du mandat, plus du
    # gestionnaire. SQLite ne supporte pas ALTER TABLE directement, d'où le
    # mode batch (recrée la table sous le capot).
    with op.batch_alter_table('gestionnaire', schema=None) as batch_op:
        batch_op.drop_column('compte_bancaire_id')

    with op.batch_alter_table('mandatgestion', schema=None) as batch_op:
        batch_op.add_column(sa.Column('compte_bancaire_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_mandatgestion_compte_bancaire_id', 'comptebancaire', ['compte_bancaire_id'], ['id']
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('mandatgestion', schema=None) as batch_op:
        batch_op.drop_constraint('fk_mandatgestion_compte_bancaire_id', type_='foreignkey')
        batch_op.drop_column('compte_bancaire_id')

    with op.batch_alter_table('gestionnaire', schema=None) as batch_op:
        batch_op.add_column(sa.Column('compte_bancaire_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_gestionnaire_compte_bancaire_id', 'comptebancaire', ['compte_bancaire_id'], ['id']
        )
