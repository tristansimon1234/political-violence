from pathlib import Path

import pytest
from import_sources import lire_csv


def _csv(tmp_path: Path, contenu: str) -> Path:
    f = tmp_path / "panel.csv"
    f.write_text("url,type,sous_type,critere\n" + contenu, encoding="utf-8")
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
