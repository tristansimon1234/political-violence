"""Les listes fermées du SQL doivent rester le miroir exact de radar/schemas.py.

On lit la dernière migration qui (re)définit chaque contrainte.
"""

import re
from pathlib import Path

from radar.schemas import NATURES_VIDEO, SOUS_TYPES_PAR_TYPE, TYPES_SOURCE

MIGRATIONS = sorted((Path(__file__).parents[1] / "supabase/migrations").glob("*.sql"))


def _liste(sql: str) -> set[str]:
    return set(re.findall(r"'(\w+)'", sql))


def _derniere(motif: str) -> list[tuple[str, ...]] | list[str]:
    for f in reversed(MIGRATIONS):
        trouves: list[str] | list[tuple[str, ...]] = re.findall(motif, f.read_text())
        if trouves:
            return trouves
    raise AssertionError(f"motif absent des migrations : {motif}")


def test_types_source_identiques() -> None:
    (liste,) = _derniere(r"check \(type in \(([^)]*)\)\)")
    assert isinstance(liste, str)
    assert _liste(liste) == set(TYPES_SOURCE)


def test_sous_types_identiques() -> None:
    trouves = {
        t: _liste(liste) for t, liste in _derniere(r"when '(\w+)' then sous_type in \(([^)]*)\)")
    }
    assert trouves == {t: set(s) for t, s in SOUS_TYPES_PAR_TYPE.items()}


def test_natures_video_identiques() -> None:
    (liste,) = _derniere(r"check \(nature in \(([^)]*)\)\)")
    assert isinstance(liste, str)
    assert _liste(liste) == set(NATURES_VIDEO)
