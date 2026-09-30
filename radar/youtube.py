"""Client unique de l'API YouTube Data v3, avec suivi du quota.

Coûts (unités) : channels.list = 1, playlistItems.list = 1, videos.list = 1.
search.list (100 unités) n'est jamais utilisé.
"""

import logging
import re
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, Literal

import requests
from pydantic import BaseModel

log = logging.getLogger(__name__)

API = "https://www.googleapis.com/youtube/v3"

Transport = Callable[[str, dict[str, str]], Any]


class QuotaDepasse(RuntimeError):
    """Levée avant un appel qui ferait dépasser le budget du run."""


class ResolutionImpossible(ValueError):
    pass


# --- Réponses de l'API (champs utiles uniquement) ---


class _Snippet(BaseModel):
    title: str
    customUrl: str | None = None


class _ChannelStats(BaseModel):
    subscriberCount: int | None = None


class _RelatedPlaylists(BaseModel):
    uploads: str


class _ChannelContent(BaseModel):
    relatedPlaylists: _RelatedPlaylists


class _ChannelItem(BaseModel):
    id: str
    snippet: _Snippet
    statistics: _ChannelStats
    contentDetails: _ChannelContent


class _ChannelsResponse(BaseModel):
    items: list[_ChannelItem] = []


class _PlaylistItemContent(BaseModel):
    videoId: str
    videoPublishedAt: datetime | None = None  # absent pour les vidéos privées


class _PlaylistItem(BaseModel):
    contentDetails: _PlaylistItemContent


class _PlaylistItemsResponse(BaseModel):
    items: list[_PlaylistItem] = []
    nextPageToken: str | None = None


class _VideoStats(BaseModel):
    viewCount: int = 0
    commentCount: int | None = None  # absent si commentaires fermés


class _VideoItem(BaseModel):
    id: str
    statistics: _VideoStats


class _VideoSnippet(BaseModel):
    title: str
    publishedAt: datetime


class _VideoContent(BaseModel):
    duration: str = "P0D"


class _VideoPlayer(BaseModel):
    embedWidth: int | None = None
    embedHeight: int | None = None


class _VideoDetailItem(BaseModel):
    id: str
    snippet: _VideoSnippet
    contentDetails: _VideoContent
    statistics: _VideoStats
    player: _VideoPlayer = _VideoPlayer()


class _VideoDetailsResponse(BaseModel):
    items: list[_VideoDetailItem] = []


class _VideosResponse(BaseModel):
    items: list[_VideoItem] = []


# --- Résultats exposés ---


class Chaine(BaseModel):
    channel_id: str
    handle: str | None
    nom: str
    abonnes: int | None
    uploads_playlist_id: str


class StatsRecentes(BaseModel):
    videos: int
    vues: int
    part_commentaires_ouverts: float | None
    derniere_video_at: datetime | None
    tronque: bool  # True si la limite de pages a coupé le parcours avant la fin de la fenêtre


class VideoDetail(BaseModel):
    id: str
    titre: str  # donnée brute : jamais stockée au-delà de l'usage immédiat
    publiee_at: datetime
    duree_s: int
    vues: int
    commentaires_ouverts: bool
    ratio: float | None  # largeur / hauteur du lecteur ; < 1 = vertical ; None si inconnu


def duree_iso8601(duree: str) -> int:
    """'PT1H2M3S' → 3723 secondes. 'P0D' (live à venir) → 0."""
    m = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", duree)
    if not m:
        raise ValueError(f"Durée ISO 8601 invalide : {duree}")
    j, h, mi, se = (int(g) if g else 0 for g in m.groups())
    return ((j * 24 + h) * 60 + mi) * 60 + se


def parser_reference(ref: str) -> tuple[Literal["id", "forHandle", "forUsername"], str]:
    """URL, @handle ou ID de chaîne → paramètre de channels.list."""
    ref = ref.strip()
    if m := re.fullmatch(r"(?:https?://)?(?:www\.|m\.)?youtube\.com/channel/(UC[\w-]{22})/?", ref):
        return "id", m.group(1)
    if re.fullmatch(r"UC[\w-]{22}", ref):
        return "id", ref
    if m := re.fullmatch(r"(?:https?://)?(?:www\.|m\.)?youtube\.com/(@[\w.\-]+)(?:/\w*)?/?", ref):
        return "forHandle", m.group(1)
    if re.fullmatch(r"@[\w.\-]+", ref):
        return "forHandle", ref
    if m := re.fullmatch(r"(?:https?://)?(?:www\.|m\.)?youtube\.com/user/([\w.\-]+)/?", ref):
        return "forUsername", m.group(1)
    raise ResolutionImpossible(
        f"Référence non reconnue (URL /@handle, /channel/UC… ou /user/) : {ref}"
    )


def _transport_http(url: str, params: dict[str, str]) -> Any:
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


