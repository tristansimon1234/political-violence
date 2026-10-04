"""Sujets d'actualité (étape 6) : regroupement des vidéos politiques par événement.

Chaque jour, Claude rattache les vidéos politiques publiées ce jour-là à un sujet encore actif,
à un nouveau sujet, ou à aucun. Une vidéo appartient à 0 ou 1 sujet. Le titre d'un sujet est
une donnée dérivée, neutre, écrite par le modèle (pas un titre de vidéo) : conservé toute la
campagne. Un sujet n'est affiché qu'à partir de 3 vidéos de 2 chaînes (docs/donnees.md).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from pydantic import BaseModel

FENETRE_ACTIF_JOURS = 7  # un sujet s'éteint après 7 jours sans nouvelle vidéo
MIN_VIDEOS = 3
MIN_CHAINES = 2
LOT_SUJETS = 60  # vidéos par appel
MAX_TITRE_SUJET = 80
MAX_TITRE_VIDEO = 160
AUCUN = "aucun"


@dataclass(frozen=True)
class VideoASituer:
    video_id: str
    jour: date  # date de publication (Paris)
    chaine: str
    titre: str  # titre brut (30 jours max), vide s'il a été purgé
    sous_sujet: str  # libellé neutre écrit à la description de la vidéo


@dataclass
class Sujet:
    id: str
    titre: str
    premier_jour: date
    dernier_jour: date
    videos: int


class NouveauSujet(BaseModel):
    cle: str
    titre: str


class Rattachement(BaseModel):
    video: int
    sujet: str


class ReponseSujets(BaseModel):
    nouveaux: list[NouveauSujet]
    rattachements: list[Rattachement]


SYSTEME_SUJETS = f"""You group French political YouTube videos by news event ("story").

A story is one specific event or controversy that several videos react to: an announcement, a
candidacy, a vote, a debate, a statement, a politicised news item, a war development. It is
narrower than a broad theme (not "immigration", but "the asylum bill vote") and broader than a
single video's angle (all videos about peace talks in Ukraine, Putin's reaction to them, and
the state of the front this week belong to one story "Guerre en Ukraine et négociations").

You receive the stories still active (id, neutral title, number of videos, last day) and new
videos (index, day, channel, title, short neutral label). For EVERY video, return one
rattachement:
- `sujet` = the id of an active story if the video is about that event;
- otherwise `sujet` = the key of a new story you create in `nouveaux` (keys "N1", "N2"...),
  when the video covers a specific event that other videos are likely to cover too;
- otherwise `sujet` = "{AUCUN}" (general commentary, recurring show without a specific event,
  non-political content, or too vague).
Prefer an existing story over a new one when it is the same event. Never create two new
stories for the same event.

