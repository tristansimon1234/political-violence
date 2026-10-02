"""Taxonomie du Radar : source de vérité unique.

Toute modification d'une liste fermée incrémente VERSION_TAXONOMIE.
"""

from typing import Final, Literal, get_args

VERSION_TAXONOMIE: Final = 6

# --- Sources du panel (docs/decisions.md, 01/10/2026) ---

TypeSource = Literal["media_traditionnel", "media_natif", "politique"]

SousTypeMediaTraditionnel = Literal["info_continu", "tv_radio", "talk_show", "presse_nationale"]
SousTypeMediaNatif = Literal["pure_player", "createur"]
SousTypePolitique = Literal["parti", "personnalite"]
SousType = SousTypeMediaTraditionnel | SousTypeMediaNatif | SousTypePolitique

TYPES_SOURCE: Final[tuple[TypeSource, ...]] = get_args(TypeSource)

SOUS_TYPES_PAR_TYPE: Final[dict[TypeSource, tuple[SousType, ...]]] = {
    "media_traditionnel": get_args(SousTypeMediaTraditionnel),
    "media_natif": get_args(SousTypeMediaNatif),
    "politique": get_args(SousTypePolitique),
}

# Libellés d'interface.
LIBELLES_TYPE: Final[dict[TypeSource, str]] = {
    "media_traditionnel": "Médias traditionnels",
    "media_natif": "Médias natifs du web",
    "politique": "Politiques",
}

# Critère commun d'activité : au moins 10 vidéos sur 90 jours, Shorts compris.
SEUIL_ACTIVITE_VIDEOS: Final = 10
FENETRE_ACTIVITE_JOURS: Final = 90

# --- Vidéos ---

FormatVideo = Literal["short", "long"]
FORMATS_VIDEO: Final[tuple[FormatVideo, ...]] = get_args(FormatVideo)


# --- Classification (docs/donnees.md) ---

Theme = Literal[
    "pouvoir_achat",
    "securite",
    "immigration",
    "retraites",
    "sante",
    "education",
    "ecologie_energie",
    "economie_emploi",
    "logement",
    "institutions",
    "international_defense",
    "agriculture",
    "societe",
    "autre",
]
THEMES: Final[tuple[Theme, ...]] = get_args(Theme)

# v6 (01/10/2026) : « opinion_debat » scindé en `opinion` (une thèse) et `debat` (plusieurs voix).
NatureVideo = Literal["info_factuelle", "opinion", "debat"]
NATURES_VIDEO: Final[tuple[NatureVideo, ...]] = get_args(NatureVideo)


def position_applicable(nature: NatureVideo) -> bool:
    """Position seulement sous une vidéo qui défend une thèse (jamais factuelle ni débat)."""
    return nature == "opinion"


# Accord avec le propos de la vidéo, pas opinion sur le sujet.
Position = Literal["accord_video", "nuance", "desaccord_video", "hors_sujet"]
POSITIONS: Final[tuple[Position, ...]] = get_args(Position)

# v5 (01/10/2026) : les six émotions sont remplacées par la tonalité et l'hostilité (booléen).
# Émotions fines : hors périmètre v1.
Tonalite = Literal["positive", "neutre", "negative"]
TONALITES: Final[tuple[Tonalite, ...]] = get_args(Tonalite)

MAX_THEMES_COMMENTAIRE: Final = 3


def sous_type_valide(type_source: TypeSource, sous_type: str) -> bool:
    return sous_type in SOUS_TYPES_PAR_TYPE[type_source]
