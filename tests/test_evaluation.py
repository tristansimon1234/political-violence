"""Étape 4 : minimisation des entrées, position, échantillon stratifié, étiquetage, rapport."""

import json
import random
from datetime import date
from pathlib import Path
from typing import Any, cast

import pytest

from radar.classification import (
    Classement,
    ClassementCommentaire,
    classement_jev,
    masquer,
    normaliser,
    questions_jev,
)
from radar.evaluation import (
    MAX_PAR_VIDEO,
    Candidate,
    Couts,
    Etiquette,
    Ligne,
    Volume,
    candidates,
    cascade,
    classer_claude,
    classer_jev,
    comparer,
    echantillonner,
    ecrire_echantillon,
    ecrire_resultats,
    fichier_etiquetage,
    lire_echantillon,
    lire_etiquettes,
    lire_resultats,
    rapport,
    repartir,
)
from radar.llm import (
    BudgetDepasse,
    ClientClaude,
    ClientJev,
    QuestionChoix,
    QuestionOuiNon,
    RepChoix,
    ReponseInvalide,
    RepOuiNon,
    lire_reponse_jev,
)
from radar.storage import StockageLocal, purger

TITRE = "TitreVideoTresReconnaissable"
CHAINE = "ChaineTresReconnaissable"
TEXTE = "TexteCommentaireTresReconnaissable"
AUTEUR_HASH = "a" * 32


def test_masquer_mentions_et_url() -> None:
    t = masquer("Merci @Jean_Dupont ! Voir https://exemple.fr/x?y=1 et www.site.com @x.y-z")
    assert "Jean_Dupont" not in t and "exemple.fr" not in t and "site.com" not in t
    assert t.count("@[mention]") == 2 and t.count("[lien]") == 2
    assert masquer(t) == t  # idempotent
    assert masquer("contact@exemple.fr") == "contact@exemple.fr"  # pas une mention


# --- Position jamais calculée sur une vidéo factuelle ---


def test_position_nulle_sur_video_factuelle() -> None:
    c = ClassementCommentaire(
        numero=1,
        est_politique=True,
        themes=["immigration"],
        position="accord_video",
        emotion="colere",
    )
    assert normaliser(c, "info_factuelle").position is None
    assert normaliser(c, "opinion_debat").position == "accord_video"
    assert "position" not in questions_jev("info_factuelle")
    assert "position" in questions_jev("opinion_debat")


def _reps(p_politique: float, conf_theme: float = 0.9) -> dict[str, RepOuiNon | RepChoix]:
    return {
        "politique": RepOuiNon(p_politique, max(p_politique, 1 - p_politique)),
        "theme": RepChoix(
            "retraites",
            {"retraites": 0.6, "economie_emploi": 0.35, "sante": 0.05},
            conf_theme,
        ),
        "emotion": RepChoix("colere", {"colere": 0.8}, 0.8),
        "position": RepChoix("nuance", {"nuance": 0.7}, 0.7),
    }


def test_classement_jev() -> None:
    c = classement_jev(_reps(0.9), "opinion_debat")
    assert c.themes == ("retraites", "economie_emploi")  # principal d'abord, secondaire ≥ 0,3
    assert c.position == "nuance" and c.confiance == 0.7
    f = classement_jev(_reps(0.9), "info_factuelle")
    assert f.position is None and f.confiance == 0.8
    n = classement_jev(_reps(0.2, conf_theme=0.1), "info_factuelle")
    assert not n.est_politique and n.themes == () and n.confiance == 0.8  # thème ignoré


def test_normaliser_limite_les_themes() -> None:
    c = ClassementCommentaire(
        numero=1,
        est_politique=True,
        themes=["sante", "sante", "logement", "education", "securite"],
        position=None,
        emotion="neutre",
    )
    assert normaliser(c, "opinion_debat").themes == ("sante", "logement", "education")
    c2 = c.model_copy(update={"est_politique": False})
    assert normaliser(c2, "opinion_debat").themes == ()


# --- Réponses Jev ---

Q: dict[str, QuestionOuiNon | QuestionChoix] = {
    "politique": QuestionOuiNon("?"),
    "theme": QuestionChoix("?", {"retraites": "", "sante": ""}),
}


