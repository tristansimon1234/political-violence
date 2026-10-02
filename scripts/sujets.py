"""Détection des sujets d'actualité (étape 6) : vidéos politiques regroupées par événement.

    python scripts/sujets.py --dry-run      # vidéos à rattacher par jour, coût estimé
    python scripts/sujets.py --budget-claude 3

Jour par jour (date de publication, Paris), les vidéos politiques déjà décrites et pas encore
rattachées partent chez Claude avec les sujets encore actifs (7 jours). Résultat : tables
`sujets` et `sujets_videos`. Relancer ne renvoie que les vidéos non rattachées (idempotent).
À lancer après l'étape `videos` de la classification (il faut le sous-sujet de chaque vidéo).

Variables : SUPABASE_URL, SUPABASE_SECRET_KEY, ANTHROPIC_API_KEY.
"""

import argparse
import logging
import os
import sys
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from radar.llm import BudgetDepasse, ClientClaude, ReponseInvalide
from radar.storage import Stockage, StockageLocal, StockageSupabase, lire_partition, partitions
from radar.sujets import (
    LOT_SUJETS,
    SYSTEME_SUJETS,
    ReponseSujets,
    Sujet,
    VideoASituer,
    actifs,
    appliquer,
    message_sujets,
    mettre_a_jour,
)
from radar.supabase_rest import Supabase

log = logging.getLogger("sujets")
PARIS = ZoneInfo("Europe/Paris")
BUCKET_BRUT = "radar-brut"
DEBUT_COLLECTE = date(2026, 9, 1)
CLAUDE_USD_PAR_APPEL = 0.02  # ~10 000 tokens en entrée, ~1 500 en sortie (Haiku 4.5)


def _jour(iso: str) -> date:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(PARIS).date()


def _brut(args: argparse.Namespace) -> Stockage:
    if args.stockage_local:
        return StockageLocal(args.stockage_local)
    return StockageSupabase(
        os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"], BUCKET_BRUT
    )


