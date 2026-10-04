"""Purge manuelle du brut (décision du 04/10/2026) : fichiers de `radar-brut` de N jours ou plus.

    python scripts/purge.py --dry-run              # liste ce qui serait supprimé
    python scripts/purge.py --retention 30

Supprime les fichiers `commentaires/`, `videos/` et `evaluation/` datés de `retention` jours ou
plus, et compte les commentaires encore non classés qu'ils contiennent (perte définitive).
Variables : SUPABASE_URL, SUPABASE_SECRET_KEY, RADAR_SEL.
"""

import argparse
import logging
import os
import sys
from datetime import UTC, datetime, timedelta

from radar.anonymisation import sel as lire_sel
from radar.classement import deja_classes, id_commentaire
from radar.storage import (
    DOSSIER_EVALUATION,
    TABLES_BRUTES,
    StockageSupabase,
    date_fichier,
    lire_partition,
    partitions,
    purger,
)

BUCKET_BRUT = "radar-brut"
BUCKET_CLASSE = "radar-classe"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="liste seulement, rien n'est supprimé")
    p.add_argument("--retention", type=int, default=30, help="âge en jours à partir duquel purger")
    args = p.parse_args()
    if args.retention < 1:
        p.error("retention doit être positive")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    url, cle = os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"]
    brut = StockageSupabase(url, cle, BUCKET_BRUT)
    aujourdhui = datetime.now(UTC).date()
    limite = aujourdhui - timedelta(days=args.retention - 1)

    vises = [(t, j, c) for t in TABLES_BRUTES for j, c in partitions(brut, t) if j < limite]
    evaluation = [
        c for c in brut.lister(DOSSIER_EVALUATION) if (j := date_fichier(c)) is None or j < limite
    ]
    sel = lire_sel()
    classes = deja_classes(StockageSupabase(url, cle, BUCKET_CLASSE))
    non_classes = sum(
        1
        for t, _, c in vises
        if t == "commentaires"
        for x in lire_partition(brut, c)
        if str(x.get("texte") or "").strip()
        and id_commentaire(str(x["comment_id"]), sel) not in classes
    )

    print("# Purge du brut" + (" (dry-run)" if args.dry_run else ""))
    print(
        f"\nFichiers datés d'avant le {limite.isoformat()} ({args.retention} jours) : "
        f"{len(vises)} fichiers bruts, {len(evaluation)} fichiers d'évaluation."
    )
    for _, _, c in vises:
        print(f"- {c}")
    print(f"\nCommentaires non vides pas encore classés dans ces fichiers : {non_classes}.")
    if args.dry_run:
        print("\nRien n'a été supprimé.")
        return 0
    supprimes = purger(brut, aujourdhui, args.retention)
    print(f"\n{len(supprimes)} fichiers supprimés.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
