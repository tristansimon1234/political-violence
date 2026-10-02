"""Classification en masse : aucun texte, identifiants hashés, idempotence, budget, position."""

import io
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

import pyarrow.parquet as pq
import pytest

from radar.classement import (
    DOSSIER_CLASSE,
    SCHEMA_CLASSE,
    Video,
    chemin_partition,
    classer,
    deja_classes,
    id_commentaire,
)
from radar.llm import ClientClaude, ClientJev
from radar.storage import StockageLocal, enregistrer

SEL = b"s" * 32
TEXTE = "TexteCommentaireTresReconnaissable"
TITRE = "TitreVideoTresReconnaissable"
CHAINE = "ChaineTresReconnaissable"
AUTEUR = "a" * 32
JOUR = date(2026, 10, 2)


class FauxJev:
    def __init__(self) -> None:
        self.envois: list[dict[str, Any]] = []

    def __call__(self, url: str, entetes: dict[str, str], corps: dict[str, Any]) -> dict[str, Any]:
        self.envois.append(corps)
        answers: dict[str, Any] = {
            "politique": {"probability": 0.9},
            "theme": {"choice": "retraites", "confidence": 0.8},
            "tonalite": {"choice": "negative", "confidence": 0.7},
            "hostilite": {"noul": 0.1},
        }
        if "position" in corps["questions"]:
            answers["position"] = {"choice": "desaccord_video", "confidence": 0.6}
        return {
            "answers": answers,
            "usage": {"input_tokens": 1000},
            "provider_metadata": {"gateway": {"cost": "0.0001"}},
        }


def _commentaires(n: int, video: str = "v1") -> list[dict[str, Any]]:
    return [
        {
            "comment_id": f"Ugx{video}{i}",
            "video_id": video,
            "source_id": "s1",
            "auteur_hash": AUTEUR,
            "texte": f"{TEXTE} {i} @Pseudo https://lien.fr",
            "likes": 0,
            "nb_reponses": 0,
            "publie_at": datetime(2026, 9, 2, tzinfo=UTC),
            "modifie_at": None,
            "recupere_le": JOUR,
        }
        for i in range(n)
    ]


def _videos() -> dict[str, Video]:
    return {
        "v1": Video("v1", "s1", "media_natif", "long", CHAINE, TITRE, "opinion"),
        "v2": Video("v2", "s1", "media_natif", "short", CHAINE, TITRE, "info_factuelle"),
    }


def _lire(st: StockageLocal) -> list[dict[str, Any]]:
    table = pq.read_table(io.BytesIO(st.lire(chemin_partition(JOUR))))  # pyright: ignore[reportUnknownMemberType]
    return table.to_pylist()


def test_aucun_texte_identifiants_hashes_et_position(tmp_path: Path) -> None:
    st = StockageLocal(tmp_path)
    faux = FauxJev()
    jev = ClientJev(1.0, cle="x", transport=faux)
    comms = _commentaires(5, "v1") + _commentaires(5, "v2")
    bilan = classer(st, jev, comms, _videos(), SEL, JOUR, paralleles=4, lot=3)
    assert (bilan.a_classer, bilan.classes, bilan.erreurs) == (10, 10, 0)
    lignes = _lire(st)
    assert len(lignes) == 10
    assert set(SCHEMA_CLASSE.names).isdisjoint({"texte", "titre", "chaine", "comment_id", "auteur"})
    brut = json.dumps(lignes, default=str)
    for interdit in (TEXTE, TITRE, CHAINE, "Ugxv1", "Pseudo", "lien.fr"):
        assert interdit not in brut
    assert {li["id"] for li in lignes} == {id_commentaire(c["comment_id"], SEL) for c in comms}
    # Position seulement sous une vidéo d'opinion.
    for li in lignes:
        if li["nature"] == "opinion":
            assert li["position"] == "desaccord_video"
        else:
            assert li["position"] is None and li["confiance_position"] is None
    # Minimisation des envois : ni auteur ni identifiant, texte masqué.
    envoye = json.dumps(faux.envois)
    assert "Ugx" not in envoye and AUTEUR not in envoye and "Pseudo" not in envoye


def test_idempotent_et_reprise(tmp_path: Path) -> None:
    st = StockageLocal(tmp_path)
    faux = FauxJev()
    comms = _commentaires(6)
    classer(st, ClientJev(1.0, cle="x", transport=faux), comms[:4], _videos(), SEL, JOUR)
    n = len(faux.envois)
    bilan = classer(st, ClientJev(1.0, cle="x", transport=faux), comms, _videos(), SEL, JOUR)
    assert bilan.a_classer == 2 and len(faux.envois) == n + 2  # seuls les nouveaux partent
    assert len(_lire(st)) == 6 and len(deja_classes(st)) == 6
    bilan = classer(st, ClientJev(1.0, cle="x", transport=faux), comms, _videos(), SEL, JOUR)
    assert bilan.a_classer == 0 and len(_lire(st)) == 6  # aucun doublon


