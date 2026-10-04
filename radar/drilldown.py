"""Drill-down par vidéo (décision du 04/10/2026) : les commentaires classés d'une vidéo.

Un fichier compressé par vidéo dans le bucket privé `radar-drilldown`
(`videos/<video_id>.json.gz`), lu par l'interface admin seulement. Contenu : texte non modifié,
date de publication et étiquettes du classement. Jamais de pseudo, d'auteur ni d'identifiant
de commentaire. Seuls les commentaires publiés dans les 30 derniers jours sont gardés ; les
fichiers des vidéos sorties de la fenêtre sont supprimés.
"""

import gzip
import json
import logging
import threading
from collections import defaultdict
from collections.abc import Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from typing import Any

from radar.classement import id_commentaire
from radar.storage import Stockage

FENETRE_JOURS = 30
DOSSIER = "videos"
INDEX = "index.json"
log = logging.getLogger(__name__)


def _date(x: Any) -> date | None:
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    return None


def fiches(
    classes: Iterable[Mapping[str, Any]],
    bruts: Iterable[Mapping[str, Any]],
    sel: bytes,
    aujourdhui: date,
) -> dict[str, list[dict[str, Any]]]:
    """Par vidéo, les commentaires classés publiés dans les 30 derniers jours, du plus ancien."""
    limite = aujourdhui - timedelta(days=FENETRE_JOURS)
    par_id = {str(c["id"]): c for c in classes}
    resultat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for b in bruts:
        publie = b.get("publie_at")
        jour = _date(publie)
        if jour is None or jour < limite:
            continue
        c = par_id.get(id_commentaire(str(b["comment_id"]), sel))
        if c is None:
            continue
        assert isinstance(publie, datetime)
        resultat[str(b["video_id"])].append(
            {
                "texte": str(b.get("texte") or ""),
                "publie_at": publie.isoformat(),
                "politique": bool(c["est_politique"]),
                "themes": list(c["themes"] or []),
                "position": c["position"],
                "tonalite": c["tonalite"],
                "hostile": bool(c["hostilite"]),
            }
        )
    for xs in resultat.values():
        xs.sort(key=lambda x: str(x["publie_at"]))
    return dict(resultat)


def chemin(video_id: str) -> str:
    return f"{DOSSIER}/{video_id}.json.gz"


ECRITURES_PARALLELES = 8
POINT_INDEX = 500  # l'index est réécrit tous les 500 fichiers : un run interrompu reprend


def publier(st: Stockage, par_video: Mapping[str, list[dict[str, Any]]]) -> tuple[int, int, int]:
    """Écrit les fichiers modifiés depuis le dernier run et supprime ceux sortis de la fenêtre.

    Renvoie (fichiers écrits, en erreur, supprimés). Un index (nombre de commentaires par
    vidéo) évite de réécrire les vidéos inchangées ; il est enregistré au fil de l'eau, si bien
    qu'un run coupé reprend là où il s'est arrêté. Un fichier en erreur est compté et retenté au
    run suivant, sans arrêter les autres.
    """
    try:
        avant: dict[str, int] = json.loads(st.lire(INDEX))
    except Exception:
        avant = {}
    a_ecrire = [(v, xs) for v, xs in sorted(par_video.items()) if avant.get(v) != len(xs)]
    fait = {v: n for v, n in avant.items() if v in par_video}
    verrou = threading.Lock()
    ecrits = erreurs = 0

    def un(paire: tuple[str, list[dict[str, Any]]]) -> bool:
        v, xs = paire
        try:
            st.ecrire(chemin(v), gzip.compress(json.dumps(xs, ensure_ascii=False).encode()))
            return True
        except Exception as e:  # une erreur sur un fichier n'arrête pas les autres
            log.warning("drill-down %s non écrit : %s", v, e)
            return False

    with ThreadPoolExecutor(max_workers=ECRITURES_PARALLELES) as pool:
        for i in range(0, len(a_ecrire), POINT_INDEX):
            lot = a_ecrire[i : i + POINT_INDEX]
            for (v, xs), ok in zip(lot, pool.map(un, lot), strict=True):
                with verrou:
                    if ok:
                        fait[v] = len(xs)
                        ecrits += 1
                    else:
                        erreurs += 1
            st.ecrire(INDEX, json.dumps(fait).encode())
            log.info("drill-down : %d / %d fichiers écrits", ecrits, len(a_ecrire))
    existants = set(st.lister(DOSSIER))
    a_supprimer = sorted(existants - {chemin(v) for v in par_video})
    st.supprimer(a_supprimer)
    st.ecrire(INDEX, json.dumps(fait).encode())
    return ecrits, erreurs, len(a_supprimer)
