"""Regroupement des vidéos par sujet d'actualité (radar/sujets.py)."""

from datetime import date

from radar.sujets import (
    AUCUN,
    NouveauSujet,
    Rattachement,
    ReponseSujets,
    Sujet,
    VideoASituer,
    actifs,
    appliquer,
    message_sujets,
    mettre_a_jour,
    nouvel_id,
)

J = date(2026, 9, 10)


def _video(i: int) -> VideoASituer:
    return VideoASituer(f"v{i}", J, f"[Chaîne {i}]", f"[titre {i}]", f"[sous-sujet {i}]")


def test_actifs_fenetre_de_7_jours() -> None:
    vieux = Sujet("a", "[a]", date(2026, 9, 1), date(2026, 9, 2), 3)
    recent = Sujet("b", "[b]", date(2026, 9, 1), date(2026, 9, 3), 3)
    futur = Sujet("c", "[c]", date(2026, 9, 11), date(2026, 9, 12), 3)
    assert [s.id for s in actifs([vieux, recent, futur], J)] == ["b"]


def test_nouvel_id_suit_les_existants() -> None:
    assert nouvel_id(J, set()) == "2026-09-10-001"
    assert nouvel_id(J, {"2026-09-10-001", "2026-09-10-002"}) == "2026-09-10-003"


def test_appliquer_existant_nouveau_aucun() -> None:
    ouvert = Sujet("2026-09-08-001", "[ouvert]", date(2026, 9, 8), date(2026, 9, 9), 4)
    lot = [_video(i) for i in range(5)]
    rep = ReponseSujets(
        nouveaux=[
            NouveauSujet(cle="N1", titre="  [nouveau   sujet] "),
            NouveauSujet(cle="N2", titre="[jamais utilisé]"),
            NouveauSujet(cle="N3", titre="   "),
        ],
        rattachements=[
            Rattachement(video=0, sujet="2026-09-08-001"),
            Rattachement(video=1, sujet="N1"),
            Rattachement(video=2, sujet="N1"),
            Rattachement(video=3, sujet=AUCUN),
            Rattachement(video=3, sujet="N1"),  # doublon : le premier compte
            Rattachement(video=9, sujet="N1"),  # index hors du lot
            Rattachement(video=4, sujet="N3"),  # clé sans titre : aucun sujet
        ],
    )
    nouveaux, liens = appliquer(rep, lot, [ouvert], J, {"2026-09-10-001"})
    assert [(s.id, s.titre) for s in nouveaux] == [("2026-09-10-002", "[nouveau sujet]")]
    assert liens == {
        "v0": "2026-09-08-001",
        "v1": "2026-09-10-002",
        "v2": "2026-09-10-002",
        "v3": None,
        "v4": None,
    }


def test_identifiant_inconnu_ou_inactif_vaut_aucun() -> None:
    rep = ReponseSujets(nouveaux=[], rattachements=[Rattachement(video=0, sujet="2026-08-01-001")])
    _, liens = appliquer(rep, [_video(0)], [], J, set())
    assert liens == {"v0": None}


def test_video_absente_de_la_reponse_non_rattachee() -> None:
    rep = ReponseSujets(nouveaux=[], rattachements=[Rattachement(video=0, sujet=AUCUN)])
    _, liens = appliquer(rep, [_video(0), _video(1)], [], J, set())
    assert "v1" not in liens  # repartira au run suivant


def test_mettre_a_jour_compte_et_dates() -> None:
    s = Sujet("x", "[x]", J, J, 0)
    modifies = mettre_a_jour(
        {"x": s},
        {"a": "x", "b": "x", "c": None},
        {"a": date(2026, 9, 9), "b": date(2026, 9, 12), "c": J},
    )
    assert modifies == {"x"}
    assert (s.videos, s.premier_jour, s.dernier_jour) == (2, date(2026, 9, 9), date(2026, 9, 12))


def test_message_sans_titre_disponible() -> None:
    v = VideoASituer("v", J, "[Chaîne]", "", "[sous-sujet]")
    m = message_sujets([], [v])
    assert "(none)" in m and "(title unavailable)" in m and "v |" not in m


def test_valider_fusions_sans_chaine_ni_inconnu() -> None:
    from radar.sujets import Fusion, ReponseFusions, valider_fusions

    rep = ReponseFusions(
        fusions=[
            Fusion(garder="a", doublons=["b", "inconnu", "a"]),
            Fusion(garder="c", doublons=["a", "b", "d"]),  # a est gardé, b déjà absorbé
            Fusion(garder="b", doublons=["e"]),  # b déjà absorbé : ignoré
        ]
    )
    assert valider_fusions(rep, {"a", "b", "c", "d", "e"}) == {"b": "a", "d": "c"}


def test_jetons_sans_accents_ni_mots_vides() -> None:
    from radar.sujets import jetons

    assert jetons("Accusations d'antisémitisme contre Paul Martin") == {
        "accus",
        "antis",
        "paul",
        "marti",
    }
    assert jetons("Blocages dans les lycées en septembre 2026") == {"bloca", "lycee"}


def test_groupes_candidats_titres_proches_et_voisins_dans_le_temps() -> None:
    from radar.sujets import groupes_candidats

    s = [
        Sujet("a", "Accusations d'antisémitisme contre Paul Martin", J, J, 161),
        Sujet("b", "Accusations antisémites contre Paul Martin", J, J, 8),
        Sujet("c", "Accusations contre Paul Martin de propos antisémites", J, J, 4),
        Sujet("d", "Grève des contrôleurs aériens", J, J, 63),
        Sujet("e", "Paul Martin en meeting à Lyon", J, J, 5),
        Sujet(
            "f", "Accusations antisémites contre Paul Martin", date(2026, 6, 1), date(2026, 6, 2), 9
        ),
        Sujet("g", "Accusations antisémites contre Paul Martin", J, J, 1),  # 1 vidéo
        Sujet("h", "Blocages et heurts dans les lycées français en septembre 2026", J, J, 181),
        Sujet("i", "Blocages et mobilisations de lycéens en septembre 2026", J, J, 3),
    ]
    assert [[x.id for x in g] for g in groupes_candidats(s)] == [["a", "b", "c"], ["h", "i"]]
