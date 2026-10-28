from datetime import date, datetime, timezone

from app.models import (
    Bien,
    CompteBancaire,
    Gestionnaire,
    LigneDepense,
    LignePaiement,
    MandatGestion,
    Occupation,
    ReleveGestion,
    UniteLocative,
    VirementRecu,
)
from app.models.enums import (
    Banque,
    RoleMandat,
    StatutExtraction,
    StatutOccupation,
    StatutPaiement,
    TypeBien,
)
from app.services.tableau_de_bord import calculer, calculer_pour_bien

AUJOURDHUI = date(2024, 9, 15)
PERIODE_COURANTE = date(2024, 9, 1)
PERIODE_PRECEDENTE = date(2024, 8, 1)


def _creer_bien_avec_unites(session, nb_unites=1, libelle="Immeuble Sedan") -> tuple[Bien, list[UniteLocative]]:
    bien = Bien(
        type=TypeBien.IMMEUBLE,
        libelle=libelle,
        adresse_rue="1 rue Test",
        adresse_code_postal="08200",
        adresse_ville="Sedan",
    )
    session.add(bien)
    session.commit()
    session.refresh(bien)

    unites = []
    for i in range(nb_unites):
        unite = UniteLocative(bien_id=bien.id, libelle=f"Appt {i + 1}")
        session.add(unite)
        session.commit()
        session.refresh(unite)
        unites.append(unite)

    return bien, unites


def _occuper(session, unite: UniteLocative) -> None:
    session.add(
        Occupation(
            unite_locative_id=unite.id, date_entree=date(2024, 1, 1), loyer_mensuel_hc=500, statut=StatutOccupation.ACTIVE
        )
    )
    session.commit()


def _creer_releve(session, gestionnaire_id: int, bien_id: int, statut=StatutExtraction.TRAITE_OK, message=None) -> ReleveGestion:
    releve = ReleveGestion(
        gestionnaire_id=gestionnaire_id,
        bien_id=bien_id,
        periode=PERIODE_COURANTE,
        date_reception=datetime.now(timezone.utc),
        chemin_fichier_pdf="x.pdf",
        hash_fichier=f"hash-{gestionnaire_id}-{bien_id}-{statut.value}",
        statut_extraction=statut,
        erreur_extraction_message=message,
    )
    session.add(releve)
    session.commit()
    session.refresh(releve)
    return releve


def test_sans_donnees(session):
    donnees = calculer(session, AUJOURDHUI)

    assert donnees.nb_biens == 0
    assert donnees.nb_unites == 0
    assert donnees.taux_occupation == 0.0
    assert donnees.loyers_attendus_mois == 0
    assert donnees.dettes_totales == 0
    assert donnees.unites_vacantes == []
    assert donnees.impayes == []
    assert donnees.releves_en_erreur == []
    assert donnees.virements_manquants == []


def test_taux_occupation(session):
    bien, unites = _creer_bien_avec_unites(session, nb_unites=2)
    _occuper(session, unites[0])

    donnees = calculer(session, AUJOURDHUI)

    assert donnees.nb_unites == 2
    assert donnees.nb_unites_occupees == 1
    assert donnees.taux_occupation == 0.5


def test_unite_sans_occupation_est_vacante(session):
    bien, unites = _creer_bien_avec_unites(session, nb_unites=1)

    donnees = calculer(session, AUJOURDHUI)

    assert len(donnees.unites_vacantes) == 1
    assert donnees.unites_vacantes[0].unite_libelle == "Appt 1"
    assert donnees.unites_vacantes[0].bien_libelle == "Immeuble Sedan"


def test_loyers_du_mois_ignore_les_autres_periodes(session):
    bien, unites = _creer_bien_avec_unites(session)
    gestionnaire = Gestionnaire(nom="Locagestion")
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)
    releve = _creer_releve(session, gestionnaire.id, bien.id)

    session.add(
        LignePaiement(
            releve_gestion_id=releve.id,
            unite_locative_id=unites[0].id,
            periode=PERIODE_COURANTE,
            montant_attendu=500,
            montant_percu=500,
            statut=StatutPaiement.PAYE,
        )
    )
    session.add(
        LignePaiement(
            releve_gestion_id=releve.id,
            unite_locative_id=unites[0].id,
            periode=PERIODE_PRECEDENTE,
            montant_attendu=500,
            montant_percu=500,
            statut=StatutPaiement.PAYE,
        )
    )
    session.commit()

    donnees = calculer(session, AUJOURDHUI)

    assert donnees.loyers_attendus_mois == 500
    assert donnees.loyers_percus_mois == 500


