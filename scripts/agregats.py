"""Recalcule les agrégats par thème depuis les commentaires classés et les pousse dans Supabase.

    python scripts/agregats.py --dry-run   # totaux, rien n'est écrit
    python scripts/agregats.py

Recalcul complet à chaque run (idempotent). Variables : SUPABASE_URL, SUPABASE_SECRET_KEY.
"""

import argparse
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from radar.agregats import agreger, agreger_videos, poids_par_video
from radar.classement import DOSSIER_CLASSE
from radar.storage import Stockage, StockageLocal, StockageSupabase, lire_partition
from radar.supabase_rest import Supabase

BUCKET_CLASSE = "radar-classe"


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
    if not args.dry_run:
        base.upsert("agregats_themes", lignes, "jour,theme,type_source,format")
        par_video = agreger_videos(classes, poids)
        base.upsert("agregats_videos", par_video, "video_id")
        print(
            f"\nÉcrit dans Supabase : {len(lignes)} lignes (agregats_themes), "
            f"{len(par_video)} vidéos (agregats_videos)."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
