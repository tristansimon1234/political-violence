"""Stockage brut : Parquet partitionné par jour de récupération, purgé à 30 jours.

Deux tables brutes, `commentaires/` et `videos/`. Une partition = les fichiers d'un jour :
`AAAA-MM-JJ-NNN.parquet` (morceaux de 50 000 lignes au plus, ajoutés à chaque écriture) et
`AAAA-MM-JJ.parquet` (ancien format, un fichier par jour, toujours lu). Un fichier ne doit pas
dépasser la taille maximale d'un objet Supabase (50 Mo). Les noms de fichiers ne contiennent
qu'une date et un numéro (aucune donnée personnelle dans les métadonnées d'objets).

Unicité : une ligne n'existe qu'une fois. Une ligne re-récupérée est écrite dans un morceau du
jour et son ancienne copie est supprimée du fichier où elle se trouvait.
"""

import io
import logging
from collections.abc import Iterable
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Protocol

import pyarrow as pa
import pyarrow.parquet as pq
import requests

log = logging.getLogger(__name__)

RETENTION_JOURS = 30
TABLES_BRUTES = ("commentaires", "videos")
# Fichiers de travail dérivés du brut (échantillons, étiquetage) : `evaluation/AAAA-MM-JJ-….`,
# datés de la plus ancienne récupération des commentaires qu'ils contiennent, purgés pareil.
DOSSIER_EVALUATION = "evaluation"

SCHEMAS: dict[str, pa.Schema] = {
    # Aucun pseudo, aucun identifiant d'auteur en clair : seulement auteur_hash.
    "commentaires": pa.schema(
        [
            ("comment_id", pa.string()),
            ("video_id", pa.string()),
            ("source_id", pa.string()),
            ("auteur_hash", pa.string()),
            ("texte", pa.string()),
            ("likes", pa.int64()),
            ("nb_reponses", pa.int64()),
            ("publie_at", pa.timestamp("s", tz="UTC")),
            ("modifie_at", pa.timestamp("s", tz="UTC")),
            ("recupere_le", pa.date32()),
        ]
    ),
    "videos": pa.schema(
        [
            ("video_id", pa.string()),
            ("source_id", pa.string()),
            ("titre", pa.string()),
            ("description", pa.string()),
            ("tags", pa.list_(pa.string())),
            ("recupere_le", pa.date32()),
        ]
    ),
}
CLES = {"commentaires": "comment_id", "videos": "video_id"}
MAX_LIGNES_FICHIER = 50_000  # ~15 Mo de commentaires avec leur texte


class Stockage(Protocol):
    def lister(self, prefixe: str) -> list[str]: ...
    def lire(self, chemin: str) -> bytes: ...
    def ecrire(self, chemin: str, donnees: bytes) -> None: ...
    def supprimer(self, chemins: list[str]) -> None: ...


class StockageLocal:
    """Système de fichiers local (tests, essais)."""

    def __init__(self, racine: Path) -> None:
        self.racine = racine

    def lister(self, prefixe: str) -> list[str]:
        dossier = self.racine / prefixe
        if not dossier.exists():
            return []
        return sorted(f"{prefixe.rstrip('/')}/{p.name}" for p in dossier.iterdir() if p.is_file())

    def lire(self, chemin: str) -> bytes:
        return (self.racine / chemin).read_bytes()

    def ecrire(self, chemin: str, donnees: bytes) -> None:
        cible = self.racine / chemin
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(donnees)

    def supprimer(self, chemins: list[str]) -> None:
        for c in chemins:
            (self.racine / c).unlink(missing_ok=True)


class StockageSupabase:
    """Bucket privé Supabase Storage, accessible uniquement avec la clé secrète (batch)."""

    def __init__(self, url: str, cle_secrete: str, bucket: str) -> None:
        self._base = url.rstrip("/") + "/storage/v1"
        self._bucket = bucket
        self._headers = {"apikey": cle_secrete}
        if not cle_secrete.startswith("sb_"):
            self._headers["Authorization"] = f"Bearer {cle_secrete}"

    def lister(self, prefixe: str) -> list[str]:
        objets: list[dict[str, Any]] = []
        while True:
            r = requests.post(
                f"{self._base}/object/list/{self._bucket}",
                headers=self._headers,
                json={"prefix": prefixe.rstrip("/"), "limit": 1000, "offset": len(objets)},
                timeout=60,
            )
            r.raise_for_status()
            page: list[dict[str, Any]] = r.json()
            objets.extend(page)
            if len(page) < 1000:
                break
        return sorted(f"{prefixe.rstrip('/')}/{o['name']}" for o in objets if o.get("id"))

    def lire(self, chemin: str) -> bytes:
        r = requests.get(
            f"{self._base}/object/{self._bucket}/{chemin}", headers=self._headers, timeout=120
        )
        r.raise_for_status()
        return r.content

    def ecrire(self, chemin: str, donnees: bytes) -> None:
        r = requests.post(
            f"{self._base}/object/{self._bucket}/{chemin}",
            headers={
                **self._headers,
                "Content-Type": "application/octet-stream",
                "x-upsert": "true",
            },
            data=donnees,
            timeout=300,
        )
        r.raise_for_status()
        log.info("storage écrit %s (%d octets)", chemin, len(donnees))

    def supprimer(self, chemins: list[str]) -> None:
        if not chemins:
            return
        r = requests.delete(
            f"{self._base}/object/{self._bucket}",
            headers=self._headers,
            json={"prefixes": chemins},
            timeout=60,
        )
        r.raise_for_status()
        log.info("storage supprimé %s", ", ".join(chemins))