def test_dettes_totales_prend_la_derniere_ligne_par_unite(session):
    bien, unites = _creer_bien_avec_unites(session)
    gestionnaire = Gestionnaire(nom="Locagestion")
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)
    releve = _creer_releve(session, gestionnaire.id, bien.id)

    session.add(
        LignePaiement(
            releve_gestion_id=releve.id,
            unite_locative_id=unites[0].id,
            periode=PERIODE_PRECEDENTE,
            montant_attendu=500,
            montant_percu=0,
            statut=StatutPaiement.IMPAYE,
            dette_cumulee=500,
        )
    )
    session.add(
        LignePaiement(
            releve_gestion_id=releve.id,
            unite_locative_id=unites[0].id,
            periode=PERIODE_COURANTE,
            montant_attendu=500,
            montant_percu=500,
            statut=StatutPaiement.PAYE,
            dette_cumulee=0,
        )
    )
    session.commit()

    donnees = calculer(session, AUJOURDHUI)

    # La dette a été régularisée sur la période la plus récente : plus de dette.
    assert donnees.dettes_totales == 0
    assert donnees.impayes == []


def test_impaye_signale_si_la_derniere_ligne_est_impayee(session):
    bien, unites = _creer_bien_avec_unites(session)
    gestionnaire = Gestionnaire(nom="Locagestion")
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)
    releve = _creer_releve(session, gestionnaire.id, bien.id)

    session.add(
        LignePaiement(
            releve_gestion_id=releve.id,
            unite_locative_id=unites[0].id,
            periode=PERIODE_COURANTE,
            montant_attendu=500,
            montant_percu=200,
            statut=StatutPaiement.PARTIEL,
            dette_cumulee=300,
        )
    )
    session.commit()

    donnees = calculer(session, AUJOURDHUI)

    assert donnees.dettes_totales == 300
    assert len(donnees.impayes) == 1
    assert donnees.impayes[0].montant_du == 300


def test_depenses_du_mois_ignore_les_autres_mois(session):
    bien, unites = _creer_bien_avec_unites(session)
    gestionnaire = Gestionnaire(nom="Locagestion")
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)
    releve = _creer_releve(session, gestionnaire.id, bien.id)

    session.add(
        LigneDepense(
            releve_gestion_id=releve.id, bien_id=bien.id, categorie="Travaux", libelle="A", montant=100, date=PERIODE_COURANTE
        )
    )
    session.add(
        LigneDepense(
            releve_gestion_id=releve.id, bien_id=bien.id, categorie="Travaux", libelle="B", montant=200, date=PERIODE_PRECEDENTE
        )
    )
    session.commit()

    donnees = calculer(session, AUJOURDHUI)

    assert donnees.depenses_mois == 100


def test_releve_en_erreur_est_liste(session):
    bien, unites = _creer_bien_avec_unites(session)
    gestionnaire = Gestionnaire(nom="ArthurImmo")
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)
    _creer_releve(session, gestionnaire.id, bien.id, statut=StatutExtraction.ERREUR_EXTRACTION, message="pas calibré")

    donnees = calculer(session, AUJOURDHUI)

    assert len(donnees.releves_en_erreur) == 1
    assert donnees.releves_en_erreur[0].message == "pas calibré"
    assert donnees.releves_en_erreur[0].gestionnaire_nom == "ArthurImmo"


def test_virement_manquant_pour_mandat_gestion_actif(session):
    bien, unites = _creer_bien_avec_unites(session)
    gestionnaire = Gestionnaire(nom="Locagestion")
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)
    session.add(
        MandatGestion(unite_locative_id=unites[0].id, gestionnaire_id=gestionnaire.id, role=RoleMandat.GESTION, date_debut=date(2024, 1, 1))
    )
    session.commit()

    donnees = calculer(session, AUJOURDHUI)

    assert len(donnees.virements_manquants) == 1
    assert donnees.virements_manquants[0].gestionnaire_nom == "Locagestion"


def test_pas_de_virement_manquant_si_virement_recu_ce_mois(session):
    bien, unites = _creer_bien_avec_unites(session)
    gestionnaire = Gestionnaire(nom="Locagestion")
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)
    session.add(
        MandatGestion(unite_locative_id=unites[0].id, gestionnaire_id=gestionnaire.id, role=RoleMandat.GESTION, date_debut=date(2024, 1, 1))
    )
    compte = CompteBancaire(banque=Banque.SG, libelle="Compte SG")
    session.add(compte)
    session.commit()
    session.refresh(compte)
    session.add(
        VirementRecu(gestionnaire_id=gestionnaire.id, compte_bancaire_id=compte.id, montant=500, date_reception=date(2024, 9, 5))
    )
    session.commit()

    donnees = calculer(session, AUJOURDHUI)

    assert donnees.virements_manquants == []


def test_pas_de_virement_manquant_pour_mandat_mise_en_location_seul(session):
    bien, unites = _creer_bien_avec_unites(session)
    gestionnaire = Gestionnaire(nom="Pergent Immobilier")
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)
    session.add(
        MandatGestion(
            unite_locative_id=unites[0].id,
            gestionnaire_id=gestionnaire.id,
            role=RoleMandat.MISE_EN_LOCATION,
            date_debut=date(2024, 1, 1),
        )
    )
    session.commit()

    donnees = calculer(session, AUJOURDHUI)

    assert donnees.virements_manquants == []


