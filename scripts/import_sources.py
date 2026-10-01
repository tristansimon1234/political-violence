"""Import initial du panel dans Supabase.

    python scripts/import_sources.py panel.csv --dry-run

CSV attendu (en-tête) : url,type,sous_type,critere[,nom]
Idempotent : upsert sur channel_id. Le champ `active` n'est jamais écrasé.
Variables : YOUTUBE_API_KEY, et hors --dry-run SUPABASE_URL, SUPABASE_SECRET_KEY.
"""

import argparse
import csv
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
from pydantic import BaseModel, ValidationError, field_validator, model_validator

from radar.schemas import VERSION_TAXONOMIE, SousType, TypeSource, sous_type_valide
from radar.supabase_rest import Supabase
from radar.youtube import (
    Chaine,
    QuotaDepasse,
    ResolutionImpossible,
    StatsRecentes,
    YouTube,
    cle_api,
    parser_reference,
)

log = logging.getLogger("import_sources")

# Fenêtre par défaut de calcul des vues et de l'activité (docs/decisions.md).
JOURS_DEFAUT = 90


class LignePanel(BaseModel):
    url: str
    type: TypeSource
    sous_type: SousType
    critere: str
    nom: str | None = None  # nom attendu, pour vérifier la résolution à l'œil
    sources: str | None = None  # provenance dans le vivier (docs/decisions.md, 01/10/2026)

    @field_validator("url")
    @classmethod
    def url_reconnue(cls, v: str) -> str:
        try:
            parser_reference(v)
        except ResolutionImpossible as e:
            raise ValueError(str(e)) from e
        return v.strip()

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
    ligne: LignePanel, chaine: Chaine, stats: StatsRecentes, jours: int, maintenant: datetime
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
        "fenetre_jours": jours,
        "videos_fenetre": stats.videos,
        "vues_fenetre": stats.vues,
        "part_commentaires_ouverts": stats.part_commentaires_ouverts,
        "derniere_video_at": stats.derniere_video_at.isoformat()
        if stats.derniere_video_at
        else None,
        "stats_maj_at": maintenant.isoformat(),
        "version_taxonomie": VERSION_TAXONOMIE,
    }


def afficher(resultats: list[tuple[LignePanel, dict[str, Any]]], jours: int) -> None:
    print(
        f"\n{'type':<12}{'sous_type':<18}{'abonnés':>12}{f'vidéos {jours}j':>12}"
        f"{f'vues {jours}j':>14}"
        f"{'com. ouverts':>13}  nom résolu (handle) [nom attendu si différent]"
    )
    for ligne, s in sorted(
        resultats, key=lambda r: (r[1]["type"], r[1]["sous_type"], -r[1]["vues_fenetre"])
    ):
        part = s["part_commentaires_ouverts"]
        abonnes = "-" if s["abonnes"] is None else f"{s['abonnes']:,}"
        attendu = f" [{ligne.nom}]" if ligne.nom and ligne.nom != s["nom"] else ""
        print(
            f"{s['type']:<12}{s['sous_type']:<18}{abonnes:>12}{s['videos_fenetre']:>12}"
            f"{s['vues_fenetre']:>14,}{'-' if part is None else f'{part:.0%}':>13}"
            f"  {s['nom']} ({s['handle']}){attendu}"
        )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("csv", type=Path)
    p.add_argument("--dry-run", action="store_true", help="appelle YouTube mais n'écrit rien")
    p.add_argument("--budget", type=int, default=3000, help="quota YouTube max pour ce run")
    p.add_argument(
        "--jours", type=int, default=JOURS_DEFAUT, help="fenêtre des vues et de l'activité"
    )
    p.add_argument("--max-pages", type=int, default=100, help="pages d'uploads max par chaîne")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    lignes = lire_csv(args.csv)
    yt = YouTube(cle_api(), budget=args.budget)
    maintenant = datetime.now(UTC)

    resultats: list[tuple[LignePanel, dict[str, Any]]] = []
    echecs: list[str] = []
    try:
        for ligne in lignes:
            try:
                chaine = yt.resoudre_chaine(ligne.url)
                stats = yt.stats_recentes(
                    chaine.uploads_playlist_id, maintenant, args.jours, args.max_pages
                )
            except ResolutionImpossible as e:
                echecs.append(str(e))
                continue
            except requests.HTTPError as e:
                echecs.append(f"{ligne.nom or ligne.url} : {e}")
                if e.response is not None and e.response.status_code == 403:
                    break  # quota épuisé ou clé refusée : inutile de continuer
                continue
            if stats.tronque:
                log.warning("%s : parcours tronqué à %d pages", chaine.nom, args.max_pages)
            resultats.append((ligne, ligne_source(ligne, chaine, stats, args.jours, maintenant)))
    except QuotaDepasse as e:
        echecs.append(f"Arrêt propre, budget atteint ({e}). Relancer pour compléter.")

    afficher(resultats, args.jours)
    sources = [s for _, s in resultats]
    for msg in echecs:
        print(f"ÉCHEC : {msg}", file=sys.stderr)
    log.info("quota youtube consommé : %d / budget %d", yt.consomme, yt.budget)

    if args.dry_run:
        print(f"\n--dry-run : {len(sources)} sources prêtes, rien écrit.")
    else:
        Supabase(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"]).upsert(
            "sources", sources, conflit="channel_id"
        )
        print(f"\n{len(sources)} sources enregistrées.")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
