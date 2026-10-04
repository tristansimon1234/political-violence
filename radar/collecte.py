"""Collecte quotidienne et backfill (docs/architecture.md, docs/backfill-septembre.md).

1. Parcours des uploads des sources actives (1 unité / 50 vidéos).
2. Métadonnées de toutes les nouvelles vidéos (1 unité / 50), format short / long, pré-filtre.
3. Commentaires uniquement pour les vidéos qui passent le pré-filtre, et pour toutes celles des
   chaînes politiques (minimisation RGPD, économie de quota) : tous les commentaires de premier
   niveau, en ordre chronologique (1 unité / page de 100) ; revisite incrémentale.
4. Stockage brut (Parquet, 30 jours) puis état dans Supabase. Arrêt propre avant le budget.

Quotidien : vidéos publiées dans les 3 derniers jours, commentaires re-récupérés chaque jour.
Backfill : vidéos publiées dans [depuis, jusqua[, commentaires récupérés une fois ; reprise
là où le run précédent s'est arrêté.
"""

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal, Protocol

from radar.anonymisation import hash_auteur
from radar.prefiltre import MotsCles
from radar.storage import Stockage, enregistrer
from radar.youtube import QuotaDepasse, VideoDetail, VideoIndisponible, YouTube, format_video

log = logging.getLogger(__name__)

FENETRE_REVISITE_JOURS = 3
# Tous les commentaires de premier niveau (décision du 02/10/2026), en ordre chronologique.
MODE_COMMENTAIRES = "tout"
MAX_PAGES_COMMENTAIRES = 300  # garde-fou : 30 000 commentaires par vidéo et par lecture
MARGE_INCREMENTALE = timedelta(hours=1)  # recouvrement entre deux lectures (doublons dédoublonnés)
MAX_PAGES_UPLOADS = 100
LOT_ECRITURE = 250  # vidéos commentées entre deux écritures (un plantage perd au plus un lot)


class Base(Protocol):
    def select(self, table: str, filtres: dict[str, str]) -> list[dict[str, Any]]: ...
    def upsert(self, table: str, lignes: list[dict[str, Any]], conflit: str) -> None: ...
    def inserer(self, table: str, ligne: dict[str, Any]) -> None: ...


@dataclass
class Parametres:
    mode: Literal["quotidien", "backfill"]
    depuis: datetime
    jusqua: datetime | None  # exclu ; None = jusqu'à maintenant
    dry_run: bool


@dataclass
class Bilan:
    videos_vues: int = 0
    videos_nouvelles: int = 0
    videos_prefiltre: int = 0
    videos_eligibles: int = 0
    videos_commentees: int = 0
    commentaires: int = 0
    pages_estimees: int = 0
    # Total annoncé par YouTube (statistics.commentCount, réponses comprises) des vidéos
    # éligibles : mesure ce que coûterait « tout prendre » (1 unité / 100 commentaires).
    commentaires_annonces: int = 0
    arret_budget: bool = False
    videos_indisponibles: int = 0
    prefiltre_par_type: Counter[str] = field(default_factory=Counter[str])
    nouvelles_par_type: Counter[str] = field(default_factory=Counter[str])
    prefiltre_par_jour: Counter[str] = field(default_factory=Counter[str])
    videos_par_jour: Counter[str] = field(default_factory=Counter[str])
    sources_parcourues: list[str] = field(default_factory=list[str])


def _format(v: VideoDetail) -> Literal["short", "long"]:
    f = format_video(v)
    return "short" if f == "short" else "long"  # « ambigu » (format inconnu) compté long


def _lecture_depuis(v: dict[str, Any]) -> datetime | None:
    """Lecture incrémentale si la vidéo a déjà été lue en entier ; sinon lecture complète."""
    if v.get("mode_commentaires") != MODE_COMMENTAIRES or not v.get("commentaires_lus_jusqua"):
        return None
    return datetime.fromisoformat(str(v["commentaires_lus_jusqua"])) - MARGE_INCREMENTALE


