"""Pré-filtre politique par mots-clés : première marche de l'entonnoir, sans LLM.

Liste versionnée dans config/mots_cles.txt (une expression par ligne, # pour les commentaires).
Recherche insensible à la casse et aux accents, sur des mots entiers, dans le titre, la
description et les tags. Orienté rappel : mieux vaut laisser passer que manquer une vidéo.
"""

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

FICHIER_MOTS_CLES = Path(__file__).parents[1] / "config" / "mots_cles.txt"


def normaliser(texte: str) -> str:
    """Minuscules, sans accents, apostrophes et tirets remplacés par des espaces."""
    sans_accents = unicodedata.normalize("NFKD", texte)
    sans_accents = "".join(c for c in sans_accents if not unicodedata.combining(c))
    return re.sub(r"[\u2019'`\-_/.]", " ", sans_accents.lower())


@dataclass(frozen=True)
class MotsCles:
    expressions: tuple[str, ...]
    version: str  # empreinte du fichier, enregistrée avec chaque vidéo
    _motif: re.Pattern[str]

    def correspond(self, *textes: str) -> bool:
        return any(self._motif.search(normaliser(t)) for t in textes if t)


def charger(chemin: Path = FICHIER_MOTS_CLES) -> MotsCles:
    contenu = chemin.read_text(encoding="utf-8")
    expressions: list[str] = []
    for ligne in contenu.splitlines():
        ligne = ligne.split("#", 1)[0].strip()
        if ligne:
            expressions.append(normaliser(ligne))
    if not expressions:
        raise ValueError(f"Aucun mot-clé dans {chemin}")
    uniques = tuple(sorted(set(expressions), key=len, reverse=True))
    motif = re.compile(r"\b(?:" + "|".join(re.escape(e) for e in uniques) + r")\b")
    version = hashlib.sha256(contenu.encode()).hexdigest()[:8]
    return MotsCles(uniques, version, motif)