def _ligne_sujet(s: Sujet, aujourdhui: date) -> dict[str, Any]:
    return {
        "id": s.id,
        "titre": s.titre,
        "premier_jour": s.premier_jour.isoformat(),
        "dernier_jour": s.dernier_jour.isoformat(),
        "maj_le": aujourdhui.isoformat(),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="volumes et coût estimé, aucun appel")
    p.add_argument("--budget-claude", type=float, default=3.0, help="dollars max pour Claude")
    p.add_argument(
        "--depuis", type=date.fromisoformat, default=DEBUT_COLLECTE, help="premier jour traité"
    )
    p.add_argument("--stockage-local", type=Path, help="dossier local du brut au lieu du bucket")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    debut = datetime.now(UTC)
    aujourdhui = debut.date()
    base = Supabase(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

    sources = {str(s["id"]): str(s.get("nom") or "") for s in base.select("sources", {})}
    videos = {str(v["video_id"]): v for v in base.select("videos", {"prefiltre": "eq.true"})}
    sous_sujets = {
        str(s["video_id"]): str(s["sous_sujet"])
        for s in base.select("videos_sujets", {"principal": "eq.true"})
    }
    titres: dict[str, str] = {}
    brut = _brut(args)
    for c in partitions(brut, "videos").values():
        for v in lire_partition(brut, c):
            titres[str(v["video_id"])] = str(v.get("titre") or "")
    sujets = {
        str(s["id"]): Sujet(
            str(s["id"]),
            str(s["titre"]),
            date.fromisoformat(str(s["premier_jour"])),
            date.fromisoformat(str(s["dernier_jour"])),
            0,
        )
        for s in base.select("sujets", {})
    }
    rattachees: set[str] = set()
    for li in base.select("sujets_videos", {}):
        rattachees.add(str(li["video_id"]))
        if li.get("sujet_id") and str(li["sujet_id"]) in sujets:
            sujets[str(li["sujet_id"])].videos += 1

    jours = {v: _jour(str(x["publiee_at"])) for v, x in videos.items()}
    par_jour: defaultdict[date, list[VideoASituer]] = defaultdict(list)
    for v in sorted(videos, key=lambda v: str(videos[v]["publiee_at"])):
        if v in rattachees or v not in sous_sujets or jours[v] < args.depuis:
            continue
        par_jour[jours[v]].append(
            VideoASituer(
                v,
                jours[v],
                sources.get(str(videos[v]["source_id"]), ""),
                titres.get(v, ""),
                sous_sujets[v],
            )
        )
    a_situer = sum(len(x) for x in par_jour.values())
    appels = sum(-(-len(x) // LOT_SUJETS) for x in par_jour.values())
    sans_description = sum(1 for v in videos if v not in sous_sujets and jours[v] >= args.depuis)

    print("# Sujets d'actualité" + (" (dry-run)" if args.dry_run else ""))
    print(
        f"\nVidéos politiques à rattacher : {a_situer} sur {len(par_jour)} jours "
        f"({appels} appels Claude) ; déjà rattachées : {len(rattachees)} ; pas encore décrites "
        f"(ignorées, lancer l'étape `videos` de la classification) : {sans_description}. "
        f"Sujets existants : {len(sujets)}."
    )
    if args.dry_run:
        print(f"\nCoût estimé : ~{appels * CLAUDE_USD_PAR_APPEL:.2f} USD. Rien n'a été envoyé.")
        return 0

    claude = ClientClaude(budget_usd=args.budget_claude)
    rattachees_run = 0
    sans_sujet = 0
    crees = 0
    try:
        for jour in sorted(par_jour):
            liste = par_jour[jour]
            for i in range(0, len(liste), LOT_SUJETS):
                lot = liste[i : i + LOT_SUJETS]
                ouverts = actifs(list(sujets.values()), jour)
                try:
                    rep = claude.classer(
                        SYSTEME_SUJETS, message_sujets(ouverts, lot), ReponseSujets, 6000
                    )
                except ReponseInvalide as e:
                    log.warning("lot ignoré (%s, %d vidéos) : %s", jour, len(lot), e)
                    continue
                nouveaux, liens = appliquer(rep, lot, ouverts, jour, set(sujets))
                for s in nouveaux:
                    sujets[s.id] = s
                modifies = mettre_a_jour(sujets, liens, jours)
                # Sujets d'abord (clé étrangère), puis rattachements.
                base.upsert(
                    "sujets",
                    [_ligne_sujet(sujets[sid], aujourdhui) for sid in sorted(modifies)],
                    "id",
                )
                base.upsert(
                    "sujets_videos",
                    [
                        {"video_id": v, "sujet_id": sid, "rattache_le": aujourdhui.isoformat()}
                        for v, sid in liens.items()
                    ],
                    "video_id",
                )
                crees += sum(1 for s in nouveaux if s.id in modifies)
                rattachees_run += len(liens)
                sans_sujet += sum(1 for sid in liens.values() if sid is None)
            log.info(
                "%s : %d vidéos, sujets %d, coût Claude %.2f $",
                jour,
                len(liste),
                len(sujets),
                claude.compteur.cout_usd,
            )
    except BudgetDepasse as e:
        print(f"\nArrêt au budget Claude ({e}) : relancer pour continuer.")

    affiches = [s for s in sujets.values() if s.videos >= 3]
    print(
        f"\n## Bilan\n\n- Vidéos rattachées : {rattachees_run} / {a_situer}, dont {sans_sujet} "
        f"sans sujet\n- Sujets créés : {crees} ; sujets d'au moins 3 vidéos : {len(affiches)} "
        f"(le critère des 2 chaînes est appliqué à l'affichage)\n- Coût Claude : "
        f"{claude.compteur.cout_usd:.2f} USD\n"
        f"- Durée : {(datetime.now(UTC) - debut).total_seconds() / 60:.0f} min"
    )
    return 0


if __name__ == "__main__":
    code = main()
    logging.shutdown()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)  # même sortie que scripts/classification.py
