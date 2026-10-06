"""Collecte YouTube : quotidienne ou backfill.

    python scripts/collecte.py --dry-run                              # estimation, rien écrit
    python scripts/collecte.py                                        # quotidien (3 derniers jours)
    python scripts/collecte.py --depuis 2026-09-01 --jusqua 2026-09-07  # backfill, bornes incluses

Variables : YOUTUBE_API_KEY, SUPABASE_URL, SUPABASE_SECRET_KEY ; hors --dry-run : RADAR_SEL.
Stockage brut : bucket privé Supabase `radar-brut` (ou --stockage-local DOSSIER pour un essai).
Idempotent : relancer reprend là où le run s'est arrêté, sans doublon.
"""

import argparse
import logging
import os
import sys
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

from radar.anonymisation import sel
from radar.collecte import FENETRE_REVISITE_JOURS, MODE_COMMENTAIRES, Bilan, Parametres, collecter
from radar.prefiltre import charger
from radar.storage import Stockage, StockageLocal, StockageSupabase
from radar.supabase_rest import Supabase
from radar.youtube import YouTube, cle_api

log = logging.getLogger("collecte")

BUCKET = "radar-brut"


def rapport(p: Parametres, b: Bilan, yt: YouTube, debut: datetime) -> str:
    lignes = [
        f"# Collecte {p.mode}{' (dry-run)' if p.dry_run else ''} — {debut:%d/%m/%Y %H:%M} UTC",
        f"Période des vidéos : {p.depuis:%d/%m/%Y} → "
        f"{(p.jusqua - timedelta(days=1)) if p.jusqua else datetime.now(UTC):%d/%m/%Y}",
        "",
        f"- Vidéos examinées : {b.videos_vues} (nouvelles : {b.videos_nouvelles})",
        f"- Passent le pré-filtre ou chaîne politique : {b.videos_prefiltre}",
        f"- Éligibles aux commentaires : {b.videos_eligibles} "
        f"(≤ {b.pages_estimees} pages ≈ {b.pages_estimees} unités au plus) ; Shorts ignorés : "
        f"{b.shorts_ignores}",
        f"- Commentaires annoncés par YouTube sur ces vidéos (réponses comprises) : "
        f"{b.commentaires_annonces} ; tout prendre coûterait au plus "
        f"~{b.commentaires_annonces // 100 + b.videos_eligibles} unités",
        f"- Vidéos commentées : {b.videos_commentees}, commentaires : {b.commentaires}"
        + (
            f", vidéos indisponibles sautées : {b.videos_indisponibles}"
            if b.videos_indisponibles
            else ""
        ),
        f"- Quota consommé : {yt.consomme} / {yt.budget}"
        + (" — ARRÊT PROPRE AVANT LE BUDGET, relancer pour reprendre" if b.arret_budget else ""),
    ]
    if p.dry_run:
        lignes.append(
            f"- Estimation totale d'un run réel : {yt.consomme + b.pages_estimees} unités"
        )
    lignes += ["", "Pré-filtre par catégorie (nouvelles vidéos → retenues) :"]
    for t in sorted(set(b.nouvelles_par_type) | set(b.prefiltre_par_type)):
        lignes.append(f"- {t} : {b.nouvelles_par_type[t]} → {b.prefiltre_par_type[t]}")
    lignes += ["", "Par jour de publication (vidéos → retenues) :"]
    for j in sorted(b.videos_par_jour):
        lignes.append(f"- {j} : {b.videos_par_jour[j]} → {b.prefiltre_par_jour[j]}")
    return "\n".join(lignes)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--depuis", type=date.fromisoformat, help="backfill : premier jour (inclus)")
    p.add_argument("--jusqua", type=date.fromisoformat, help="backfill : dernier jour (inclus)")
    p.add_argument("--budget", type=int, default=3000, help="quota YouTube max pour ce run")
    p.add_argument("--dry-run", action="store_true", help="aucune écriture, commentaires estimés")
    p.add_argument("--stockage-local", type=Path, help="dossier local au lieu du bucket")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    debut = datetime.now(UTC)
    if args.depuis:
        jusqua = args.jusqua or (debut.date() - timedelta(days=1))
        params = Parametres(
            mode="backfill",
            depuis=datetime.combine(args.depuis, time(), UTC),
            jusqua=datetime.combine(jusqua + timedelta(days=1), time(), UTC),
            dry_run=args.dry_run,
        )
    else:
        params = Parametres(
            mode="quotidien",
            depuis=debut - timedelta(days=FENETRE_REVISITE_JOURS),
            jusqua=None,
            dry_run=args.dry_run,
        )

    url, cle = os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"]
    base = Supabase(url, cle)
    stockage: Stockage | None = None
    if not args.dry_run:
        stockage = (
            StockageLocal(args.stockage_local)
            if args.stockage_local
            else StockageSupabase(url, cle, BUCKET)
        )
    yt = YouTube(cle_api(), budget=args.budget)
    mots_cles = charger()
    log.info(
        "mots-clés : %d expressions, version %s", len(mots_cles.expressions), mots_cles.version
    )

    bilan = collecter(params, yt, base, stockage, mots_cles, None if args.dry_run else sel(), debut)
    print(rapport(params, bilan, yt, debut))
    log.info("quota youtube consommé : %d / budget %d", yt.consomme, yt.budget)

    if not args.dry_run:
        base.inserer(
            "collecte_runs",
            {
                "mode": params.mode,
                "dry_run": False,
                "debut": debut.isoformat(),
                "fin": datetime.now(UTC).isoformat(),
                "budget": yt.budget,
                "quota_consomme": yt.consomme,
                "arret_budget": bilan.arret_budget,
                "videos_vues": bilan.videos_vues,
                "videos_prefiltre": bilan.videos_prefiltre,
                "videos_commentees": bilan.videos_commentees,
                "commentaires": bilan.commentaires,
                "details": {
                    "depuis": params.depuis.isoformat(),
                    "jusqua": params.jusqua.isoformat() if params.jusqua else None,
                    "prefiltre_version": mots_cles.version,
                    "mode_commentaires": MODE_COMMENTAIRES,
                    "videos_indisponibles": bilan.videos_indisponibles,
                    "commentaires_annonces": bilan.commentaires_annonces,
                },
            },
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