def test_arret_au_budget_ecrit_ce_qui_est_classe(tmp_path: Path) -> None:
    st = StockageLocal(tmp_path)
    jev = ClientJev(0.00035, cle="x", transport=FauxJev())  # ~4 appels à 0,0001 $
    bilan = classer(st, jev, _commentaires(20), _videos(), SEL, JOUR, paralleles=1, lot=2)
    assert bilan.arret_budget and 0 < bilan.classes < 20
    assert len(_lire(st)) == bilan.classes
    # Relance : reprend sans reclasser.
    bilan2 = classer(
        st, ClientJev(1.0, cle="x", transport=FauxJev()), _commentaires(20), _videos(), SEL, JOUR
    )
    assert bilan2.a_classer == 20 - bilan.classes and len(_lire(st)) == 20


def test_video_inconnue_ignoree(tmp_path: Path) -> None:
    st = StockageLocal(tmp_path)
    bilan = classer(
        st,
        ClientJev(1.0, cle="x", transport=FauxJev()),
        _commentaires(3, "v9"),
        _videos(),
        SEL,
        JOUR,
    )
    assert bilan.a_classer == 0 and DOSSIER_CLASSE not in [p.name for p in tmp_path.iterdir()]


# --- Script de bout en bout (Supabase et modèles simulés) ---


class _Usage:
    input_tokens = 300
    output_tokens = 30


class _Reponse:
    def __init__(self, sortie: Any) -> None:
        self.parsed_output = sortie
        self.stop_reason = "end_turn"
        self.usage = _Usage()


class FauxAnthropic:
    def __init__(self) -> None:
        self.messages = self
        self.envois = 0

    def parse(self, **kwargs: Any) -> _Reponse:
        self.envois += 1
        return _Reponse(kwargs["output_format"](nature_video="opinion", resume="r"))


class FausseBase:
    def __init__(self) -> None:
        self.videos = [
            {"video_id": "v1", "source_id": "s1", "format": "long", "nature": None},
            {"video_id": "v2", "source_id": "s1", "format": "short", "nature": "info_factuelle"},
        ]
        self.modifs: list[tuple[dict[str, str], dict[str, Any]]] = []

    def select(self, table: str, filtres: dict[str, str]) -> list[dict[str, Any]]:
        if table == "sources":
            return [{"id": "s1", "type": "media_natif", "nom": CHAINE}]
        return self.videos

    def modifier(self, table: str, filtres: dict[str, str], valeurs: dict[str, Any]) -> None:
        self.modifs.append((filtres, valeurs))


def test_script_dry_run_puis_classement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import classification as script

    brut = StockageLocal(tmp_path / "brut")
    enregistrer(
        brut,
        "videos",
        JOUR,
        [
            {"video_id": v, "source_id": "s1", "titre": TITRE, "description": "", "tags": []}
            for v in ("v1", "v2")
        ],
        depuis=JOUR,
    )
    enregistrer(
        brut, "commentaires", JOUR, _commentaires(3, "v1") + _commentaires(2, "v2"), depuis=JOUR
    )
    base, faux_jev, faux_claude = FausseBase(), FauxJev(), FauxAnthropic()
    monkeypatch.setenv("SUPABASE_URL", "http://x")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_x")
    monkeypatch.setenv("RADAR_SEL", SEL.decode())

    def jev(budget_usd: float) -> ClientJev:
        return ClientJev(budget_usd, cle="x", transport=faux_jev)

    def claude(budget_usd: float) -> ClientClaude:
        return ClientClaude(budget_usd, client=cast(Any, faux_claude))

    monkeypatch.setattr(script, "Supabase", lambda url, cle: base)  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType]
    monkeypatch.setattr(script, "ClientJev", jev)
    monkeypatch.setattr(script, "ClientClaude", claude)

    def lancer(*args: str) -> str:
        monkeypatch.setattr(
            sys, "argv", ["classification", *args, "--stockage-local", str(tmp_path)]
        )
        assert script.main() == 0
        return capsys.readouterr().out

    sortie = lancer("--dry-run")
    assert "à classer : 5" in sortie and "Vidéos sans nature : 1" in sortie
    assert not faux_jev.envois and faux_claude.envois == 0 and not base.modifs
    sortie = lancer()
    assert "Commentaires classés : 5 / 5" in sortie and TEXTE not in sortie
    assert faux_claude.envois == 1  # seule v1 n'avait pas de nature
    assert base.modifs == [
        (
            {"video_id": "in.(v1)"},
            {"nature": "opinion", "nature_classee_le": base.modifs[0][1]["nature_classee_le"]},
        )
    ]
    sortie = lancer()
    assert "à classer : 0" in sortie
