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
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from radar.anonymisation import sel as lire_sel
from radar.classement import (
    PARALLELES,
    PLAFOND_PAR_VIDEO,
    Bilan,
    Video,
    classer,
    classes_par_video,
    id_commentaire,
    plafonner,
)
from radar.classification import en_nature, normaliser_sujets
from radar.evaluation import Candidate, classer_videos, decrire_videos_batch
from radar.llm import BudgetDepasse, ClientClaude, ClientJev
from radar.schemas import VERSION_TAXONOMIE, NatureVideo, Theme
from radar.storage import (
    RETENTION_JOURS,
    Stockage,
    StockageLocal,
    StockageSupabase,
    lire_partition,
    partitions,
)
from radar.supabase_rest import Supabase

log = logging.getLogger("classification")
BUCKET_BRUT = "radar-brut"
BUCKET_CLASSE = "radar-classe"
# Coûts mesurés le 02/10/2026 (docs/evaluation-resultats.md), pour l'estimation du dry-run.
JEV_USD_PAR_1000 = 0.065
CLAUDE_USD_PAR_VIDEO_DIRECT = 0.0025  # mesuré le 02/10 : 5,02 USD pour 2 100 vidéos
CLAUDE_USD_PAR_VIDEO = 0.0009  # estimé : batch (-50 %) et 10 vidéos par requête
LOT_BATCH_VIDEOS = 5000  # vidéos par batch Claude (500 requêtes), écrites à chaque retour
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


