# Real Estate Manager

Application personnelle de gestion d'un patrimoine locatif : biens et immeubles, gestionnaires, locataires, et suivi financier (loyers, impayés, dépenses, virements). Conçue pour tourner en local sur un Raspberry Pi 5.

## Fonctionnalités

- Gestion du patrimoine : biens isolés et immeubles, avec leurs unités locatives (surface, DPE, régime fiscal...).
- Gestionnaires et mandats : qui s'occupe de la mise en location, qui s'occupe de la gestion (loyers, urgences, comptes-rendus), avec association aux biens/unités.
- Locataires : association aux unités, historique des occupations, type de garantie (VISALE, assurance loyers impayés, garant), détection des unités vacantes.
- Suivi financier : triage manuel de la boîte mail dédiée (import des comptes-rendus PDF), suivi mensuel des paiements/impayés/dettes, dépenses par bien, déclaration manuelle des virements reçus et rapprochement avec les paiements attendus.
- Vue d'ensemble du patrimoine (tableau de bord).

## Stack technique

- **Backend** : Python 3.11+, FastAPI, SQLModel (SQLAlchemy), Alembic pour les migrations.
- **Base de données** : SQLite (mono-utilisateur, pas de serveur dédié).
- **Frontend** : Jinja2 + HTMX + Alpine.js, vendorisés localement (pas de CDN).
- **Auth** : session cookie signée, mots de passe hashés en Argon2.

Voir [`CLAUDE.md`](CLAUDE.md) pour le détail des choix d'architecture, des contraintes du projet et de l'état d'avancement.

## Installation

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env   # puis adapter les valeurs, notamment SECRET_KEY
```

Générer une vraie clé secrète pour `.env` :

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Pour l'ingestion mail, renseigner dans `.env` l'adresse de la boîte Gmail dédiée et un **mot de passe d'application** (pas le mot de passe du compte — voir `CLAUDE.md`) : `GMAIL_IMAP_ADRESSE`, `GMAIL_IMAP_MOT_DE_PASSE`.

## Base de données

```bash
.venv/bin/alembic upgrade head
```

## Créer un utilisateur

Il n'y a pas d'écran d'inscription (application mono-utilisateur) :

```bash
.venv/bin/python scripts/creer_utilisateur.py --email moi@exemple.fr
```

## Lancer l'application

```bash
.venv/bin/python -m app.main
```

L'application écoute en local sur `http://127.0.0.1:8000`. En production, elle est servie sous `/real-estate-manager/` par un reverse proxy qui termine le TLS (voir `CLAUDE.md`).

## Tests

```bash
.venv/bin/python -m pytest tests/ -q
```

## État d'avancement

- [x] Modèle de données (15 entités) et migrations.
- [x] Authentification.
- [x] Écran Patrimoine (biens, immeubles, unités locatives).
- [x] Écran Gestionnaires, comptes bancaires et mandats.
- [x] Écran Locataires et occupations (colocation, clôture de bail, vacance).
- [x] Écran Finances (virements, rapprochement assisté, dépenses, grille de paiements).
- [x] Écran Documents (import manuel de PDF, stockage, extraction) — adaptateurs par gestionnaire non calibrés faute d'exemple réel de compte-rendu.
- [x] Ingestion mail (IMAP + triage manuel, la boîte dédiée recevant tout le courrier personnel transféré).
- [ ] Tableau de bord.
- [ ] Déploiement systemd.