New story titles: in French, neutral and factual, 3 to 10 words, at most {MAX_TITRE_SUJET}
characters, no judgement, no quotation, never a copy of a video title, no person's name unless
the event cannot be described without it (for instance a candidacy)."""


def actifs(sujets: list[Sujet], jour: date) -> list[Sujet]:
    """Sujets encore actifs le jour donné (dernière vidéo dans les 7 jours précédents)."""
    debut = jour - timedelta(days=FENETRE_ACTIF_JOURS)
    return [s for s in sujets if s.premier_jour <= jour and s.dernier_jour >= debut]


def _ligne(texte: str, n: int) -> str:
    return " ".join(texte.split())[:n]


def message_sujets(ouverts: list[Sujet], lot: list[VideoASituer]) -> str:
    lignes = ["Active stories:"]
    lignes += [
        f"- {s.id} | {s.titre} | {s.videos} videos | last {s.dernier_jour.isoformat()}"
        for s in ouverts
    ] or ["(none)"]
    lignes.append("\nNew videos:")
    lignes += [
        f"{i} | {v.jour.isoformat()} | {_ligne(v.chaine, 60)} | "
        f"{_ligne(v.titre, MAX_TITRE_VIDEO) or '(title unavailable)'} | {_ligne(v.sous_sujet, 60)}"
        for i, v in enumerate(lot)
    ]
    return "\n".join(lignes)


def nouvel_id(jour: date, existants: set[str]) -> str:
    n = 1
    while f"{jour.isoformat()}-{n:03d}" in existants:
        n += 1
    return f"{jour.isoformat()}-{n:03d}"


def appliquer(
    rep: ReponseSujets,
    lot: list[VideoASituer],
    ouverts: list[Sujet],
    jour: date,
    existants: set[str],
) -> tuple[list[Sujet], dict[str, str | None]]:
    """Nouveaux sujets (ceux qui reçoivent au moins une vidéo) et rattachement de chaque vidéo.

    Une vidéo absente de la réponse n'est pas rattachée : elle repart au run suivant. Un
    identifiant inconnu, une clé sans titre ou "aucun" valent « aucun sujet ».
    """
    ids_ouverts = {s.id for s in ouverts}
    titres = {n.cle: _ligne(n.titre, MAX_TITRE_SUJET) for n in rep.nouveaux if _ligne(n.titre, 1)}
    crees: dict[str, Sujet] = {}
    liens: dict[str, str | None] = {}
    pris = set(existants)
    for r in rep.rattachements:
        if not 0 <= r.video < len(lot) or lot[r.video].video_id in liens:
            continue
        cible: str | None = None
        if r.sujet in ids_ouverts:
            cible = r.sujet
        elif r.sujet in titres:
            if r.sujet not in crees:
                ident = nouvel_id(jour, pris)
                pris.add(ident)
                crees[r.sujet] = Sujet(ident, titres[r.sujet], jour, jour, 0)
            cible = crees[r.sujet].id
        liens[lot[r.video].video_id] = cible
    return list(crees.values()), liens


def mettre_a_jour(
    sujets: dict[str, Sujet], liens: dict[str, str | None], jours: dict[str, date]
) -> set[str]:
    """Reporte les nouveaux rattachements sur les sujets ; renvoie les sujets modifiés."""
    modifies: set[str] = set()
    for vid, sid in liens.items():
        if sid is None or sid not in sujets:
            continue
        s = sujets[sid]
        s.videos += 1
        s.premier_jour = min(s.premier_jour, jours[vid])
        s.dernier_jour = max(s.dernier_jour, jours[vid])
        modifies.add(sid)
    return modifies


# --- Fusion des doublons ---
# Deux sujets peuvent décrire le même événement (créés dans deux lots, ou après une pause de
# plus de 7 jours). À chaque run, chaque sujet nouvellement créé est comparé par Claude, sur le
# sens et non sur les mots, à tous les sujets actifs autour de ses dates ; s'il décrit le même
# événement qu'un d'eux, le plus petit des deux est fondu dans le plus gros.

FENETRE_DOUBLON_JOURS = 30
MAX_SUJETS_COMPARES = 400
AUCUN_DOUBLON = "aucun"


class ReponseDoublon(BaseModel):
    meme_evenement: str  # id d'un sujet de la liste, ou "aucun"


SYSTEME_DOUBLON = f"""You check duplicates among news stories ("sujets") detected in French
political YouTube videos. You receive one NEW story and a list of other stories of the same
period (id, neutral title, number of videos, first and last day).

If the NEW story is the SAME event as one story of the list (same announcement, same
controversy, same vote, same mobilisation, same news item, possibly worded very differently or
continued later), return its id in `meme_evenement`. Otherwise return "{AUCUN_DOUBLON}".

Different events that merely share a theme, a place or a person are NOT the same story (two
different statements by the same politician, two different strikes, two different votes).
When unsure, return "{AUCUN_DOUBLON}"."""


def comparables(nouveau: Sujet, sujets: Iterable[Sujet]) -> list[Sujet]:
    """Sujets actifs à moins de 30 jours des dates du nouveau (lui exclu), les plus gros
    d'abord, 400 au plus."""
    debut = nouveau.premier_jour - timedelta(days=FENETRE_DOUBLON_JOURS)
    fin = nouveau.dernier_jour + timedelta(days=FENETRE_DOUBLON_JOURS)
    liste = [
        s
        for s in sujets
        if s.id != nouveau.id and s.dernier_jour >= debut and s.premier_jour <= fin
    ]
    liste.sort(key=lambda s: (-s.videos, s.id))
    return liste[:MAX_SUJETS_COMPARES]


def _ligne_sujet_liste(s: Sujet) -> str:
    return (
        f"{s.id} | {_ligne(s.titre, MAX_TITRE_SUJET)} | {s.videos} videos | "
        f"{s.premier_jour.isoformat()} → {s.dernier_jour.isoformat()}"
    )


def message_doublon(nouveau: Sujet, liste: list[Sujet]) -> str:
    return "\n".join(
        ["NEW story:", _ligne_sujet_liste(nouveau), "", "Other stories:"]
        + [_ligne_sujet_liste(s) for s in liste]
    )


def cible_doublon(rep: ReponseDoublon, nouveau: Sujet, liste: list[Sujet]) -> str | None:
    """Identifiant du sujet identique, s'il est bien dans la liste ; None sinon."""
    cible = rep.meme_evenement.strip()
    ids = {s.id for s in liste}
    return cible if cible in ids and cible != nouveau.id else None
