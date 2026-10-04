"""Recalcule les agrégats par thème depuis les commentaires classés et les pousse dans Supabase.

    python scripts/agregats.py --dry-run   # totaux, rien n'est écrit
    python scripts/agregats.py

Recalcul complet à chaque run (idempotent) : agrégats par thème, par chaîne et par vidéo, et
drill-down (commentaires classés des 30 derniers jours, un fichier par vidéo dans le bucket
privé `radar-drilldown`).
Variables : SUPABASE_URL, SUPABASE_SECRET_KEY, RADAR_SEL.
"""

import argparse
import logging
import os
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from radar.agregats import agreger, agreger_videos, poids_par_video
from radar.anonymisation import sel as lire_sel
from radar.classement import DOSSIER_CLASSE
from radar.drilldown import fiches, publier
from radar.storage import Stockage, StockageLocal, StockageSupabase, lire_partition, partitions
from radar.supabase_rest import Supabase

BUCKET_CLASSE = "radar-classe"
BUCKET_BRUT = "radar-brut"
BUCKET_DRILLDOWN = "radar-drilldown"


def _stockage(args: argparse.Namespace) -> Stockage:
    if args.stockage_local:
        return StockageLocal(args.stockage_local)
    return StockageSupabase(
        os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"], BUCKET_CLASSE
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="totaux seulement, rien n'est écrit")
    p.add_argument("--stockage-local", type=Path, help="dossier local au lieu du bucket")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    st = _stockage(args)
    classes: list[dict[str, Any]] = []
    for c in st.lister(DOSSIER_CLASSE):
        if c.endswith(".parquet"):
            classes.extend(lire_partition(st, c))
    base = Supabase(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
    # Plafond par vidéo (décision du 04/10/2026) : pondération par le volume réel.
    volumes = {
        str(v["video_id"]): int(v["commentaires"]) for v in base.select("volumes_videos", {})
    }
    poids = poids_par_video(classes, volumes)
    lignes = agreger(classes, poids)
    lignes_chaines = agreger(classes, poids, par_chaine=True)
    par_type: defaultdict[str, float] = defaultdict(float)
    for li in lignes:
        par_type[str(li["type_source"])] += float(li["commentaires"])
    jours = sorted({str(li["jour"]) for li in lignes})
    print("# Agrégats par thème" + (" (dry-run)" if args.dry_run else ""))
    print(
        f"\nCommentaires classés : {len(classes)} ; lignes d'agrégats : {len(lignes)} ; "
        f"jours : {jours[0] if jours else '-'} → {jours[-1] if jours else '-'}."
    )
    for t, n in sorted(par_type.items()):
        print(f"- {t} : {n:.0f} commentaires")
    ponderees = sum(1 for w in poids.values() if w > 1)
    print(
        f"\nVidéos pondérées (plus de commentaires que de classés) : {ponderees} ; "
        f"commentaires estimés : {sum(float(li['commentaires']) for li in lignes):.0f}."
    )
    # Drill-down : texte du brut des commentaires classés (30 derniers jours).
    url, cle = os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"]
    brut: Stockage = (
        StockageLocal(args.stockage_local / "brut")
        if args.stockage_local
        else StockageSupabase(url, cle, BUCKET_BRUT)
    )
    bruts = [x for _, c in partitions(brut, "commentaires") for x in lire_partition(brut, c)]
    par_video_dd = fiches(classes, bruts, lire_sel(), datetime.now(UTC).date())
    print(
        f"\nDrill-down : {len(par_video_dd)} vidéos, "
        f"{sum(len(x) for x in par_video_dd.values())} commentaires classés (30 derniers jours)."
    )
    if not args.dry_run:
        base.upsert("agregats_themes", lignes, "jour,theme,type_source,format")
        base.upsert("agregats_chaines", lignes_chaines, "jour,theme,source_id,format")
        par_video = agreger_videos(classes, poids)
        base.upsert("agregats_videos", par_video, "video_id")
        print(
            f"\nÉcrit dans Supabase : {len(lignes)} lignes (agregats_themes), "
            f"{len(lignes_chaines)} lignes (agregats_chaines), {len(par_video)} vidéos "
            "(agregats_videos)."
        )
        # Le drill-down en dernier : les chiffres sont à jour même s'il est interrompu.
        drilldown: Stockage = (
            StockageLocal(args.stockage_local / "drilldown")
            if args.stockage_local
            else StockageSupabase(url, cle, BUCKET_DRILLDOWN)
        )
        ecrits, erreurs, supprimes = publier(drilldown, par_video_dd)
        print(
            f"Drill-down : {ecrits} fichiers écrits, {erreurs} en erreur (retentés au prochain "
            f"run), {supprimes} supprimés."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
