"""Classification en masse des commentaires collectés par Jev (décision du 02/10/2026).

Entrée : le brut (bucket `radar-brut`, 30 jours). Sortie : une ligne par commentaire dans le
bucket privé `radar-classe`, conservé toute la campagne et **sans aucun texte** : identifiant
du commentaire hashé (même sel que les auteurs), auteur hashé, vidéo, source, étiquettes.

- Idempotent : un commentaire déjà classé (même identifiant hashé) n'est jamais reclassé.
- Plafond (décision du 04/10/2026) : au plus 150 commentaires classés par vidéo, tirés au
  hasard (ordre de l'identifiant hashé, stable d'un run à l'autre) ; les agrégats pondèrent
  chaque commentaire classé par (commentaires de la vidéo) / (commentaires classés).
- Minimisation : Jev ne reçoit que le texte masqué et le contexte de la vidéo (titre, chaîne,
  nature), jamais l'auteur ni l'identifiant (radar/classification.py).
- Position seulement sous une vidéo `opinion` ; None sinon.
- Appels Jev en parallèle ; arrêt propre au budget, ce qui est classé est écrit par lots.
"""

import hashlib
import io
import json
import logging
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from radar.anonymisation import hash_auteur
from radar.classification import Classement, ContexteVideo, classement_jev, etat_jev, questions_jev
from radar.llm import BudgetDepasse, ClientJev, ReponseInvalide
from radar.schemas import VERSION_TAXONOMIE, NatureVideo
from radar.storage import Stockage, morceaux_suivants

log = logging.getLogger(__name__)

DOSSIER_CLASSE = "classe"
MODELE = "jev"
PLAFOND_PAR_VIDEO = 150
LOT = 2000  # commentaires envoyés à Jev entre deux bilans
ECRITURE = 20_000  # commentaires classés par fichier (~1,5 Mo ; un objet Supabase : 50 Mo max)
PARALLELES = 10

# Aucun texte : ni commentaire, ni titre, ni chaîne, ni identifiant en clair.
SCHEMA_CLASSE = pa.schema(
    [
        ("id", pa.string()),  # HMAC du comment_id YouTube
        ("auteur_hash", pa.string()),
        ("video_id", pa.string()),
        ("source_id", pa.string()),
        ("type_source", pa.string()),
        ("format", pa.string()),
        ("nature", pa.string()),
        ("publie_at", pa.timestamp("s", tz="UTC")),
        ("recupere_le", pa.date32()),
        ("est_politique", pa.bool_()),
        ("themes", pa.list_(pa.string())),
        ("position", pa.string()),
        ("tonalite", pa.string()),
        ("hostilite", pa.bool_()),
        ("confiance", pa.float64()),
        ("confiance_position", pa.float64()),
        ("modele", pa.string()),
        ("version_taxonomie", pa.int32()),
        ("version_consignes", pa.string()),
        ("classe_le", pa.date32()),
    ]
)


def id_commentaire(comment_id: str, sel: bytes) -> str:
    """Identifiant interne du commentaire : hashé avec le sel secret, stable."""
    resultat = hash_auteur(comment_id, sel)
    assert resultat is not None
    return resultat


def version_consignes() -> str:
    """Empreinte des questions envoyées à Jev : change dès qu'une consigne change."""
    contenu = {
        n: json.dumps(q.__dict__, sort_keys=True) for n, q in questions_jev("opinion").items()
    }
    return hashlib.sha256(json.dumps(contenu, sort_keys=True).encode()).hexdigest()[:12]


@dataclass(frozen=True)
class Video:
    video_id: str
    source_id: str
    type_source: str
    format: str
    chaine: str
    titre: str
    nature: NatureVideo


def chemin_partition(jour: date) -> str:
    """Ancien format : un fichier par jour de classification (toujours lu)."""
    return f"{DOSSIER_CLASSE}/{jour.isoformat()}.parquet"


def classes_par_video(st: Stockage) -> tuple[set[str], Counter[str]]:
    """Identifiants hashés déjà classés, et nombre de commentaires classés par vidéo."""
    ids: set[str] = set()
    par_video: Counter[str] = Counter()
    for c in st.lister(DOSSIER_CLASSE):
        if c.endswith(".parquet"):
            table = pq.read_table(io.BytesIO(st.lire(c)), columns=["id", "video_id"])  # pyright: ignore[reportUnknownMemberType]
            ids.update(str(x) for x in table.column("id").to_pylist())
            par_video.update(str(x) for x in table.column("video_id").to_pylist())
    return ids, par_video


def deja_classes(st: Stockage) -> set[str]:
    return classes_par_video(st)[0]


def plafonner(
    commentaires: Iterable[Mapping[str, Any]],
    deja_par_video: Mapping[str, int],
    sel: bytes,
    plafond: int = PLAFOND_PAR_VIDEO,
) -> list[Mapping[str, Any]]:
    """Garde au plus `plafond` commentaires classés par vidéo, déjà classés compris.

    Tirage stable : les plus petits identifiants hashés d'abord (pseudo-aléatoire, le même à
    chaque run, donc idempotent).
    """
    par_video: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for x in commentaires:
        par_video[str(x["video_id"])].append(x)
    garde: list[Mapping[str, Any]] = []
    for v, xs in par_video.items():
        reste = max(0, plafond - deja_par_video.get(v, 0))
        xs.sort(key=lambda x: id_commentaire(str(x["comment_id"]), sel))
        garde.extend(xs[:reste])
    return garde


