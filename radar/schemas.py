"""Taxonomie du Radar : source de vérité unique.

Toute modification d'une liste fermée incrémente VERSION_TAXONOMIE.
"""

from typing import Final, Literal, get_args

VERSION_TAXONOMIE: Final = 1

# --- Sources du panel ---

TypeSource = Literal["media", "influenceur", "politique"]

SousTypeMedia = Literal["info_continu", "tv_radio", "talk_show", "presse_nationale", "pure_player"]
SousTypeInfluenceur = Literal["vulgarisation", "commentateur", "debat"]
SousTypePolitique = Literal["parti", "personnalite"]
SousType = SousTypeMedia | SousTypeInfluenceur | SousTypePolitique

TYPES_SOURCE: Final[tuple[TypeSource, ...]] = get_args(TypeSource)

SOUS_TYPES_PAR_TYPE: Final[dict[TypeSource, tuple[SousType, ...]]] = {
    "media": get_args(SousTypeMedia),
    "influenceur": get_args(SousTypeInfluenceur),
    "politique": get_args(SousTypePolitique),
}

# Quotas cibles du panel (docs/decisions.md, 30/09/2026).
QUOTAS_PANEL: Final[dict[TypeSource, int]] = {"media": 25, "influenceur": 12, "politique": 13}


def sous_type_valide(type_source: TypeSource, sous_type: str) -> bool:
    return sous_type in SOUS_TYPES_PAR_TYPE[type_source]
