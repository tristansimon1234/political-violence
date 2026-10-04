"""Sujets d'actualité (étape 6) : regroupement des vidéos politiques par événement.

Chaque jour, Claude rattache les vidéos politiques publiées ce jour-là à un sujet encore actif,
à un nouveau sujet, ou à aucun. Une vidéo appartient à 0 ou 1 sujet. Le titre d'un sujet est
une donnée dérivée, neutre, écrite par le modèle (pas un titre de vidéo) : conservé toute la
campagne. Un sujet n'est affiché qu'à partir de 3 vidéos de 2 chaînes (docs/donnees.md).
"""

import re
import unicodedata
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
# plus de 7 jours). À chaque run, le code repère les sujets aux titres proches et voisins dans
# le temps ; Claude tranche groupe par groupe ; les vidéos des doublons passent au sujet gardé.

FENETRE_FUSION_JOURS = 45
SEUIL_TITRES = 0.4  # part de mots communs (Jaccard) pour soupçonner un doublon
ECART_MAX_JOURS = 30  # deux sujets plus éloignés dans le temps ne sont pas comparés
MAX_GROUPE = 15

_MOTS_VIDES = frozenset(
    {
        "a",
        "au",
        "aux",
        "avec",
        "ce",
        "ces",
        "contre",
        "d",
        "dans",
        "de",
        "des",
        "du",
        "en",
        "entre",
        "et",
        "l",
        "la",
        "le",
        "les",
        "leur",
        "lors",
        "pour",
        "par",
        "sa",
        "se",
        "son",
        "sur",
        "un",
        "une",
        "apres",
        "avant",
        "face",
        "fin",
    }
)


_MOIS = frozenset(
    [
        "janvier",
        "fevrier",
        "mars",
        "avril",
        "mai",
        "juin",
        "juillet",
        "aout",
        "septembre",
        "octobre",
        "novembre",
        "decembre",
    ]
)
LETTRES_JETON = 5


def jetons(titre: str) -> frozenset[str]:
    """Mots significatifs d'un titre : minuscules, sans accents, sans mots vides ni dates
    (mois, nombres), réduits à 5 lettres (« antisémitisme » et « antisémites », « lycées » et
    « lycéens » se rejoignent)."""
    sans_accents = "".join(
        c for c in unicodedata.normalize("NFD", titre.lower()) if not unicodedata.combining(c)
    )
    mots = re.findall(r"[a-z0-9]+", sans_accents)
    return frozenset(
        m[:LETTRES_JETON]
        for m in mots
        if m not in _MOTS_VIDES and m not in _MOIS and not m.isdigit() and len(m) > 1
    )


def _proches(a: Sujet, b: Sujet) -> bool:
    ecart = max(a.premier_jour, b.premier_jour) - min(a.dernier_jour, b.dernier_jour)
    if ecart.days > ECART_MAX_JOURS:
        return False
    ja, jb = jetons(a.titre), jetons(b.titre)
    return bool(ja and jb) and len(ja & jb) / len(ja | jb) >= SEUIL_TITRES


def groupes_candidats(sujets: list[Sujet]) -> list[list[Sujet]]:
    """Groupes de sujets aux titres proches et voisins dans le temps (composantes connexes),
    à soumettre à Claude. Seuls les sujets d'au moins 2 vidéos actifs dans les 45 derniers
    jours de données sont comparés ; un groupe trop grand est coupé (les plus gros d'abord)."""
    if not sujets:
        return []
    fin = max(s.dernier_jour for s in sujets)
    retenus = [
        s
        for s in sujets
        if s.videos >= 2 and s.dernier_jour >= fin - timedelta(days=FENETRE_FUSION_JOURS)
    ]
    parent = {s.id: s.id for s in retenus}

    def racine(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, a in enumerate(retenus):
        for b in retenus[i + 1 :]:
            if _proches(a, b):
                parent[racine(a.id)] = racine(b.id)
    groupes: dict[str, list[Sujet]] = {}
    for s in retenus:
        groupes.setdefault(racine(s.id), []).append(s)
    resultat: list[list[Sujet]] = []
    for g in groupes.values():
        if len(g) < 2:
            continue
        g.sort(key=lambda s: (-s.videos, s.id))
        resultat.append(g[:MAX_GROUPE])
    return sorted(resultat, key=lambda g: g[0].id)


class Fusion(BaseModel):
    garder: str
    doublons: list[str]


class ReponseFusions(BaseModel):
    fusions: list[Fusion]


SYSTEME_FUSIONS = """You receive a few news stories ("sujets") detected in French political
YouTube videos, with similar titles: id, neutral title, number of videos, first and last day.

Find the stories that are the SAME event described twice (same announcement, same
controversy, same vote, same news item, possibly worded differently or continued later).
For each group, return `garder` (the id to keep: the one with the most videos) and `doublons`
(the other ids of that same event).

Do not merge different events that merely share a theme, a place or a person (two different
statements by the same politician, two different strikes, two different votes are different
stories). When unsure, do not merge. Return an empty list if there is no duplicate."""


def message_fusions(sujets: list[Sujet]) -> str:
    return "\n".join(
        f"{s.id} | {_ligne(s.titre, MAX_TITRE_SUJET)} | {s.videos} videos | "
        f"{s.premier_jour.isoformat()} → {s.dernier_jour.isoformat()}"
        for s in sujets
    )


def valider_fusions(rep: ReponseFusions, connus: set[str]) -> dict[str, str]:
    """Doublon → sujet gardé. Identifiants inconnus ignorés ; un sujet gardé n'est jamais
    absorbé ensuite, un doublon ne l'est qu'une fois (pas de chaîne de fusions)."""
    cible: dict[str, str] = {}
    gardes: set[str] = set()
    for f in rep.fusions:
        if f.garder not in connus or f.garder in cible:
            continue
        for d in f.doublons:
            if d in connus and d != f.garder and d not in cible and d not in gardes:
                cible[d] = f.garder
        gardes.add(f.garder)
    return cible
