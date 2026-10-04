"""« Pourquoi ça bouge » : résumés IA des sujets et des thèmes de la semaine.

Claude reçoit uniquement des chiffres agrégés et des métadonnées de vidéos (sous-sujet neutre,
chaîne, date, commentaires), numérotés [1], [2]… Il écrit 2 à 3 phrases neutres dont chaque
affirmation renvoie à un de ces numéros. Aucun texte de commentaire, aucun pseudo, aucune
citation. La sortie est validée : un renvoi inconnu ou un texte sans renvoi est rejeté.
"""

import hashlib
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel

TYPES_PUBLIC = ("media_traditionnel", "media_natif")
LIBELLES_TYPE = {"media_traditionnel": "médias traditionnels", "media_natif": "natifs du web"}
MIN_PRONONCES = 20
MAX_VIDEOS_CITEES = 4
MAX_CARACTERES = 900


def lundi(j: date) -> date:
    return j - timedelta(days=j.weekday())


@dataclass(frozen=True)
class VideoInfo:
    video_id: str
    jour: date  # publication (Paris)
    source_type: str
    chaine: str
    sous_sujet: str
    theme: str  # thème principal
    commentaires: float  # pondérés (plafond par vidéo)
    hostiles: float
    accord: float
    nuance: float
    desaccord: float


@dataclass
class StatsSujet:
    id: str
    titre: str
    videos: list[VideoInfo] = field(default_factory=lambda: list[VideoInfo]())
    precedent: float = 0.0

    @property
    def commentaires(self) -> float:
        return sum(v.commentaires for v in self.videos)


def stats_sujets(
    videos: Iterable[VideoInfo],
    sujet_de: Mapping[str, str],
    titres: Mapping[str, str],
    semaine: date,
) -> list[StatsSujet]:
    """Sujets de la semaine (vidéos publiées du lundi au dimanche, chaînes du public), au
    moins 3 vidéos de 2 chaînes, classés par commentaires, avec ceux de la semaine d'avant."""
    fin = semaine + timedelta(days=6)
    courant: dict[str, StatsSujet] = {}
    avant: defaultdict[str, float] = defaultdict(float)
    for v in videos:
        sid = sujet_de.get(v.video_id)
        if sid is None or v.source_type not in TYPES_PUBLIC:
            continue
        if semaine <= v.jour <= fin:
            courant.setdefault(sid, StatsSujet(sid, titres.get(sid, sid))).videos.append(v)
        elif semaine - timedelta(days=7) <= v.jour < semaine:
            avant[sid] += v.commentaires
    retenus = [
        s for s in courant.values() if len(s.videos) >= 3 and len({v.chaine for v in s.videos}) >= 2
    ]
    for s in retenus:
        s.precedent = avant.get(s.id, 0.0)
        s.videos.sort(key=lambda v: -v.commentaires)
    return sorted(retenus, key=lambda s: -s.commentaires)


@dataclass
class Element:
    """Une source numérotée donnée à Claude : un chiffre ou une vidéo."""

    texte: str
    video_id: str | None = None


def _pc(x: float, total: float) -> str:
    return f"{round(100 * x / total)} %" if total else "n.d."


def _positions(vs: list[VideoInfo]) -> tuple[float, float, float]:
    return (sum(v.accord for v in vs), sum(v.nuance for v in vs), sum(v.desaccord for v in vs))


def elements_sujet(s: StatsSujet) -> list[Element]:
    """Chiffres et vidéos d'un sujet, dans l'ordre où Claude les numérotera."""
    total = s.commentaires
    els = [
        Element(
            f"{round(total)} commentaires sous {len(s.videos)} vidéos de "
            f"{len({v.chaine for v in s.videos})} chaînes cette semaine"
            + (
                f", contre {round(s.precedent)} la semaine précédente"
                if s.precedent
                else ", sujet absent la semaine précédente"
            )
        )
    ]
    par_type = {t: [v for v in s.videos if v.source_type == t] for t in TYPES_PUBLIC}
    els.append(
        Element(
            "Répartition des commentaires : "
            + ", ".join(
                f"{_pc(sum(v.commentaires for v in vs), total)} sous les {LIBELLES_TYPE[t]}"
                for t, vs in par_type.items()
            )
        )
    )
    a, n, d = _positions(s.videos)
    if a + n + d >= MIN_PRONONCES:
        detail: list[str] = []
        for t, vs in par_type.items():
            ta, tn, td = _positions(vs)
            if ta + tn + td >= MIN_PRONONCES:
                detail.append(f"{_pc(td, ta + tn + td)} sous les {LIBELLES_TYPE[t]}")
        els.append(
            Element(
                f"Parmi les commentaires qui se prononcent sur la thèse des vidéos d'opinion : "
                f"{_pc(a, a + n + d)} d'accord, {_pc(d, a + n + d)} en désaccord"
                + (f" (désaccord : {', '.join(detail)})" if detail else "")
            )
        )
    els.append(Element(f"{_pc(sum(v.hostiles for v in s.videos), total)} de commentaires hostiles"))
    for v in s.videos[:MAX_VIDEOS_CITEES]:
        els.append(
            Element(
                f"Vidéo « {v.sous_sujet} » de {v.chaine}, publiée le {v.jour.strftime('%d/%m')}, "
                f"{round(v.commentaires)} commentaires",
                v.video_id,
            )
        )
    return els


