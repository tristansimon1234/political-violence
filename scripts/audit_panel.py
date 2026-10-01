"""Audit du panel (lecture seule) : activité sur 90 jours, longues / Shorts, candidats.

    python scripts/audit_panel.py \\
        --panel panel/panel_v0.csv \\
        --personnalites panel/personnalites_a_decider.csv \\
        --candidats panel/candidats_influenceurs.csv > audit.md

N'écrit rien dans Supabase. Le rapport (Markdown) sort sur stdout, la progression sur stderr.
Les titres des 20 dernières vidéos des candidats sont écrits dans data/audit_titres.txt
(donnée brute : à supprimer après usage, jamais commitée).
Coût : 1 unité par page de 50 uploads + 1 unité par lot de 50 vidéos. Plafond : --budget.
"""

import argparse
import logging
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests
from import_sources import LignePanel, lire_csv

from radar.youtube import Chaine, QuotaDepasse, ResolutionImpossible, VideoDetail, YouTube, cle_api

log = logging.getLogger("audit_panel")

JOURS = 90
SEUIL_ACTIVITE = 10  # vidéos sur 90 jours (docs/decisions.md)
DUREE_MAX_SHORT_S = 180  # Shorts jusqu'à 3 min depuis octobre 2024
NB_TITRES = 20


def format_video(v: VideoDetail) -> str:
    """'short', 'long' ou 'ambigu' (≤ 3 min, format du lecteur inconnu).

    Règle proposée : Short = durée ≤ 180 s ET lecteur vertical ou carré (largeur ≤ hauteur).
    """
    if v.duree_s == 0 or v.duree_s > DUREE_MAX_SHORT_S:
        return "long"
    if v.ratio is None:
        return "ambigu"
    return "short" if v.ratio <= 1 else "long"


@dataclass
class Audit:
    groupe: str
    ligne: LignePanel
    chaine: Chaine
    videos: list[VideoDetail]
    tronque: bool

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
        total, longues = len(self.videos), self.compte("long")
        if total < SEUIL_ACTIVITE:
            return f"échoue : {total} vidéos < {SEUIL_ACTIVITE}"
        if (self.part_ouverts or 0) < 0.5:
            return "échoue : commentaires fermés sur la majorité des vidéos"
        if longues < SEUIL_ACTIVITE:
            return f"passe grâce aux Shorts seulement ({longues} longues)"
        return "passe"


def _pct(x: float | None) -> str:
    return "-" if x is None else f"{x:.0%}"


def auditer(
    yt: YouTube, groupe: str, lignes: list[LignePanel], maintenant: datetime, max_pages: int
) -> tuple[list[Audit], list[str]]:
    audits: list[Audit] = []
    echecs: list[str] = []
    for ligne in lignes:
        try:
            chaine = yt.resoudre_chaine(ligne.url)
            recents, tronque = yt.ids_recents(
                chaine.uploads_playlist_id, maintenant, JOURS, max_pages
            )
            videos = yt.details_videos([i for i, _ in recents])
        except ResolutionImpossible as e:
            echecs.append(f"{ligne.nom or ligne.url} : {e}")
            continue
        except requests.HTTPError as e:
            echecs.append(f"{ligne.nom or ligne.url} : {e}")
            if e.response is not None and e.response.status_code == 403:
                raise QuotaDepasse("HTTP 403 : quota épuisé ou clé refusée") from e
            continue
        if tronque:
            log.warning("%s : parcours tronqué à %d pages", chaine.nom, max_pages)
        audits.append(Audit(groupe, ligne, chaine, videos, tronque))
    return audits, echecs


