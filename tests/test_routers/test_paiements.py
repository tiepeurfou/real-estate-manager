from datetime import date, datetime, timezone

from app.models import Bien, Gestionnaire, LignePaiement, ReleveGestion, UniteLocative
from app.models.enums import StatutExtraction, StatutPaiement, TypeBien


def _creer_unite_avec_paiement(session, periode: date, statut: StatutPaiement) -> UniteLocative:
    bien = Bien(
        type=TypeBien.IMMEUBLE,
        libelle="Immeuble Sedan",
        adresse_rue="1 rue Test",
        adresse_code_postal="08200",
        adresse_ville="Sedan",
    )
    session.add(bien)
    session.commit()
    session.refresh(bien)

    unite = UniteLocative(bien_id=bien.id, libelle="Appt 1")
    session.add(unite)
    session.commit()
    session.refresh(unite)

    gestionnaire = Gestionnaire(nom="Locagestion")
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)

    releve = ReleveGestion(
        gestionnaire_id=gestionnaire.id,
        bien_id=bien.id,
        periode=periode,
        date_reception=datetime.now(timezone.utc),
        chemin_fichier_pdf="x.pdf",
        hash_fichier=f"hash-paiement-{periode.isoformat()}",
        statut_extraction=StatutExtraction.TRAITE_OK,
    )
    session.add(releve)
    session.commit()
    session.refresh(releve)

    session.add(
        LignePaiement(
            releve_gestion_id=releve.id,
            unite_locative_id=unite.id,
            periode=periode,
            montant_attendu=500,
            montant_percu=500 if statut == StatutPaiement.PAYE else 0,
            statut=statut,
        )
    )
    session.commit()

    return unite


def test_grille_sans_unite(client_connecte):
    reponse = client_connecte.get("/paiements")
    assert reponse.status_code == 200
    assert "Aucune unité" in reponse.text


def test_acces_sans_session_redirige(client):
    reponse = client.get("/paiements", follow_redirects=False)
    assert reponse.status_code == 303
    assert reponse.headers["location"].endswith("/login")


def test_grille_affiche_le_statut_du_mois_courant(client_connecte, session):
    aujourdhui = date.today()
    periode_courante = date(aujourdhui.year, aujourdhui.month, 1)
    _creer_unite_avec_paiement(session, periode_courante, StatutPaiement.PAYE)

    reponse = client_connecte.get("/paiements")
    assert reponse.status_code == 200
    assert "paye" in reponse.text
    assert "Appt 1" in reponse.text


def test_grille_cellule_vide_sans_ligne_de_paiement(client_connecte, session):
    bien_id_sans_paiement = _creer_unite_avec_paiement(
        session, date(2000, 1, 1), StatutPaiement.PAYE
    )  # hors de la fenêtre des derniers mois affichés

    reponse = client_connecte.get("/paiements", params={"nb_mois": "3"})
    assert reponse.status_code == 200
    assert "—" in reponse.text
