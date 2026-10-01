"""Test de qualité Jev / Claude / vérité terrain (étape 4, docs/roadmap.md).

1. `preparer` : échantillon stratifié de commentaires collectés (catégorie de source, format,
   nature de vidéo), dont un sous-ensemble à étiqueter à la main. Nature des vidéos par Claude.
2. Étiquetage par Tristan d'un fichier CSV déposé dans le bucket brut.
3. `evaluer` : classement par Jev et par Claude, comparaison aux étiquettes, justesse de Jev
   par tranche de confiance, seuil de reprise recommandé et coût projeté sur la campagne.

Tous les fichiers (échantillon, étiquetage, résultats) restent dans le bucket brut, sous
`evaluation/AAAA-MM-JJ-…`, datés de la plus ancienne récupération des commentaires qu'ils
contiennent : la purge à 30 jours les supprime avec le brut. Le rapport ne contient que des
agrégats : jamais de texte de commentaire, de titre ou de nom de chaîne.
"""

import csv
import io
import json
import logging
import random
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal, TypeVar

import pyarrow as pa
import pyarrow.parquet as pq

from radar.classification import (
    SYSTEME_COMMENTAIRES,
    SYSTEME_NATURE_VIDEO,
    Classement,
    ContexteVideo,
    ReponseCommentaires,
    ReponseNatureVideo,
    classement_jev,
    en_position,
    en_theme,
    en_tonalite,
    etat_jev,
    masquer,
    message_commentaires,
    message_nature_video,
    normaliser,
    questions_jev,
)
from radar.llm import ClientClaude, ClientJev, ReponseInvalide
from radar.schemas import (
    FORMATS_VIDEO,
    NATURES_VIDEO,
    POSITIONS,
    THEMES,
    TONALITES,
    TYPES_SOURCE,
    NatureVideo,
    Position,
    Theme,
    Tonalite,
)
from radar.storage import DOSSIER_EVALUATION, Stockage, date_fichier

log = logging.getLogger(__name__)

N_ECHANTILLON = 500
N_VERITE = 100
MAX_PAR_VIDEO = 5
VIDEOS_PAR_CELLULE = 30  # vidéos candidates par catégorie et format, avant nature
MIN_COMMENTAIRES_VIDEO = 3
LOT_CLAUDE = 10  # commentaires d'une même vidéo par requête Claude
TRANCHES: tuple[tuple[float, float, str], ...] = (
    (0.0, 0.5, "< 0,5"),
    (0.5, 0.7, "0,5 - 0,7"),
    (0.7, 0.9, "0,7 - 0,9"),
    (0.9, 1.01, "≥ 0,9"),
)
SEUILS = (0.5, 0.6, 0.7, 0.8, 0.9)
TOLERANCE = 0.02  # écart de justesse accepté entre la cascade et Claude seul
FIN_CAMPAGNE = date(2027, 5, 2)  # second tour (deux semaines après le 1er tour du 18/04)

K = TypeVar("K")
Strate = tuple[str, str, str]  # (catégorie de source, format, nature)
Modele = Literal["jev", "claude"]


@dataclass(frozen=True)
class Candidate:
    video_id: str
    type_source: str
    format: str
    chaine: str
    titre: str
    description: str


@dataclass(frozen=True)
class Ligne:
    ref: str
    comment_id: str
    video_id: str
    type_source: str
    format: str
    nature: NatureVideo
    chaine: str
    titre: str
    texte: str  # déjà masqué
    verite: bool
    recupere_le: date

    @property
    def strate(self) -> Strate:
        return (self.type_source, self.format, self.nature)

    @property
    def contexte(self) -> ContexteVideo:
        return ContexteVideo(self.titre, self.chaine, self.nature)


SCHEMA_ECHANTILLON = pa.schema(
    [
        ("ref", pa.string()),
        ("comment_id", pa.string()),
        ("video_id", pa.string()),
        ("type_source", pa.string()),
        ("format", pa.string()),
        ("nature", pa.string()),
        ("chaine", pa.string()),
        ("titre", pa.string()),
        ("texte", pa.string()),
        ("verite", pa.bool_()),
        ("recupere_le", pa.date32()),
    ]
)

# Résultats des modèles : aucun texte, seulement la référence locale et les étiquettes.
SCHEMA_RESULTATS = pa.schema(
    [
        ("ref", pa.string()),
        ("modele", pa.string()),
        ("est_politique", pa.bool_()),
        ("themes", pa.list_(pa.string())),
        ("position", pa.string()),
        ("tonalite", pa.string()),
        ("hostilite", pa.bool_()),
        ("confiance", pa.float64()),
    ]
)


# --- Échantillonnage ---


