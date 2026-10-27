from pathlib import Path

import pdfplumber


def extraire_texte_pdf(chemin: Path) -> str:
    with pdfplumber.open(chemin) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)
