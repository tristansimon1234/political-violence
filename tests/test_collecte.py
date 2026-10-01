"""Collecte : pré-filtre, invariants RGPD et 30 jours, unicité, reprise, budget."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import requests

from radar.anonymisation import hash_auteur
from radar.collecte import Parametres, collecter
from radar.prefiltre import charger
from radar.storage import (
    StockageLocal,
    chemin_partition,
    enregistrer,
    lire_partition,
    partitions,
    purger,
)
from radar.youtube import YouTube

SEL = b"sel-de-test-suffisamment-long-0123456789"
J1 = datetime(2026, 10, 2, 9, 45, tzinfo=UTC)
PSEUDO = "PseudoTresReconnaissable"
AUTEUR_ID = "UCauteurEnClair0000000000"


class FausseBase:
    """Tables en mémoire, sous-ensemble des filtres PostgREST utilisés par la collecte."""

    def __init__(self, sources: list[dict[str, Any]]) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {
            "sources": sources,
            "videos": [],
            "collecte_etat": [],
            "collecte_runs": [],
        }

    def select(self, table: str, filtres: dict[str, str]) -> list[dict[str, Any]]:
        lignes = self.tables[table]
        for col, f in filtres.items():
            if col == "and":
                bornes = f.strip("()").split(",")
                for b in bornes:
                    c, op, val = b.split(".", 2)
                    if op == "gte":
                        lignes = [x for x in lignes if x[c] >= val]
                    elif op == "lt":
                        lignes = [x for x in lignes if x[c] < val]
            elif f.startswith("eq."):
                v = f[3:]
                lignes = [x for x in lignes if str(x[col]).lower() == v.lower()]
            elif f.startswith("in.("):
                ens = set(f[4:-1].split(","))
                lignes = [x for x in lignes if x[col] in ens]
        return [dict(x) for x in lignes]

    def upsert(self, table: str, lignes: list[dict[str, Any]], conflit: str) -> None:
        cles = conflit.split(",")
        for ligne in lignes:
            existantes = self.tables[table]
            for i, x in enumerate(existantes):
                if all(str(x[c]) == str(ligne[c]) for c in cles):
                    existantes[i] = {**x, **ligne}
                    break
            else:
                existantes.append(dict(ligne))

    def inserer(self, table: str, ligne: dict[str, Any]) -> None:
        self.tables[table].append(ligne)


SOURCES = [
    {"id": "s-media", "type": "media_traditionnel", "uploads_playlist_id": "UUm", "active": True},
    {"id": "s-parti", "type": "politique", "uploads_playlist_id": "UUp", "active": True},
]


class FauxYouTube:
    """3 vidéos média (dont 1 sans mot-clé) + 1 vidéo de parti sans mot-clé."""

    def __init__(self, maintenant: datetime, fermes: frozenset[str] = frozenset()) -> None:
        pub = (maintenant - timedelta(hours=5)).isoformat()
        self.videos: dict[str, dict[str, Any]] = {
            "m1": {
                "pl": "UUm",
                "titre": "Le débat sur la présidentielle",
                "pub": pub,
                "short": False,
            },
            "m2": {
                "pl": "UUm",
                "titre": "Recette de la tarte aux pommes",
                "pub": pub,
                "short": False,
            },
            "m3": {"pl": "UUm", "titre": "Le 49.3 en 30 secondes", "pub": pub, "short": True},
            "p1": {"pl": "UUp", "titre": "Nos vœux de rentrée", "pub": pub, "short": False},
        }
        self.fermes = fermes
        self.appels: list[tuple[str, str]] = []

    def __call__(self, url: str, params: dict[str, str]) -> Any:
        ressource = url.rsplit("/", 1)[1]
        self.appels.append((ressource, params.get("videoId", params.get("playlistId", ""))))
        if ressource == "playlistItems":
            return {
                "items": [
                    {"contentDetails": {"videoId": vid, "videoPublishedAt": v["pub"]}}
                    for vid, v in self.videos.items()
                    if v["pl"] == params["playlistId"]
                ]
            }
        if ressource == "videos":
            return {
                "items": [
                    {
                        "id": vid,
                        "snippet": {
                            "title": self.videos[vid]["titre"],
                            "publishedAt": self.videos[vid]["pub"],
                            "description": "",
                            "tags": list[str](),
                        },
                        "contentDetails": {
                            "duration": "PT40S" if self.videos[vid]["short"] else "PT20M"
                        },
                        "statistics": {"viewCount": "100"}
                        | ({} if vid in self.fermes else {"commentCount": "3"}),
                        "player": {"embedWidth": "405", "embedHeight": "720"}
                        if self.videos[vid]["short"]
                        else {"embedWidth": "1280", "embedHeight": "720"},
                    }
                    for vid in params["id"].split(",")
                ]
            }
        if ressource == "commentThreads":
            vid = params["videoId"]
            return {
                "items": [
                    {
                        "snippet": {
                            "totalReplyCount": 0,
                            "topLevelComment": {
                                "id": f"{vid}-c{i}",
                                "snippet": {
                                    "textDisplay": f"commentaire {i}",
                                    "authorDisplayName": PSEUDO,
                                    "authorChannelId": {"value": AUTEUR_ID},
                                    "likeCount": i,
                                    "publishedAt": self.videos[vid]["pub"],
                                },
                            },
                        }
                    }
                    for i in range(3)
                ]
            }
        raise AssertionError(ressource)


def _quotidien(dry_run: bool = False, maintenant: datetime = J1) -> Parametres:
    return Parametres("quotidien", maintenant - timedelta(days=3), None, dry_run)


def _run(
    tmp_path: Path,
    faux: FauxYouTube,
    base: FausseBase,
    p: Parametres,
    maintenant: datetime = J1,
    budget: int = 1000,
) -> Any:
    yt = YouTube("cle", budget, transport=faux)
    st = StockageLocal(tmp_path)
    bilan = collecter(
        p, yt, base, None if p.dry_run else st, charger(), None if p.dry_run else SEL, maintenant
    )
    return bilan, yt, st


def _tous_commentaires(st: StockageLocal) -> list[dict[str, Any]]:
    return [
        ligne for c in partitions(st, "commentaires").values() for ligne in lire_partition(st, c)
    ]


def test_prefiltre_commentaires_seulement_pour_videos_retenues(tmp_path: Path) -> None:
    faux = FauxYouTube(J1)
    bilan, _, _ = _run(tmp_path, faux, FausseBase(SOURCES), _quotidien())
    commentees = {v for r, v in faux.appels if r == "commentThreads"}
    # m2 (recette) n'a aucun mot-clé : pas de commentaires. p1 : chaîne politique, gardée.
    assert commentees == {"m1", "m3", "p1"}
    assert bilan.videos_prefiltre == 3 and bilan.commentaires == 9


def test_shorts_une_seule_page(tmp_path: Path) -> None:
    faux = FauxYouTube(J1)
    _run(tmp_path, faux, FausseBase(SOURCES), _quotidien())
    base = FausseBase(SOURCES)
    _run(tmp_path / "b", faux, base, _quotidien())
    formats = {v["video_id"]: v["format"] for v in base.tables["videos"]}
    assert formats == {"m1": "long", "m2": "long", "m3": "short", "p1": "long"}


def test_invariant_aucun_pseudo_ni_identifiant_auteur_en_clair(tmp_path: Path) -> None:
    faux = FauxYouTube(J1)
    _, _, st = _run(tmp_path, faux, FausseBase(SOURCES), _quotidien())
    for chemin in partitions(st, "commentaires").values():
        octets = st.lire(chemin)
        assert PSEUDO.encode() not in octets
        assert AUTEUR_ID.encode() not in octets
        schema = pq.read_schema(pa.BufferReader(octets))  # pyright: ignore[reportUnknownMemberType]
        assert "auteur_hash" in schema.names
        assert not {"auteur", "pseudo", "auteur_channel_id"} & set(schema.names)
    lignes = _tous_commentaires(st)
    assert {ligne["auteur_hash"] for ligne in lignes} == {hash_auteur(AUTEUR_ID, SEL)}


def test_hash_stable_avec_le_meme_sel() -> None:
    assert hash_auteur(AUTEUR_ID, SEL) == hash_auteur(AUTEUR_ID, SEL)
    assert hash_auteur(AUTEUR_ID, SEL) != hash_auteur(
        AUTEUR_ID, b"un-autre-sel-tout-aussi-long-000000"
    )
    assert hash_auteur(None, SEL) is None


def test_invariant_commentaire_unique_date_de_sa_derniere_recuperation(tmp_path: Path) -> None:
    faux = FauxYouTube(J1)
    base = FausseBase(SOURCES)
    _, _, st = _run(tmp_path, faux, base, _quotidien(), J1)
    j2 = J1 + timedelta(days=1)
    _run(tmp_path, faux, base, _quotidien(maintenant=j2), j2)
    lignes = _tous_commentaires(st)
    ids = [ligne["comment_id"] for ligne in lignes]
    assert len(ids) == len(set(ids)) == 9
    assert {ligne["recupere_le"] for ligne in lignes} == {j2.date()}
    assert set(partitions(st, "commentaires")) == {j2.date()}  # partition J1 vidée et supprimée


def test_relancer_le_meme_jour_ne_cree_pas_de_doublon(tmp_path: Path) -> None:
    faux = FauxYouTube(J1)
    base = FausseBase(SOURCES)
    _, _, st = _run(tmp_path, faux, base, _quotidien())
    avant = len(faux.appels)
    _run(tmp_path, faux, base, _quotidien())
    assert not [a for a in faux.appels[avant:] if a[0] == "commentThreads"]
    assert len(_tous_commentaires(st)) == 9
    assert len(base.tables["videos"]) == 4


def test_unicite_avec_commentaires_non_re_recuperes(tmp_path: Path) -> None:
    st = StockageLocal(tmp_path)
    j1, j2 = date(2026, 10, 1), date(2026, 10, 2)
    ligne = {
        "video_id": "v",
        "source_id": "s",
        "auteur_hash": "h",
        "texte": "t",
        "likes": 0,
        "nb_reponses": 0,
        "publie_at": J1,
        "modifie_at": None,
    }
    enregistrer(
        st, "commentaires", j1, [{**ligne, "comment_id": "a"}, {**ligne, "comment_id": "b"}], j1
    )
    enregistrer(st, "commentaires", j2, [{**ligne, "comment_id": "b"}], j1)
    p1 = [x["comment_id"] for x in lire_partition(st, chemin_partition("commentaires", j1))]
    p2 = [x["comment_id"] for x in lire_partition(st, chemin_partition("commentaires", j2))]
    assert (p1, p2) == (["a"], ["b"])


def test_invariant_aucune_partition_de_plus_de_30_jours_apres_purge(tmp_path: Path) -> None:
    st = StockageLocal(tmp_path)
    aujourdhui = date(2026, 10, 31)
    for table in ("commentaires", "videos"):
        for n in range(45):
            st.ecrire(chemin_partition(table, aujourdhui - timedelta(days=n)), b"x")
    purger(st, aujourdhui)
    for table in ("commentaires", "videos"):
        jours = partitions(st, table)
        assert jours
        assert all((aujourdhui - j).days < 30 for j in jours)
        assert len(jours) == 30


def test_commentaires_fermes_pas_d_appel(tmp_path: Path) -> None:
    faux = FauxYouTube(J1, fermes=frozenset({"m1"}))
    _run(tmp_path, faux, FausseBase(SOURCES), _quotidien())
    assert ("commentThreads", "m1") not in faux.appels


def test_commentaires_desactives_403_ne_bloque_pas(tmp_path: Path) -> None:
    faux = FauxYouTube(J1)

    def transport(url: str, params: dict[str, str]) -> Any:
        if url.endswith("commentThreads") and params["videoId"] == "m1":
            r = requests.Response()
            r.status_code = 403
            r._content = b'{"error": {"errors": [{"reason": "commentsDisabled"}]}}'  # pyright: ignore[reportPrivateUsage]
            raise requests.HTTPError(response=r)
        return faux(url, params)

    yt = YouTube("cle", 1000, transport=transport)
    bilan = collecter(
        _quotidien(), yt, FausseBase(SOURCES), StockageLocal(tmp_path), charger(), SEL, J1
    )
    assert bilan.commentaires == 6


def test_dry_run_n_ecrit_rien_et_estime_les_pages(tmp_path: Path) -> None:
    faux = FauxYouTube(J1)
    base = FausseBase(SOURCES)
    bilan, _, st = _run(tmp_path, faux, base, _quotidien(dry_run=True))
    assert not [a for a in faux.appels if a[0] == "commentThreads"]
    assert bilan.pages_estimees == 2 + 1 + 2  # m1 long, m3 short, p1 long
    assert base.tables["videos"] == [] and not partitions(st, "commentaires")


def test_backfill_arret_propre_puis_reprise_sans_doublon(tmp_path: Path) -> None:
    faux = FauxYouTube(datetime(2026, 9, 3, 12, tzinfo=UTC))
    base = FausseBase(SOURCES)
    p = Parametres(
        "backfill",
        datetime(2026, 9, 1, tzinfo=UTC),
        datetime(2026, 9, 8, tzinfo=UTC),
        False,
    )
    # Budget : 2 parcours + 2 lots de détails + 1 page de commentaires (le faux n'a qu'une page).
    bilan1, yt1, st = _run(tmp_path, faux, base, p, J1, budget=5)
    assert bilan1.arret_budget and yt1.consomme <= yt1.budget
    assert bilan1.videos_commentees == 1  # m1 tient dans le budget, m3 et p1 non
    avant = len(faux.appels)
    bilan2, _, _ = _run(tmp_path, faux, base, p, J1, budget=1000)
    nouveaux = faux.appels[avant:]
    assert not [
        a for a in nouveaux if a[0] in ("playlistItems", "videos")
    ]  # reprise sans reparcours
    assert not bilan2.arret_budget and bilan2.videos_commentees == 2
    ids = [ligne["comment_id"] for ligne in _tous_commentaires(st)]
    assert len(ids) == len(set(ids)) == 9
    _, yt3, _ = _run(tmp_path, faux, base, p, J1, budget=1000)
    assert yt3.consomme == 0  # tout est fait : rien à refaire


def _erreur_http(statut: int, raison: str) -> requests.HTTPError:
    r = requests.Response()
    r.status_code = statut
    r._content = f'{{"error": {{"errors": [{{"reason": "{raison}"}}]}}}}'.encode()  # pyright: ignore[reportPrivateUsage]
    return requests.HTTPError(response=r)


def test_video_indisponible_sautee_et_marquee(tmp_path: Path) -> None:
    faux = FauxYouTube(J1)

    def transport(url: str, params: dict[str, str]) -> Any:
        if url.endswith("commentThreads") and params["videoId"] == "m1":
            raise _erreur_http(404, "videoNotFound")
        return faux(url, params)

    base = FausseBase(SOURCES)
    st = StockageLocal(tmp_path)
    yt = YouTube("cle", 1000, transport=transport)
    bilan = collecter(_quotidien(), yt, base, st, charger(), SEL, J1)
    assert bilan.videos_indisponibles == 1 and bilan.commentaires == 6
    m1 = next(v for v in base.tables["videos"] if v["video_id"] == "m1")
    assert m1["commentaires_fermes"] and m1["derniere_collecte"] is None
    assert len(_tous_commentaires(st)) == 6


def test_quota_youtube_epuise_arret_propre(tmp_path: Path) -> None:
    faux = FauxYouTube(J1)

    def transport(url: str, params: dict[str, str]) -> Any:
        if url.endswith("commentThreads") and params["videoId"] == "m3":
            raise _erreur_http(403, "quotaExceeded")
        return faux(url, params)

    st = StockageLocal(tmp_path)
    yt = YouTube("cle", 1000, transport=transport)
    bilan = collecter(_quotidien(), yt, FausseBase(SOURCES), st, charger(), SEL, J1)
    assert bilan.arret_budget and bilan.videos_commentees == 1
    assert len(_tous_commentaires(st)) == 3  # m1 collectée avant l'arrêt, bien stockée


def test_erreur_imprevue_sauve_ce_qui_est_collecte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import radar.collecte

    monkeypatch.setattr(radar.collecte, "LOT_ECRITURE", 1)
    faux = FauxYouTube(J1)

    def transport(url: str, params: dict[str, str]) -> Any:
        if url.endswith("commentThreads") and params["videoId"] == "p1":
            raise requests.ConnectionError("coupure réseau")
        return faux(url, params)

    base = FausseBase(SOURCES)
    st = StockageLocal(tmp_path)
    yt = YouTube("cle", 1000, transport=transport)
    with pytest.raises(requests.ConnectionError):
        collecter(_quotidien(), yt, base, st, charger(), SEL, J1)
    assert len(_tous_commentaires(st)) == 6  # m1 et m3 sauvés avant l'erreur
    collectees = {v["video_id"] for v in base.tables["videos"] if v["derniere_collecte"]}
    assert collectees == {"m1", "m3"}
    # La relance ne refait que p1.
    bilan = collecter(
        _quotidien(), YouTube("cle", 1000, transport=faux), base, st, charger(), SEL, J1
    )
    assert bilan.videos_commentees == 1 and len(_tous_commentaires(st)) == 9


def test_transport_reessaie_et_masque_la_cle(monkeypatch: pytest.MonkeyPatch) -> None:
    import radar.youtube

    reponses = [500, 200]

    def get(url: str, params: dict[str, str], timeout: int) -> requests.Response:
        r = requests.Response()
        r.status_code = reponses.pop(0) if reponses else 404
        r._content = b'{"items": []}'  # pyright: ignore[reportPrivateUsage]
        return r

    monkeypatch.setattr(radar.youtube.requests, "get", get)

    def dormir(secondes: float) -> None:
        return None

    monkeypatch.setattr(radar.youtube.time, "sleep", dormir)
    assert radar.youtube._transport_http("https://x/videos", {"key": "CLESECRETE"}) == {"items": []}  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(requests.HTTPError) as e:
        radar.youtube._transport_http("https://x/videos", {"key": "CLESECRETE"})  # pyright: ignore[reportPrivateUsage]
    assert "CLESECRETE" not in str(e.value)


@pytest.mark.parametrize(
    ("titre", "attendu"),
    [
        ("Présidentielle : le débat", True),
        ("Le 49.3 expliqué", True),
        ("L'Assemblée nationale vote", True),
        ("MÉLENCHON répond", True),
        ("Recette de crêpes", False),
        ("Réponse à vos questions", False),  # « réponse » ne contient pas de mot-clé entier
    ],
)
def test_prefiltre_mots_entiers_sans_accents(titre: str, attendu: bool) -> None:
    assert charger().correspond(titre) is attendu
