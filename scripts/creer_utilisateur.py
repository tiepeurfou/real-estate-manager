#!/usr/bin/env python3
"""Crée un utilisateur de l'application (il n'existe pas d'écran d'inscription,
l'app étant mono-utilisateur).

Usage : .venv/bin/python scripts/creer_utilisateur.py --email moi@exemple.fr
"""
import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session  # noqa: E402

from app.database import engine  # noqa: E402
from app.services.gestion_utilisateurs import creer_utilisateur  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()

    password = getpass.getpass("Mot de passe : ")
    confirmation = getpass.getpass("Confirmer le mot de passe : ")
    if password != confirmation:
        print("Les deux mots de passe ne correspondent pas.", file=sys.stderr)
        raise SystemExit(1)

    with Session(engine) as session:
        utilisateur = creer_utilisateur(session, args.email, password)

    print(f"Utilisateur créé : {utilisateur.email} (id={utilisateur.id})")


if __name__ == "__main__":
    main()
