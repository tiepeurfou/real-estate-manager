# Real Estate Manager

Application de gestion d'un patrimoine locatif personnel : biens/immeubles, gestionnaires, locataires, et suivi financier (loyers, impayés, dépenses, virements).

## Contexte métier

Le propriétaire possède :
- 1 appartement à Villiers-sur-Marne (loi Pinel), en **gestion locative complète** par ArthurImmo (un seul gestionnaire fait tout).
- 1 immeuble de 3 appartements à Sedan : **mise en location** par Pergent Immobilier, **gestion** (loyers, urgences, comptes-rendus) par Locagestion.
- 1 immeuble de 4 appartements à Charleville-Mézières : même répartition que Sedan.

Deux rôles de gestionnaire sont donc modélisés séparément : `mise_en_location` (recherche de locataire, états des lieux) et `gestion` (loyers, urgences, comptes-rendus). Une "gestion locative complète" se traduit simplement par un même gestionnaire portant les deux rôles sur une unité — **il n'existe pas de valeur d'enum à part pour ce cas** (voir `app/models/mandat_gestion.py`).

## Contraintes fortes (à respecter dans toute évolution)

1. **Raspberry Pi 5 (16 Go RAM, SSD, Debian Bookworm)** est la cible d'exécution. Toujours privilégier les composants légers et locaux plutôt que des alternatives lourdes (pas de moteur DB serveur séparé, pas de bundler JS, pas de queue/broker pour ce volume de données).
2. **Projet totalement indépendant** des autres projets de l'utilisateur : aucune réutilisation de code/fonction/méthode provenant d'ailleurs. Ce dépôt est autonome.
3. L'interface web doit être servie sous le path `/real-estate-manager/`. Le HTTPS/TLS n'est **pas** géré par cette application : il est assuré en amont par un reverse proxy mTLS tournant sur un autre Raspberry Pi — **ce proxy doit retirer le préfixe avant de transmettre la requête** (ex. `reverse_proxy` avec strip du préfixe côté Caddy/nginx) ; côté app, le préfixe n'est utilisé que pour générer les URLs sortantes (via `--root-path`, voir plus bas). L'authentification applicative reste donc un simple login/mot de passe.
4. **Pas de connexion bancaire automatique** (ni agrégateur DSP2, ni scraping) : les virements reçus sont **déclarés manuellement** par l'utilisateur via un écran dédié, avec un rapprochement assisté contre les lignes de paiement extraites des comptes-rendus PDF.
5. Les mails des gestionnaires sont lus depuis une **boîte Gmail dédiée** (pas la boîte personnelle de l'utilisateur), en **IMAP + mot de passe d'application** (pas l'API Gmail OAuth2 — en statut "Test" sur Google Cloud, les refresh tokens des scopes restreints comme `gmail.readonly` expirent au bout de 7 jours, impraticable pour un service autonome ; IMAP + mot de passe d'application n'a pas cette limite). **La boîte dédiée reçoit tout le courrier personnel transféré** (pas que les 3 gestionnaires) : impossible de filtrer par expéditeur. Le tri est donc **manuel**, pièce jointe PDF par pièce jointe, via l'écran `/ingestion-mail` (import ou "ignorer").
6. **Tous les modules de code applicatif (routers, services, logique métier) doivent avoir une couverture de tests unitaires complète** (cas heureux + cas limites/erreurs), pas seulement un test de fumée — contrairement au modèle de données initial qui n'a qu'un test illustratif.

## Stack technique

| Couche | Choix | Pourquoi |
|---|---|---|
| Langage | Python 3.11+ | léger à l'exécution, écosystème mature pour parsing PDF/mail |
| Backend web | FastAPI + Uvicorn | léger, async natif pour le polling mail en tâche de fond |
| ORM / modèles | SQLModel | typage propre, basé sur SQLAlchemy + Pydantic |
| Base de données | SQLite (`data/app.db`) | mono-utilisateur, zéro serveur dédié, suffisant pour ce volume |
| Migrations | Alembic (configuré, autogenerate branché sur `SQLModel.metadata`) | |
| Frontend | Jinja2 + HTMX + Alpine.js, vendorisés localement dans `app/static/js/` (pas de CDN) | pas de build JS, faible empreinte CPU/RAM sur ARM |
| Auth | Session cookie (`itsdangerous`/Starlette `SessionMiddleware`) + mots de passe hashés en Argon2 (`argon2-cffi`) | cohérent avec le TLS déjà géré en amont ; pas besoin de JWT/OAuth pour une appli mono-utilisateur |
| Scheduler (à venir) | APScheduler in-process | pas de worker/broker externe |
| Ingestion mail | IMAP stdlib (`imaplib`/`email`), zéro dépendance supplémentaire | pas d'API OAuth : évite l'expiration à 7 jours des refresh tokens en statut "Test" Google Cloud ; stdlib suffit, pas besoin d'`imap-tools` |
| Parsing PDF (à venir) | pdfplumber ou pymupdf, un adaptateur par gestionnaire (`app/services/extraction/`) | formats de compte-rendu différents selon ArthurImmo / Pergent / Locagestion |
| Déploiement (à venir) | systemd direct (sans Docker) | évite tout overhead de conteneur |

## État d'avancement

- [x] Architecture, modèle de données et écrans clés discutés et actés.
- [x] **Modèle de données implémenté** (`app/models/`) : 15 entités + migration initiale Alembic appliquée et testée.
- [x] **Squelette applicatif FastAPI + authentification** (`app/main.py`, `app/security.py`, `app/routers/auth.py`) : login/logout par session cookie, mots de passe Argon2, pas d'écran d'inscription (créer un utilisateur via `scripts/creer_utilisateur.py`).
- [x] **Écran Patrimoine (biens + unités locatives)** (`app/routers/biens.py`, `app/routers/unites.py`) : CRUD complet. Un `appartement_isole` reçoit automatiquement sa seule `UniteLocative` à la création (jamais ajoutée/retirée à la main) ; un `immeuble` gère ses unités une à une. Suppression bloquée (409) si des occupations, mandats, relevés ou lignes financières sont rattachés.
- [x] **Écran Gestionnaires** (`app/routers/gestionnaires.py`, `app/routers/mandats.py`, `app/routers/comptes_bancaires.py`) : CRUD gestionnaires + comptes bancaires (paramétrage compte↔gestionnaire pour les futurs virements), et gestion des mandats (lier une unité à un gestionnaire avec un rôle, terminer, supprimer). Une "gestion locative complète" se vérifie bien comme deux `MandatGestion` (un par rôle) pour le même gestionnaire — couvert par un test dédié.
- [x] **Écran Locataires** (`app/routers/locataires.py`, `app/routers/occupations.py`, + routes d'attribution dans `app/routers/unites.py`) : CRUD locataires, filtre actif/historique/tous, attribution d'une unité avec colocation (plusieurs locataires sur une même `Occupation` via `OccupationLocataire`), clôture de bail, détection de vacance (dérivée, aucune occupation active). La page de détail d'un bien affiche désormais l'occupant ou "Vacant" par unité.
- [x] **Écran Finances** (`app/routers/virements.py`, `app/routers/depenses.py`, `app/routers/paiements.py`) : déclaration manuelle d'un virement reçu (compte bancaire pré-rempli selon le gestionnaire via Alpine.js), rapprochement assisté avec écart calculé en direct côté client (candidats = lignes de paiement/dépense du gestionnaire non encore rapprochées à un autre virement), grille de paiements (unités × mois) et liste des dépenses avec totaux par catégorie. La grille/les dépenses restent vides jusqu'à ce que l'ingestion mail alimente `LignePaiement`/`LigneDepense` — c'est voulu, ces écrans sont de simples vues sur ces tables.
- [x] **Écran Documents + architecture d'extraction PDF** (`app/routers/documents.py`, `app/services/releves.py`, `app/services/pdf.py`, `app/services/extraction/`) : import manuel d'un compte-rendu PDF (gestionnaire + bien + période), stockage sur disque dédupliqué par hash SHA-256 (`data/documents/<gestionnaire>/<AAAA-MM>/`), extraction de texte via `pdfplumber`, puis un **adaptateur par gestionnaire** (contrat commun dans `extraction/base.py` : `AdaptateurExtraction.extraire(texte) -> ResultatExtraction`) transforme le texte en `LignePaiement`/`LigneDepense` rattachées aux unités par libellé. **Aucun exemple réel de compte-rendu n'étant disponible**, les 3 adaptateurs (`arthurimmo.py`, `pergent.py`, `locagestion.py`) sont volontairement non calibrés : ils lèvent `ExtractionNonCalibreeError` plutôt que de deviner un format et produire des données potentiellement fausses dans les finances de l'utilisateur. Le relevé est alors marqué `erreur_extraction` avec le message explicite (`ReleveGestion.erreur_extraction_message`), visible et "relançable" dans l'écran Documents dès qu'un vrai exemple de PDF permettra d'implémenter le bon adaptateur. Suppression/relance bloquées (409) si des lignes du relevé sont déjà rapprochées à un virement.
- [x] **Ingestion mail** (`app/services/mail.py`, `app/services/ingestion_mail.py`, `app/routers/ingestion_mail.py`) : connexion IMAP (stdlib `imaplib`/`email`, zéro dépendance), écran de **triage manuel** (`/ingestion-mail`) — la boîte dédiée recevant tout le courrier personnel transféré (pas que les 3 gestionnaires), aucun filtrage par expéditeur n'est possible ; chaque pièce jointe PDF non encore traitée (`CandidatCourrielTraite`) est listée et l'utilisateur choisit gestionnaire/bien/période pour l'importer (réutilise `enregistrer_releve`) ou l'ignorer. Testé avec un vrai faux serveur IMAP (`tests/faux_serveur_imap.py`, socket + protocole réel) ; **le compte Gmail dédié `patrimoine.locatif.touchet@gmail.com` est opérationnel** (mot de passe d'application obtenu, connexion IMAP réelle confirmée), identifiants dans `.env` (`GMAIL_IMAP_*`, chargé via `python-dotenv`).
- [x] **Tableau de bord** (`app/services/tableau_de_bord.py`, `app/routers/tableau_de_bord.py`) : devenu la route `/` (remplace l'ancien accueil placeholder). Cartes chiffrées (biens, taux d'occupation, loyers perçus/attendus du mois, dettes locataires en cours, dépenses du mois), tuiles par bien (en alerte si vacance/impayé/relevé en erreur), et liste d'alertes (unités vacantes, impayés, relevés en erreur d'extraction, virements non encore déclarés ce mois pour les gestionnaires ayant un mandat `gestion` actif). Les dettes et impayés se basent sur la **dernière ligne de paiement connue par unité** (pas une somme sur l'historique, puisque `dette_cumulee` est déjà cumulative).
- [x] **Déploiement systemd préparé** (`deploy/real-estate-manager.service`) : unité `Type=simple`, tourne en l'utilisateur `pi`, relance automatique (`Restart=on-failure`). `APP_HOST`/`APP_PORT` (nouveaux, dans `app/config.py`) remplacent l'ancien `host="127.0.0.1"` codé en dur dans `app/main.py` — nécessaire puisque le reverse proxy qui termine le TLS tourne sur un **autre** Raspberry Pi et doit pouvoir joindre cette appli sur le réseau (mettre `APP_HOST=0.0.0.0` ou l'IP LAN dans `.env` en production). **Le service n'a pas été installé ni démarré** (demande explicite de l'utilisateur) — voir la section Déploiement ci-dessous pour les commandes à lancer soi-même.
- [ ] Calibrer les 3 adaptateurs d'extraction sur de vrais exemples de PDF (bloquant pour une extraction automatique fiable).
- [ ] Brancher l'ingestion mail sur un scheduler (APScheduler) pour un polling périodique plutôt qu'un déclenchement manuel de la page.
- [ ] Installer et démarrer réellement le service systemd (volontairement laissé à l'utilisateur).

## Modèle de données — résumé

Voir le détail des champs directement dans `app/models/` (un fichier par entité, nommé en snake_case du nom de la classe). Schéma relationnel :

```
Bien 1──N UniteLocative N──N Gestionnaire (via MandatGestion + rôle)
UniteLocative 1──N Occupation N──N Locataire (via OccupationLocataire)
Gestionnaire 1──1 CompteBancaire
Gestionnaire 1──N ReleveGestion 1──N LignePaiement / LigneDepense
Gestionnaire 1──N VirementRecu ──1 Rapprochement──N RapprochementLigne──(LignePaiement | LigneDepense)
```

Un bien de type `appartement_isole` n'a qu'une seule `UniteLocative` ; un `immeuble` en a plusieurs. La vacance d'une unité est **dérivée** (aucune `Occupation` avec `statut = active`), jamais stockée en dur.

## Authentification

Pas d'écran d'inscription (application mono-utilisateur) : créer un compte via `scripts/creer_utilisateur.py --email ...` (mot de passe saisi en masqué via `getpass`, jamais en argument de ligne de commande). La logique réutilisable est dans `app/services/gestion_utilisateurs.py`.

Un accès non authentifié à une route protégée (dépendance `get_current_user`, `app/security.py`) lève une `HTTPException(401)`, interceptée par un handler global (`app/main.py`) qui redirige vers `/login` plutôt que de renvoyer une erreur JSON.

## Préfixe d'URL `/real-estate-manager/`

Le code applicatif (routes, templates) ne connaît pas le préfixe — il est injecté au lancement via `uvicorn --root-path` (voir le bloc `if __name__ == "__main__"` de `app/main.py`, ou l'unité systemd en prod). Le reverse proxy de l'autre Raspberry Pi doit **retirer** le préfixe avant de transmettre la requête ici ; `--root-path` ne fait que corriger les URLs générées (redirections, liens `url_for`) pour qu'elles soient correctes vues depuis l'extérieur. En test, le client tape directement les routes sans préfixe (`/login`, `/`), ce qui reflète cette vue interne.

## Déploiement systemd

Le fichier `deploy/real-estate-manager.service` est prêt mais **n'a jamais été installé ni démarré** (demande explicite de l'utilisateur — ne pas le faire sans qu'il le demande). Pour l'installer soi-même :

```bash
# 1. S'assurer que .env a APP_HOST=0.0.0.0 (ou l'IP LAN du Pi) — 127.0.0.1 par défaut
#    n'est PAS joignable depuis l'autre Raspberry Pi qui fait reverse proxy.
# 2. Vérifier que les migrations sont à jour et qu'un utilisateur existe :
.venv/bin/alembic upgrade head
.venv/bin/python scripts/creer_utilisateur.py --email moi@exemple.fr   # si pas déjà fait

# 3. Installer l'unité systemd :
sudo cp deploy/real-estate-manager.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now real-estate-manager

# Suivi :
sudo systemctl status real-estate-manager
journalctl -u real-estate-manager -f
```

Les migrations ne sont **pas** auto-appliquées au démarrage du service (volontaire — éviter qu'une migration non testée s'applique seule sur un redémarrage/crash-loop) : `alembic upgrade head` reste une étape manuelle avant chaque déploiement d'une nouvelle version.

## Commandes utiles

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"     # installation
.venv/bin/alembic revision --autogenerate -m "message"          # nouvelle migration
.venv/bin/alembic upgrade head                                   # appliquer les migrations
.venv/bin/python -m pytest tests/ -q                              # lancer les tests
.venv/bin/python scripts/creer_utilisateur.py --email moi@exemple.fr   # créer un utilisateur
```

**Points d'attention à ne pas perdre en régénérant des fichiers :**
- `migrations/script.py.mako` a été modifié pour ajouter `import sqlmodel` (SQLModel ne l'ajoute pas automatiquement dans les scripts autogénérés, ce qui casse `upgrade()` sur les colonnes de type `AutoString`).
- Les tests utilisant une base SQLite en mémoire (`tests/conftest.py`) doivent utiliser `poolclass=StaticPool` — sans lui, chaque connexion ouvre une base `:memory:` vide différente.
- Dépendance de test `httpx2` (pas `httpx`) : Starlette `TestClient` a déprécié `httpx` en faveur de `httpx2`.
- `.env` est chargé via `python-dotenv` dans `app/config.py` (`load_dotenv`) — ne pas retirer cet appel, sans lui aucune variable de `.env` n'est lue (bug présent jusqu'à l'ajout de l'ingestion mail).
- Les datetimes persistées doivent être timezone-aware (`datetime.now(timezone.utc)`) — SQLModel/SQLAlchemy refuse désormais les datetimes naïves sur les colonnes `DateTime`.
- Le vrai `.env` du développeur contient de vrais identifiants Gmail (nécessaires à l'usage réel) : `tests/conftest.py` a un fixture `autouse` qui force `GMAIL_IMAP_ADRESSE`/`GMAIL_IMAP_MOT_DE_PASSE` à vide par défaut pour chaque test, sans quoi les tests dépendraient du contenu de `.env` et pourraient se connecter à la vraie boîte mail.
