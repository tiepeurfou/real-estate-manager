from datetime import date, datetime, timezone

from app.models import Bien, Gestionnaire, LigneDepense, LignePaiement, MandatGestion, ReleveGestion, UniteLocative
from app.models.enums import RoleMandat, StatutExtraction, StatutPaiement, TypeBien


def _creer_bien_avec_unite(session, libelle_bien="Immeuble Sedan") -> tuple[Bien, UniteLocative]:
    bien = Bien(
        type=TypeBien.IMMEUBLE,
        libelle=libelle_bien,
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
    return bien, unite


def test_acces_sans_session_redirige(client):
    reponse = client.get("/tableau-de-bord/mois", follow_redirects=False)
    assert reponse.status_code == 303
    assert reponse.headers["location"].endswith("/login")


def test_sans_parametres_utilise_le_mois_courant(client_connecte):
    reponse = client_connecte.get("/tableau-de-bord/mois")
    assert reponse.status_code == 200
    assert "mois courant" in reponse.text


def test_mois_passe_n_affiche_pas_le_badge_mois_courant_et_propose_suivant(client_connecte):
    reponse = client_connecte.get("/tableau-de-bord/mois", params={"annee": 2024, "mois": 9})
    assert reponse.status_code == 200
    assert "Septembre 2024" in reponse.text
    assert "mois courant" not in reponse.text


def test_mois_invalide(client_connecte):
    assert client_connecte.get("/tableau-de-bord/mois", params={"annee": 2024, "mois": 13}).status_code == 400
    assert client_connecte.get("/tableau-de-bord/mois", params={"annee": 2024, "mois": 0}).status_code == 400


def test_annee_invalide(client_connecte):
    assert client_connecte.get("/tableau-de-bord/mois", params={"annee": 0, "mois": 9}).status_code == 400


def test_bien_inexistant(client_connecte):
    assert client_connecte.get("/tableau-de-bord/mois", params={"bien_id": 999}).status_code == 404


def test_affiche_les_loyers_et_depenses_du_mois(client_connecte, session):
    bien, unite = _creer_bien_avec_unite(session)
    gestionnaire = Gestionnaire(nom="Locagestion")
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)
    releve = ReleveGestion(
        gestionnaire_id=gestionnaire.id, bien_id=bien.id, periode=date(2024, 9, 1),
        date_reception=datetime.now(timezone.utc), chemin_fichier_pdf="x.pdf", hash_fichier="h1",
        statut_extraction=StatutExtraction.TRAITE_OK,
    )
    session.add(releve)
    session.commit()
    session.refresh(releve)
    session.add(
        LignePaiement(releve_gestion_id=releve.id, unite_locative_id=unite.id, periode=date(2024, 9, 1), montant_attendu=500, montant_percu=500, statut=StatutPaiement.PAYE)
    )
    session.add(LigneDepense(bien_id=bien.id, categorie="Travaux", libelle="x", montant=120, date=date(2024, 9, 10)))
    session.commit()

    reponse = client_connecte.get("/tableau-de-bord/mois", params={"annee": 2024, "mois": 9})
    assert reponse.status_code == 200
    assert "500" in reponse.text
    assert "120.00" in reponse.text
    assert "Travaux" in reponse.text
    assert "Locagestion" in reponse.text


def test_signale_un_gestionnaire_sans_compte_rendu(client_connecte, session):
    bien, unite = _creer_bien_avec_unite(session)
    gestionnaire = Gestionnaire(nom="Pergent Immobilier")
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)
    session.add(
        MandatGestion(unite_locative_id=unite.id, gestionnaire_id=gestionnaire.id, role=RoleMandat.GESTION, date_debut=date(2024, 1, 1))
    )
    session.commit()

    reponse = client_connecte.get("/tableau-de-bord/mois", params={"annee": 2024, "mois": 9})
    assert reponse.status_code == 200
    assert "pas encore reçu" in reponse.text
    assert "Pergent Immobilier" in reponse.text


def test_filtre_par_bien_masque_la_vue_par_type(client_connecte, session):
    bien, unite = _creer_bien_avec_unite(session)

    reponse = client_connecte.get("/tableau-de-bord/mois", params={"annee": 2024, "mois": 9, "bien_id": bien.id})
    assert reponse.status_code == 200
    assert "Par type de bien" not in reponse.text


def test_sans_filtre_affiche_la_vue_par_type(client_connecte, session):
    _creer_bien_avec_unite(session)

    reponse = client_connecte.get("/tableau-de-bord/mois", params={"annee": 2024, "mois": 9})
    assert reponse.status_code == 200
    assert "Par type de bien" in reponse.text


def test_lien_depuis_le_detail_du_bien(client_connecte, session):
    bien, unite = _creer_bien_avec_unite(session)

    detail = client_connecte.get(f"/biens/{bien.id}")
    assert f"/tableau-de-bord/mois?bien_id={bien.id}" in detail.text
