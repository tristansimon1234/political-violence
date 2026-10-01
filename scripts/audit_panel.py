"""Audit du vivier du panel (lecture seule), règles du 01/10/2026 (docs/decisions.md).

    python scripts/audit_panel.py panel/vivier.csv --budget 2200 > audit.md

N'écrit rien dans Supabase. Le rapport (Markdown) sort sur stdout, la progression sur stderr.
Pour les médias natifs, les titres des 20 dernières vidéos sont écrits dans data/audit_titres.txt
pour évaluer la part de politique française (donnée brute : à supprimer après usage).
Coût : 1 unité par chaîne + 1 par page de 50 uploads + 1 par lot de 50 vidéos. Plafond : --budget.
"""

import argparse
import logging
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests
from import_sources import LignePanel, lire_csv

from radar.schemas import FENETRE_ACTIVITE_JOURS, LIBELLES_TYPE, SEUIL_ACTIVITE_VIDEOS
from radar.youtube import Chaine, QuotaDepasse, ResolutionImpossible, VideoDetail, YouTube, cle_api

log = logging.getLogger("audit_panel")

DUREE_MAX_SHORT_S = 180  # Shorts jusqu'à 3 min depuis octobre 2024
NB_TITRES = 20


def format_video(v: VideoDetail) -> str:
    """'short', 'long' ou 'ambigu' (≤ 3 min, format du lecteur inconnu).

    Règle : Short = durée ≤ 180 s ET lecteur vertical ou carré (largeur ≤ hauteur).
    """
    if v.duree_s == 0 or v.duree_s > DUREE_MAX_SHORT_S:
        return "long"
    if v.ratio is None:
        return "ambigu"
    return "short" if v.ratio <= 1 else "long"


@dataclass
class Audit:
    ligne: LignePanel
    chaine: Chaine | None  # None : chaîne introuvable
    videos: list[VideoDetail]

    def compte(self, fmt: str) -> int:
        return sum(format_video(v) == fmt for v in self.videos)

    def vues(self, fmt: str | None = None) -> int:
        return sum(v.vues for v in self.videos if fmt is None or format_video(v) == fmt)

    @property
    def part_ouverts(self) -> float | None:
        if not self.videos:
            return None
        return sum(v.commentaires_ouverts for v in self.videos) / len(self.videos)

    @property
    def verdict(self) -> str:
        """Règles 2 à 5. La part de politique française (médias natifs) s'évalue sur les titres."""
        n = len(self.videos)
        if self.ligne.sous_type == "parti":
            if self.chaine is None or n == 0:
                return "entre : sans chaîne active"
            return "entre (parti : activité non requise)"
        if self.chaine is None:
            return "réserve : chaîne introuvable"
        if n < SEUIL_ACTIVITE_VIDEOS:
            return f"réserve : {n} vidéos < {SEUIL_ACTIVITE_VIDEOS}"
        if self.ligne.type == "media_natif":
            return "activité OK, politique française à évaluer"
        return "entre"


def _pct(x: float | None) -> str:
    return "-" if x is None else f"{x:.0%}"


def auditer(
    yt: YouTube,
    lignes: list[LignePanel],
    maintenant: datetime,
    max_pages: int,
    audits: list[Audit],
    echecs: list[str],
) -> None:
    """Remplit `audits` et `echecs` au fil de l'eau : un arrêt sur quota garde le partiel."""
    for ligne in lignes:
        try:
            chaine = yt.resoudre_chaine(ligne.url)
            recents, tronque = yt.ids_recents(
                chaine.uploads_playlist_id, maintenant, FENETRE_ACTIVITE_JOURS, max_pages
            )
            videos = yt.details_videos([i for i, _ in recents])
        except ResolutionImpossible as e:
            echecs.append(f"{ligne.nom or ligne.url} : {e}")
            audits.append(Audit(ligne, None, []))
            continue
        except requests.HTTPError as e:
            echecs.append(f"{ligne.nom or ligne.url} : {e}")
            if e.response is not None and e.response.status_code == 403:
                raise QuotaDepasse("HTTP 403 : quota épuisé ou clé refusée") from e
            continue
        if tronque:
            echecs.append(
                f"{chaine.nom} : parcours tronqué à {max_pages} pages (vues sous-estimées)"
            )
        audits.append(Audit(ligne, chaine, videos))