def test_lire_reponse_jev_formats() -> None:
    brut = {
        "answers": {
            "politique": {"type": "noul", "noul": 0.8},
            "theme": {"type": "choice", "choice": "sante", "probabilities": {"sante": 0.7}},
        }
    }
    r = lire_reponse_jev(Q, brut)
    assert r["politique"] == RepOuiNon(0.8, 0.8)
    assert isinstance(r["theme"], RepChoix) and r["theme"].confiance == 0.7
    brut2 = {
        "answers": {
            "politique": {"probabilities": {"true": 0.3, "false": 0.7}, "confidence": 0.65},
            "theme": {"value": "retraites", "confidence": 0.9},
        }
    }
    r2 = lire_reponse_jev(Q, brut2)
    assert r2["politique"] == RepOuiNon(0.3, 0.65)


@pytest.mark.parametrize(
    "brut",
    [
        {},
        {"answers": {"politique": {"probability": 0.5}}},
        {"answers": {"politique": {"probability": 2}, "theme": {"choice": "sante"}}},
        {"answers": {"politique": {"probability": 0.5}, "theme": {"choice": "inconnu"}}},
    ],
)
def test_lire_reponse_jev_invalide(brut: dict[str, Any]) -> None:
    with pytest.raises(ReponseInvalide):
        lire_reponse_jev(Q, brut)


def test_budget_jev() -> None:
    def transport(url: str, entetes: dict[str, str], corps: dict[str, Any]) -> dict[str, Any]:
        return {
            "answers": {"politique": {"probability": 0.9}, "theme": {"choice": "sante"}},
            "providerMetadata": {"gateway": {"cost": "0.01"}},
        }

    jev = ClientJev(budget_usd=0.02, cle="x", transport=transport)
    jev.evaluer("état", Q)
    jev.evaluer("état", Q)
    with pytest.raises(BudgetDepasse):
        jev.evaluer("état", Q)
    assert jev.compteur.appels == 2 and jev.compteur.cout_usd == pytest.approx(0.02)


# --- Faux modèles : capture de tout ce qui est envoyé ---


class FauxJev:
    def __init__(self) -> None:
        self.envois: list[str] = []

    def __call__(self, url: str, entetes: dict[str, str], corps: dict[str, Any]) -> dict[str, Any]:
        self.envois.append(json.dumps(corps, ensure_ascii=False))
        conf = 0.95 if "0" in corps["state"]["comment"][-3:] else 0.55
        answers: dict[str, Any] = {
            "politique": {"probability": conf},
            "theme": {"choice": "retraites", "confidence": conf},
            "emotion": {"choice": "colere", "confidence": conf},
        }
        if "position" in corps["questions"]:
            answers["position"] = {"choice": "nuance", "confidence": conf}
        return {"answers": answers, "usage": {"inputTokens": 200}}


class _Usage:
    input_tokens = 300
    output_tokens = 50


class _Reponse:
    def __init__(self, sortie: Any) -> None:
        self.parsed_output = sortie
        self.usage = _Usage()
        self.stop_reason = "end_turn"


class FauxAnthropic:
    def __init__(self) -> None:
        self.envois: list[str] = []
        self.messages = self

    def parse(self, **kwargs: Any) -> _Reponse:
        self.envois.append(json.dumps(kwargs["messages"], ensure_ascii=False) + kwargs["system"])
        sortie = kwargs["output_format"]
        message: str = kwargs["messages"][0]["content"]
        n = message.count("\n[")
        return _Reponse(
            sortie.model_validate(
                {
                    "commentaires": [
                        {
                            "numero": i,
                            "est_politique": True,
                            "themes": ["retraites"],
                            "position": "accord_video",
                            "emotion": "colere",
                        }
                        for i in range(1, n + 1)
                    ]
                }
            )
        )


def _lignes(n: int = 12) -> list[Ligne]:
    return [
        Ligne(
            ref=f"C{i:03d}",
            comment_id=f"UgxCOMMENTID{i}",
            video_id=f"v{i % 3}",
            type_source=["media_traditionnel", "media_natif", "politique"][i % 3],
            format="long" if i % 2 else "short",
            nature="opinion_debat" if i % 4 else "info_factuelle",
            chaine=CHAINE,
            titre=TITRE,
            texte=masquer(f"{TEXTE} {i} @PseudoCite https://lien.fr"),
            verite=i <= 6,
            recupere_le=date(2026, 10, 2),
        )
        for i in range(1, n + 1)
    ]


