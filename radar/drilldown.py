"""Drill-down par vidéo (décision du 04/10/2026) : les commentaires classés d'une vidéo.

Un fichier compressé par vidéo dans le bucket privé `radar-drilldown`
(`videos/<video_id>.json.gz`), lu par l'interface admin seulement. Contenu : texte non modifié,
date de publication et étiquettes du classement. Jamais de pseudo, d'auteur ni d'identifiant
de commentaire. Seuls les commentaires publiés dans les 30 derniers jours sont gardés ; les
fichiers des vidéos sorties de la fenêtre sont supprimés.
"""

import gzip
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import date, datetime, timedelta
from typing import Any

from radar.classement import id_commentaire
from radar.storage import Stockage

FENETRE_JOURS = 30
DOSSIER = "videos"
INDEX = "index.json"


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


def publier(st: Stockage, par_video: Mapping[str, list[dict[str, Any]]]) -> tuple[int, int]:
    """Écrit les fichiers modifiés depuis le dernier run et supprime ceux sortis de la fenêtre.

    Renvoie (fichiers écrits, fichiers supprimés). Un index (nombre de commentaires par vidéo)
    évite de réécrire les vidéos inchangées.
    """
    try:
        avant: dict[str, int] = json.loads(st.lire(INDEX))
    except Exception:
        avant = {}
    ecrits = 0
    for v, xs in sorted(par_video.items()):
        if avant.get(v) == len(xs):
            continue
        donnees = json.dumps(xs, ensure_ascii=False).encode()
        st.ecrire(chemin(v), gzip.compress(donnees))
        ecrits += 1
    existants = set(st.lister(DOSSIER))
    a_supprimer = sorted(existants - {chemin(v) for v in par_video})
    st.supprimer(a_supprimer)
    st.ecrire(INDEX, json.dumps({v: len(xs) for v, xs in par_video.items()}).encode())
    return ecrits, len(a_supprimer)
