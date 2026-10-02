"""Agrégats par thème calculés depuis les commentaires classés (bucket `radar-classe`).

Une ligne par jour de publication (heure de Paris), thème, type de source, format.
Un commentaire multi-thèmes compte 1/n dans chacun de ses thèmes ; un commentaire non
politique compte 1 dans `non_politique`. Les sommes sur les thèmes égalent donc le nombre de
commentaires (invariant testé). Aucun texte, aucun identifiant de commentaire ni d'auteur.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from radar.schemas import NON_POLITIQUE, VERSION_TAXONOMIE

PARIS = ZoneInfo("Europe/Paris")
MESURES = (
    "commentaires",
    "positifs",
    "neutres",
    "negatifs",
    "hostiles",
    "sous_opinion",
    "accord",
    "nuance",
    "desaccord",
    "hors_sujet",
)
_TONALITES = {"positive": "positifs", "neutre": "neutres", "negative": "negatifs"}
_POSITIONS = {
    "accord_video": "accord",
    "nuance": "nuance",
    "desaccord_video": "desaccord",
    "hors_sujet": "hors_sujet",
}

Cle = tuple[date, str, str, str]  # jour, thème, type de source, format


def jour_paris(ligne: Mapping[str, Any]) -> date:
    """Jour de publication à Paris ; à défaut, jour de récupération."""
    publie = ligne.get("publie_at")
    if isinstance(publie, datetime):
        return publie.astimezone(PARIS).date()
    recupere = ligne["recupere_le"]
    return recupere if isinstance(recupere, date) else date.fromisoformat(str(recupere)[:10])


def agreger(classes: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    sommes: dict[Cle, dict[str, float]] = defaultdict(lambda: dict.fromkeys(MESURES, 0.0))
    for c in classes:
        themes = list(c["themes"] or []) if c["est_politique"] else []
        parts = [(t, 1 / len(themes)) for t in themes] or [(NON_POLITIQUE, 1.0)]
        jour = jour_paris(c)
        for theme, poids in parts:
            s = sommes[(jour, theme, str(c["type_source"]), str(c["format"]))]
            s["commentaires"] += poids
            s[_TONALITES[str(c["tonalite"])]] += poids
            if c["hostilite"]:
                s["hostiles"] += poids
            # Position : uniquement sous une vidéo d'opinion (None ailleurs).
            if c["nature"] == "opinion" and c["position"] in _POSITIONS:
                s["sous_opinion"] += poids
                s[_POSITIONS[str(c["position"])]] += poids
    return [
        {
            "jour": jour.isoformat(),
            "theme": theme,
            "type_source": type_source,
            "format": fmt,
            **{m: round(v, 4) for m, v in s.items()},
            "version_taxonomie": VERSION_TAXONOMIE,
        }
        for (jour, theme, type_source, fmt), s in sorted(sommes.items())
    ]


def agreger_videos(classes: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Par vidéo : commentaires classés, hostiles, et position (vidéos d'opinion seulement)."""
    par_video: dict[str, dict[str, int]] = defaultdict(
        lambda: dict.fromkeys(
            ("commentaires", "hostiles", "accord", "nuance", "desaccord", "hors_sujet"), 0
        )
    )
    for c in classes:
        s = par_video[str(c["video_id"])]
        s["commentaires"] += 1
        s["hostiles"] += int(bool(c["hostilite"]))
        if c["nature"] == "opinion" and c["position"] in _POSITIONS:
            s[_POSITIONS[str(c["position"])]] += 1
    return [{"video_id": v, **s} for v, s in sorted(par_video.items())]