def test_minimisation_des_envois() -> None:
    lignes = _lignes()
    faux_jev, faux_claude = FauxJev(), FauxAnthropic()
    jev = classer_jev(ClientJev(1.0, cle="x", transport=faux_jev), lignes)
    claude = classer_claude(ClientClaude(1.0, client=cast(Any, faux_claude)), lignes)
    assert len(jev) == len(claude) == len(lignes)
    envois = faux_jev.envois + faux_claude.envois
    for e in envois:
        assert "UgxCOMMENTID" not in e  # jamais l'identifiant du commentaire
        assert AUTEUR_HASH not in e and "auteur" not in e.lower() and "author" not in e.lower()
        assert "PseudoCite" not in e and "lien.fr" not in e  # mentions et URL masquées
    assert any(TEXTE in e and TITRE in e and CHAINE in e for e in envois)  # contexte vidéo
    zdr = [
        json.loads(e)["providerOptions"]["gateway"]["zeroDataRetention"] for e in faux_jev.envois
    ]
    assert all(zdr)
    # Position jamais conservée sur une vidéo factuelle, quel que soit le modèle.
    for li in lignes:
        if li.nature == "info_factuelle":
            assert jev[li.ref].position is None and claude[li.ref].position is None


# --- Échantillon stratifié ---


def test_repartir() -> None:
    assert repartir({"a": 100, "b": 100}, 50) == {"a": 25, "b": 25}
    assert repartir({"a": 3, "b": 100, "c": 100}, 51) == {"a": 3, "b": 24, "c": 24}
    assert repartir({"a": 3, "b": 4}, 50) == {"a": 3, "b": 4}
    assert sum(repartir({"a": 7, "b": 9, "c": 11}, 20).values()) == 20


def _corpus() -> tuple[list[Candidate], dict[str, list[dict[str, Any]]]]:
    cands: list[Candidate] = []
    comms: dict[str, list[dict[str, Any]]] = {}
    for t in ("media_traditionnel", "media_natif", "politique"):
        for f in ("short", "long"):
            for k in range(8):
                vid = f"{t}-{f}-{k}"
                cands.append(Candidate(vid, t, f, CHAINE, TITRE, ""))
                comms[vid] = [
                    {
                        "comment_id": f"{vid}-c{j}",
                        "texte": f"commentaire {j}",
                        "recupere_le": date(2026, 10, 2 + j % 2),
                    }
                    for j in range(20)
                ]
    return cands, comms


def test_echantillon_stratifie() -> None:
    cands, comms = _corpus()
    natures = {
        c.video_id: ("opinion_debat" if int(c.video_id[-1]) % 2 else "info_factuelle")
        for c in cands
    }
    lignes = echantillonner(cast(Any, natures), cands, comms, random.Random(1), n=120, n_verite=24)
    assert len(lignes) == 120 and sum(li.verite for li in lignes) == 24
    assert len({li.ref for li in lignes}) == 120 and len({li.comment_id for li in lignes}) == 120
    par_strate: dict[tuple[str, str, str], int] = {}
    verite: dict[tuple[str, str, str], int] = {}
    for li in lignes:
        par_strate[li.strate] = par_strate.get(li.strate, 0) + 1
        verite[li.strate] = verite.get(li.strate, 0) + int(li.verite)
    assert len(par_strate) == 12 and set(par_strate.values()) == {10}  # égal entre strates
    assert set(verite.values()) == {2}
    par_video: dict[str, int] = {}
    for li in lignes:
        par_video[li.video_id] = par_video.get(li.video_id, 0) + 1
    assert max(par_video.values()) <= MAX_PAR_VIDEO
    # Reproductible avec la même graine.
    again = echantillonner(cast(Any, natures), cands, comms, random.Random(1), n=120, n_verite=24)
    assert [li.comment_id for li in again] == [li.comment_id for li in lignes]


def test_candidates_par_cellule() -> None:
    sources = {"s1": {"type": "media_natif", "nom": CHAINE}}
    videos = [{"video_id": f"v{i}", "source_id": "s1", "format": "long"} for i in range(50)]
    bruts = {f"v{i}": {"titre": TITRE, "description": ""} for i in range(50)}
    nb = {f"v{i}": (5 if i % 2 else 1) for i in range(50)}
    c = candidates(videos, sources, bruts, nb, random.Random(0))
    assert len(c) == 25 and all(nb[x.video_id] >= 3 for x in c)


