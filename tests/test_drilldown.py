"""Drill-down par vidéo : commentaires classés des 30 derniers jours, sans auteur ni identifiant."""

import gzip
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from radar.classement import id_commentaire
from radar.drilldown import chemin, fiches, publier
from radar.storage import StockageLocal

SEL = b"s" * 32
AUJOURDHUI = date(2026, 10, 4)


def _brut(cid: str, video: str, jour: int, mois: int = 9) -> dict[str, Any]:
    return {
        "comment_id": cid,
        "video_id": video,
        "source_id": "s1",
        "auteur_hash": "HASH_AUTEUR",
        "texte": f"texte {cid}",
        "publie_at": datetime(2026, mois, jour, 12, tzinfo=UTC),
    }


def _classe(cid: str, video: str) -> dict[str, Any]:
    return {
        "id": id_commentaire(cid, SEL),
        "video_id": video,
        "est_politique": True,
        "themes": ["retraites"],
        "position": "accord_video",
        "tonalite": "neutre",
        "hostilite": False,
    }


def test_fiches_classes_30_jours_sans_auteur_ni_identifiant() -> None:
    bruts = [
        _brut("a", "v1", 20),
        _brut("b", "v1", 10),
        _brut("c", "v1", 1),  # plus de 30 jours : exclu
        _brut("d", "v2", 21),  # pas classé : exclu
    ]
    par_video = fiches(
        [_classe("a", "v1"), _classe("b", "v1"), _classe("c", "v1")], bruts, SEL, AUJOURDHUI
    )
    assert list(par_video) == ["v1"]
    assert [x["texte"] for x in par_video["v1"]] == ["texte b", "texte a"]
    contenu = json.dumps(par_video)
    assert "HASH_AUTEUR" not in contenu and id_commentaire("a", SEL) not in contenu
    assert '"a"' not in contenu  # identifiant YouTube absent


def test_publier_ecrit_les_changements_et_supprime_les_sortis(tmp_path: Path) -> None:
    st = StockageLocal(tmp_path)
    xs = [{"texte": "t"}]
    assert publier(st, {"v1": xs, "v2": xs}) == (2, 0)
    assert publier(st, {"v1": xs, "v2": xs}) == (0, 0)  # inchangé : rien de réécrit
    assert publier(st, {"v1": xs + xs}) == (1, 1)  # v1 modifié, v2 sorti de la fenêtre
    assert st.lister("videos") == [chemin("v1")]
    assert json.loads(gzip.decompress(st.lire(chemin("v1")))) == xs + xs
