"""Source (c) du vivier des médias natifs : recherche standardisée par candidat déclaré.

    python scripts/recherche_vivier.py panel/candidats_declares.csv --budget 1300 > recherche.md

Pour chaque candidat : search.list q="<nom> interview", type=video, relevanceLanguage=fr,
regionCode=FR, publiées depuis 12 mois, 25 résultats. EXCEPTION UNIQUE au bannissement de
search.list (docs/decisions.md, 01/10/2026) : 100 unités par candidat.
Sortie : les chaînes trouvées (ID, nom, nombre de vidéos, candidats concernés), sans titre de vidéo.
"""

import argparse
import csv
import logging
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from radar.youtube import QuotaDepasse, YouTube, cle_api

log = logging.getLogger("recherche_vivier")


def lire_candidats(chemin: Path) -> list[str]:
    with chemin.open(newline="", encoding="utf-8") as f:
        return [ligne["nom"].strip() for ligne in csv.DictReader(f) if ligne["nom"].strip()]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("candidats", type=Path, help="CSV avec une colonne 'nom'")
    p.add_argument("--budget", type=int, required=True, help="quota YouTube max (100 par candidat)")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", stream=sys.stderr)

    noms = lire_candidats(args.candidats)
    yt = YouTube(cle_api(), budget=args.budget)
    maintenant = datetime.now(UTC)

    chaines: dict[str, str] = {}
    videos: dict[str, int] = defaultdict(int)
    candidats: dict[str, set[str]] = defaultdict(set)
    faits: list[str] = []
    arret = ""
    for nom in noms:
        try:
            resultats = yt.recherche_interviews(nom, maintenant)
        except QuotaDepasse as e:
            arret = f"Arrêt propre : {e}. Candidats non traités : {', '.join(noms[len(faits) :])}."
            break
        faits.append(nom)
        for channel_id, titre in resultats:
            chaines[channel_id] = titre
            videos[channel_id] += 1
            candidats[channel_id].add(nom)

    lignes = [
        f"# Recherche du vivier — {maintenant:%d/%m/%Y}",
        "",
        f"Candidats traités ({len(faits)}) : {', '.join(faits)}.",
        "",
        "| channel_id | chaîne | vidéos trouvées | candidats |",
        "|---|---|---:|---|",
    ]
    for cid in sorted(chaines, key=lambda c: (-len(candidats[c]), -videos[c], chaines[c])):
        lignes.append(
            f"| {cid} | {chaines[cid]} | {videos[cid]} | {', '.join(sorted(candidats[cid]))} |"
        )
    if arret:
        lignes += ["", arret]
    lignes += ["", f"Quota YouTube consommé : **{yt.consomme} / {yt.budget}** unités."]
    print("\n".join(lignes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
