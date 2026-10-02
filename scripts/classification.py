"""Classification en masse des commentaires collectés (Jev seul, décision du 02/10/2026).

    python scripts/classification.py --dry-run     # volumes et coût estimé, aucun appel
    python scripts/classification.py --budget-jev 20 --budget-claude 5

1. Nature des vidéos commentées qui n'en ont pas (Claude, un appel par vidéo) → `videos.nature`.
2. Commentaires du brut non encore classés → Jev (appels en parallèle) → bucket `radar-classe`
   (une ligne par commentaire, sans texte, identifiant et auteur hashés).

Variables : SUPABASE_URL, SUPABASE_SECRET_KEY, AI_GATEWAY_API_KEY, ANTHROPIC_API_KEY, RADAR_SEL.
Relancer ne reclasse rien : seuls les commentaires absents de `radar-classe` partent.
"""

import argparse
import logging
import os
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from radar.anonymisation import sel as lire_sel
from radar.classement import (
    PARALLELES,
    Bilan,
    Video,
    classer,
    deja_classes,
    id_commentaire,
)
from radar.classification import en_nature
from radar.evaluation import Candidate, classer_videos
from radar.llm import BudgetDepasse, ClientClaude, ClientJev
from radar.schemas import NatureVideo
from radar.storage import Stockage, StockageLocal, StockageSupabase, lire_partition, partitions
from radar.supabase_rest import Supabase

log = logging.getLogger("classification")
BUCKET_BRUT = "radar-brut"
BUCKET_CLASSE = "radar-classe"
# Coûts mesurés le 02/10/2026 (docs/evaluation-resultats.md), pour l'estimation du dry-run.
JEV_USD_PAR_1000 = 0.065
CLAUDE_USD_PAR_VIDEO = 0.001
LOT_NATURES = 100


def _stockages(args: argparse.Namespace) -> tuple[Stockage, Stockage]:
    if args.stockage_local:
        return StockageLocal(args.stockage_local / "brut"), StockageLocal(
            args.stockage_local / "classe"
        )
    url, cle = os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"]
    return StockageSupabase(url, cle, BUCKET_BRUT), StockageSupabase(url, cle, BUCKET_CLASSE)


