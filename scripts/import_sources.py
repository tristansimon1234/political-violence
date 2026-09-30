"""Import initial du panel dans Supabase.

    python scripts/import_sources.py panel.csv --dry-run

CSV attendu (en-tête) : url,type,sous_type,critere
Idempotent : upsert sur channel_id. Le champ `active` n'est jamais écrasé.
Variables : YOUTUBE_API_KEY, et hors --dry-run SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.
"""

import argparse
import csv
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError, field_validator, model_validator

from radar.schemas import VERSION_TAXONOMIE, SousType, TypeSource, sous_type_valide
from radar.supabase_rest import Supabase
from radar.youtube import Chaine, QuotaDepasse, ResolutionImpossible, Stats90j, YouTube

log = logging.getLogger("import_sources")


class LignePanel(BaseModel):
    url: str
    type: TypeSource
    sous_type: SousType
    critere: str

    @field_validator("critere")
    @classmethod
    def critere_non_vide(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("critère d'inclusion obligatoire")
        return v.strip()

    @model_validator(mode="after")
    def sous_type_coherent(self) -> "LignePanel":
        if not sous_type_valide(self.type, self.sous_type):
            raise ValueError(f"sous_type {self.sous_type} incompatible avec type {self.type}")
        return self


def lire_csv(chemin: Path) -> list[LignePanel]:
    """Valide tout le fichier avant le moindre appel API."""
    lignes: list[LignePanel] = []
    erreurs: list[str] = []
    with chemin.open(newline="", encoding="utf-8") as f:
        for n, brut in enumerate(csv.DictReader(f), start=2):
            try:
                lignes.append(LignePanel.model_validate(brut))
            except ValidationError as e:
                erreurs.append(f"ligne {n} : {e.errors()[0]['msg']}")
    if erreurs:
        raise SystemExit("CSV invalide :\n" + "\n".join(erreurs))
    return lignes


def ligne_source(
    ligne: LignePanel, chaine: Chaine, stats: Stats90j, maintenant: datetime
) -> dict[str, Any]:
    return {
        "channel_id": chaine.channel_id,
        "handle": chaine.handle,
        "nom": chaine.nom,
        "type": ligne.type,
        "sous_type": ligne.sous_type,
        "critere_inclusion": ligne.critere,
        "uploads_playlist_id": chaine.uploads_playlist_id,
        "abonnes": chaine.abonnes,
        "videos_90j": stats.videos,
        "vues_90j": stats.vues,
        "part_commentaires_ouverts": stats.part_commentaires_ouverts,
        "derniere_video_at": stats.derniere_video_at.isoformat()
        if stats.derniere_video_at
        else None,
        "stats_maj_at": maintenant.isoformat(),
        "version_taxonomie": VERSION_TAXONOMIE,
    }


def afficher(sources: list[dict[str, Any]]) -> None:
    print(
        f"\n{'type':<12}{'sous_type':<18}{'vidéos/j':>9}{'vues 90j':>14}{'com. ouverts':>13}  nom"
    )
    for s in sorted(sources, key=lambda s: (s["type"], s["sous_type"], -s["vues_90j"])):
        part = s["part_commentaires_ouverts"]
        print(
            f"{s['type']:<12}{s['sous_type']:<18}{s['videos_90j'] / 90:>9.1f}"
            f"{s['vues_90j']:>14,}{'-' if part is None else f'{part:.0%}':>13}  {s['nom']}"
        )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("csv", type=Path)
    p.add_argument("--dry-run", action="store_true", help="appelle YouTube mais n'écrit rien")
    p.add_argument("--budget", type=int, default=3000, help="quota YouTube max pour ce run")
    p.add_argument("--max-pages", type=int, default=60, help="pages d'uploads max par chaîne")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    lignes = lire_csv(args.csv)
    yt = YouTube(os.environ["YOUTUBE_API_KEY"], budget=args.budget)
    maintenant = datetime.now(UTC)

    sources: list[dict[str, Any]] = []
    echecs: list[str] = []
    try:
        for ligne in lignes:
            try:
                chaine = yt.resoudre_chaine(ligne.url)
            except ResolutionImpossible as e:
                echecs.append(str(e))
                continue
            stats = yt.stats_90j(chaine.uploads_playlist_id, maintenant, args.max_pages)
            if stats.tronque:
                log.warning("%s : parcours tronqué à %d pages", chaine.nom, args.max_pages)
            sources.append(ligne_source(ligne, chaine, stats, maintenant))
    except QuotaDepasse as e:
        echecs.append(f"Arrêt propre, budget atteint ({e}). Relancer pour compléter.")

    afficher(sources)
    for msg in echecs:
        print(f"ÉCHEC : {msg}", file=sys.stderr)
    log.info("quota youtube consommé : %d / budget %d", yt.consomme, yt.budget)

    if args.dry_run:
        print(f"\n--dry-run : {len(sources)} sources prêtes, rien écrit.")
    else:
        Supabase(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"]).upsert(
            "sources", sources, conflit="channel_id"
        )
        print(f"\n{len(sources)} sources enregistrées.")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
