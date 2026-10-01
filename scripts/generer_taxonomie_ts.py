"""Génère web/lib/taxonomie.ts depuis radar/schemas.py (source de vérité).

    python scripts/generer_taxonomie_ts.py

Ne jamais éditer le fichier généré à la main. tests/test_taxonomie_ts.py échoue s'il est périmé.
"""

import json
from pathlib import Path

from radar.schemas import (
    EMOTIONS,
    FENETRE_ACTIVITE_JOURS,
    FORMATS_VIDEO,
    LIBELLES_TYPE,
    NATURES_VIDEO,
    POSITIONS,
    SEUIL_ACTIVITE_VIDEOS,
    SOUS_TYPES_PAR_TYPE,
    THEMES,
    TONALITES,
    TYPES_SOURCE,
    VERSION_TAXONOMIE,
)

CIBLE = Path(__file__).parents[1] / "web" / "lib" / "taxonomie.ts"


def _j(valeur: object) -> str:
    return json.dumps(valeur, ensure_ascii=False)


def _liste(nom: str, type_ts: str, valeurs: tuple[str, ...]) -> list[str]:
    return [
        f"export const {nom} = {_j(list(valeurs))} as const;",
        f"export type {type_ts} = (typeof {nom})[number];",
        "",
    ]


def contenu() -> str:
    sous_types = {t: list(s) for t, s in SOUS_TYPES_PAR_TYPE.items()}
    return "\n".join(
        [
            "// Fichier généré par scripts/generer_taxonomie_ts.py depuis radar/schemas.py.",
            "// Ne pas éditer à la main.",
            "",
            f"export const VERSION_TAXONOMIE = {VERSION_TAXONOMIE};",
            "",
            f"export const TYPES_SOURCE = {_j(list(TYPES_SOURCE))} as const;",
            "export type TypeSource = (typeof TYPES_SOURCE)[number];",
            "",
            f"export const SOUS_TYPES_PAR_TYPE = {_j(sous_types)} as const;",
            "export type SousType = (typeof SOUS_TYPES_PAR_TYPE)[TypeSource][number];",
            "",
            f"export const LIBELLES_TYPE: Record<TypeSource, string> = {_j(LIBELLES_TYPE)};",
            "",
            f"export const SEUIL_ACTIVITE_VIDEOS = {SEUIL_ACTIVITE_VIDEOS};",
            f"export const FENETRE_ACTIVITE_JOURS = {FENETRE_ACTIVITE_JOURS};",
            "",
            f"export const FORMATS_VIDEO = {_j(list(FORMATS_VIDEO))} as const;",
            "export type FormatVideo = (typeof FORMATS_VIDEO)[number];",
            "",
            *_liste("THEMES", "Theme", THEMES),
            *_liste("NATURES_VIDEO", "NatureVideo", NATURES_VIDEO),
            *_liste("POSITIONS", "Position", POSITIONS),
            *_liste("EMOTIONS", "Emotion", EMOTIONS),
            *_liste("TONALITES", "Tonalite", TONALITES),
        ]
    )


def main() -> None:
    CIBLE.parent.mkdir(parents=True, exist_ok=True)
    CIBLE.write_text(contenu(), encoding="utf-8")
    print(f"écrit : {CIBLE}")


if __name__ == "__main__":
    main()
