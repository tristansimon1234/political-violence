"""Classification des commentaires et des vidéos : prompts neutres, sorties typées.

Minimisation (RGPD) : un modèle ne reçoit que le texte du commentaire, mentions @ et URL
masquées, et le contexte de la vidéo (titre, chaîne, nature). Jamais l'auteur, même hashé,
ni l'identifiant du commentaire : les commentaires d'une requête sont numérotés 1..n.

La position (accord avec la vidéo) n'est demandée et conservée que pour les vidéos
`opinion_debat` ; elle vaut toujours None sur une vidéo `info_factuelle`.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

from pydantic import BaseModel

from radar.llm import Question, QuestionChoix, QuestionOuiNon, RepChoix, RepOuiNon
from radar.schemas import (
    EMOTIONS,
    MAX_THEMES_COMMENTAIRE,
    POSITIONS,
    THEMES,
    Emotion,
    NatureVideo,
    Position,
    Theme,
)

_MENTION = re.compile(r"(?<![\w.])@[\w.\-]+")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
MAX_CARACTERES_COMMENTAIRE = 2000
MAX_CARACTERES_DESCRIPTION = 1500

# Définitions publiées avec la méthodologie (neutres, sans jugement sur le fond).
DEFINITIONS_THEMES: dict[Theme, str] = {
    "pouvoir_achat": "prix, salaires, inflation, carburant, factures, fiscalité des ménages",
    "securite": "délinquance, police, justice pénale, terrorisme",
    "immigration": "immigration, asile, intégration, nationalité",
    "retraites": "système de retraite, âge de départ, pensions",
    "sante": "hôpital, médecins, assurance maladie, politique de santé",
    "education": "école, enseignants, université, jeunesse",
    "ecologie_energie": "climat, environnement, énergie, nucléaire, transports",
    "economie_emploi": "croissance, entreprises, emploi, chômage, dette et budget publics",
    "logement": "logement, loyers, construction, accès à la propriété",
    "institutions": "élections, candidats, partis, gouvernement, Parlement, Constitution",
    "international_defense": "politique étrangère, Union européenne, conflits, armée",
    "agriculture": "agriculteurs, alimentation, politique agricole",
    "societe": "laïcité, religion, famille, mœurs, discriminations, médias",
    "autre": "sujet politique ou d'intérêt public qui n'entre dans aucun thème ci-dessus",
}

DEFINITIONS_POSITIONS: dict[Position, str] = {
    "accord_video": "le commentaire approuve le propos tenu dans la vidéo",
    "nuance": "le commentaire approuve en partie, avec des réserves",
    "desaccord_video": "le commentaire conteste le propos tenu dans la vidéo",
    "hors_sujet": "le commentaire ne se prononce pas sur le propos de la vidéo",
}

DEFINITIONS_EMOTIONS: dict[Emotion, str] = {
    "colere": "colère, indignation",
    "moquerie": "ironie, sarcasme, dérision",
    "inquietude": "peur, inquiétude",
    "enthousiasme": "soutien, joie, admiration",
    "lassitude": "résignation, fatigue, désintérêt",
    "neutre": "aucune émotion marquée",
}


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


# --- Sorties typées ---


class ClassementCommentaire(BaseModel):
    numero: int
    est_politique: bool
    themes: list[Theme]
    position: Position | None
    emotion: Emotion


class ReponseCommentaires(BaseModel):
    commentaires: list[ClassementCommentaire]


class ReponseNatureVideo(BaseModel):
    nature_video: NatureVideo


@dataclass(frozen=True)
class Classement:
    """Classement normalisé d'un commentaire (après contrôle des règles)."""

    est_politique: bool
    themes: tuple[Theme, ...]  # le premier est le thème principal ; vide si non politique
    position: Position | None
    emotion: Emotion
    confiance: float | None = None  # fournie par Jev ; None pour Claude


def normaliser(c: ClassementCommentaire, nature: NatureVideo) -> Classement:
    themes: list[Theme] = []
    for t in c.themes:
        if t not in themes:
            themes.append(t)
    return Classement(
        est_politique=c.est_politique,
        themes=tuple(themes[:MAX_THEMES_COMMENTAIRE]) if c.est_politique else (),
        position=c.position if nature == "opinion_debat" else None,
        emotion=c.emotion,
    )


# --- Prompts ---


def _liste(definitions: Iterable[tuple[str, str]]) -> str:
    return "\n".join(f"- {cle} : {d}" for cle, d in definitions)


SYSTEME_COMMENTAIRES = f"""Tu classes des commentaires YouTube publiés sous des vidéos françaises.
Tu décris ce que dit chaque commentaire, sans jamais juger s'il a raison ou tort, et sans
tenir compte de l'orientation politique de la vidéo, de la chaîne ou du commentaire.

Pour chaque commentaire numéroté :
- est_politique : vrai si le commentaire parle de politique ou d'un enjeu d'intérêt public
  (politiques publiques, élections, institutions, personnalités politiques, débat de société).
  Faux pour une réaction sur la forme de la vidéo, un message personnel, une salutation, une
  publicité.
- themes : de 1 à {MAX_THEMES_COMMENTAIRE} thèmes du commentaire lui-même (pas ceux de la
  vidéo), du plus au moins important ; liste vide si est_politique est faux.
{_liste(DEFINITIONS_THEMES.items())}
- position : accord avec le propos de la vidéo, pas opinion sur le sujet.
{_liste(DEFINITIONS_POSITIONS.items())}
  Uniquement si la vidéo est de nature « opinion_debat » ; null sinon.
- emotion : l'émotion dominante exprimée.
{_liste(DEFINITIONS_EMOTIONS.items())}

Les mentions et les liens ont été masqués. Réponds pour chaque numéro, dans l'ordre."""

