"""Classification des commentaires et des vidéos : prompts neutres, sorties typées.

Minimisation (RGPD) : un modèle ne reçoit que le texte du commentaire, mentions @ et URL
masquées, et le contexte de la vidéo (titre, chaîne, nature, résumé). Jamais l'auteur, même hashé,
ni l'identifiant du commentaire : les commentaires d'une requête sont numérotés 1..n.

La position (accord avec la vidéo) n'est demandée et conservée que pour les vidéos `opinion` ;
elle vaut toujours None sur une vidéo `info_factuelle` ou `debat`.

Résumé de la vidéo (décision du 02/10/2026) : une phrase neutre écrite par Claude à partir du
titre et de la description, dans le même appel que la nature. Dérivé du brut, il est conservé
et purgé avec lui (30 jours).
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from radar.llm import Question, QuestionChoix, QuestionOuiNon, RepChoix, RepOuiNon
from radar.schemas import (
    MAX_THEMES_COMMENTAIRE,
    NATURES_VIDEO,
    POSITIONS,
    THEMES,
    TONALITES,
    NatureVideo,
    Position,
    Theme,
    Tonalite,
    position_applicable,
)

_MENTION = re.compile(r"(?<![\w.])@[\w.\-]+")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
MAX_CARACTERES_COMMENTAIRE = 2000
MAX_CARACTERES_DESCRIPTION = 1500

# Définitions envoyées aux modèles, en anglais (consignes mieux suivies) ; traduction française
# publiée dans docs/etiquetage.md et la méthodologie. Neutres, sans jugement sur le fond.
DEFINITIONS_THEMES: dict[Theme, str] = {
    "pouvoir_achat": "Purchasing power: prices, inflation, wages versus cost of living, fuel "
    "and energy bills, household taxes.",
    "securite": "Public safety: crime, violence, police, criminal justice and sentencing, "
    "terrorism.",
    "immigration": "Immigration: migration flows, asylum, removal orders, integration, "
    "nationality, regularisation of undocumented workers.",
    "retraites": "Pensions: retirement age, pension system and its reforms, pension amounts.",
    "sante": "Health: hospitals and emergency services, doctors and medical deserts, health "
    "insurance, care workers, health policy.",
    "education": "Education: schools, teachers and their pay, curricula, exams, universities, "
    "young people in education.",
    "ecologie_energie": "Environment and energy: climate change, heatwaves, pollution, energy "
    "sources (nuclear, renewables), transport policy.",
    "economie_emploi": "Economy and jobs: growth, companies, employment and unemployment, "
    "labour shortages, working conditions, public debt and budget.",
    "logement": "Housing: rents, property prices, access to home ownership, construction.",
    "institutions": "Political life and institutions: elections, candidates, parties and their "
    "programmes, government, Parliament, how laws are passed, Constitution, democracy.",
    "international_defense": "International affairs and defence: foreign policy, European "
    "Union, wars and conflicts, armed forces, international trade rules.",
    "agriculture": "Agriculture: farmers, their protests and incomes, food production, "
    "agricultural standards and subsidies.",
    "societe": "Society: secularism (laïcité), religion, family, customs, discrimination, "
    "social cohesion.",
    "autre": "Another political or public-interest topic that fits none of the themes above.",
}

DEFINITIONS_POSITIONS: dict[Position, str] = {
    "accord_video": "Agreement: the comment approves the thesis defended in the video.",
    "nuance": "Partial agreement: 'yes, but', agreement with reservations, or a point the video "
    "did not consider without rejecting its thesis.",
    "desaccord_video": "Disagreement: the comment rejects the thesis defended in the video.",
    "hors_sujet": "No stance on the thesis: practical question, unrelated remark, or a comment "
    "only about the form of the video (praise or criticism of its quality, sound, graphics, "
    "guests or balance).",
}

DEFINITIONS_TONALITES: dict[Tonalite, str] = {
    "positive": "Positive: support, praise, gratitude, joy, enthusiasm, hope.",
    "neutre": "Neutral: calm statement of facts or opinion, simple question, no marked "
    "feeling. An opinion stated calmly is neutral, even a disagreement.",
    "negative": "Negative: anger, indignation, worry, weariness, disappointment, sadness, mockery.",
}

HOSTILITE_OUI = (
    "Insult, slur, personal attack, contempt or dehumanisation aimed at a person or a group, "
    "threat, call to violence, or anger expressed aggressively against someone. Also hostile: "
    "accusing a person, a media outlet or an institution of lying, manipulating or rigging; "
    "denigrating a group through a generalisation; contemptuous mockery of a person, a group "
    "or the authorities."
)
HOSTILITE_NON = (
    "Disagreement, even firm; criticism of a policy, a measure, a rule or a decision; a "
    "grievance or indignation without attacking anyone ('it's a scandal'); light irony about "
    "a situation."
)

# Règles de lecture, communes à Jev et Claude (tirées de l'étiquetage de Tristan, 01/10/2026).
REGLE_POLITIQUE = (
    "A comment is political when it addresses politics or a public-interest issue: public "
    "policy, elections, institutions, politicians, social debates, or a reaction to the "
    "public-interest event shown in the video, even if the comment does not name the topic. "
    "It is not political when it is only about the video or the media itself (praise, sound, "
    "graphics, music, casting, balance of a panel, choice of topics covered), personal "
    "chatter, greetings, sport, consumer products or advertising."
)
REGLE_THEMES = (
    "Themes describe the comment itself, not the video. When the comment reacts to the "
    "video's event without naming a topic, use the theme of that event."
)
REGLE_POSITION = (
    "Position is agreement with the thesis defended in the video, never the commenter's "
    "opinion on the topic, and never a judgement on the form of the video. It is only asked "
    "for opinion videos, which defend a single thesis."
)


def masquer(texte: str) -> str:
    """Masque les mentions @ et les URL, tronque les textes très longs."""
    texte = _URL.sub("[lien]", texte)
    texte = _MENTION.sub("@[mention]", texte)
    return texte[:MAX_CARACTERES_COMMENTAIRE]


@dataclass(frozen=True)
class ContexteVideo:
    titre: str
    chaine: str
    nature: NatureVideo
    resume: str = ""  # sujet et thèse de la vidéo ; vide si non calculé


# --- Sorties typées ---


class ClassementCommentaire(BaseModel):
    numero: int
    est_politique: bool
    themes: list[Theme]
    position: Position | None
    tonalite: Tonalite
    hostilite: bool


class ReponseCommentaires(BaseModel):
    commentaires: list[ClassementCommentaire]


class ReponseNatureVideo(BaseModel):
    nature_video: NatureVideo
    resume: str  # obligatoire : un champ facultatif peut être omis par le modèle


@dataclass(frozen=True)
class Classement:
    """Classement normalisé d'un commentaire (après contrôle des règles)."""

    est_politique: bool
    themes: tuple[Theme, ...]  # le premier est le thème principal ; vide si non politique
    position: Position | None
    tonalite: Tonalite
    hostilite: bool
    confiance: float | None = None  # fournie par Jev ; None pour Claude