def tableau_panel(audits: list[Audit]) -> list[str]:
    out = [
        "| type | sous_type | chaîne | vidéos | longues | Shorts | ambiguës | % Shorts "
        "| vues 90j | % vues Shorts | com. ouverts |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for a in sorted(audits, key=lambda a: (a.ligne.type, a.ligne.sous_type, -a.vues())):
        n = len(a.videos)
        out.append(
            f"| {a.ligne.type} | {a.ligne.sous_type} | {a.chaine.nom}{' ⚠ tronqué' * a.tronque} "
            f"| {n} | {a.compte('long')} | {a.compte('short')} | {a.compte('ambigu')} "
            f"| {_pct(a.compte('short') / n if n else None)} | {a.vues():,} "
            f"| {_pct(a.vues('short') / a.vues() if a.vues() else None)} | {_pct(a.part_ouverts)} |"
        )
    return out


def tableau_classement(audits: list[Audit]) -> list[str]:
    out = [
        "| rang | nom | handle | abonnés | vidéos 90j (longues / Shorts / ambiguës) "
        "| vues 90j | com. ouverts | verdict |",
        "|---:|---|---|---:|---|---:|---:|---|",
    ]
    for rang, a in enumerate(sorted(audits, key=lambda a: -len(a.videos)), start=1):
        abonnes = "-" if a.chaine.abonnes is None else f"{a.chaine.abonnes:,}"
        out.append(
            f"| {rang} | {a.chaine.nom} | {a.chaine.handle} | {abonnes} "
            f"| {len(a.videos)} ({a.compte('long')} / {a.compte('short')} / {a.compte('ambigu')}) "
            f"| {a.vues():,} | {_pct(a.part_ouverts)} | {a.verdict} |"
        )
    return out


def ecrire_titres(audits: list[Audit], chemin: Path) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8") as f:
        for a in audits:
            f.write(f"\n## {a.chaine.nom} ({a.chaine.handle})\n")
            recentes = sorted(a.videos, key=lambda v: v.publiee_at, reverse=True)[:NB_TITRES]
            for v in recentes:
                f.write(f"- [{format_video(v)}] {v.titre}\n")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--panel", type=Path, required=True)
    p.add_argument("--personnalites", type=Path, required=True)
    p.add_argument("--candidats", type=Path, required=True)
    p.add_argument("--budget", type=int, default=3000, help="quota YouTube max pour tout le lot")
    p.add_argument("--max-pages", type=int, default=100, help="pages d'uploads max par chaîne")
    p.add_argument("--titres", type=Path, default=Path("data/audit_titres.txt"))
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", stream=sys.stderr)

    groupes = {
        "candidats": lire_csv(args.candidats),
        "personnalites": lire_csv(args.personnalites),
        "panel": lire_csv(args.panel),
    }
    yt = YouTube(cle_api(), budget=args.budget)
    maintenant = datetime.now(UTC)

    resultats: dict[str, list[Audit]] = {g: [] for g in groupes}
    echecs: list[str] = []
    try:
        for groupe, lignes in groupes.items():
            audits, ech = auditer(yt, groupe, lignes, maintenant, args.max_pages)
            resultats[groupe] = audits
            echecs += ech
    except QuotaDepasse as e:
        echecs.append(f"Arrêt propre : {e}. Rapport partiel.")

    rapport = [f"# Audit du panel — {maintenant:%d/%m/%Y}, fenêtre {JOURS} jours", ""]
    rapport += ["## Candidats influenceurs", "", *tableau_classement(resultats["candidats"]), ""]
    rapport += ["## Personnalités (classement par activité)", ""]
    rapport += [*tableau_classement(resultats["personnalites"]), ""]
    rapport += ["## Panel : longues et Shorts", "", *tableau_panel(resultats["panel"]), ""]
    if echecs:
        rapport += ["## Échecs", "", *(f"- {e}" for e in echecs), ""]
    rapport.append(f"Quota YouTube consommé : **{yt.consomme} / {yt.budget}** unités.")
    print("\n".join(rapport))

    ecrire_titres(resultats["candidats"], args.titres)
    log.info("quota consommé : %d / %d — titres dans %s", yt.consomme, yt.budget, args.titres)
    return 0


if __name__ == "__main__":
    sys.exit(main())
