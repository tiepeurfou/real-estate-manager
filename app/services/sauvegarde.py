import logging
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from app.config import BASE_DIR, DATABASE_PATH, SAUVEGARDE_DB_NOMBRE_JOURS_CONSERVES

logger = logging.getLogger(__name__)

DOSSIER_SAUVEGARDES = BASE_DIR / "data" / "backups"
PREFIXE_FICHIER = "app-"


def _nom_fichier(jour: date) -> str:
    return f"{PREFIXE_FICHIER}{jour.isoformat()}.db"


def sauvegarder_la_base(aujourdhui: Optional[date] = None) -> Path:
    """Copie cohérente de data/app.db vers data/backups/, horodatée par jour
    (un fichier par jour ; relancer le même jour écrase simplement la copie
    du jour, ce qui est sans conséquence). Utilise l'API native de backup de
    SQLite (`Connection.backup`), pas un simple `cp` : SQLite peut être en
    cours d'écriture (mode WAL) au moment de la copie, un `cp` brut
    risquerait une sauvegarde corrompue/incohérente. Purge ensuite les
    sauvegardes plus anciennes que SAUVEGARDE_DB_NOMBRE_JOURS_CONSERVES."""
    aujourdhui = aujourdhui or date.today()
    DOSSIER_SAUVEGARDES.mkdir(parents=True, exist_ok=True)
    destination = DOSSIER_SAUVEGARDES / _nom_fichier(aujourdhui)

    source = sqlite3.connect(DATABASE_PATH)
    try:
        cible = sqlite3.connect(destination)
        try:
            source.backup(cible)
        finally:
            cible.close()
    finally:
        source.close()

    _purger_les_anciennes_sauvegardes(aujourdhui)
    return destination


def _purger_les_anciennes_sauvegardes(aujourdhui: date) -> None:
    limite = aujourdhui - timedelta(days=SAUVEGARDE_DB_NOMBRE_JOURS_CONSERVES)
    for fichier in DOSSIER_SAUVEGARDES.glob(f"{PREFIXE_FICHIER}*.db"):
        try:
            jour_fichier = date.fromisoformat(fichier.stem.removeprefix(PREFIXE_FICHIER))
        except ValueError:
            continue
        if jour_fichier < limite:
            fichier.unlink()
