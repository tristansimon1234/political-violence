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

# Libellés d'interface (les définitions complètes sont dans radar/classification.py).
LIBELLES_THEMES: Final[dict[Theme, str]] = {
    "pouvoir_achat": "Pouvoir d'achat",
    "securite": "Sécurité",
    "immigration": "Immigration",
    "retraites": "Retraites",
    "sante": "Santé",
    "education": "Éducation",
    "ecologie_energie": "Écologie et énergie",
    "economie_emploi": "Économie et emploi",
    "logement": "Logement",
    "institutions": "Vie politique et institutions",
    "international_defense": "International et défense",
    "agriculture": "Agriculture",
    "societe": "Société",
    "autre": "Autre",
}
# Définitions affichées dans l'interface et la méthodologie : traduction fidèle de celles
# données aux modèles (radar/classification.py, en anglais). Modifier les deux ensemble.
DEFINITIONS_THEMES_FR: Final[dict[Theme, str]] = {
    "pouvoir_achat": "Prix, inflation, salaires face au coût de la vie, carburant et factures "
    "d'énergie, impôts des ménages.",
    "securite": "Délinquance, violences, police, justice pénale et peines, terrorisme.",
    "immigration": "Flux migratoires, asile, obligations de quitter le territoire, intégration, "
    "nationalité, régularisation des travailleurs sans papiers.",
    "retraites": "Âge de départ, système de retraite et ses réformes, montant des pensions.",
    "sante": "Hôpital et urgences, médecins et déserts médicaux, assurance maladie, soignants, "
    "politique de santé.",
    "education": "École, enseignants et leur rémunération, programmes, examens, université, "
    "jeunes en formation.",
    "ecologie_energie": "Changement climatique, canicules, pollution, sources d'énergie "
    "(nucléaire, renouvelables), politique des transports.",
    "economie_emploi": "Croissance, entreprises, emploi et chômage, pénuries de main-d'œuvre, "
    "conditions de travail, dette publique et budget.",
    "logement": "Loyers, prix de l'immobilier, accès à la propriété, construction.",
    "institutions": "Élections, candidats, partis et leurs programmes, gouvernement, Parlement, "
    "fabrication des lois, Constitution, démocratie.",
    "international_defense": "Politique étrangère, Union européenne, guerres et conflits, "
    "armées, règles du commerce international.",
    "agriculture": "Agriculteurs, leurs mobilisations et leurs revenus, production alimentaire, "
    "normes et aides agricoles.",
    "societe": "Laïcité, religion, famille, mœurs, discriminations, cohésion sociale.",
    "autre": "Autre sujet politique ou d'intérêt public qui n'entre dans aucun des thèmes "
    "ci-dessus.",
}
LIBELLES_POSITIONS: Final[dict[Position, str]] = {
    "accord_video": "Accord avec la vidéo",
    "nuance": "Nuance",
    "desaccord_video": "Désaccord avec la vidéo",
    "hors_sujet": "Ne se prononce pas",
}
LIBELLES_TONALITES: Final[dict[Tonalite, str]] = {
    "positive": "Positive",
    "neutre": "Neutre",
    "negative": "Négative",
}

# Agrégats : les commentaires non politiques forment une ligne à part.
NON_POLITIQUE: Final = "non_politique"


def sous_type_valide(type_source: TypeSource, sous_type: str) -> bool:
    return sous_type in SOUS_TYPES_PAR_TYPE[type_source]
