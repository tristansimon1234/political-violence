from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from radar.youtube import QuotaDepasse, ResolutionImpossible, YouTube, parser_reference

MAINTENANT = datetime(2026, 9, 30, tzinfo=UTC)
UC = "UC" + "a" * 22


@pytest.mark.parametrize(
    ("ref", "attendu"),
    [
        ("https://www.youtube.com/@BFMTV", ("forHandle", "@BFMTV")),
        ("youtube.com/@le.media-tv/videos", ("forHandle", "@le.media-tv")),
        ("@franceinfo", ("forHandle", "@franceinfo")),
        (f"https://www.youtube.com/channel/{UC}", ("id", UC)),
        (UC, ("id", UC)),
        ("https://www.youtube.com/user/lemondefr", ("forUsername", "lemondefr")),
    ],
)
def test_parser_reference(ref: str, attendu: tuple[str, str]) -> None:
    assert parser_reference(ref) == attendu


def test_parser_reference_inconnue() -> None:
    with pytest.raises(ResolutionImpossible):
        parser_reference("https://www.youtube.com/c/QuelqueChose")


class FauxYouTube:
    """Playlist d'uploads : une vidéo par jour, de la plus récente à la plus ancienne."""

    def __init__(self, nb_videos: int) -> None:
        self.nb = nb_videos
        self.appels: list[str] = []

    def __call__(self, url: str, params: dict[str, str]) -> Any:
        ressource = url.rsplit("/", 1)[1]
        self.appels.append(ressource)
        if ressource == "playlistItems":
            debut = int(params.get("pageToken", "0"))
            fin = min(debut + 50, self.nb)
            items = [
                {
                    "contentDetails": {
                        "videoId": f"v{i}",
                        "videoPublishedAt": (MAINTENANT - timedelta(days=i, hours=1)).isoformat(),
                    }
                }
                for i in range(debut, fin)
            ]
            return {"items": items, "nextPageToken": str(fin) if fin < self.nb else None}
        if ressource == "videos":
            ids = params["id"].split(",")
            return {
                "items": [
                    # Une vidéo sur deux a les commentaires fermés.
                    {
                        "id": v,
                        "statistics": {"viewCount": "100"}
                        | ({} if int(v[1:]) % 2 else {"commentCount": "3"}),
                    }
                    for v in ids
                ]
            }
        raise AssertionError(ressource)


def test_stats_s_arretent_a_la_fenetre() -> None:
    faux = FauxYouTube(nb_videos=500)
    yt = YouTube("cle", budget=100, transport=faux)
    stats = yt.stats_recentes("UU", MAINTENANT, jours=90, max_pages=60)
    assert stats.videos == 90  # jours 0 à 89
    assert stats.vues == 9000
    assert stats.part_commentaires_ouverts == pytest.approx(0.5)
    assert not stats.tronque
    # 2 pages d'uploads (100 vidéos vues) + 2 lots de videos.list
    assert faux.appels.count("playlistItems") == 2
    assert yt.consomme == 4


def test_stats_tronquees() -> None:
    yt = YouTube("cle", budget=100, transport=FauxYouTube(nb_videos=500))
    stats = yt.stats_recentes("UU", MAINTENANT, jours=90, max_pages=1)
    assert stats.tronque
    assert stats.videos == 50


def test_run_ne_depasse_jamais_le_budget() -> None:
    faux = FauxYouTube(nb_videos=500)
    yt = YouTube("cle", budget=3, transport=faux)
    with pytest.raises(QuotaDepasse):
        yt.stats_recentes("UU", MAINTENANT, jours=90, max_pages=60)
    assert yt.consomme <= yt.budget
    assert len(faux.appels) == yt.consomme


def test_resoudre_chaine() -> None:
    def transport(url: str, params: dict[str, str]) -> Any:
        assert params["forHandle"] == "@x"
        return {
            "items": [
                {
                    "id": UC,
                    "snippet": {"title": "X", "customUrl": "@x"},
                    "statistics": {"subscriberCount": "1200"},
                    "contentDetails": {"relatedPlaylists": {"uploads": "UU" + "a" * 22}},
                }
            ]
        }

    yt = YouTube("cle", budget=1, transport=transport)
    c = yt.resoudre_chaine("@x")
    assert c.abonnes == 1200 and c.uploads_playlist_id.startswith("UU")
    assert yt.consomme == 1


def test_resoudre_chaine_introuvable() -> None:
    yt = YouTube("cle", budget=1, transport=lambda url, params: {"items": []})
    with pytest.raises(ResolutionImpossible):
        yt.resoudre_chaine("@inexistante")


def test_recherche_interviews_coute_100_et_respecte_le_budget() -> None:
    appels: list[dict[str, str]] = []

    def transport(url: str, params: dict[str, str]) -> Any:
        appels.append(params)
        return {"items": [{"snippet": {"channelId": "UCx", "channelTitle": "X"}}]}

    yt = YouTube("cle", budget=150, transport=transport)
    assert yt.recherche_interviews("Jean Dupont", MAINTENANT) == [("UCx", "X")]
    assert yt.consomme == 100
    p = appels[0]
    assert p["q"] == "Jean Dupont interview"
    assert (p["type"], p["relevanceLanguage"], p["regionCode"], p["maxResults"]) == (
        "video",
        "fr",
        "FR",
        "25",
    )
    assert p["publishedAfter"] == "2025-09-30T00:00:00Z"
    with pytest.raises(QuotaDepasse):
        yt.recherche_interviews("Autre", MAINTENANT)
    assert yt.consomme == 100