def _ecrire_sujets(
    base: Supabase, sujets: dict[str, list[tuple[Theme, str, float]]], jour: date
) -> None:
    """Remplace les sujets des vidéos décrites (une ligne par vidéo et par thème)."""
    vids = sorted(sujets)
    for i in range(0, len(vids), LOT_NATURES):
        lot = vids[i : i + LOT_NATURES]
        base.supprimer("videos_sujets", {"video_id": f"in.({','.join(lot)})"})
        base.upsert(
            "videos_sujets",
            [
                {
                    "video_id": v,
                    "theme": theme,
                    "sous_sujet": sous_sujet,
                    "poids": round(poids, 4),
                    "principal": rang == 0,
                    "version_taxonomie": VERSION_TAXONOMIE,
                    "classe_le": jour.isoformat(),
                }
                for v in lot
                for rang, (theme, sous_sujet, poids) in enumerate(sujets[v])
            ],
            "video_id,theme",
        )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="volumes et coût estimé, aucun appel")
    p.add_argument("--budget-jev", type=float, default=20.0, help="dollars max pour Jev")
    p.add_argument("--budget-claude", type=float, default=5.0, help="dollars max pour Claude")
    p.add_argument("--paralleles", type=int, default=PARALLELES, help="appels Jev simultanés")
    p.add_argument("--limite", type=int, default=0, help="au plus N commentaires (essai)")
    p.add_argument(
        "--videos-seulement",
        action="store_true",
        help="décrire les vidéos (nature, sujets, thèses) sans classer les commentaires",
    )
    p.add_argument(
        "--paralleles-claude", type=int, default=8, help="descriptions de vidéos simultanées"
    )
    p.add_argument(
        "--direct",
        action="store_true",
        help="un appel par vidéo (immédiat, 2 à 3 fois plus cher) au lieu du batch",
    )
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
    for _, c in partitions(brut, "videos"):
        for v in lire_partition(brut, c):
            bruts_videos[str(v["video_id"])] = v
    commentaires = [x for _, c in partitions(brut, "commentaires") for x in lire_partition(brut, c)]
    deja, deja_par_video = classes_par_video(classe)
    non_vides = [x for x in commentaires if str(x.get("texte") or "").strip()]
    non_classes = [x for x in non_vides if id_commentaire(str(x["comment_id"]), sel) not in deja]
    # Plafond par vidéo (décision du 04/10/2026) ; le volume réel de chaque vidéo sert à pondérer.
    a_classer = plafonner(non_classes, deja_par_video, sel, PLAFOND_PAR_VIDEO)
    volumes = Counter(str(x["video_id"]) for x in non_vides)
    if args.limite:
        a_classer = a_classer[: args.limite]
    vids = {str(x["video_id"]) for x in a_classer}
    # Vidéos à décrire (nature et sujets) : toutes les vidéos politiques du brut, commentées ou
    # non (l'agenda compte aussi les vidéos sans réaction), sans nature ou sans sujets.
    avec_sujets = {
        str(v["video_id"]) for v in base.select("videos_sujets", {"principal": "eq.true"})
    }
    # Thèses (vidéos d'opinion) : dérivées du brut, effacées 30 jours après sa récupération.
    limite_theses = aujourdhui - timedelta(days=RETENTION_JOURS - 1)
    if not args.dry_run:
        base.supprimer("videos_theses", {"recupere_le": f"lt.{limite_theses.isoformat()}"})
    avec_these = {str(v["video_id"]) for v in base.select("videos_theses", {})}
    candidates_videos = (
        vids if args.limite else {v for v, ligne in lignes_videos.items() if ligne.get("prefiltre")}
    )
    a_decrire = sorted(
        v
        for v in candidates_videos
        if v in lignes_videos
        and v in bruts_videos
        and (
            not lignes_videos[v].get("nature")
            or v not in avec_sujets
            or (lignes_videos[v].get("nature") == "opinion" and v not in avec_these)
        )
    )
    sans_nature = [v for v in a_decrire if not lignes_videos[v].get("nature")]
    inconnues = sorted(v for v in vids if v not in lignes_videos or v not in bruts_videos)

    print("# Classification en masse" + (" (dry-run)" if args.dry_run else ""))
    print(
        f"\nCommentaires dans le brut : {len(commentaires)} ; déjà classés : {len(deja)} ; "
        f"non classés : {len(non_classes)} ; à classer avec le plafond de {PLAFOND_PAR_VIDEO} "
        f"par vidéo : {len(a_classer)} sous {len(vids)} vidéos."
    )
    print(
        f"Vidéos à décrire (nature et sujets) : {len(a_decrire)}, dont {len(sans_nature)} sans "
        f"nature ; vidéos introuvables (ignorées) : {len(inconnues)}."
    )
    if args.dry_run:
        print(
            f"\nCoût estimé : Jev ~{len(a_classer) * JEV_USD_PAR_1000 / 1000:.2f} USD, "
            f"Claude (vidéos) ~{len(a_decrire) * CLAUDE_USD_PAR_VIDEO:.2f} USD en batch "
            f"(~{len(a_decrire) * CLAUDE_USD_PAR_VIDEO_DIRECT:.2f} USD avec --direct). "
            "Rien n'a été envoyé."
        )
        return 0

    # Volume réel de commentaires (non vides) par vidéo, pour la pondération des agrégats. Jamais
    # revu à la baisse : une purge du brut ne doit pas fausser les poids.
    connus = {str(v["video_id"]): int(v["commentaires"]) for v in base.select("volumes_videos", {})}
    base.upsert(
        "volumes_videos",
        [
            {
                "video_id": v,
                "commentaires": max(n, connus.get(v, 0)),
                "maj_le": aujourdhui.isoformat(),
            }
            for v, n in sorted(volumes.items())
            if v in lignes_videos and n > connus.get(v, 0)
        ],
        "video_id",
    )

    # 1. Nature et sujets des vidéos (Claude), écrits dans Supabase au fur et à mesure. Une
    # nature déjà attribuée n'est jamais changée (les commentaires classés en dépendent).
    claude = ClientClaude(budget_usd=args.budget_claude)
    natures: dict[str, NatureVideo] = {
        v: en_nature(str(lignes_videos[v]["nature"]))
        for v in vids
        if v in lignes_videos and lignes_videos[v].get("nature")
    }
    decrites = 0
    try:
        # Par défaut : API Batch, 10 vidéos par requête (décision du 04/10/2026) ; --direct :
        # un appel par vidéo, résultat immédiat (essais).
        taille = LOT_NATURES if args.direct else LOT_BATCH_VIDEOS
        for i in range(0, len(a_decrire), taille):
            cands = [
                Candidate(
                    v,
                    str(sources.get(str(lignes_videos[v]["source_id"]), {}).get("type", "")),
                    str(lignes_videos[v]["format"]),
                    str(sources.get(str(lignes_videos[v]["source_id"]), {}).get("nom", "")),
                    str(bruts_videos[v].get("titre") or ""),
                    str(bruts_videos[v].get("description") or ""),
                )
                for v in a_decrire[i : i + taille]
            ]
            reponses = (
                classer_videos(claude, cands, args.paralleles_claude)
                if args.direct
                else decrire_videos_batch(claude, cands)
            )
            nouvelles: dict[str, NatureVideo] = {
                v: r.nature_video for v, r in reponses.items() if not lignes_videos[v].get("nature")
            }
            _ecrire_natures(base, nouvelles, aujourdhui)
            natures.update(nouvelles)
            sujets = {v: normaliser_sujets(r.sujets) for v, r in reponses.items() if r.sujets}
            _ecrire_sujets(base, sujets, aujourdhui)
            theses = [
                {
                    "video_id": v,
                    "these": " ".join(r.resume.split())[:400],
                    "explicite": r.these_explicite
                    and not r.resume.strip().startswith("Sujet peu précis"),
                    "recupere_le": str(bruts_videos[v].get("recupere_le") or aujourdhui)[:10],
                    "classe_le": aujourdhui.isoformat(),
                }
                for v, r in reponses.items()
                if (lignes_videos[v].get("nature") or r.nature_video) == "opinion"
                and r.resume.strip()
            ]
            base.upsert("videos_theses", theses, "video_id")
            decrites += len(reponses)
    except BudgetDepasse as e:
        print(f"\nDescription des vidéos : arrêt au budget Claude ({e}).")

    if args.videos_seulement:
        print(
            f"\n## Bilan (vidéos seulement)\n\n- Vidéos décrites (nature, sujets, thèses) : "
            f"{decrites} / {len(a_decrire)}, coût Claude {claude.compteur.cout_usd:.2f} USD\n"
            f"- Durée : {(datetime.now(UTC) - debut).total_seconds() / 60:.0f} min"
        )
        return 0

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
        f"\n## Bilan\n\n- Vidéos décrites (nature et sujets) : {decrites}, coût Claude "
        f"{claude.compteur.cout_usd:.2f} USD\n- Commentaires classés : {bilan.classes} / "
        f"{bilan.a_classer} (vidéos de nature connue), erreurs {bilan.erreurs}\n- Coût Jev : "
        f"{bilan.cout_usd:.2f} USD "
        f"({1000 * bilan.cout_usd / max(1, bilan.classes):.3f} USD / 1 000)\n"
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