def chemin_partition(table: str, jour: date) -> str:
    """Ancien format : un fichier par jour (encore lu, plus écrit par le brut)."""
    return f"{table}/{jour.isoformat()}.parquet"


def partitions(st: Stockage, dossier: str) -> list[tuple[date, str]]:
    """(jour, chemin) de tous les fichiers Parquet d'un dossier, triés."""
    resultat: list[tuple[date, str]] = []
    for chemin in st.lister(dossier):
        jour = date_fichier(chemin)
        if chemin.endswith(".parquet") and jour is not None:
            resultat.append((jour, chemin))
    return sorted(resultat)


def morceaux_suivants(st: Stockage, dossier: str, jour: date, n: int) -> list[str]:
    """Chemins des `n` prochains morceaux du jour : `dossier/AAAA-MM-JJ-NNN.parquet`."""
    prefixe = f"{dossier}/{jour.isoformat()}-"
    pris = [
        int(c.removeprefix(prefixe).removesuffix(".parquet"))
        for c in st.lister(dossier)
        if c.startswith(prefixe) and c.removeprefix(prefixe).removesuffix(".parquet").isdigit()
    ]
    debut = max(pris, default=0) + 1
    return [f"{prefixe}{k:03d}.parquet" for k in range(debut, debut + n)]


def lire_partition(st: Stockage, chemin: str) -> list[dict[str, Any]]:
    # Stubs pyarrow incomplets sur la signature (types internes inconnus).
    table = pq.read_table(io.BytesIO(st.lire(chemin)))  # pyright: ignore[reportUnknownMemberType]
    return table.to_pylist()


def _ecrire_partition(st: Stockage, table: str, chemin: str, lignes: list[dict[str, Any]]) -> None:
    tampon = io.BytesIO()
    donnees = pa.Table.from_pylist(lignes, schema=SCHEMAS[table])
    pq.write_table(donnees, tampon)  # pyright: ignore[reportUnknownMemberType]
    st.ecrire(chemin, tampon.getvalue())


def enregistrer(
    st: Stockage,
    table: str,
    jour: date,
    lignes: Iterable[dict[str, Any]],
    depuis: date,
    index: dict[str, set[str]] | None = None,
) -> int:
    """Ajoute `lignes` en nouveaux morceaux du jour `jour`, en garantissant l'unicité de la clé.

    Les anciennes copies sont cherchées dans les fichiers de `depuis` à `jour` (inclus) :
    `depuis` est la première date à laquelle ces objets ont pu être récupérés. `index`
    (chemin → clés), partagé entre les écritures d'un même run, évite de relire un fichier
    déjà vu : chaque fichier est lu au plus une fois, sauf s'il faut le réécrire.
    """
    cle = CLES[table]
    nouvelles = {ligne[cle]: {**ligne, "recupere_le": jour} for ligne in lignes}
    if not nouvelles:
        return 0
    index = {} if index is None else index
    for jour_p, chemin in partitions(st, table):
        if jour_p < depuis or jour_p > jour:
            continue
        anciennes: list[dict[str, Any]] | None = None
        if chemin not in index:
            anciennes = lire_partition(st, chemin)
            index[chemin] = {str(ligne[cle]) for ligne in anciennes}
        if index[chemin].isdisjoint(nouvelles):
            continue
        anciennes = anciennes if anciennes is not None else lire_partition(st, chemin)
        gardees = [ligne for ligne in anciennes if ligne[cle] not in nouvelles]
        if gardees:
            _ecrire_partition(st, table, chemin, gardees)
            index[chemin] = {str(ligne[cle]) for ligne in gardees}
        else:
            st.supprimer([chemin])
            del index[chemin]
    finales = list(nouvelles.values())
    lots = [finales[i : i + MAX_LIGNES_FICHIER] for i in range(0, len(finales), MAX_LIGNES_FICHIER)]
    for chemin, lot in zip(morceaux_suivants(st, table, jour, len(lots)), lots, strict=True):
        _ecrire_partition(st, table, chemin, lot)
        index[chemin] = {str(ligne[cle]) for ligne in lot}
    return len(nouvelles)


def date_fichier(chemin: str) -> date | None:
    """Date en tête du nom de fichier (`AAAA-MM-JJ…`), None si absente."""
    try:
        return date.fromisoformat(chemin.rsplit("/", 1)[-1][:10])
    except ValueError:
        return None


def purger(st: Stockage, aujourdhui: date, retention: int = RETENTION_JOURS) -> list[str]:
    """Supprime les partitions et fichiers d'évaluation de `retention` jours ou plus.

    Texte brut : 30 jours maximum. Un fichier d'évaluation sans date est supprimé aussi.
    """
    limite = aujourdhui - timedelta(days=retention - 1)
    a_supprimer = [
        chemin for table in TABLES_BRUTES for jour, chemin in partitions(st, table) if jour < limite
    ]
    for chemin in st.lister(DOSSIER_EVALUATION):
        jour = date_fichier(chemin)
        if jour is None or jour < limite:
            a_supprimer.append(chemin)
    st.supprimer(a_supprimer)
    return a_supprimer
