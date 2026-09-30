import sys
from pathlib import Path
from typing import Any

import pytest
from import_sources import lire_csv

from radar.youtube import YouTube


def _csv(tmp_path: Path, contenu: str) -> Path:
    f = tmp_path / "panel.csv"
    f.write_text("url,type,sous_type,critere,nom\n" + contenu, encoding="utf-8")
    return f


def test_csv_valide(tmp_path: Path) -> None:
    lignes = lire_csv(_csv(tmp_path, "@a,media,info_continu,top vues 90j info continu\n"))
    assert lignes[0].sous_type == "info_continu"


@pytest.mark.parametrize(
    "ligne",
    [
        "@a,media,parti,x\n",  # sous_type incompatible
        "@a,media,info_continu,  \n",  # critère vide
        "@a,orientation,debat,x\n",  # type inconnu
    ],
)
def test_csv_invalide_refuse_avant_tout_appel(tmp_path: Path, ligne: str) -> None:
    with pytest.raises(SystemExit):
        lire_csv(_csv(tmp_path, ligne))


def test_main_dry_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import import_sources
    from test_youtube import UC, FauxYouTube

    faux = FauxYouTube(nb_videos=10)

    def transport(url: str, params: dict[str, str]) -> Any:
        if url.endswith("/channels"):
            return {
                "items": [
                    {
                        "id": UC,
                        "snippet": {"title": "Chaîne A", "customUrl": "@a"},
                        "statistics": {"subscriberCount": "5000"},
                        "contentDetails": {"relatedPlaylists": {"uploads": "UUa"}},
                    }
                ]
            }
        return faux(url, params)

    def fabrique(cle: str, budget: int) -> YouTube:
        return YouTube(cle, budget, transport=transport)

    monkeypatch.setattr(import_sources, "YouTube", fabrique)
    monkeypatch.setenv("YOUTUBE_API_KEY", "x")
    csv = _csv(tmp_path, "@a,media,info_continu,critère,Chaîne B\n")
    monkeypatch.setattr(sys, "argv", ["import_sources", str(csv), "--dry-run"])
    assert import_sources.main() == 0
    sortie = capsys.readouterr().out
    assert "Chaîne A (@a) [Chaîne B]" in sortie
    assert "--dry-run : 1 sources prêtes" in sortie
