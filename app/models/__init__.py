"""Réexporte tous les modèles pour que SQLModel.metadata les connaisse
(nécessaire pour la création des tables et l'autogénération Alembic)."""

from app.models.bien import Bien
from app.models.candidat_courriel_notifie import CandidatCourrielNotifie
from app.models.candidat_courriel_traite import CandidatCourrielTraite
from app.models.compte_bancaire import CompteBancaire
from app.models.contact_gestionnaire import ContactGestionnaire
from app.models.depense_recurrente import DepenseRecurrente
from app.models.gestionnaire import Gestionnaire
from app.models.ligne_depense import LigneDepense
from app.models.ligne_paiement import LignePaiement
from app.models.locataire import Locataire
from app.models.mandat_gestion import MandatGestion
from app.models.occupation import Occupation
from app.models.occupation_locataire import OccupationLocataire
from app.models.rappel_dpe_notifie import RappelDpeNotifie
from app.models.rappel_revision_loyer_notifie import RappelRevisionLoyerNotifie
from app.models.rapprochement import Rapprochement
from app.models.rapprochement_ligne import RapprochementLigne
from app.models.releve_gestion import ReleveGestion
from app.models.unite_locative import UniteLocative
from app.models.utilisateur import Utilisateur
from app.models.virement_recu import VirementRecu

__all__ = [
    "Bien",
    "CandidatCourrielNotifie",
    "CandidatCourrielTraite",
    "CompteBancaire",
    "ContactGestionnaire",
    "DepenseRecurrente",
    "Gestionnaire",
    "LigneDepense",
    "LignePaiement",
    "Locataire",
    "MandatGestion",
    "Occupation",
    "OccupationLocataire",
    "RappelDpeNotifie",
    "RappelRevisionLoyerNotifie",
    "Rapprochement",
    "RapprochementLigne",
    "ReleveGestion",
    "UniteLocative",
    "Utilisateur",
    "VirementRecu",
]