assert set(DEFINITIONS_THEMES) == set(THEMES)
assert set(DEFINITIONS_POSITIONS) == set(POSITIONS)
assert set(DEFINITIONS_EMOTIONS) == set(EMOTIONS)


def message_commentaires(contexte: ContexteVideo, textes: list[str]) -> str:
    """Message utilisateur : contexte vidéo + commentaires masqués, numérotés 1..n."""
    lignes = [
        f"Chaîne : {contexte.chaine}",
        f"Titre de la vidéo : {contexte.titre}",
        f"Nature de la vidéo : {contexte.nature}",
        "",
        "Commentaires :",
    ]
    for i, t in enumerate(textes, start=1):
        lignes.append(f"[{i}] {masquer(t)}")
    return "\n".join(lignes)


SYSTEME_NATURE_VIDEO = """Tu indiques la nature d'une vidéo YouTube française à partir de son titre,
de sa description et de sa chaîne, sans jugement sur le fond.
- info_factuelle : la vidéo rapporte des faits (journal, reportage, extrait de discours ou de
  séance sans commentaire, annonce).
- opinion_debat : la vidéo défend un point de vue, commente ou fait débattre (éditorial, débat,
  plateau, interview, chronique, analyse engagée)."""


def message_nature_video(titre: str, description: str, chaine: str) -> str:
    return "\n".join(
        [
            f"Chaîne : {chaine}",
            f"Titre : {titre}",
            f"Description : {masquer(description)[:MAX_CARACTERES_DESCRIPTION]}",
        ]
    )


# --- Jev : questions fermées, un appel par commentaire ---

SEUIL_THEME_SECONDAIRE = 0.3  # probabilité minimale d'un thème secondaire (Jev)

_INSTRUCTIONS_POLITIQUE = (
    "Le commentaire parle-t-il de politique ou d'un enjeu d'intérêt public (politiques "
    "publiques, élections, institutions, personnalités politiques, débat de société) ? "
    "Non pour une réaction sur la forme de la vidéo, un message personnel, une salutation "
    "ou une publicité."
)


def _criteres(definitions: Iterable[tuple[str, str]]) -> dict[str, str]:
    return dict(definitions)


def questions_jev(nature: NatureVideo) -> dict[str, Question]:
    questions: dict[str, Question] = {
        "politique": QuestionOuiNon(_INSTRUCTIONS_POLITIQUE),
        "theme": QuestionChoix(
            "Quel est le thème principal du commentaire lui-même (pas celui de la vidéo) ?",
            _criteres(DEFINITIONS_THEMES.items()),
        ),
        "emotion": QuestionChoix(
            "Quelle est l'émotion dominante exprimée par le commentaire ?",
            _criteres(DEFINITIONS_EMOTIONS.items()),
        ),
    }
    if nature == "opinion_debat":
        questions["position"] = QuestionChoix(
            "Le commentaire est-il d'accord avec le propos tenu dans la vidéo ? "
            "Il s'agit de l'accord avec la vidéo, pas de l'opinion sur le sujet.",
            _criteres(DEFINITIONS_POSITIONS.items()),
        )
    return questions


def etat_jev(contexte: ContexteVideo, texte: str) -> str:
    """État évalué par Jev : contexte vidéo + commentaire masqué."""
    return "\n".join(
        [
            f"Chaîne : {contexte.chaine}",
            f"Titre de la vidéo : {contexte.titre}",
            f"Nature de la vidéo : {contexte.nature}",
            f"Commentaire : {masquer(texte)}",
        ]
    )


def classement_jev(reponses: dict[str, RepOuiNon | RepChoix], nature: NatureVideo) -> Classement:
    """Convertit les réponses de Jev ; confiance = la plus faible des questions utiles."""
    politique, theme, emotion = reponses["politique"], reponses["theme"], reponses["emotion"]
    assert isinstance(politique, RepOuiNon)
    assert isinstance(theme, RepChoix) and isinstance(emotion, RepChoix)
    est_politique = politique.probabilite_oui >= 0.5
    confiances = [politique.confiance, emotion.confiance]
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
    if nature == "opinion_debat":
        rep = reponses["position"]
        assert isinstance(rep, RepChoix)
        position = en_position(rep.choix)
        confiances.append(rep.confiance)
    return Classement(
        est_politique=est_politique,
        themes=themes,
        position=position,
        emotion=en_emotion(emotion.choix),
        confiance=min(confiances),
    )


def en_theme(v: str) -> Theme:
    for t in THEMES:
        if t == v:
            return t
    raise ValueError(v)


def en_position(v: str) -> Position:
    for p in POSITIONS:
        if p == v:
            return p
    raise ValueError(v)


def en_emotion(v: str) -> Emotion:
    for e in EMOTIONS:
        if e == v:
            return e
    raise ValueError(v)