def candidates(
    videos: Iterable[Mapping[str, Any]],
    sources: Mapping[str, Mapping[str, Any]],
    bruts_videos: Mapping[str, Mapping[str, Any]],
    nb_commentaires: Mapping[str, int],
    rng: random.Random,
) -> list[Candidate]:
    """Jusqu'à VIDEOS_PAR_CELLULE vidéos commentées par catégorie de source et format."""
    cellules: dict[tuple[str, str], list[Candidate]] = defaultdict(list)
    for v in sorted(videos, key=lambda v: str(v["video_id"])):
        vid = str(v["video_id"])
        s = sources.get(str(v["source_id"]))
        brut = bruts_videos.get(vid)
        if s is None or brut is None or nb_commentaires.get(vid, 0) < MIN_COMMENTAIRES_VIDEO:
            continue
        c = Candidate(
            vid,
            str(s["type"]),
            str(v["format"]),
            str(s["nom"]),
            str(brut.get("titre") or ""),
            str(brut.get("description") or ""),
        )
        cellules[(c.type_source, c.format)].append(c)
    choisies: list[Candidate] = []
    for cle in sorted(cellules):
        liste = cellules[cle]
        rng.shuffle(liste)
        choisies.extend(liste[:VIDEOS_PAR_CELLULE])
    return choisies