@dataclass
class StatsTheme:
    theme: str
    libelle: str
    commentaires: float
    precedent: float
    part: float  # part des commentaires politiques de la semaine
    accord: float
    nuance: float
    desaccord: float
    hostiles: float
    sujets: list[StatsSujet]


def elements_theme(t: StatsTheme) -> list[Element]:
    els = [
        Element(
            f"{round(t.commentaires)} commentaires sur le thème « {t.libelle} » cette semaine, "
            f"{round(100 * t.part)} % des commentaires politiques"
            + (f", contre {round(t.precedent)} la semaine précédente" if t.precedent else "")
        )
    ]
    p = t.accord + t.nuance + t.desaccord
    if p >= MIN_PRONONCES:
        els.append(
            Element(
                f"Sous les vidéos d'opinion du thème : {_pc(t.accord, p)} d'accord et "
                f"{_pc(t.desaccord, p)} en désaccord avec la vidéo"
            )
        )
    els.append(Element(f"{_pc(t.hostiles, t.commentaires)} de commentaires hostiles"))
    for s in t.sujets[:3]:
        els.append(
            Element(
                f"Sujet « {s.titre} » : {round(s.commentaires)} commentaires sous "
                f"{len(s.videos)} vidéos",
                s.videos[0].video_id if s.videos else None,
            )
        )
    return els


SYSTEME_RESUME = """You write the "Pourquoi ça bouge" note of a French media-monitoring
dashboard that measures reactions of YouTube commenters (not the opinion of the French public).

You receive numbered facts [1], [2]... about one news story or one theme for one week: figures
and the main videos (neutral label, channel, date, number of comments). Write 2 or 3 short
sentences in French explaining what drives the reactions.

Rules:
- Use only the facts given. Every sentence ends with at least one reference like [2] to the
  facts it relies on. Never invent a number, a cause or a context that is not in the facts.
- Neutral and descriptive: no evaluative adjective, no judgement on the commenters, the videos
  or the people concerned, never attribute an opinion to a person or a party.
- Say "les commentaires" or "les commentateurs", never "les Français" or "l'opinion".
- No quotation marks around invented words, no comment text, no usernames.
- At most 600 characters."""


class ReponseResume(BaseModel):
    texte: str


def message_resume(sujet: str, elements: list[Element]) -> str:
    lignes = [sujet, "", "Facts:"]
    lignes += [f"[{i}] {e.texte}" for i, e in enumerate(elements, start=1)]
    return "\n".join(lignes)


_RENVOI = re.compile(r"\[(\d+)\]")


class ResumeInvalide(Exception):
    pass


def valider(texte: str, n_elements: int) -> tuple[str, list[int]]:
    """Texte nettoyé et numéros cités ; rejette un texte sans renvoi ou avec un renvoi inconnu."""
    propre = " ".join(texte.split())
    if not propre or len(propre) > MAX_CARACTERES:
        raise ResumeInvalide("texte vide ou trop long")
    cites = sorted({int(x) for x in _RENVOI.findall(propre)})
    if not cites:
        raise ResumeInvalide("aucun renvoi")
    if any(not 1 <= c <= n_elements for c in cites):
        raise ResumeInvalide(f"renvoi inconnu : {cites}")
    return propre, cites


def empreinte(elements: list[Element]) -> str:
    """Change quand les chiffres changent : le résumé est alors régénéré."""
    return hashlib.sha256("\n".join(e.texte for e in elements).encode()).hexdigest()[:16]


def ligne_resume(
    cle: str,
    type_: str,
    cible: str,
    semaine: date,
    texte: str,
    cites: list[int],
    elements: list[Element],
    modele: str,
    aujourdhui: date,
) -> dict[str, Any]:
    return {
        "id": cle,
        "categorie": type_,
        "cible": cible,
        "semaine": semaine.isoformat(),
        "texte": texte,
        "sources": [
            {"n": n, "texte": elements[n - 1].texte, "video_id": elements[n - 1].video_id}
            for n in cites
        ],
        "empreinte": empreinte(elements),
        "modele": modele,
        "cree_le": aujourdhui.isoformat(),
    }