def tableau(audits: list[Audit]) -> list[str]:
    out = [
        "| chaîne | handle | catégorie | source(s) | longues / Shorts 90j | vues 90j "
        "| dont Shorts | part politique FR | com. ouverts | verdict |",
        "|---|---|---|---|---|---:|---:|---|---:|---|",
    ]
    ordre = list(LIBELLES_TYPE)
    for a in sorted(
        audits, key=lambda a: (ordre.index(a.ligne.type), a.ligne.sous_type, -a.vues())
    ):
        nom = a.chaine.nom if a.chaine else (a.ligne.nom or a.ligne.url)
        handle = a.chaine.handle if a.chaine else a.ligne.url
        formats = f"{a.compte('long')} / {a.compte('short')}"
        if a.compte("ambigu"):
            formats += f" (+{a.compte('ambigu')} ambiguës)"
        politique_fr = "à évaluer" if a.ligne.type == "media_natif" and a.videos else "-"
        part_shorts = _pct(a.vues("short") / a.vues() if a.vues() else None)
        out.append(
            f"| {nom} | {handle} | {a.ligne.type} / {a.ligne.sous_type} | {a.ligne.sources or '-'} "
            f"| {formats} | {a.vues():,} | {part_shorts} "
            f"| {politique_fr} | {_pct(a.part_ouverts)} | {a.verdict} |"
        )
    return out


def decompte(audits: list[Audit]) -> list[str]:
    c = Counter((a.ligne.type, a.verdict.split(" ")[0].rstrip(":")) for a in audits)
    out = ["| catégorie | entre | à évaluer | réserve |", "|---|---:|---:|---:|"]
    for t, libelle in LIBELLES_TYPE.items():
        out.append(
            f"| {libelle} | {c[(t, 'entre')]} | {c[(t, 'activité')]} | {c[(t, 'réserve')]} |"
        )
    return out


def ecrire_titres(audits: list[Audit], chemin: Path) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8") as f:
        for a in audits:
            if a.ligne.type != "media_natif" or a.chaine is None:
                continue
            f.write(f"\n## {a.chaine.nom} ({a.chaine.handle})\n")
            recentes = sorted(a.videos, key=lambda v: v.publiee_at, reverse=True)[:NB_TITRES]
            for v in recentes:
                f.write(f"- [{format_video(v)}] {v.titre}\n")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("vivier", type=Path, nargs="+", help="un ou plusieurs CSV du vivier")
    p.add_argument("--budget", type=int, required=True, help="quota YouTube max pour ce run")
    p.add_argument("--max-pages", type=int, default=100, help="pages d'uploads max par chaîne")
    p.add_argument("--titres", type=Path, default=Path("data/audit_titres.txt"))
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", stream=sys.stderr)

    lignes = [ligne for f in args.vivier for ligne in lire_csv(f)]
    yt = YouTube(cle_api(), budget=args.budget)
    maintenant = datetime.now(UTC)

    audits: list[Audit] = []
    echecs: list[str] = []
    try:
        auditer(yt, lignes, maintenant, args.max_pages, audits, echecs)
    except QuotaDepasse as e:
        echecs.append(f"Arrêt propre : {e}. Rapport partiel, relancer le reste.")

    rapport = [
        f"# Audit du vivier — {maintenant:%d/%m/%Y}, fenêtre {FENETRE_ACTIVITE_JOURS} jours",
        "",
        *tableau(audits),
        "",
        "## Décompte",
        "",
        *decompte(audits),
        "",
    ]
    if echecs:
        rapport += ["## Signalements", "", *(f"- {e}" for e in echecs), ""]
    rapport.append(f"Quota YouTube consommé : **{yt.consomme} / {yt.budget}** unités.")
    print("\n".join(rapport))

    ecrire_titres(audits, args.titres)
    log.info("quota consommé : %d / %d — titres dans %s", yt.consomme, yt.budget, args.titres)
    return 0


if __name__ == "__main__":
    sys.exit(main())
