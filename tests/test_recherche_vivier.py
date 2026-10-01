import sys
from pathlib import Path
from typing import Any

import pytest

from radar.youtube import YouTube


def test_recherche_vivier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import recherche_vivier

    def transport(url: str, params: dict[str, str]) -> Any:
        assert url.endswith("/search")
        commun = {"snippet": {"channelId": "UCcommun", "channelTitle": "Commune"}}
        propre = {"snippet": {"channelId": f"UC{params['q'][0]}", "channelTitle": params["q"]}}
        return {"items": [commun, commun, propre]}

    def fabrique(cle: str, budget: int) -> YouTube:
        return YouTube(cle, budget, transport=transport)

    csv = tmp_path / "c.csv"
    csv.write_text("nom\nAlice A\nBruno B\nChloé C\n", encoding="utf-8")
    monkeypatch.setattr(recherche_vivier, "YouTube", fabrique)
    monkeypatch.setenv("YOUTUBE_API_KEY", "x")
    monkeypatch.setattr(sys, "argv", ["r", str(csv), "--budget", "250"])
    assert recherche_vivier.main() == 0
    sortie = capsys.readouterr().out
    assert "| UCcommun | Commune | 4 | Alice A, Bruno B |" in sortie
    assert "Candidats non traités : Chloé C." in sortie
    assert "**200 / 250**" in sortie
