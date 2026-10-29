from email.message import EmailMessage

import app.services.mail as mail_module
from app.models import Bien, CandidatCourrielTraite, Gestionnaire, ReleveGestion, UniteLocative
from app.models.enums import StatutCandidatCourriel, TypeBien
from tests.aide_pdf import creer_pdf_bytes
from tests.faux_serveur_imap import FauxServeurImap


def _email_avec_pdf(nom_pdf="releve.pdf", contenu_pdf: bytes | None = None) -> bytes:
    message = EmailMessage()
    message["From"] = "quelqu-un@exemple.fr"
    message["Subject"] = "Compte-rendu"
    message["Date"] = "Tue, 10 Sep 2024 08:00:00 +0200"
    message.set_content("Voir document joint.")
    message.add_attachment(
        contenu_pdf or creer_pdf_bytes("Compte-rendu"), maintype="application", subtype="pdf", filename=nom_pdf
    )
    return message.as_bytes()


def _pointer_vers(monkeypatch, serveur, utilisateur="test@exemple.fr", mot_de_passe="motdepasse"):
    monkeypatch.setattr(mail_module, "GMAIL_IMAP_HOTE", "127.0.0.1")
    monkeypatch.setattr(mail_module, "GMAIL_IMAP_PORT", serveur.port)
    monkeypatch.setattr(mail_module, "GMAIL_IMAP_ADRESSE", utilisateur)
    monkeypatch.setattr(mail_module, "GMAIL_IMAP_MOT_DE_PASSE", mot_de_passe)
    monkeypatch.setattr(mail_module, "GMAIL_IMAP_SSL", False)


def _creer_bien_et_gestionnaire(session):
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
    session.add(UniteLocative(bien_id=bien.id, libelle="Appt 1"))
    session.commit()

    gestionnaire = Gestionnaire(nom="Locagestion")
    session.add(gestionnaire)
    session.commit()
    session.refresh(gestionnaire)

    return bien, gestionnaire


def test_non_configure_affiche_un_message(client_connecte):
    reponse = client_connecte.get("/ingestion-mail")
    assert reponse.status_code == 200
    assert "non configurée" in reponse.text


def test_acces_sans_session_redirige(client):
    reponse = client.get("/ingestion-mail", follow_redirects=False)
    assert reponse.status_code == 303
    assert reponse.headers["location"].endswith("/login")


def test_liste_les_candidats_depuis_le_faux_serveur(client_connecte, monkeypatch, dossier_documents_temporaire):
    messages = {"1": _email_avec_pdf()}
    with FauxServeurImap(messages, "test@exemple.fr", "motdepasse") as serveur:
        _pointer_vers(monkeypatch, serveur)
        reponse = client_connecte.get("/ingestion-mail")

    assert reponse.status_code == 200
    assert "releve.pdf" in reponse.text
    assert "quelqu-un@exemple.fr" in reponse.text


def test_erreur_de_connexion_affiche_un_message(client_connecte, monkeypatch, dossier_documents_temporaire):
    monkeypatch.setattr(mail_module, "GMAIL_IMAP_HOTE", "127.0.0.1")
    monkeypatch.setattr(mail_module, "GMAIL_IMAP_PORT", 1)
    monkeypatch.setattr(mail_module, "GMAIL_IMAP_ADRESSE", "test@exemple.fr")
    monkeypatch.setattr(mail_module, "GMAIL_IMAP_MOT_DE_PASSE", "motdepasse")
    monkeypatch.setattr(mail_module, "GMAIL_IMAP_SSL", False)

    reponse = client_connecte.get("/ingestion-mail")
    assert reponse.status_code == 200
    assert "Connexion IMAP impossible" in reponse.text


def test_importer_cree_le_releve_et_marque_traite(client_connecte, session, monkeypatch, dossier_documents_temporaire, engine):
    bien, gestionnaire = _creer_bien_et_gestionnaire(session)
    messages = {"1": _email_avec_pdf()}

    with FauxServeurImap(messages, "test@exemple.fr", "motdepasse") as serveur:
        _pointer_vers(monkeypatch, serveur)

        reponse = client_connecte.post(
            "/ingestion-mail/importer",
            data={
                "message_uid": "1",
                "nom_piece_jointe": "releve.pdf",
                "gestionnaire_id": str(gestionnaire.id),
                "bien_id": str(bien.id),
                "periode": "2024-09-01",
            },
            follow_redirects=False,
        )
        assert reponse.status_code == 303

        reponse_liste = client_connecte.get("/ingestion-mail")
        assert "releve.pdf" not in reponse_liste.text

    from sqlmodel import Session, select

    with Session(engine) as s:
        releve = s.exec(select(ReleveGestion)).first()
        assert releve is not None
        assert releve.gestionnaire_id == gestionnaire.id

        candidat = s.exec(select(CandidatCourrielTraite)).first()
        assert candidat.statut == StatutCandidatCourriel.IMPORTE
        assert candidat.releve_gestion_id == releve.id


def test_importer_gestionnaire_inexistant(client_connecte, session, monkeypatch, dossier_documents_temporaire):
    bien, _ = _creer_bien_et_gestionnaire(session)
    messages = {"1": _email_avec_pdf()}

    with FauxServeurImap(messages, "test@exemple.fr", "motdepasse") as serveur:
        _pointer_vers(monkeypatch, serveur)
        reponse = client_connecte.post(
            "/ingestion-mail/importer",
            data={
                "message_uid": "1",
                "nom_piece_jointe": "releve.pdf",
                "gestionnaire_id": "999",
                "bien_id": str(bien.id),
                "periode": "2024-09-01",
            },
        )
        assert reponse.status_code == 404