def _ecrire_natures(base: Supabase, natures: dict[str, NatureVideo], jour: date) -> None:
    par_nature: dict[str, list[str]] = {}
    for vid, n in natures.items():
        par_nature.setdefault(n, []).append(vid)
    for n, vids in par_nature.items():
        for i in range(0, len(vids), LOT_NATURES):
            lot = ",".join(vids[i : i + LOT_NATURES])
            base.modifier(
                "videos",
                {"video_id": f"in.({lot})"},
                {"nature": n, "nature_classee_le": jour.isoformat()},
            )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="volumes et coût estimé, aucun appel")
    p.add_argument("--budget-jev", type=float, default=20.0, help="dollars max pour Jev")
    p.add_argument("--budget-claude", type=float, default=5.0, help="dollars max pour Claude")
    p.add_argument("--paralleles", type=int, default=PARALLELES, help="appels Jev simultanés")
    p.add_argument("--limite", type=int, default=0, help="au plus N commentaires (essai)")
    p.add_argument("--stockage-local", type=Path, help="dossier local au lieu des buckets")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    debut = datetime.now(UTC)
    aujourdhui = debut.date()
    sel = lire_sel()
    brut, classe = _stockages(args)
    base = Supabase(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

    sources = {str(s["id"]): s for s in base.select("sources", {})}
    lignes_videos = {str(v["video_id"]): v for v in base.select("videos", {})}
    bruts_videos: dict[str, dict[str, Any]] = {}
    for c in partitions(brut, "videos").values():
        for v in lire_partition(brut, c):
            bruts_videos[str(v["video_id"])] = v
    commentaires = [
        x for c in partitions(brut, "commentaires").values() for x in lire_partition(brut, c)
    ]
    deja = deja_classes(classe)
    a_classer = [
        x
        for x in commentaires
        if id_commentaire(str(x["comment_id"]), sel) not in deja
        and str(x.get("texte") or "").strip()
    ]
    if args.limite:
        a_classer = a_classer[: args.limite]
    vids = {str(x["video_id"]) for x in a_classer}
    sans_nature = sorted(
        v
        for v in vids
        if v in lignes_videos and not lignes_videos[v].get("nature") and v in bruts_videos
    )
    inconnues = sorted(v for v in vids if v not in lignes_videos or v not in bruts_videos)

    print("# Classification en masse" + (" (dry-run)" if args.dry_run else ""))
    print(
        f"\nCommentaires dans le brut : {len(commentaires)} ; déjà classés : {len(deja)} ; "
        f"à classer : {len(a_classer)} sous {len(vids)} vidéos."
    )
    print(
        f"Vidéos sans nature : {len(sans_nature)} ; "
        f"vidéos introuvables (ignorées) : {len(inconnues)}."
    )
    if args.dry_run:
        print(
            f"\nCoût estimé : Jev ~{len(a_classer) * JEV_USD_PAR_1000 / 1000:.2f} $, "
            f"Claude (nature) ~{len(sans_nature) * CLAUDE_USD_PAR_VIDEO:.2f} $. "
            "Rien n'a été envoyé."
        )
        return 0

    # 1. Nature des vidéos (Claude), écrite dans Supabase au fur et à mesure.
    claude = ClientClaude(budget_usd=args.budget_claude)
    natures: dict[str, NatureVideo] = {
        v: en_nature(str(lignes_videos[v]["nature"]))
        for v in vids
        if v in lignes_videos and lignes_videos[v].get("nature")
    }
    try:
        for i in range(0, len(sans_nature), LOT_NATURES):
            cands = [
                Candidate(
                    v,
                    str(sources.get(str(lignes_videos[v]["source_id"]), {}).get("type", "")),
                    str(lignes_videos[v]["format"]),
                    str(sources.get(str(lignes_videos[v]["source_id"]), {}).get("nom", "")),
                    str(bruts_videos[v].get("titre") or ""),
                    str(bruts_videos[v].get("description") or ""),
                )
                for v in sans_nature[i : i + LOT_NATURES]
            ]
            nouvelles: dict[str, NatureVideo] = {
                v: r.nature_video for v, r in classer_videos(claude, cands).items()
            }
            _ecrire_natures(base, nouvelles, aujourdhui)
            natures.update(nouvelles)
    except BudgetDepasse as e:
        print(f"\nNature des vidéos : arrêt au budget Claude ({e}).")

    # 2. Commentaires (Jev) des vidéos dont la nature est connue.
    videos: dict[str, Video] = {}
    for v, n in natures.items():
        ligne = lignes_videos[v]
        src = sources.get(str(ligne["source_id"]), {})
        videos[v] = Video(
            v,
            str(ligne["source_id"]),
            str(src.get("type", "")),
            str(ligne["format"]),
            str(src.get("nom", "")),
            str(bruts_videos[v].get("titre") or ""),
            n,
        )

    def rapporter(b: Bilan) -> None:
        log.info(
            "classés %d / %d, erreurs %d, coût Jev %.2f $",
            b.classes,
            b.a_classer,
            b.erreurs,
            b.cout_usd,
        )

    jev = ClientJev(budget_usd=args.budget_jev)
    bilan = classer(
        classe,
        jev,
        a_classer,
        videos,
        sel,
        aujourdhui,
        paralleles=args.paralleles,
        rapporter=rapporter,
    )
    duree = (datetime.now(UTC) - debut).total_seconds() / 60
    print(
        f"\n## Bilan\n\n- Natures classées : {len(natures)} vidéos, coût Claude "
        f"{claude.compteur.cout_usd:.2f} $\n- Commentaires classés : {bilan.classes} / "
        f"{bilan.a_classer} (vidéos de nature connue), erreurs {bilan.erreurs}\n- Coût Jev : "
        f"{bilan.cout_usd:.2f} $ ({1000 * bilan.cout_usd / max(1, bilan.classes):.3f} $ / 1 000)\n"
        f"- Durée : {duree:.0f} min"
        + (
            "\n- **Arrêt au budget Jev** : relancer pour continuer (rien n'est reclassé)."
            if bilan.arret_budget
            else ""
        )
    )
    return 0


if __name__ == "__main__":
    code = main()
    logging.shutdown()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)  # même sortie que scripts/evaluation.py (plantage à la fermeture évité)