def normaliser(c: ClassementCommentaire, nature: NatureVideo) -> Classement:
    themes: list[Theme] = []
    for t in c.themes:
        if t not in themes:
            themes.append(t)
    return Classement(
        est_politique=c.est_politique,
        themes=tuple(themes[:MAX_THEMES_COMMENTAIRE]) if c.est_politique else (),
        position=(c.position or "hors_sujet") if position_applicable(nature) else None,
        tonalite=c.tonalite,
        hostilite=c.hostilite,
    )


# --- Prompts ---


def _liste(definitions: Iterable[tuple[str, str]]) -> str:
    return "\n".join(f"  - {cle}: {d}" for cle, d in definitions)


SYSTEME_COMMENTAIRES = f"""You classify YouTube comments posted under French videos. The
comments are in French. Describe what each comment says: never judge whether it is right or
wrong, and ignore the political leaning of the video, the channel or the comment.

For each numbered comment:
- est_politique: true or false. {REGLE_POLITIQUE}
- themes: 1 to {MAX_THEMES_COMMENTAIRE} themes, most important first; empty list when
  est_politique is false. {REGLE_THEMES}
{_liste(DEFINITIONS_THEMES.items())}
- position: required when the video type is opinion, null when it is info_factuelle or
  debat. {REGLE_POSITION}
{_liste(DEFINITIONS_POSITIONS.items())}
- tonalite: the overall tone of the comment.
{_liste(DEFINITIONS_TONALITES.items())}
- hostilite: true when the comment is hostile. Hostile: {HOSTILITE_OUI} Not hostile:
  {HOSTILITE_NON}

Mentions and links have been masked. Answer for every number, in order."""

assert set(DEFINITIONS_THEMES) == set(THEMES)
assert set(DEFINITIONS_POSITIONS) == set(POSITIONS)
assert set(DEFINITIONS_TONALITES) == set(TONALITES)


def message_commentaires(contexte: ContexteVideo, textes: list[str]) -> str:
    """Message utilisateur : contexte vidéo + commentaires masqués, numérotés 1..n."""
    lignes = [
        f"Channel: {contexte.chaine}",
        f"Video title: {contexte.titre}",
        f"Video type: {contexte.nature}",
        *([f"Video summary: {contexte.resume}"] if contexte.resume else []),
        "",
        "Comments:",
    ]
    for i, t in enumerate(textes, start=1):
        lignes.append(f"[{i}] {masquer(t)}")
    return "\n".join(lignes)


SYSTEME_NATURE_VIDEO = """You describe a French YouTube video from its title, description and
channel, without judging its content.

nature_video, the type of the video:
- info_factuelle: the video reports facts (news bulletin, report, unedited excerpt of a speech
  or session, announcement).
- opinion: the video defends one point of view (editorial, column, rant, opinionated
  analysis, video of a party or a candidate, interview of a single guest presenting views).
- debat: the video confronts several points of view (debate show, panel with opposing guests,
  face-to-face).

resume: one neutral sentence in French, at most 35 words, giving the subject of the video and:
for an opinion video, the thesis it defends ("La vidéo soutient que ...");
for a debate, the question debated ("Débat sur ...");
for a factual video, the fact reported.
Use only the title and the description; never add facts, never judge. Ignore links, sponsors
and calls to subscribe. When the title and description are too vague, start with
"Sujet peu précis :" and say what can be inferred."""