# --- Étiquetage manuel ---


def test_etiquetage_aller_retour() -> None:
    lignes = _lignes()
    csv_bytes = fichier_etiquetage(lignes)
    texte = csv_bytes.decode("utf-8-sig")
    assert texte.count("\n") == 1 + sum(li.verite for li in lignes)
    lignes_csv = texte.splitlines()
    remplies = [lignes_csv[0]]
    for ligne in lignes_csv[1:]:
        champs = ligne.split(";")
        ref = champs[0]
        nature = next(li.nature for li in lignes if li.ref == ref)
        champs[7] = "retraites+sante" if ref != "C002" else "aucun"
        champs[8] = "desaccord_video" if nature == "opinion_debat" else "-"
        champs[9] = "colere"
        remplies.append(";".join(champs))
    remplies[-1] = ";".join([*remplies[-1].split(";")[:7], "", "", ""])  # ligne non remplie
    etiquettes = lire_etiquettes(("\n".join(remplies) + "\n").encode(), lignes)
    assert len(etiquettes) == sum(li.verite for li in lignes) - 1
    assert etiquettes["C002"].est_politique is False and etiquettes["C002"].themes == ()
    assert etiquettes["C001"].themes == ("retraites", "sante")


def test_etiquetage_invalide_signale() -> None:
    lignes = _lignes()
    entete = (
        "ref;categorie;format;nature_video;chaine;titre_video;commentaire;themes;position;emotion"
    )
    mauvais = f"{entete}\nC001;x;x;x;x;x;x;inflation;;joie\nC999;x;x;x;x;x;x;sante;-;colere\n"
    with pytest.raises(ValueError) as e:
        lire_etiquettes(mauvais.encode(), lignes)
    message = str(e.value)
    assert "C001 : thème inconnu" in message and "C001 : émotion" in message
    assert "C001 : position" in message and "C999 : référence inconnue" in message


# --- Rapport : agrégats seulement ---


def _cl(conf: float | None, ok: bool = True) -> Classement:
    return Classement(True, ("retraites",) if ok else ("sante",), None, "colere", conf)


def test_cascade() -> None:
    jev = {"a": _cl(0.95), "b": _cl(0.4, ok=False)}
    claude = {"a": _cl(None, ok=False), "b": _cl(None)}
    c = cascade(jev, claude, 0.7)
    assert c["a"] is jev["a"] and c["b"] is claude["b"]


def test_comparer_dimensions() -> None:
    ref = Etiquette(True, ("retraites", "sante"), None, "colere")
    d = comparer(Classement(True, ("sante", "retraites"), None, "colere"), ref)
    assert d["theme_principal"] is False and d["theme_commun"] is True
    assert d["position"] is None and d["complet"] is False
    non = comparer(Classement(False, (), None, "neutre"), Etiquette(False, (), None, "neutre"))
    assert non["theme_principal"] is None and non["complet"] is True


def test_rapport_sans_texte_ni_titre(tmp_path: Path) -> None:
    lignes = _lignes()
    faux_jev, faux_claude = FauxJev(), FauxAnthropic()
    jev = classer_jev(ClientJev(1.0, cle="x", transport=faux_jev), lignes)
    claude = classer_claude(ClientClaude(1.0, client=cast(Any, faux_claude)), lignes)
    etiquettes = {
        li.ref: Etiquette(
            True,
            ("retraites",),
            "accord_video" if li.nature == "opinion_debat" else None,
            "colere",
        )
        for li in lignes
        if li.verite
    }
    texte = rapport(
        lignes,
        jev,
        claude,
        etiquettes,
        Couts(0.01, 12, 0.05, 12, 0.01),
        Volume(7000, 7),
        date(2026, 10, 2),
    )
    for interdit in (TEXTE, TITRE, CHAINE, "UgxCOMMENTID", "PseudoCite"):
        assert interdit not in texte
    assert "Seuil de reprise" in texte and "Recommandation" in texte
    assert "< 0,5" in texte and "≥ 0,9" in texte
    # Projection : 1 000 commentaires / jour jusqu'au 02/05/2027 inclus.
    assert Volume(7000, 7).campagne(date(2026, 10, 2)) == (213, 213000)