def ajouter_a_la_partition(st: Stockage, jour: date, lignes: Sequence[Mapping[str, Any]]) -> None:
    """Écrit des lignes dans un nouveau morceau du jour (`classe/AAAA-MM-JJ-NNN.parquet`)."""
    if not lignes:
        return
    (chemin,) = morceaux_suivants(st, DOSSIER_CLASSE, jour, 1)
    tampon = io.BytesIO()
    donnees = pa.Table.from_pylist(list(lignes), schema=SCHEMA_CLASSE)
    pq.write_table(donnees, tampon)  # pyright: ignore[reportUnknownMemberType]
    st.ecrire(chemin, tampon.getvalue())


def ligne_classee(
    commentaire: Mapping[str, Any],
    video: Video,
    c: Classement,
    sel: bytes,
    aujourdhui: date,
    consignes: str,
) -> dict[str, Any]:
    return {
        "id": id_commentaire(str(commentaire["comment_id"]), sel),
        "auteur_hash": commentaire.get("auteur_hash"),
        "video_id": video.video_id,
        "source_id": video.source_id,
        "type_source": video.type_source,
        "format": video.format,
        "nature": video.nature,
        "publie_at": commentaire.get("publie_at"),
        "recupere_le": commentaire.get("recupere_le"),
        "est_politique": c.est_politique,
        "themes": list(c.themes),
        "position": c.position,
        "tonalite": c.tonalite,
        "hostilite": c.hostilite,
        "confiance": c.confiance,
        "confiance_position": c.confiance_position,
        "modele": MODELE,
        "version_taxonomie": VERSION_TAXONOMIE,
        "version_consignes": consignes,
        "classe_le": aujourdhui,
    }


@dataclass
class Bilan:
    a_classer: int = 0
    classes: int = 0
    erreurs: int = 0
    arret_budget: bool = False
    cout_usd: float = 0.0


def classer(
    st: Stockage,
    jev: ClientJev,
    commentaires: Iterable[Mapping[str, Any]],
    videos: Mapping[str, Video],
    sel: bytes,
    aujourdhui: date,
    paralleles: int = PARALLELES,
    lot: int = LOT,
    rapporter: Callable[[Bilan], None] | None = None,
    ecriture: int = ECRITURE,
    plafond: int | None = PLAFOND_PAR_VIDEO,
) -> Bilan:
    """Classe les commentaires non encore classés des vidéos connues ; écrit par morceaux.

    Un morceau est écrit tous les `ecriture` commentaires classés, à l'arrêt au budget et en
    cas d'erreur imprévue : un plantage perd au plus le classement en attente d'écriture.
    """
    deja, par_video = classes_par_video(st)
    consignes = version_consignes()
    a_faire: list[Mapping[str, Any]] = [
        x
        for x in commentaires
        if str(x["video_id"]) in videos
        and id_commentaire(str(x["comment_id"]), sel) not in deja
        and str(x.get("texte") or "").strip()
    ]
    if plafond is not None:
        a_faire = plafonner(a_faire, par_video, sel, plafond)
    bilan = Bilan(a_classer=len(a_faire))

    def un(x: Mapping[str, Any]) -> tuple[Mapping[str, Any], Classement | None]:
        v = videos[str(x["video_id"])]
        try:
            reps = jev.evaluer(
                etat_jev(ContexteVideo(v.titre, v.chaine, v.nature), str(x["texte"])),
                questions_jev(v.nature),
            )
        except ReponseInvalide as e:
            log.warning("commentaire ignoré : %s", e)
            return x, None
        return x, classement_jev(reps, v.nature)

    en_attente: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=paralleles) as pool:
        try:
            for i in range(0, len(a_faire), lot):
                lignes: list[dict[str, Any]] = []
                try:
                    for x, c in pool.map(un, a_faire[i : i + lot]):
                        if c is None:
                            bilan.erreurs += 1
                            continue
                        v = videos[str(x["video_id"])]
                        lignes.append(ligne_classee(x, v, c, sel, aujourdhui, consignes))
                except BudgetDepasse as e:
                    # Les appels déjà partis se terminent ; ceux qui ont abouti sont perdus pour ce
                    # lot uniquement s'ils n'ont pas été collectés : on écrit ce qu'on a.
                    log.warning("arrêt au budget : %s", e)
                    bilan.arret_budget = True
                en_attente.extend(lignes)
                if len(en_attente) >= ecriture:
                    ajouter_a_la_partition(st, aujourdhui, en_attente)
                    en_attente.clear()
                bilan.classes += len(lignes)
                bilan.cout_usd = jev.compteur.cout_usd
                if rapporter is not None:
                    rapporter(bilan)
                if bilan.arret_budget:
                    break
        finally:
            # Ce qui est classé est écrit même en cas d'erreur imprévue.
            ajouter_a_la_partition(st, aujourdhui, en_attente)
    return bilan