def message_nature_video(titre: str, description: str, chaine: str) -> str:
    return "\n".join(
        [
            f"Channel: {chaine}",
            f"Title: {titre}",
            f"Description: {masquer(description)[:MAX_CARACTERES_DESCRIPTION]}",
        ]
    )


# --- Jev : questions fermées, un appel par commentaire ---

SEUIL_THEME_SECONDAIRE = 0.3  # probabilité minimale d'un thème secondaire (Jev)

_INSTRUCTIONS_POLITIQUE = (
    "Is the French YouTube comment `comment` about politics or a public-interest issue? "
    + REGLE_POLITIQUE
)
_POLITIQUE_OUI = (
    "Public policy, elections, institutions, politicians, social debates, or a reaction to "
    "the public-interest event shown in `video`."
)
_POLITIQUE_NON = (
    "Only about the video itself, personal chatter, greetings, sport, consumer products or "
    "advertising."
)


def _criteres(definitions: Iterable[tuple[str, str]]) -> dict[str, str]:
    return dict(definitions)


def questions_jev(nature: NatureVideo) -> dict[str, Question]:
    questions: dict[str, Question] = {
        "politique": QuestionOuiNon(_INSTRUCTIONS_POLITIQUE, _POLITIQUE_OUI, _POLITIQUE_NON),
        "theme": QuestionChoix(
            "What is the main theme of the French YouTube comment `comment`? " + REGLE_THEMES,
            _criteres(DEFINITIONS_THEMES.items()),
        ),
        "tonalite": QuestionChoix(
            "What is the overall tone of the French YouTube comment `comment`?",
            _criteres(DEFINITIONS_TONALITES.items()),
        ),
        "hostilite": QuestionOuiNon(
            "Is the French YouTube comment `comment` hostile?", HOSTILITE_OUI, HOSTILITE_NON
        ),
    }
    if position_applicable(nature):
        questions["position"] = QuestionChoix(
            "What is the stance of the French YouTube comment `comment` towards the video "
            "`video`? " + REGLE_POSITION,
            _criteres(DEFINITIONS_POSITIONS.items()),
        )
    return questions


def etat_jev(contexte: ContexteVideo, texte: str) -> dict[str, Any]:
    """État évalué par Jev : objet JSON à champs nommés (contexte vidéo + commentaire masqué)."""
    return {
        "video": {
            "channel": contexte.chaine,
            "title": contexte.titre,
            "type": contexte.nature,
            **({"summary": contexte.resume} if contexte.resume else {}),
        },
        "comment": masquer(texte),
    }


def classement_jev(reponses: dict[str, RepOuiNon | RepChoix], nature: NatureVideo) -> Classement:
    """Convertit les réponses de Jev ; confiance = la plus faible des questions utiles."""
    politique, theme = reponses["politique"], reponses["theme"]
    tonalite, hostilite = reponses["tonalite"], reponses["hostilite"]
    assert isinstance(politique, RepOuiNon) and isinstance(hostilite, RepOuiNon)
    assert isinstance(theme, RepChoix) and isinstance(tonalite, RepChoix)
    est_politique = politique.probabilite_oui >= 0.5
    confiances = [politique.confiance, tonalite.confiance, hostilite.confiance]
    themes: tuple[Theme, ...] = ()
    if est_politique:
        confiances.append(theme.confiance)
        secondaires = sorted(
            (
                (p, t)
                for t, p in theme.probabilites.items()
                if t != theme.choix and p >= SEUIL_THEME_SECONDAIRE
            ),
            reverse=True,
        )
        noms = [theme.choix, *(t for _, t in secondaires)][:MAX_THEMES_COMMENTAIRE]
        themes = tuple(t for t in THEMES if t in noms)
        themes = (en_theme(theme.choix), *(t for t in themes if t != theme.choix))
    position: Position | None = None
    if position_applicable(nature):
        rep = reponses["position"]
        assert isinstance(rep, RepChoix)
        position = en_position(rep.choix)
        confiances.append(rep.confiance)
    return Classement(
        est_politique=est_politique,
        themes=themes,
        position=position,
        tonalite=en_tonalite(tonalite.choix),
        hostilite=hostilite.probabilite_oui >= 0.5,
        confiance=min(confiances),
    )


def en_theme(v: str) -> Theme:
    for t in THEMES:
        if t == v:
            return t
    raise ValueError(v)


def en_nature(v: str) -> NatureVideo:
    for n in NATURES_VIDEO:
        if n == v:
            return n
    raise ValueError(f"nature de vidéo inconnue : {v}")


def en_position(v: str) -> Position:
    for p in POSITIONS:
        if p == v:
            return p
    raise ValueError(v)


def en_tonalite(v: str) -> Tonalite:
    for t in TONALITES:
        if t == v:
            return t
    raise ValueError(v)
