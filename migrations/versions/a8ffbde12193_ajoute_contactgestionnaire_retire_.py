"""ajoute contactgestionnaire, retire contact_email et contact_tel

Revision ID: a8ffbde12193
Revises: d25ed9c14b0a
Create Date: 2026-10-28 11:17:58.013553

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'a8ffbde12193'
down_revision: Union[str, Sequence[str], None] = 'd25ed9c14b0a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'contactgestionnaire',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('gestionnaire_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.Enum('EMAIL', 'TELEPHONE', name='typecontact'), nullable=False),
        sa.Column('valeur', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('libelle', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(['gestionnaire_id'], ['gestionnaire.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )

    # Un gestionnaire peut avoir plusieurs emails/téléphones : on migre les
    # valeurs existantes (un email + un tel par gestionnaire) vers la
    # nouvelle table avant de retirer les colonnes de gestionnaire.
    connexion = op.get_bind()
    lignes = connexion.execute(sa.text("SELECT id, contact_email, contact_tel FROM gestionnaire")).fetchall()
    for gestionnaire_id, contact_email, contact_tel in lignes:
        if contact_email:
            connexion.execute(
                sa.text(
                    "INSERT INTO contactgestionnaire (gestionnaire_id, type, valeur) "
                    "VALUES (:gid, 'EMAIL', :valeur)"
                ),
                {"gid": gestionnaire_id, "valeur": contact_email},
            )
        if contact_tel:
            connexion.execute(
                sa.text(
                    "INSERT INTO contactgestionnaire (gestionnaire_id, type, valeur) "
                    "VALUES (:gid, 'TELEPHONE', :valeur)"
                ),
                {"gid": gestionnaire_id, "valeur": contact_tel},
            )

    with op.batch_alter_table('gestionnaire', schema=None) as batch_op:
        batch_op.drop_column('contact_tel')
        batch_op.drop_column('contact_email')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('gestionnaire', schema=None) as batch_op:
        batch_op.add_column(sa.Column('contact_email', sa.VARCHAR(), nullable=True))
        batch_op.add_column(sa.Column('contact_tel', sa.VARCHAR(), nullable=True))

    connexion = op.get_bind()
    lignes = connexion.execute(
        sa.text("SELECT gestionnaire_id, type, valeur FROM contactgestionnaire")
    ).fetchall()
    for gestionnaire_id, type_contact, valeur in lignes:
        colonne = "contact_email" if type_contact == "EMAIL" else "contact_tel"
        connexion.execute(
            sa.text(f"UPDATE gestionnaire SET {colonne} = :valeur WHERE id = :gid"),
            {"valeur": valeur, "gid": gestionnaire_id},
        )

    op.drop_table('contactgestionnaire')
