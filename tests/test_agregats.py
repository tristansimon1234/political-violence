"""Agrégats par thème : 1/n par thème, totaux exacts, position sous opinion seulement."""

from datetime import UTC, date, datetime
from typing import Any

import pytest

from radar.agregats import MESURES, agreger, jour_paris
from radar.schemas import NON_POLITIQUE


def _c(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "est_politique": True,
        "themes": ["retraites"],
        "type_source": "media_natif",
        "format": "long",
        "nature": "opinion",
        "position": "desaccord_video",
        "tonalite": "negative",
        "hostilite": False,
        "publie_at": datetime(2026, 9, 2, 10, tzinfo=UTC),
        "recupere_le": date(2026, 10, 2),
    }
    return {**base, **kw}


def test_multi_themes_un_sur_n_et_totaux() -> None:
    classes = [
        _c(themes=["retraites", "sante", "economie_emploi"]),
        _c(themes=["retraites"]),
        _c(est_politique=False, themes=[], position="hors_sujet", tonalite="neutre"),
    ]
    lignes = agreger(classes)
    par_theme = {li["theme"]: li for li in lignes}
    assert par_theme["retraites"]["commentaires"] == pytest.approx(1 + 1 / 3, abs=1e-3)
    assert par_theme["sante"]["commentaires"] == pytest.approx(1 / 3, abs=1e-3)
    assert par_theme[NON_POLITIQUE]["commentaires"] == 1
    # Invariant : les totaux par thème égalent le nombre de commentaires, mesure par mesure.
    assert sum(li["commentaires"] for li in lignes) == pytest.approx(len(classes), abs=1e-3)
    assert sum(li["negatifs"] + li["neutres"] + li["positifs"] for li in lignes) == pytest.approx(
        3, abs=1e-3
    )
    assert all(set(MESURES) <= set(li) for li in lignes)


def test_position_seulement_sous_opinion() -> None:
    lignes = agreger(
        [
            _c(nature="opinion", position="accord_video"),
            _c(nature="info_factuelle", position=None),
            _c(nature="debat", position=None),
        ]
    )
    (li,) = lignes
    assert li["commentaires"] == 3 and li["sous_opinion"] == 1 and li["accord"] == 1
    assert li["desaccord"] == 0 and li["hors_sujet"] == 0


def test_politiques_a_part_et_jour_paris() -> None:
    lignes = agreger(
        [
            _c(type_source="politique"),
            _c(
                type_source="media_traditionnel", publie_at=datetime(2026, 9, 2, 23, 30, tzinfo=UTC)
            ),
        ]
    )
    assert {li["type_source"] for li in lignes} == {"politique", "media_traditionnel"}
    # 23 h 30 UTC = le lendemain à Paris.
    assert {li["jour"] for li in lignes if li["type_source"] == "media_traditionnel"} == {
        "2026-09-03"
    }
    assert jour_paris({"publie_at": None, "recupere_le": date(2026, 10, 2)}) == date(2026, 10, 2)


def test_aucun_identifiant_ni_texte() -> None:
    (li,) = agreger([_c(id="abc", auteur_hash="h" * 32, video_id="v1")])
    assert not {"id", "auteur_hash", "video_id", "texte", "titre"} & set(li)


def test_agregats_par_video() -> None:
    from radar.agregats import agreger_videos

    lignes = agreger_videos(
        [
            {**_c(position="accord_video"), "video_id": "v1"},
            {**_c(position="desaccord_video", hostilite=True), "video_id": "v1"},
            {**_c(nature="info_factuelle", position=None), "video_id": "v2"},
        ]
    )
    par = {x["video_id"]: x for x in lignes}
    assert par["v1"] == {
        "video_id": "v1",
        "commentaires": 2,
        "hostiles": 1,
        "accord": 1,
        "nuance": 0,
        "desaccord": 1,
        "hors_sujet": 0,
    }
    assert par["v2"]["commentaires"] == 1 and par["v2"]["accord"] == 0  # pas de position
