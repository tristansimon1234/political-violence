import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from audit_panel import format_video

from radar.youtube import VideoDetail, YouTube, duree_iso8601


@pytest.mark.parametrize(
    ("iso", "secondes"),
    [("PT45S", 45), ("PT3M", 180), ("PT1H2M3S", 3723), ("P1DT1S", 86401), ("P0D", 0)],
)
def test_duree_iso8601(iso: str, secondes: int) -> None:
    assert duree_iso8601(iso) == secondes


def _video(duree_s: int, ratio: float | None) -> VideoDetail:
    return VideoDetail(
        id="v",
        titre="t",
        publiee_at=datetime(2026, 9, 1, tzinfo=UTC),
        duree_s=duree_s,
        vues=0,
        commentaires_ouverts=True,
        ratio=ratio,
    )


@pytest.mark.parametrize(
    ("duree_s", "ratio", "attendu"),
    [
        (50, 9 / 16, "short"),
        (180, 9 / 16, "short"),
        (181, 9 / 16, "long"),  # vertical mais trop long
        (50, 16 / 9, "long"),  # court mais horizontal
        (50, None, "ambigu"),
        (0, None, "long"),  # live à venir
    ],
)
def test_format_video(duree_s: int, ratio: float | None, attendu: str) -> None:
    assert format_video(_video(duree_s, ratio)) == attendu


def test_main_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import audit_panel

    maintenant = datetime.now(UTC)

    def transport(url: str, params: dict[str, str]) -> Any:
        ressource = url.rsplit("/", 1)[1]
        if ressource == "channels":
            return {
                "items": [
                    {
                        "id": "UC" + "a" * 22,
                        "snippet": {"title": "Chaîne A", "customUrl": "@a"},
                        "statistics": {"subscriberCount": "5000"},
                        "contentDetails": {"relatedPlaylists": {"uploads": "UUa"}},
                    }
                ]
            }
        if ressource == "playlistItems":
            return {
                "items": [
                    {
                        "contentDetails": {
                            "videoId": f"v{i}",
                            "videoPublishedAt": (maintenant - timedelta(days=i)).isoformat(),
                        }
                    }
                    for i in range(12)
                ]
            }
        # videos : les 4 premières sont des Shorts verticaux
        return {
            "items": [
                {
                    "id": v,
                    "snippet": {"title": f"titre {v}", "publishedAt": maintenant.isoformat()},
                    "contentDetails": {"duration": "PT40S" if int(v[1:]) < 4 else "PT12M"},
                    "statistics": {"viewCount": "10", "commentCount": "1"},
                    "player": {"embedWidth": "405", "embedHeight": "720"}
                    if int(v[1:]) < 4
                    else {"embedWidth": "1280", "embedHeight": "720"},
                }
                for v in params["id"].split(",")
            ]
        }

    def fabrique(cle: str, budget: int) -> YouTube:
        return YouTube(cle, budget, transport=transport)

    csv = tmp_path / "c.csv"
    csv.write_text("url,type,sous_type,critere\n@a,influenceur,debat,x\n", encoding="utf-8")
    titres = tmp_path / "titres.txt"
    monkeypatch.setattr(audit_panel, "YouTube", fabrique)
    monkeypatch.setenv("YOUTUBE_API_KEY", "x")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit",
            "--panel",
            str(csv),
            "--personnalites",
            str(csv),
            "--candidats",
            str(csv),
            "--titres",
            str(titres),
        ],
    )
    assert audit_panel.main() == 0
    sortie = capsys.readouterr().out
    assert "| 12 (8 / 4 / 0) |" in sortie
    assert "passe grâce aux Shorts seulement (8 longues)" in sortie
    assert "| 12 | 8 | 4 | 0 | 33% |" in sortie
    assert "[short] titre v0" in titres.read_text(encoding="utf-8")
    assert "Quota YouTube consommé : **9 / 3000**" in sortie