# --- Fichiers du bucket : aller-retour et purge à 30 jours ---


def test_fichiers_evaluation_et_purge(tmp_path: Path) -> None:
    st = StockageLocal(tmp_path)
    lignes = _lignes()
    jour = date(2026, 10, 2)
    ecrire_echantillon(st, jour, lignes)
    assert lire_echantillon(st, jour) == lignes
    res = {"jev": {"C001": _cl(0.8)}, "claude": {"C001": _cl(None)}}
    ecrire_resultats(st, jour, res)
    assert lire_resultats(st, jour) == res
    st.ecrire("evaluation/2026-10-02-etiquetage-rempli.csv", b"x")
    st.ecrire("evaluation/sans-date.csv", b"x")
    assert purger(st, date(2026, 10, 31)) == ["evaluation/sans-date.csv"]  # 29 jours : gardés
    supprimes = purger(st, date(2026, 11, 1))  # 30 jours : tout part
    assert len(supprimes) == 3 and st.lister("evaluation") == []


# --- Script de bout en bout (faux modèles, stockage local) ---


class FausseBaseEval:
    def __init__(self, videos: list[dict[str, Any]], sources: list[dict[str, Any]]) -> None:
        self.tables = {"videos": videos, "sources": sources}

    def select(self, table: str, filtres: dict[str, str]) -> list[dict[str, Any]]:
        return list(self.tables[table])


class FauxAnthropicNature(FauxAnthropic):
    def parse(self, **kwargs: Any) -> _Reponse:
        if kwargs["output_format"].__name__ == "ReponseNatureVideo":
            self.envois.append(kwargs["messages"][0]["content"])
            return _Reponse(kwargs["output_format"](nature_video="opinion_debat"))
        return super().parse(**kwargs)


def test_script_preparer_evaluer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import sys

    import evaluation as script
    from radar.storage import enregistrer

    st = StockageLocal(tmp_path)
    jour = date(2026, 10, 2)
    sources = [{"id": "s1", "type": "media_traditionnel", "nom": CHAINE}]
    videos = [
        {"video_id": f"v{i}", "source_id": "s1", "format": "long", "publiee_at": "2026-09-01"}
        for i in range(4)
    ]
    enregistrer(
        st,
        "videos",
        jour,
        [
            {"video_id": f"v{i}", "source_id": "s1", "titre": TITRE, "description": "", "tags": []}
            for i in range(4)
        ],
        depuis=jour,
    )
    enregistrer(
        st,
        "commentaires",
        jour,
        [
            {
                "comment_id": f"v{i}-c{j}",
                "video_id": f"v{i}",
                "source_id": "s1",
                "auteur_hash": AUTEUR_HASH,
                "texte": f"{TEXTE} {j}",
                "likes": 0,
                "nb_reponses": 0,
                "publie_at": None,
                "modifie_at": None,
            }
            for i in range(4)
            for j in range(6)
        ],
        depuis=jour,
    )
    faux_claude, faux_jev = FauxAnthropicNature(), FauxJev()
    monkeypatch.setenv("SUPABASE_URL", "http://x")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_x")

    def base(url: str, cle: str) -> FausseBaseEval:
        return FausseBaseEval(videos, sources)

    def claude(budget_usd: float) -> ClientClaude:
        return ClientClaude(budget_usd, client=cast(Any, faux_claude))

    def jev(budget_usd: float) -> ClientJev:
        return ClientJev(budget_usd, cle="x", transport=faux_jev)

    monkeypatch.setattr(script, "Supabase", base)
    monkeypatch.setattr(script, "ClientClaude", claude)
    monkeypatch.setattr(script, "ClientJev", jev)

    def lancer(*args: str) -> str:
        monkeypatch.setattr(sys, "argv", ["evaluation", *args, "--stockage-local", str(tmp_path)])
        assert script.main() == 0
        return capsys.readouterr().out

    sortie = lancer("preparer")
    assert "à étiqueter" in sortie
    rapport_ = lancer("evaluer")
    assert "Étiquettes absentes" in rapport_
    for interdit in (TEXTE, TITRE, CHAINE, AUTEUR_HASH):
        assert interdit not in sortie and interdit not in rapport_
    # Étiquetage rempli puis nouvelle évaluation, sans nouvel appel aux modèles.
    appels = len(faux_jev.envois)
    brut = st.lire(f"evaluation/{jour}-etiquetage.csv").decode("utf-8-sig").splitlines()
    rempli = [brut[0]] + [
        ";".join([*x.split(";")[:7], "retraites", "accord_video", "colere"]) for x in brut[1:]
    ]
    st.ecrire(f"evaluation/{jour}-etiquetage-rempli.csv", "\n".join(rempli).encode())
    rapport_ = lancer("evaluer")
    assert (
        "Justesse face aux étiquettes de Tristan" in rapport_
        and "Étiquettes absentes" not in rapport_
    )
    assert len(faux_jev.envois) == appels
    assert "Recommandation" in rapport_ and TEXTE not in rapport_