class YouTube:
    def __init__(self, api_key: str, budget: int, transport: Transport = _transport_http) -> None:
        self._api_key = api_key
        self.budget = budget
        self.consomme = 0
        self._transport = transport

    def _appel(self, ressource: str, params: dict[str, str], cout: int = 1) -> Any:
        if self.consomme + cout > self.budget:
            raise QuotaDepasse(
                f"{ressource} refusé : {self.consomme}+{cout} > budget {self.budget}"
            )
        # Compté avant l'appel : un appel en erreur consomme aussi du quota.
        self.consomme += cout
        log.info("youtube %s cout=%d total=%d/%d", ressource, cout, self.consomme, self.budget)
        return self._transport(f"{API}/{ressource}", {**params, "key": self._api_key})

    def resoudre_chaine(self, ref: str) -> Chaine:
        cle, valeur = parser_reference(ref)
        brut = self._appel("channels", {"part": "snippet,statistics,contentDetails", cle: valeur})
        rep = _ChannelsResponse.model_validate(brut)
        if not rep.items:
            raise ResolutionImpossible(f"Chaîne introuvable : {ref}")
        c = rep.items[0]
        return Chaine(
            channel_id=c.id,
            handle=c.snippet.customUrl,
            nom=c.snippet.title,
            abonnes=c.statistics.subscriberCount,
            uploads_playlist_id=c.contentDetails.relatedPlaylists.uploads,
        )

    def ids_recents(
        self, uploads_playlist_id: str, maintenant: datetime, jours: int, max_pages: int
    ) -> tuple[list[tuple[str, datetime]], bool]:
        """(id, date) des uploads des `jours` derniers jours, plus un indicateur de troncature.

        Coût : 1 unité par page de 50 uploads.
        """
        limite = maintenant - timedelta(days=jours)
        videos: list[tuple[str, datetime]] = []
        page: str | None = None
        tronque = False
        for n in range(max_pages):
            params = {
                "part": "contentDetails",
                "playlistId": uploads_playlist_id,
                "maxResults": "50",
            }
            if page:
                params["pageToken"] = page
            rep = _PlaylistItemsResponse.model_validate(self._appel("playlistItems", params))
            dates = [i.contentDetails.videoPublishedAt for i in rep.items]
            for item in rep.items:
                pub = item.contentDetails.videoPublishedAt
                if pub is None or pub < limite:
                    continue
                videos.append((item.contentDetails.videoId, pub))
            page = rep.nextPageToken
            fini = page is None or any(d is not None and d < limite for d in dates)
            if fini:
                break
            tronque = n == max_pages - 1
        return videos, tronque

    def details_videos(self, ids: list[str]) -> list[VideoDetail]:
        """Titre, durée, format du lecteur et statistiques. Coût : 1 unité par lot de 50."""
        details: list[VideoDetail] = []
        for i in range(0, len(ids), 50):
            params = {
                "part": "snippet,contentDetails,statistics,player",
                "id": ",".join(ids[i : i + 50]),
                "maxHeight": "720",  # nécessaire pour obtenir embedWidth/embedHeight
            }
            rep = _VideoDetailsResponse.model_validate(self._appel("videos", params))
            for v in rep.items:
                w, h = v.player.embedWidth, v.player.embedHeight
                details.append(
                    VideoDetail(
                        id=v.id,
                        titre=v.snippet.title,
                        publiee_at=v.snippet.publishedAt,
                        duree_s=duree_iso8601(v.contentDetails.duration),
                        vues=v.statistics.viewCount,
                        commentaires_ouverts=v.statistics.commentCount is not None,
                        ratio=w / h if w and h else None,
                    )
                )
        return details

    def stats_recentes(
        self, uploads_playlist_id: str, maintenant: datetime, jours: int, max_pages: int
    ) -> StatsRecentes:
        """Vues et activité des vidéos publiées sur les `jours` derniers jours.

        Coût : 1 unité par page de 50 uploads + 1 unité par lot de 50 vidéos.
        """
        videos, tronque = self.ids_recents(uploads_playlist_id, maintenant, jours, max_pages)
        ids = [v for v, _ in videos]
        derniere = max((d for _, d in videos), default=None)
        vues = 0
        ouvertes = 0
        for i in range(0, len(ids), 50):
            lot = ids[i : i + 50]
            rep_v = _VideosResponse.model_validate(
                self._appel("videos", {"part": "statistics", "id": ",".join(lot)})
            )
            for v in rep_v.items:
                vues += v.statistics.viewCount
                ouvertes += v.statistics.commentCount is not None
        return StatsRecentes(
            videos=len(ids),
            vues=vues,
            part_commentaires_ouverts=ouvertes / len(ids) if ids else None,
            derniere_video_at=derniere,
            tronque=tronque,
        )
