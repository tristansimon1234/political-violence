from radar.schemas import (
    QUOTAS_PANEL,
    SOUS_TYPES_PAR_TYPE,
    TYPES_SOURCE,
    sous_type_valide,
)


def test_chaque_type_a_des_sous_types() -> None:
    assert set(SOUS_TYPES_PAR_TYPE) == set(TYPES_SOURCE)
    assert all(SOUS_TYPES_PAR_TYPE[t] for t in TYPES_SOURCE)


def test_sous_types_non_partages_entre_types() -> None:
    tous = [s for t in TYPES_SOURCE for s in SOUS_TYPES_PAR_TYPE[t]]
    assert len(tous) == len(set(tous))


def test_sous_type_valide() -> None:
    assert sous_type_valide("media", "info_continu")
    assert not sous_type_valide("media", "parti")
    assert not sous_type_valide("politique", "inconnu")


def test_quotas_panel() -> None:
    assert set(QUOTAS_PANEL) == set(TYPES_SOURCE)
    assert sum(QUOTAS_PANEL.values()) == 50