def _pages_estimees(v: dict[str, Any]) -> int:
    """Estimation (majorant) du nombre de pages : total annoncé / 100, au moins 1 page."""
    if _lecture_depuis(v) is not None:
        return 1
    return min(MAX_PAGES_COMMENTAIRES, max(1, -(-int(v["nb_commentaires"] or 0) // 100)))


def _par_lots(ids: list[str], taille: int = 100) -> list[list[str]]:
    return [ids[i : i + taille] for i in range(0, len(ids), taille)]


def collecter(
    p: Parametres,
    yt: YouTube,
    base: Base,
    stockage: Stockage | None,
    mots_cles: MotsCles,
    sel: bytes | None,
    maintenant: datetime | None = None,
) -> Bilan:
    maintenant = maintenant or datetime.now(UTC)
    aujourdhui = maintenant.date()
    bilan = Bilan()
    if not p.dry_run and (stockage is None or sel is None):
        raise ValueError("stockage et sel obligatoires hors --dry-run")

    sources = {s["id"]: s for s in base.select("sources", {"active": "eq.true"})}
    deja_parcourues: set[str] = set()
    if p.mode == "backfill":
        assert p.jusqua is not None
        etat = base.select(
            "collecte_etat",
            {"depuis": f"eq.{p.depuis.date()}", "jusqua": f"eq.{p.jusqua.date()}"},
        )
        deja_parcourues = {e["source_id"] for e in etat}

    videos: dict[str, dict[str, Any]] = {}  # lignes complètes de la table `videos`
    bruts_videos: list[dict[str, Any]] = []
    touchees: set[str] = set()
    commentaires: list[dict[str, Any]] = []
    premieres: list[date] = []
    index: dict[str, set[str]] = {}  # fichiers du brut déjà lus pendant ce run

    def ecrire() -> None:
        """Stockage brut d'abord, puis état : une vidéo marquée collectée est stockée.

        Appelée par lots pendant la collecte : idempotente, chaque appel n'écrit que le
        nouveau depuis le précédent.
        """
        if p.dry_run:
            return
        assert stockage is not None
        enregistrer(stockage, "videos", aujourdhui, bruts_videos, aujourdhui, index)
        enregistrer(
            stockage,
            "commentaires",
            aujourdhui,
            commentaires,
            min(premieres, default=aujourdhui),
            index,
        )
        base.upsert("videos", [videos[i] for i in sorted(touchees)], conflit="video_id")
        if p.mode == "backfill" and p.jusqua is not None:
            base.upsert(
                "collecte_etat",
                [
                    {
                        "source_id": sid,
                        "depuis": str(p.depuis.date()),
                        "jusqua": str(p.jusqua.date()),
                    }
                    for sid in bilan.sources_parcourues
                ],
                conflit="source_id,depuis,jusqua",
            )
        bruts_videos.clear()
        commentaires.clear()
        premieres.clear()
        touchees.clear()
        log.info(
            "écriture : %d vidéos commentées, %d commentaires",
            bilan.videos_commentees,
            bilan.commentaires,
        )

    try:
        # 1-2. Uploads et métadonnées
        for source_id, s in sources.items():
            if source_id in deja_parcourues:
                filtres = {"source_id": f"eq.{source_id}"}
                filtres["and"] = (
                    f"(publiee_at.gte.{p.depuis.isoformat()},publiee_at.lt.{p.jusqua.isoformat()})"
                    if p.jusqua
                    else f"(publiee_at.gte.{p.depuis.isoformat()})"
                )
                for v in base.select("videos", filtres):
                    videos[v["video_id"]] = v
                continue
            recents, _ = yt.ids_periode(
                s["uploads_playlist_id"], p.depuis, p.jusqua, MAX_PAGES_UPLOADS
            )
            ids = [i for i, _ in recents]
            connues: dict[str, dict[str, Any]] = {}
            for lot in _par_lots(ids):
                for v in base.select("videos", {"video_id": f"in.({','.join(lot)})"}):
                    connues[v["video_id"]] = v
            videos.update(connues)
            nouvelles = [i for i in ids if i not in connues]
            for d in yt.details_videos(nouvelles):
                fmt = _format(d)
                politique = s["type"] == "politique"
                passe = politique or mots_cles.correspond(d.titre, d.description, " ".join(d.tags))
                videos[d.id] = {
                    "video_id": d.id,
                    "source_id": source_id,
                    "publiee_at": d.publiee_at.isoformat(),
                    "format": fmt,
                    "duree_s": d.duree_s,
                    "vues": d.vues,
                    "nb_commentaires": d.nb_commentaires,
                    "prefiltre": passe,
                    "prefiltre_version": mots_cles.version,
                    "commentaires_fermes": d.nb_commentaires is None,
                    "premiere_vue": aujourdhui.isoformat(),
                    "premiere_collecte": None,
                    "derniere_collecte": None,
                    "nb_collectes": 0,
                    "mode_commentaires": None,
                    "commentaires_lus_jusqua": None,
                    "maj_at": maintenant.isoformat(),
                }
                touchees.add(d.id)
                bilan.videos_nouvelles += 1
                bilan.nouvelles_par_type[s["type"]] += 1
                bruts_videos.append(
                    {
                        "video_id": d.id,
                        "source_id": source_id,
                        "titre": d.titre,
                        "description": d.description,
                        "tags": d.tags,
                    }
                )
            bilan.sources_parcourues.append(source_id)

        # 3. Vidéos éligibles aux commentaires
        limite_revisite = maintenant - timedelta(days=FENETRE_REVISITE_JOURS)
        eligibles: list[dict[str, Any]] = []
        for v in videos.values():
            bilan.videos_vues += 1
            bilan.videos_par_jour[str(v["publiee_at"])[:10]] += 1
            if not v["prefiltre"]:
                continue
            type_source = sources[v["source_id"]]["type"] if v["source_id"] in sources else "?"
            bilan.videos_prefiltre += 1
            bilan.prefiltre_par_type[type_source] += 1
            bilan.prefiltre_par_jour[str(v["publiee_at"])[:10]] += 1
            if v["commentaires_fermes"]:
                continue
            if p.mode == "quotidien":
                ok = (
                    datetime.fromisoformat(v["publiee_at"]) >= limite_revisite
                    and v["derniere_collecte"] != aujourdhui.isoformat()
                )
            else:
                # Jamais collectée, ou collectée dans l'ancien mode (200 par pertinence).
                ok = (
                    v.get("mode_commentaires") != MODE_COMMENTAIRES
                    or v["derniere_collecte"] is None
                )
            if ok:
                eligibles.append(v)
        eligibles.sort(key=lambda v: v["publiee_at"])
        bilan.videos_eligibles = len(eligibles)
        bilan.pages_estimees = sum(_pages_estimees(v) for v in eligibles)
        bilan.commentaires_annonces = sum(int(v["nb_commentaires"] or 0) for v in eligibles)

        if p.dry_run:
            return bilan

        # 4. Commentaires
        assert sel is not None
        for v in eligibles:
            try:
                recus = yt.commentaires(
                    v["video_id"], MAX_PAGES_COMMENTAIRES, depuis=_lecture_depuis(v)
                )
            except VideoIndisponible as e:
                # Supprimée ou devenue privée depuis la lecture des métadonnées : on ne la
                # redemande plus (traitée comme commentaires fermés).
                log.warning("vidéo indisponible : %s", e)
                v["commentaires_fermes"] = True
                v["maj_at"] = maintenant.isoformat()
                touchees.add(v["video_id"])
                bilan.videos_indisponibles += 1
                continue
            for c in recus:
                commentaires.append(
                    {
                        "comment_id": c.comment_id,
                        "video_id": c.video_id,
                        "source_id": v["source_id"],
                        "auteur_hash": hash_auteur(c.auteur_channel_id, sel),
                        "texte": c.texte,
                        "likes": c.likes,
                        "nb_reponses": c.nb_reponses,
                        "publie_at": c.publie_at,
                        "modifie_at": c.modifie_at,
                    }
                )
            if v["premiere_collecte"]:
                premieres.append(date.fromisoformat(v["premiere_collecte"]))
            v["premiere_collecte"] = v["premiere_collecte"] or aujourdhui.isoformat()
            v["derniere_collecte"] = aujourdhui.isoformat()
            v["nb_collectes"] = int(v["nb_collectes"]) + 1
            v["mode_commentaires"] = MODE_COMMENTAIRES
            v["commentaires_lus_jusqua"] = maintenant.isoformat()
            v["maj_at"] = maintenant.isoformat()
            touchees.add(v["video_id"])
            bilan.videos_commentees += 1
            bilan.commentaires += len(recus)
            if bilan.videos_commentees % LOT_ECRITURE == 0:
                ecrire()
    except QuotaDepasse as e:
        log.warning("arrêt propre avant le budget : %s", e)
        bilan.arret_budget = True
        if p.dry_run:
            return bilan
    except Exception:
        # Erreur imprévue : on sauve ce qui a été collecté avant de la laisser remonter.
        if not p.dry_run:
            log.exception("erreur imprévue, écriture de ce qui a été collecté")
            ecrire()
        raise

    # Pas de purge ici : elle est lancée à la main (scripts/purge.py, décision du 04/10/2026).
    ecrire()
    return bilan