def test_pas_de_virement_manquant_si_mandat_termine(session):
    bien, unites = _creer_bien_avec_unites(session)
    gestionnaire = Gestionnaire(nom="Locagestion")
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)
    session.add(
        MandatGestion(
            unite_locative_id=unites[0].id,
            gestionnaire_id=gestionnaire.id,
            role=RoleMandat.GESTION,
            date_debut=date(2023, 1, 1),
            date_fin=date(2024, 3, 1),
        )
    )
    session.commit()

    donnees = calculer(session, AUJOURDHUI)

    assert donnees.virements_manquants == []


def test_tuile_bien_en_alerte_si_unite_vacante(session):
    bien, unites = _creer_bien_avec_unites(session, nb_unites=1)

    donnees = calculer(session, AUJOURDHUI)

    assert len(donnees.tuiles_biens) == 1
    assert donnees.tuiles_biens[0].en_alerte is True


def test_tuile_bien_sans_alerte_si_tout_va_bien(session):
    bien, unites = _creer_bien_avec_unites(session, nb_unites=1)
    _occuper(session, unites[0])

    donnees = calculer(session, AUJOURDHUI)

    assert donnees.tuiles_biens[0].en_alerte is False
    assert donnees.tuiles_biens[0].nb_occupees == 1


def test_calculer_pour_bien_sans_donnees(session):
    bien, unites = _creer_bien_avec_unites(session, nb_unites=1)

    donnees = calculer_pour_bien(session, bien.id, AUJOURDHUI)

    assert donnees.bien_id == bien.id
    assert donnees.loyers_attendus_mois == 0
    assert donnees.loyers_percus_mois == 0
    assert donnees.dettes_totales == 0
    assert donnees.depenses_mois == 0


def test_calculer_pour_bien_ignore_les_autres_biens(session):
    bien1, unites1 = _creer_bien_avec_unites(session, nb_unites=1, libelle="Immeuble Sedan")
    bien2, unites2 = _creer_bien_avec_unites(session, nb_unites=1, libelle="Immeuble Charleville")
    gestionnaire = Gestionnaire(nom="Locagestion")
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)
    releve1 = _creer_releve(session, gestionnaire.id, bien1.id)
    releve2 = _creer_releve(session, gestionnaire.id, bien2.id)

    session.add(
        LignePaiement(
            releve_gestion_id=releve1.id,
            unite_locative_id=unites1[0].id,
            periode=PERIODE_COURANTE,
            montant_attendu=500,
            montant_percu=500,
            statut=StatutPaiement.PAYE,
        )
    )
    session.add(
        LignePaiement(
            releve_gestion_id=releve2.id,
            unite_locative_id=unites2[0].id,
            periode=PERIODE_COURANTE,
            montant_attendu=700,
            montant_percu=700,
            statut=StatutPaiement.PAYE,
        )
    )
    session.commit()

    donnees_bien1 = calculer_pour_bien(session, bien1.id, AUJOURDHUI)

    assert donnees_bien1.loyers_attendus_mois == 500
    assert donnees_bien1.loyers_percus_mois == 500


def test_calculer_pour_bien_dettes_et_impayes(session):
    bien, unites = _creer_bien_avec_unites(session, nb_unites=1)
    gestionnaire = Gestionnaire(nom="Locagestion")
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)
    releve = _creer_releve(session, gestionnaire.id, bien.id)

    session.add(
        LignePaiement(
            releve_gestion_id=releve.id,
            unite_locative_id=unites[0].id,
            periode=PERIODE_COURANTE,
            montant_attendu=500,
            montant_percu=200,
            statut=StatutPaiement.PARTIEL,
            dette_cumulee=300,
        )
    )
    session.commit()

    donnees = calculer_pour_bien(session, bien.id, AUJOURDHUI)

    assert donnees.dettes_totales == 300


def test_calculer_pour_bien_depenses_rattachees_au_bien_et_a_une_unite(session):
    bien, unites = _creer_bien_avec_unites(session, nb_unites=1)

    session.add(
        LigneDepense(bien_id=bien.id, categorie="Taxe foncière", libelle="Taxe", montant=1200, date=PERIODE_COURANTE)
    )
    session.add(
        LigneDepense(
            unite_locative_id=unites[0].id, categorie="Travaux", libelle="Plomberie", montant=300, date=PERIODE_COURANTE
        )
    )
    session.add(
        LigneDepense(bien_id=bien.id, categorie="Taxe foncière", libelle="Vieille taxe", montant=999, date=PERIODE_PRECEDENTE)
    )
    session.commit()

    donnees = calculer_pour_bien(session, bien.id, AUJOURDHUI)

    assert donnees.depenses_mois == 1500


def test_calculer_pour_bien_inexistant_ne_leve_pas(session):
    donnees = calculer_pour_bien(session, 999, AUJOURDHUI)

    assert donnees.bien_id == 999
    assert donnees.loyers_attendus_mois == 0
    assert donnees.depenses_mois == 0
