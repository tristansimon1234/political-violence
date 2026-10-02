from radar.schemas import (
    LIBELLES_TYPE,
    SOUS_TYPES_PAR_TYPE,
    TYPES_SOURCE,
    sous_type_valide,
)


def test_chaque_type_a_des_sous_types_et_un_libelle() -> None:
    assert set(SOUS_TYPES_PAR_TYPE) == set(TYPES_SOURCE) == set(LIBELLES_TYPE)
    assert all(SOUS_TYPES_PAR_TYPE[t] for t in TYPES_SOURCE)


def test_sous_types_non_partages_entre_types() -> None:
    tous = [s for t in TYPES_SOURCE for s in SOUS_TYPES_PAR_TYPE[t]]
    assert len(tous) == len(set(tous))


def test_sous_type_valide() -> None:
    assert sous_type_valide("media_traditionnel", "info_continu")
    assert sous_type_valide("media_natif", "createur")
    assert not sous_type_valide("media_traditionnel", "pure_player")
    assert not sous_type_valide("politique", "inconnu")


def test_categorie_influenceur_supprimee() -> None:
    assert "influenceur" not in TYPES_SOURCE


def test_libelles_complets() -> None:
    from radar.schemas import (
        LIBELLES_POSITIONS,
        LIBELLES_THEMES,
        LIBELLES_TONALITES,
        POSITIONS,
        THEMES,
        TONALITES,
    )

    assert set(LIBELLES_THEMES) == set(THEMES)
    from radar.classification import DEFINITIONS_THEMES
    from radar.schemas import DEFINITIONS_THEMES_FR

    assert set(DEFINITIONS_THEMES_FR) == set(DEFINITIONS_THEMES) == set(THEMES)
    assert set(LIBELLES_POSITIONS) == set(POSITIONS)
    assert set(LIBELLES_TONALITES) == set(TONALITES)
