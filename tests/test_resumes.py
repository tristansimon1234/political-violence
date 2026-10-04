"""Résumés IA : sujets de la semaine, sources numérotées, validation des renvois."""

from datetime import date

import pytest

from radar.resumes import (
    ResumeInvalide,
    VideoInfo,
    elements_sujet,
    empreinte,
    lundi,
    stats_sujets,
    valider,
)

SEM = date(2026, 9, 14)


def _v(i: int, jour: date, chaine: str, type_: str = "media_natif", n: float = 100) -> VideoInfo:
    return VideoInfo(
        f"v{i}", jour, type_, chaine, f"[sous-sujet {i}]", "securite", n, 10, 30, 5, 40
    )


def test_stats_sujets_semaine_seuils_et_politiques_a_part() -> None:
    vids = [
        _v(1, SEM, "[A]"),
        _v(2, SEM, "[B]", "media_traditionnel"),
        _v(3, SEM, "[A]"),
        _v(4, SEM, "[P]", "politique"),  # chaîne politique : lue à part
        _v(5, SEM - date.resolution * 3, "[A]", n=50),  # semaine précédente
        _v(6, SEM, "[A]"),
        _v(7, SEM, "[A]"),
        _v(8, SEM, "[A]"),  # sujet y : une seule chaîne, exclu
    ]
    sujet_de = {f"v{i}": "x" for i in range(1, 6)} | {"v6": "y", "v7": "y", "v8": "y"}
    stats = stats_sujets(vids, sujet_de, {"x": "[Sujet X]"}, SEM)
    assert [s.id for s in stats] == ["x"]
    assert len(stats[0].videos) == 3 and stats[0].precedent == 50


def test_elements_sans_texte_de_commentaire_et_videos_liees() -> None:
    vids = [_v(1, SEM, "[A]"), _v(2, SEM, "[B]"), _v(3, SEM, "[A]")]
    (s,) = stats_sujets(vids, {"v1": "x", "v2": "x", "v3": "x"}, {"x": "[X]"}, SEM)
    els = elements_sujet(s)
    assert any(e.video_id == "v1" for e in els)
    assert all("@" not in e.texte for e in els)
    assert "300 commentaires sous 3 vidéos de 2 chaînes" in els[0].texte


def test_valider_renvois() -> None:
    assert valider("Les commentaires montent [1]. Désaccord marqué [2][3].", 3) == (
        "Les commentaires montent [1]. Désaccord marqué [2][3].",
        [1, 2, 3],
    )
    with pytest.raises(ResumeInvalide):
        valider("Aucun renvoi ici.", 3)
    with pytest.raises(ResumeInvalide):
        valider("Renvoi inconnu [7].", 3)


def test_lundi_et_empreinte_stable() -> None:
    assert lundi(date(2026, 9, 20)) == SEM
    from radar.resumes import Element

    assert empreinte([Element("a")]) == empreinte([Element("a")]) != empreinte([Element("b")])
