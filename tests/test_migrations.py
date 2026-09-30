"""Les listes fermées du SQL doivent rester le miroir exact de radar/schemas.py."""

import re
from pathlib import Path

from radar.schemas import SOUS_TYPES_PAR_TYPE, TYPES_SOURCE

MIGRATION = Path(__file__).parents[1] / "supabase/migrations/20260930000001_sources.sql"


def _liste(sql: str) -> set[str]:
    return set(re.findall(r"'(\w+)'", sql))


def test_types_source_identiques() -> None:
    sql = MIGRATION.read_text()
    m = re.search(r"type text not null check \(type in \(([^)]*)\)\)", sql)
    assert m
    assert _liste(m.group(1)) == set(TYPES_SOURCE)


def test_sous_types_identiques() -> None:
    sql = MIGRATION.read_text()
    trouves = {
        t: _liste(liste)
        for t, liste in re.findall(r"when '(\w+)' then sous_type in \(([^)]*)\)", sql)
    }
    assert trouves == {t: set(s) for t, s in SOUS_TYPES_PAR_TYPE.items()}