def test_corps_jev_protocole_typesafe() -> None:
    """Schéma de requête du paquet officiel typesafe-sdk 0.7.2 (POST /v1/systemone)."""
    jev = ClientJev(1.0, cle="x", transport=FauxJev())
    corps = jev.corps("état", questions_jev("opinion_debat"))
    assert corps["model"] == "typesafe-ai/jev" and corps["state"] == "état"
    q = corps["questions"]
    assert q["politique"]["type"] == "noul" and set(q["politique"]["criteria"]) == {"true", "false"}
    assert q["theme"]["type"] == "choice" and "retraites" in q["theme"]["criteria"]
    assert set(q) == {"politique", "theme", "emotion", "position"}


def test_cout_jev_reel_de_la_gateway() -> None:
    """Réponse réelle de la sonde du 01/10/2026 (texte fictif) : coût lu, pas estimé."""
    from radar.llm import cout_jev

    brut = {
        "model": "typesafe-ai/jev",
        "answers": {"politique": {"type": "noul", "noul": 0.95}},
        "usage": {"input_tokens": 1178, "output_tokens": 290},
        "provider_metadata": {"gateway": {"cost": "0.000049476", "surchargeCost": "0"}},
    }
    assert cout_jev(brut) == (1178, pytest.approx(0.000049476))


def test_fichier_synthetique_et_commande(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import sys

    import evaluation as script
    from radar.evaluation import charger_synthetique

    source = Path(__file__).parents[1] / "evaluation" / "synthetique_v1.csv"
    donnees = source.read_bytes()
    lignes = charger_synthetique(donnees, date(2026, 10, 2))
    assert len(lignes) == 100 and len({li.ref for li in lignes}) == 100
    assert {li.nature for li in lignes} == {"info_factuelle", "opinion_debat"}
    assert len(lire_etiquettes(donnees, lignes)) == 100  # étiqueté par Tristan le 01/10

    texte = donnees.decode("utf-8-sig").splitlines()
    rempli = [texte[0]]
    for x in texte[1:]:
        champs = x.split(";")
        position = "nuance" if champs[3] == "opinion_debat" else "-"
        rempli.append(";".join([*champs[:7], "retraites", position, "colere"]))
    fichier = tmp_path / "rempli.csv"
    fichier.write_text("\n".join(rempli), encoding="utf-8")

    faux_claude, faux_jev = FauxAnthropic(), FauxJev()

    def claude(budget_usd: float) -> ClientClaude:
        return ClientClaude(budget_usd, client=cast(Any, faux_claude))

    def jev(budget_usd: float) -> ClientJev:
        return ClientJev(budget_usd, cle="x", transport=faux_jev)

    monkeypatch.setattr(script, "ClientClaude", claude)
    monkeypatch.setattr(script, "ClientJev", jev)
    monkeypatch.setattr(sys, "argv", ["evaluation", "synthetique", "--fichier", str(fichier)])
    assert script.main() == 0
    sortie = capsys.readouterr().out
    assert "Coût / million" in sortie and "Désaccords avec tes étiquettes" in sortie
    assert len(faux_jev.envois) == 100


def test_position_obligatoire_sur_video_d_opinion() -> None:
    """Claude sans position sous une vidéo d'opinion : repli sur hors_sujet, jamais None."""
    c = ClassementCommentaire(
        numero=1, est_politique=False, themes=[], position=None, emotion="enthousiasme"
    )
    assert normaliser(c, "opinion_debat").position == "hors_sujet"
    assert normaliser(c, "info_factuelle").position is None
