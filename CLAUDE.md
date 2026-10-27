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
5. Les mails des gestionnaires sont lus depuis une **boîte Gmail dédiée** (pas la boîte personnelle de l'utilisateur), via l'API Gmail en OAuth2, scope `gmail.readonly`.
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
| Parsing PDF (à venir) | pdfplumber ou pymupdf, un adaptateur par gestionnaire (`app/services/extraction/`) | formats de compte-rendu différents selon ArthurImmo / Pergent / Locagestion |
| Déploiement (à venir) | systemd direct (sans Docker) | évite tout overhead de conteneur |

## État d'avancement

- [x] Architecture, modèle de données et écrans clés discutés et actés.
- [x] **Modèle de données implémenté** (`app/models/`) : 15 entités + migration initiale Alembic appliquée et testée.
- [x] **Squelette applicatif FastAPI + authentification** (`app/main.py`, `app/security.py`, `app/routers/auth.py`) : login/logout par session cookie, mots de passe Argon2, pas d'écran d'inscription (créer un utilisateur via `scripts/creer_utilisateur.py`).
- [x] **Écran Patrimoine (biens + unités locatives)** (`app/routers/biens.py`, `app/routers/unites.py`) : CRUD complet. Un `appartement_isole` reçoit automatiquement sa seule `UniteLocative` à la création (jamais ajoutée/retirée à la main) ; un `immeuble` gère ses unités une à une. Suppression bloquée (409) si des occupations, mandats, relevés ou lignes financières sont rattachés.
- [x] **Écran Gestionnaires** (`app/routers/gestionnaires.py`, `app/routers/mandats.py`, `app/routers/comptes_bancaires.py`) : CRUD gestionnaires + comptes bancaires (paramétrage compte↔gestionnaire pour les futurs virements), et gestion des mandats (lier une unité à un gestionnaire avec un rôle, terminer, supprimer). Une "gestion locative complète" se vérifie bien comme deux `MandatGestion` (un par rôle) pour le même gestionnaire — couvert par un test dédié.
- [ ] Endpoints FastAPI des écrans métier restants (Locataires, Finances, Documents).
- [ ] Templates HTMX de ces écrans (tableau de bord, grille de paiements).
- [ ] Ingestion mail (Gmail API) + adaptateurs d'extraction PDF par gestionnaire.
- [ ] Déploiement systemd.

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