def test_importer_bien_inexistant(client_connecte, session, monkeypatch, dossier_documents_temporaire):
    _, gestionnaire = _creer_bien_et_gestionnaire(session)
    messages = {"1": _email_avec_pdf()}

    with FauxServeurImap(messages, "test@exemple.fr", "motdepasse") as serveur:
        _pointer_vers(monkeypatch, serveur)
        reponse = client_connecte.post(
            "/ingestion-mail/importer",
            data={
                "message_uid": "1",
                "nom_piece_jointe": "releve.pdf",
                "gestionnaire_id": str(gestionnaire.id),
                "bien_id": "999",
                "periode": "2024-09-01",
            },
        )
        assert reponse.status_code == 404


def test_importer_periode_invalide(client_connecte, session, monkeypatch, dossier_documents_temporaire):
    bien, gestionnaire = _creer_bien_et_gestionnaire(session)
    messages = {"1": _email_avec_pdf()}

    with FauxServeurImap(messages, "test@exemple.fr", "motdepasse") as serveur:
        _pointer_vers(monkeypatch, serveur)
        reponse = client_connecte.post(
            "/ingestion-mail/importer",
            data={
                "message_uid": "1",
                "nom_piece_jointe": "releve.pdf",
                "gestionnaire_id": str(gestionnaire.id),
                "bien_id": str(bien.id),
                "periode": "pas-une-date",
            },
        )
        assert reponse.status_code == 400


def test_importer_periode_vide_est_rejetee_proprement(client_connecte, session, monkeypatch, dossier_documents_temporaire):
    # "periode" est un champ Form(...) requis : une valeur vide est traitée
    # par Starlette comme un champ absent (422 natif FastAPI), jamais
    # comme une chaîne vide atteignant notre propre validation.
    bien, gestionnaire = _creer_bien_et_gestionnaire(session)
    messages = {"1": _email_avec_pdf()}

    with FauxServeurImap(messages, "test@exemple.fr", "motdepasse") as serveur:
        _pointer_vers(monkeypatch, serveur)
        reponse = client_connecte.post(
            "/ingestion-mail/importer",
            data={
                "message_uid": "1",
                "nom_piece_jointe": "releve.pdf",
                "gestionnaire_id": str(gestionnaire.id),
                "bien_id": str(bien.id),
                "periode": "",
            },
        )
        assert reponse.status_code == 422


def test_importer_piece_jointe_disparue_entre_le_listing_et_l_import(
    client_connecte, session, monkeypatch, dossier_documents_temporaire
):
    # Scénario : le mail a été déplacé/supprimé de la boîte entre le moment
    # où l'utilisateur a vu la liste et le clic "importer". Le faux serveur
    # ne connaît plus ce message_uid : recuperer_piece_jointe() lève un
    # ValueError explicite, que la route traduit en 400 (pas de 500).
    bien, gestionnaire = _creer_bien_et_gestionnaire(session)
    messages = {"1": _email_avec_pdf()}

    with FauxServeurImap(messages, "test@exemple.fr", "motdepasse") as serveur:
        _pointer_vers(monkeypatch, serveur)
        reponse = client_connecte.post(
            "/ingestion-mail/importer",
            data={
                "message_uid": "999",
                "nom_piece_jointe": "releve.pdf",
                "gestionnaire_id": str(gestionnaire.id),
                "bien_id": str(bien.id),
                "periode": "2024-09-01",
            },
        )
        assert reponse.status_code == 400


def test_importer_deux_fois_le_meme_contenu_est_refuse(
    client_connecte, session, monkeypatch, dossier_documents_temporaire
):
    bien, gestionnaire = _creer_bien_et_gestionnaire(session)
    contenu_pdf = creer_pdf_bytes("Compte-rendu")
    # Même contenu PDF strictement (reportlab produit des octets différents à
    # chaque appel, même pour un texte identique, donc on réutilise les mêmes octets).
    messages = {"1": _email_avec_pdf(contenu_pdf=contenu_pdf), "2": _email_avec_pdf("releve-bis.pdf", contenu_pdf=contenu_pdf)}

    with FauxServeurImap(messages, "test@exemple.fr", "motdepasse") as serveur:
        _pointer_vers(monkeypatch, serveur)
        donnees_base = {"gestionnaire_id": str(gestionnaire.id), "bien_id": str(bien.id), "periode": "2024-09-01"}

        reponse1 = client_connecte.post(
            "/ingestion-mail/importer",
            data={**donnees_base, "message_uid": "1", "nom_piece_jointe": "releve.pdf"},
            follow_redirects=False,
        )
        assert reponse1.status_code == 303

        reponse2 = client_connecte.post(
            "/ingestion-mail/importer",
            data={**donnees_base, "message_uid": "2", "nom_piece_jointe": "releve-bis.pdf"},
            follow_redirects=False,
        )
        assert reponse2.status_code == 400


def test_ignorer_marque_traite_et_disparait_de_la_liste(client_connecte, monkeypatch, dossier_documents_temporaire, engine):
    messages = {"1": _email_avec_pdf()}

    with FauxServeurImap(messages, "test@exemple.fr", "motdepasse") as serveur:
        _pointer_vers(monkeypatch, serveur)

        reponse = client_connecte.post(
            "/ingestion-mail/ignorer",
            data={"message_uid": "1", "nom_piece_jointe": "releve.pdf"},
            follow_redirects=False,
        )
        assert reponse.status_code == 303

        reponse_liste = client_connecte.get("/ingestion-mail")
        assert "releve.pdf" not in reponse_liste.text

    from sqlmodel import Session, select

    with Session(engine) as s:
        candidat = s.exec(select(CandidatCourrielTraite)).first()
        assert candidat.statut == StatutCandidatCourriel.IGNORE
        assert candidat.releve_gestion_id is None