def repartir(capacites: Mapping[K, int], total: int) -> dict[K, int]:
    """Répartition la plus égale possible de `total` entre des cases de capacité limitée."""
    quotas: dict[K, int] = dict.fromkeys(capacites, 0)
    restant = min(total, sum(capacites.values()))
    ouvertes = [k for k in capacites if capacites[k] > 0]
    while restant > 0 and ouvertes:
        part = max(1, restant // len(ouvertes))
        for k in list(ouvertes):
            if restant == 0:
                break
            ajout = min(part, capacites[k] - quotas[k], restant)
            quotas[k] += ajout
            restant -= ajout
            if quotas[k] >= capacites[k]:
                ouvertes.remove(k)
    return quotas


def echantillonner(
    natures: Mapping[str, NatureVideo],
    candidates_: Iterable[Candidate],
    commentaires: Mapping[str, Sequence[Mapping[str, Any]]],
    rng: random.Random,
    n: int = N_ECHANTILLON,
    n_verite: int = N_VERITE,
) -> list[Ligne]:
    """Échantillon stratifié (égal entre strates, plafonné par vidéo) ; `n_verite` à étiqueter."""
    par_strate: dict[Strate, list[tuple[Candidate, list[Mapping[str, Any]]]]] = defaultdict(list)
    for c in candidates_:
        if c.video_id not in natures:
            continue
        valides = [x for x in commentaires.get(c.video_id, []) if masquer(str(x["texte"])).strip()]
        if valides:
            valides = sorted(valides, key=lambda x: str(x["comment_id"]))
            rng.shuffle(valides)
            par_strate[(c.type_source, c.format, natures[c.video_id])].append((c, valides))
    capacites = {
        s: sum(min(MAX_PAR_VIDEO, len(cs)) for _, cs in vids) for s, vids in par_strate.items()
    }
    quotas = repartir(capacites, n)
    retenues: dict[Strate, list[tuple[Candidate, Mapping[str, Any]]]] = {}
    for s, vids in sorted(par_strate.items()):
        choix: list[tuple[Candidate, Mapping[str, Any]]] = []
        tour = 0
        while len(choix) < quotas[s] and tour < MAX_PAR_VIDEO:
            for c, cs in vids:  # un commentaire par vidéo et par tour : étalement maximal
                if len(choix) < quotas[s] and tour < len(cs):
                    choix.append((c, cs[tour]))
            tour += 1
        retenues[s] = choix
    quotas_verite = repartir({s: len(x) for s, x in retenues.items()}, n_verite)
    tout: list[tuple[Candidate, Mapping[str, Any], bool, Strate]] = []
    for s, choix in retenues.items():
        tout.extend((c, x, i < quotas_verite[s], s) for i, (c, x) in enumerate(choix))
    rng.shuffle(tout)  # l'ordre du fichier d'étiquetage ne trahit pas la strate
    return [
        Ligne(
            ref=f"C{i:03d}",
            comment_id=str(x["comment_id"]),
            video_id=c.video_id,
            type_source=c.type_source,
            format=c.format,
            nature=s[2],  # pyright: ignore[reportArgumentType]
            chaine=c.chaine,
            titre=c.titre,
            texte=masquer(str(x["texte"])),
            verite=verite,
            recupere_le=_date(x["recupere_le"]),
        )
        for i, (c, x, verite, s) in enumerate(tout, start=1)
    ]


def _date(v: Any) -> date:
    return v if isinstance(v, date) else date.fromisoformat(str(v)[:10])


# --- Classement ---


def classer_natures(claude: ClientClaude, cands: Iterable[Candidate]) -> dict[str, NatureVideo]:
    natures: dict[str, NatureVideo] = {}
    for c in cands:
        try:
            r = claude.classer(
                SYSTEME_NATURE_VIDEO,
                message_nature_video(c.titre, c.description, c.chaine),
                ReponseNatureVideo,
                max_tokens=100,
            )
        except ReponseInvalide as e:
            log.warning("nature vidéo ignorée : %s", e)
            continue
        natures[c.video_id] = r.nature_video
    return natures


def classer_claude(claude: ClientClaude, lignes: Iterable[Ligne]) -> dict[str, Classement]:
    # Un lot partage un même contexte : même vidéo et même nature.
    par_video: dict[tuple[str, str], list[Ligne]] = defaultdict(list)
    for li in lignes:
        par_video[(li.video_id, li.nature)].append(li)
    resultats: dict[str, Classement] = {}
    for cle in sorted(par_video):
        groupe = par_video[cle]
        for i in range(0, len(groupe), LOT_CLAUDE):
            lot = groupe[i : i + LOT_CLAUDE]
            ctx = lot[0].contexte
            try:
                r = claude.classer(
                    SYSTEME_COMMENTAIRES,
                    message_commentaires(ctx, [li.texte for li in lot]),
                    ReponseCommentaires,
                )
            except ReponseInvalide as e:
                log.warning("lot claude ignoré : %s", e)
                continue
            for c in r.commentaires:
                if 1 <= c.numero <= len(lot):
                    resultats[lot[c.numero - 1].ref] = normaliser(c, ctx.nature)
    return resultats


def classer_jev(jev: ClientJev, lignes: Iterable[Ligne]) -> dict[str, Classement]:
    resultats: dict[str, Classement] = {}
    for li in lignes:
        try:
            reps = jev.evaluer(etat_jev(li.contexte, li.texte), questions_jev(li.nature))
        except ReponseInvalide as e:
            log.warning("commentaire jev ignoré : %s", e)
            continue
        resultats[li.ref] = classement_jev(reps, li.nature)
    return resultats


# --- Étiquetage manuel ---

COLONNES_ETIQUETAGE = (
    "ref",
    "categorie",
    "format",
    "nature_video",
    "chaine",
    "titre_video",
    "commentaire",
    "themes",
    "position",
    "tonalite",
    "hostilite",
)
AUCUN_THEME = "aucun"
SANS_POSITION = "-"
OUI, NON = "oui", "non"


@dataclass(frozen=True)
class Etiquette:
    est_politique: bool
    themes: tuple[Theme, ...]
    position: Position | None
    tonalite: Tonalite
    hostilite: bool | None  # None : pas encore tranché (dimension ignorée)


def fichier_etiquetage(lignes: Iterable[Ligne]) -> bytes:
    """CSV `;` en UTF-8 avec BOM (ouvrable dans Excel / Numbers), colonnes à remplir vides."""
    tampon = io.StringIO()
    w = csv.writer(tampon, delimiter=";")
    w.writerow(COLONNES_ETIQUETAGE)
    for li in sorted((li for li in lignes if li.verite), key=lambda li: li.ref):
        position = "" if li.nature == "opinion_debat" else SANS_POSITION
        w.writerow(
            [
                li.ref,
                li.type_source,
                li.format,
                li.nature,
                li.chaine,
                li.titre,
                li.texte,
                "",
                position,
                "",
                "",
            ]
        )
    return ("﻿" + tampon.getvalue()).encode("utf-8")


def lire_etiquettes(donnees: bytes, lignes: Iterable[Ligne]) -> dict[str, Etiquette]:
    """Lit le CSV rempli ; lignes vides ignorées ; lève ValueError listant les erreurs."""
    natures = {li.ref: li.nature for li in lignes if li.verite}
    texte = donnees.decode("utf-8-sig")
    separateur = (
        ";" if texte.split("\n", 1)[0].count(";") >= texte.split("\n", 1)[0].count(",") else ","
    )
    erreurs: list[str] = []
    etiquettes: dict[str, Etiquette] = {}
    for rang in csv.DictReader(io.StringIO(texte), delimiter=separateur):
        ref = (rang.get("ref") or "").strip()
        brut_themes = (rang.get("themes") or "").strip().lower()
        brut_position = (rang.get("position") or "").strip().lower()
        brut_tonalite = (rang.get("tonalite") or "").strip().lower()
        brut_hostilite = (rang.get("hostilite") or "").strip().lower()
        if ref not in natures:
            erreurs.append(f"{ref or '?'} : référence inconnue")
            continue
        vide = not (brut_themes or brut_tonalite or brut_hostilite)
        if vide and brut_position in ("", SANS_POSITION):
            continue  # pas encore étiqueté
        nature = natures[ref]
        themes: list[Theme] = []
        if brut_themes != AUCUN_THEME:
            for t in (x.strip() for x in brut_themes.split("+")):
                theme: Theme | None = next((v for v in THEMES if v == t), None)
                if theme is None:
                    erreurs.append(f"{ref} : thème inconnu « {t} »")
                elif theme not in themes:
                    themes.append(theme)
            if not themes:
                erreurs.append(f"{ref} : thèmes vides (écrire « {AUCUN_THEME} » si non politique)")
        position: Position | None = None
        if nature == "opinion_debat":
            position = next((p for p in POSITIONS if p == brut_position), None)
            if position is None:
                erreurs.append(f"{ref} : position attendue ({', '.join(POSITIONS)})")
        tonalite: Tonalite | None = next((t for t in TONALITES if t == brut_tonalite), None)
        if tonalite is None:
            erreurs.append(f"{ref} : tonalité attendue ({', '.join(TONALITES)})")
            continue
        if brut_hostilite not in (OUI, NON, ""):
            erreurs.append(f"{ref} : hostilité attendue ({OUI}, {NON} ou vide)")
            continue
        hostilite = None if not brut_hostilite else brut_hostilite == OUI
        etiquettes[ref] = Etiquette(bool(themes), tuple(themes[:3]), position, tonalite, hostilite)
    if erreurs:
        raise ValueError("Étiquetage invalide :\n" + "\n".join(erreurs))
    return etiquettes


# --- Comparaison ---

DIMENSIONS = (
    "politique",
    "theme_principal",
    "theme_commun",
    "position",
    "tonalite",
    "hostilite",
    "complet",
)
DIMENSIONS_COMPLET = ("politique", "theme_principal", "position", "tonalite", "hostilite")
LIBELLES_DIMENSIONS = {
    "politique": "Politique / non politique",
    "theme_principal": "Thème principal",
    "theme_commun": "Au moins un thème commun",
    "position": "Position (vidéos d'opinion)",
    "tonalite": "Tonalité",
    "hostilite": "Hostilité",
    "complet": "Tout juste (politique, thème principal, position, tonalité, hostilité)",
}

Reference = Etiquette | Classement


def comparer(pred: Classement, ref: Reference) -> dict[str, bool | None]:
    """Justesse par dimension ; None quand la dimension ne s'applique pas."""
    d: dict[str, bool | None] = {
        "politique": pred.est_politique == ref.est_politique,
        "theme_principal": pred.themes[:1] == ref.themes[:1] if ref.est_politique else None,
        "theme_commun": bool(set(pred.themes) & set(ref.themes)) if ref.est_politique else None,
        "position": pred.position == ref.position if ref.position is not None else None,
        "tonalite": pred.tonalite == ref.tonalite,
        "hostilite": pred.hostilite == ref.hostilite if ref.hostilite is not None else None,
    }
    d["complet"] = all(v for k, v in d.items() if k in DIMENSIONS_COMPLET and v is not None)
    return d


def taux(
    preds: Mapping[str, Classement], refs: Mapping[str, Reference], dimension: str
) -> tuple[int, int]:
    """(justes, total) sur les références communes où la dimension s'applique."""
    ok = n = 0
    for r, ref in refs.items():
        p = preds.get(r)
        if p is None:
            continue
        v = comparer(p, ref)[dimension]
        if v is not None:
            n += 1
            ok += int(v)
    return ok, n


def tranche(confiance: float) -> str:
    for bas, haut, nom in TRANCHES:
        if bas <= confiance < haut:
            return nom
    return TRANCHES[-1][2]


def cascade(
    jev: Mapping[str, Classement], claude: Mapping[str, Classement], seuil: float
) -> dict[str, Classement]:
    """Jev quand sa confiance atteint le seuil, Claude sinon (reprise)."""
    resultat: dict[str, Classement] = {}
    for r, j in jev.items():
        if j.confiance is not None and j.confiance >= seuil:
            resultat[r] = j
        elif r in claude:
            resultat[r] = claude[r]
    return resultat


@dataclass(frozen=True)
class Couts:
    jev_usd: float
    jev_n: int
    claude_usd: float  # classement des commentaires seulement
    claude_n: int
    natures_usd: float

    @property
    def jev_par_commentaire(self) -> float:
        return self.jev_usd / self.jev_n if self.jev_n else 0.0

    @property
    def claude_par_commentaire(self) -> float:
        return self.claude_usd / self.claude_n if self.claude_n else 0.0


@dataclass(frozen=True)
class Volume:
    commentaires: int  # commentaires collectés sur la période de l'échantillon
    jours: int  # jours de publication couverts

    def campagne(self, aujourdhui: date) -> tuple[int, int]:
        """(jours restants, commentaires projetés) jusqu'au second tour."""
        jours = max(0, (FIN_CAMPAGNE - aujourdhui).days + 1)
        par_jour = self.commentaires / self.jours if self.jours else 0.0
        return jours, round(par_jour * jours)


def _pct(ok: int, n: int) -> str:
    return f"{100 * ok / n:.0f} % ({ok}/{n})" if n else "—"


def _usd(v: float) -> str:
    return f"{v:,.2f} $".replace(",", " ")


def rapport(
    lignes: list[Ligne],
    jev: Mapping[str, Classement],
    claude: Mapping[str, Classement],
    etiquettes: Mapping[str, Etiquette],
    couts: Couts,
    volume: Volume,
    aujourdhui: date,
) -> str:
    """Rapport en agrégats : aucun texte, titre ou nom de chaîne."""
    out = [f"# Test Jev / Claude — {aujourdhui:%d/%m/%Y}", ""]

    out += ["## Échantillon", "", "| Catégorie | Format | Nature | Commentaires | Étiquetés |"]
    out += ["|---|---|---|---:|---:|"]
    n_strate = Counter(li.strate for li in lignes)
    n_verite = Counter(li.strate for li in lignes if li.ref in etiquettes)
    for s in [(t, f, n) for t in TYPES_SOURCE for f in FORMATS_VIDEO for n in NATURES_VIDEO]:
        if n_strate[s]:
            out.append(f"| {s[0]} | {s[1]} | {s[2]} | {n_strate[s]} | {n_verite[s]} |")
    out += [
        "",
        f"Total : {len(lignes)} commentaires, {len(etiquettes)} étiquetés par Tristan. "
        f"Classés : Jev {len(jev)}, Claude {len(claude)}.",
        "",
    ]

    out += ["## Coût mesuré", ""]
    out += [
        f"- Jev : {_usd(couts.jev_usd)} pour {couts.jev_n} commentaires "
        f"({_usd(1000 * couts.jev_par_commentaire)} / 1 000)",
        f"- Claude : {_usd(couts.claude_usd)} pour {couts.claude_n} commentaires "
        f"({_usd(1000 * couts.claude_par_commentaire)} / 1 000) ; nature des vidéos : "
        f"{_usd(couts.natures_usd)}",
        "",
    ]

    if etiquettes:
        out += ["## Justesse face aux étiquettes de Tristan", ""]
        out += [
            f"| Dimension | Jev | Claude | Accord Jev / Claude ({len(lignes)}) |",
            "|---|---:|---:|---:|",
        ]
        for d in DIMENSIONS:
            out.append(
                f"| {LIBELLES_DIMENSIONS[d]} | {_pct(*taux(jev, etiquettes, d))} | "
                f"{_pct(*taux(claude, etiquettes, d))} | {_pct(*taux(jev, claude, d))} |"
            )
        out += ["", "Par catégorie de source (« tout juste ») :", ""]
        out += ["| Catégorie | Jev | Claude |", "|---|---:|---:|"]
        for t in TYPES_SOURCE:
            refs = {r: e for r, e in etiquettes.items() if _type(lignes, r) == t}
            out.append(
                f"| {t} | {_pct(*taux(jev, refs, 'complet'))} | "
                f"{_pct(*taux(claude, refs, 'complet'))} |"
            )
        out.append("")
    else:
        out += [
            "## Justesse face aux étiquettes de Tristan",
            "",
            "Étiquettes absentes : seule la comparaison Jev / Claude est disponible.",
            "",
        ]
        out += ["| Dimension | Accord Jev / Claude |", "|---|---:|"]
        for d in DIMENSIONS:
            out.append(f"| {LIBELLES_DIMENSIONS[d]} | {_pct(*taux(jev, claude, d))} |")
        out.append("")

    out += ["## Jev par tranche de confiance", ""]
    out += [
        "| Confiance | Commentaires | Accord avec Claude (tout juste) | Justesse face à Tristan "
        "(tout juste) |",
        "|---|---:|---:|---:|",
    ]
    for _, _, nom in TRANCHES:
        dans = {
            r: j for r, j in jev.items() if j.confiance is not None and tranche(j.confiance) == nom
        }
        out.append(
            f"| {nom} | {len(dans)} | {_pct(*taux(dans, claude, 'complet'))} | "
            f"{_pct(*taux(dans, etiquettes, 'complet'))} |"
        )
    out.append("")

    jours, projetes = volume.campagne(aujourdhui)
    if volume.commentaires:
        projection = (
            f"Projection : {volume.commentaires} commentaires collectés sur {volume.jours} jours "
            f"de publication, soit ~{projetes:,} commentaires sur les {jours} jours restants "
            f"jusqu'au second tour ({FIN_CAMPAGNE:%d/%m/%Y})."
        ).replace(",", " ")
        colonne = "Coût campagne"
    else:
        projetes = 1_000_000
        projection = "Pas de volume réel (données synthétiques) : coût exprimé pour 1 million."
        colonne = "Coût / million"
    out += [
        "## Seuil de reprise par Claude",
        "",
        projection,
        "",
        f"| Seuil | Part reprise par Claude | Justesse (tout juste) | Coût / 1 000 | {colonne} |",
        "|---|---:|---:|---:|---:|",
    ]
    cj, cc = couts.jev_par_commentaire, couts.claude_par_commentaire
    lignes_seuils: list[tuple[str, float, tuple[int, int]]] = [
        ("Jev seul", 0.0, taux(jev, etiquettes, "complet"))
    ]
    for s in SEUILS:
        reprise = sum(1 for j in jev.values() if j.confiance is None or j.confiance < s)
        part = reprise / len(jev) if jev else 0.0
        lignes_seuils.append(
            (
                f"{s:.1f}".replace(".", ","),
                part,
                taux(cascade(jev, claude, s), etiquettes, "complet"),
            )
        )
    lignes_seuils.append(("Claude seul", 1.0, taux(claude, etiquettes, "complet")))
    for nom, part, (ok, n) in lignes_seuils:
        cout = (cj + part * cc) if nom != "Claude seul" else cc
        out.append(
            f"| {nom} | {100 * part:.0f} % | {_pct(ok, n)} | {_usd(1000 * cout)} | "
            f"{_usd(projetes * cout)} |"
        )
    out += ["", "## Recommandation", ""]
    out.append(recommandation(lignes_seuils, cj, cc, projetes))
    out += [
        "",
        "Lecture : justesse mesurée sur les commentaires étiquetés (petits effectifs) ; "
        "la projection suppose le volume quotidien de l'échantillon et les prix mesurés.",
    ]
    return "\n".join(out)


def _type(lignes: list[Ligne], ref: str) -> str:
    return next((li.type_source for li in lignes if li.ref == ref), "?")


def recommandation(
    lignes_seuils: list[tuple[str, float, tuple[int, int]]], cj: float, cc: float, projetes: int
) -> str:
    _, _, (ok_c, n_c) = lignes_seuils[-1]
    if n_c == 0:
        return "Pas de recommandation : étiquettes de Tristan absentes ou classement Claude vide."
    cible = ok_c / n_c - TOLERANCE
    for nom, part, (ok, n) in lignes_seuils[:-1]:
        if n and ok / n >= cible:
            cout = cj + part * cc
            return (
                f"Seuil **{nom}** : justesse {_pct(ok, n)}, à moins de "
                f"{100 * TOLERANCE:.0f} points de Claude seul ({_pct(ok_c, n_c)}), "
                f"{100 * part:.0f} % des commentaires repris par Claude, coût projeté "
                f"{_usd(projetes * cout)} sur la campagne (Claude seul : {_usd(projetes * cc)})."
            )
    return (
        f"Aucun seuil n'approche Claude seul ({_pct(ok_c, n_c)}) à {100 * TOLERANCE:.0f} points "
        f"près : Claude seul, coût projeté {_usd(projetes * cc)} sur la campagne."
    )


# --- Fichiers du bucket ---


def chemin(jour: date, nom: str) -> str:
    return f"{DOSSIER_EVALUATION}/{jour.isoformat()}-{nom}"


def dernier_echantillon(st: Stockage) -> date | None:
    jours = [
        j
        for c in st.lister(DOSSIER_EVALUATION)
        if c.endswith("-echantillon.parquet") and (j := date_fichier(c)) is not None
    ]
    return max(jours, default=None)


def ecrire_echantillon(st: Stockage, jour: date, lignes: list[Ligne]) -> None:
    tampon = io.BytesIO()
    table = pa.Table.from_pylist([li.__dict__ for li in lignes], schema=SCHEMA_ECHANTILLON)
    pq.write_table(table, tampon)  # pyright: ignore[reportUnknownMemberType]
    st.ecrire(chemin(jour, "echantillon.parquet"), tampon.getvalue())


def lire_echantillon(st: Stockage, jour: date) -> list[Ligne]:
    table = pq.read_table(io.BytesIO(st.lire(chemin(jour, "echantillon.parquet"))))  # pyright: ignore[reportUnknownMemberType]
    return [Ligne(**r) for r in table.to_pylist()]


def ecrire_resultats(
    st: Stockage, jour: date, resultats: Mapping[str, Mapping[str, Classement]]
) -> None:
    lignes = [
        {
            "ref": r,
            "modele": m,
            "est_politique": c.est_politique,
            "themes": list(c.themes),
            "position": c.position,
            "tonalite": c.tonalite,
            "hostilite": c.hostilite,
            "confiance": c.confiance,
        }
        for m, res in resultats.items()
        for r, c in sorted(res.items())
    ]
    tampon = io.BytesIO()
    pq.write_table(pa.Table.from_pylist(lignes, schema=SCHEMA_RESULTATS), tampon)  # pyright: ignore[reportUnknownMemberType]
    st.ecrire(chemin(jour, "resultats.parquet"), tampon.getvalue())


def lire_resultats(st: Stockage, jour: date) -> dict[Modele, dict[str, Classement]]:
    table = pq.read_table(io.BytesIO(st.lire(chemin(jour, "resultats.parquet"))))  # pyright: ignore[reportUnknownMemberType]
    res: dict[Modele, dict[str, Classement]] = {"jev": {}, "claude": {}}
    for r in table.to_pylist():
        modele: Modele = "jev" if r["modele"] == "jev" else "claude"
        res[modele][r["ref"]] = Classement(
            est_politique=bool(r["est_politique"]),
            themes=tuple(en_theme(t) for t in r["themes"]),
            position=en_position(r["position"]) if r["position"] else None,
            tonalite=en_tonalite(r["tonalite"]),
            hostilite=bool(r["hostilite"]),
            confiance=r["confiance"],
        )
    return res


def ecrire_json(st: Stockage, jour: date, nom: str, donnees: Mapping[str, Any]) -> None:
    st.ecrire(chemin(jour, nom), json.dumps(donnees, sort_keys=True).encode())


def lire_json(st: Stockage, jour: date, nom: str) -> dict[str, Any]:
    resultat: dict[str, Any] = json.loads(st.lire(chemin(jour, nom)))
    return resultat


# --- Test synthétique (commentaires fictifs, versionnés dans Git) ---


def charger_synthetique(donnees: bytes, aujourdhui: date) -> list[Ligne]:
    """Commentaires fictifs au format du fichier d'étiquetage ; tous à comparer."""
    texte = donnees.decode("utf-8-sig")
    lignes: list[Ligne] = []
    for r in csv.DictReader(io.StringIO(texte), delimiter=";"):
        nature: NatureVideo = (
            "opinion_debat" if r["nature_video"] == "opinion_debat" else ("info_factuelle")
        )
        lignes.append(
            Ligne(
                ref=r["ref"],
                comment_id=r["ref"],
                video_id=r["titre_video"],
                type_source=r["categorie"],
                format=r["format"],
                nature=nature,
                chaine=r["chaine"],
                titre=r["titre_video"],
                texte=masquer(r["commentaire"]),
                verite=True,
                recupere_le=aujourdhui,
            )
        )
    return lignes


def _etiquette(c: Reference) -> str:
    themes = "+".join(c.themes) or AUCUN_THEME
    hostile = "?" if c.hostilite is None else ("hostile" if c.hostilite else "non hostile")
    return f"{themes} / {c.position or SANS_POSITION} / {c.tonalite} / {hostile}"


def desaccords(
    lignes: list[Ligne],
    jev: Mapping[str, Classement],
    claude: Mapping[str, Classement],
    etiquettes: Mapping[str, Etiquette],
) -> str:
    """Désaccords avec les étiquettes, texte affiché : réservé aux données synthétiques."""
    out = [
        "## Désaccords avec tes étiquettes (données synthétiques)",
        "",
        "| Réf | Commentaire | Tristan | Jev (confiance) | Claude |",
        "|---|---|---|---|---|",
    ]
    for li in sorted(lignes, key=lambda li: li.ref):
        e = etiquettes.get(li.ref)
        j, c = jev.get(li.ref), claude.get(li.ref)
        if e is None or j is None or c is None:
            continue
        if comparer(j, e)["complet"] and comparer(c, e)["complet"]:
            continue
        conf = f" ({j.confiance:.2f})" if j.confiance is not None else ""
        texte = li.texte.replace("|", "/")
        out.append(
            f"| {li.ref} | {texte} | {_etiquette(e)} | {_etiquette(j)}{conf} | {_etiquette(c)} |"
        )
    return "\n".join(out)


# --- Arbitrage à l'aveugle (données synthétiques) ---

Source = Literal["tristan", "jev", "claude"]
DIMENSIONS_ARBITRAGE = ("themes", "position", "tonalite", "hostilite")
LETTRES = "ABC"
AUCUNE = "aucune"
COLONNES_ARBITRAGE = (
    "id",
    "ref",
    "dimension",
    "chaine",
    "titre_video",
    "nature_video",
    "commentaire",
    "A",
    "B",
    "C",
    "choix",
    "note",
)


def _valeur(c: Reference, dimension: str) -> str | None:
    if dimension == "themes":
        return "+".join(c.themes) or AUCUN_THEME
    if dimension == "position":
        return c.position or SANS_POSITION
    if dimension == "tonalite":
        return c.tonalite
    if c.hostilite is None:
        return None
    return "hostile" if c.hostilite else "non hostile"


def fichier_arbitrage(
    lignes: list[Ligne],
    jev: Mapping[str, Classement],
    claude: Mapping[str, Classement],
    etiquettes: Mapping[str, Etiquette],
    rng: random.Random,
) -> tuple[bytes, dict[str, dict[str, list[str]]]]:
    """Une ligne par désaccord (commentaire et dimension), options anonymes A/B/C mélangées.

    Renvoie le CSV à remplir et la clé {id: {lettre: [sources]}}, à garder à part.
    """
    tampon = io.StringIO()
    w = csv.writer(tampon, delimiter=";")
    w.writerow(COLONNES_ARBITRAGE)
    cle: dict[str, dict[str, list[str]]] = {}
    n = 0
    for li in sorted(lignes, key=lambda li: li.ref):
        sources: dict[Source, Reference | None] = {
            "tristan": etiquettes.get(li.ref),
            "jev": jev.get(li.ref),
            "claude": claude.get(li.ref),
        }
        if any(v is None for v in sources.values()):
            continue
        for dim in DIMENSIONS_ARBITRAGE:
            if dim == "position" and li.nature != "opinion_debat":
                continue
            options: dict[str, list[str]] = {}
            for nom, c in sources.items():
                assert c is not None
                valeur = _valeur(c, dim)
                if valeur is not None:  # hostilité pas encore tranchée par Tristan
                    options.setdefault(valeur, []).append(nom)
            if len(options) < 2 or sum(len(v) for v in options.values()) < len(sources):
                continue
            valeurs = sorted(options)
            rng.shuffle(valeurs)
            n += 1
            ident = f"R{n:03d}"
            cle[ident] = {LETTRES[i]: options[v] for i, v in enumerate(valeurs)}
            cellules = [*valeurs, *[""] * (len(LETTRES) - len(valeurs))]
            w.writerow(
                [ident, li.ref, dim, li.chaine, li.titre, li.nature, li.texte, *cellules, "", ""]
            )
    return ("﻿" + tampon.getvalue()).encode("utf-8"), cle


def rapport_arbitrage(donnees: bytes, cle: Mapping[str, Mapping[str, list[str]]]) -> str:
    """Taux de victoires de chaque source sur les désaccords arbitrés à l'aveugle."""
    texte = donnees.decode("utf-8-sig")
    separateur = ";" if texte.split("\n", 1)[0].count(";") else ","
    en_lice: Counter[tuple[str, str]] = Counter()
    gagne: Counter[tuple[str, str]] = Counter()
    arbitres: Counter[str] = Counter()
    plusieurs: Counter[str] = Counter()
    aucune: Counter[str] = Counter()
    erreurs: list[str] = []
    for r in csv.DictReader(io.StringIO(texte), delimiter=separateur):
        ident = (r.get("id") or "").strip()
        choix = (r.get("choix") or "").strip().upper().replace(" ", "")
        dim = (r.get("dimension") or "").strip()
        if ident not in cle:
            erreurs.append(f"{ident or '?'} : identifiant inconnu")
            continue
        if not choix:
            continue
        options = cle[ident]
        if choix == AUCUNE.upper():
            lettres: set[str] = set()
            aucune[dim] += 1
        else:
            lettres = set(choix.split("+"))
            if not lettres <= set(options):
                erreurs.append(f"{ident} : choix « {choix} » hors des options {sorted(options)}")
                continue
            if len(lettres) > 1:
                plusieurs[dim] += 1
        arbitres[dim] += 1
        for lettre, sources in options.items():
            for s in sources:
                en_lice[(s, dim)] += 1
                gagne[(s, dim)] += int(lettre in lettres)
    if erreurs:
        raise ValueError("Arbitrage invalide :\n" + "\n".join(erreurs))
    total = sum(arbitres.values())
    out = [
        "# Arbitrage à l'aveugle",
        "",
        f"{total} désaccords arbitrés sur {len(cle)} : plusieurs réponses acceptables pour "
        f"{sum(plusieurs.values())}, aucune pour {sum(aucune.values())}.",
        "",
        "Part des désaccords où la réponse de chaque source a été retenue :",
        "",
        "| Dimension | Arbitrés | Tristan (1er jet) | Jev | Claude |",
        "|---|---:|---:|---:|---:|",
    ]
    sources_: tuple[Source, ...] = ("tristan", "jev", "claude")
    for dim in (*DIMENSIONS_ARBITRAGE, "total"):
        dims = DIMENSIONS_ARBITRAGE if dim == "total" else (dim,)
        cellules = [
            _pct(sum(gagne[(s, d)] for d in dims), sum(en_lice[(s, d)] for d in dims))
            for s in sources_
        ]
        n = sum(arbitres[d] for d in dims)
        out.append(f"| {dim} | {n} | " + " | ".join(cellules) + " |")
    out += [
        "",
        "Lecture : seuls les désaccords comptent ; quand les trois sources sont d'accord, la "
        "ligne n'est pas proposée. Plusieurs lettres = réponses également acceptables.",
    ]
    return "\n".join(out)
