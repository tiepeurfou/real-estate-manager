from enum import Enum


class TypeBien(str, Enum):
    APPARTEMENT_ISOLE = "appartement_isole"
    IMMEUBLE = "immeuble"


class DpeLettre(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"


class RoleMandat(str, Enum):
    MISE_EN_LOCATION = "mise_en_location"
    GESTION = "gestion"


class TypeGarantie(str, Enum):
    VISALE = "visale"
    ASSURANCE_LOYERS_IMPAYES = "assurance_loyers_impayes"
    GARANT_PERSONNE = "garant_personne"
    AUCUNE = "aucune"


class StatutOccupation(str, Enum):
    ACTIVE = "active"
    TERMINEE = "terminee"


class Banque(str, Enum):
    SG = "SG"
    LCL = "LCL"
    BOURSORAMA = "BOURSORAMA"


class StatutExtraction(str, Enum):
    NON_TRAITE = "non_traite"
    TRAITE_OK = "traite_ok"
    ERREUR_EXTRACTION = "erreur_extraction"


class StatutPaiement(str, Enum):
    PAYE = "paye"
    IMPAYE = "impaye"
    PARTIEL = "partiel"


class StatutCandidatCourriel(str, Enum):
    IMPORTE = "importe"
    IGNORE = "ignore"


class TypeContact(str, Enum):
    EMAIL = "email"
    TELEPHONE = "telephone"


class FrequenceDepense(str, Enum):
    MENSUELLE = "mensuelle"
    TRIMESTRIELLE = "trimestrielle"
    ANNUELLE = "annuelle"
