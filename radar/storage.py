"""Stockage brut : Parquet partitionné par jour de récupération, purgé à 30 jours.

Deux tables brutes, une partition par jour : `commentaires/AAAA-MM-JJ.parquet` et
`videos/AAAA-MM-JJ.parquet`. Les noms de fichiers ne contiennent qu'une date (aucune donnée
personnelle dans les métadonnées d'objets).

Unicité : une ligne n'existe qu'une fois. Une ligne re-récupérée est écrite dans la partition
du jour et son ancienne copie est supprimée de la partition où elle se trouvait.
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
        r = requests.post(
            f"{self._base}/object/list/{self._bucket}",
            headers=self._headers,
            json={"prefix": prefixe.rstrip("/"), "limit": 1000, "offset": 0},
            timeout=60,
        )
        r.raise_for_status()
        objets: list[dict[str, Any]] = r.json()
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
    return f"{table}/{jour.isoformat()}.parquet"


def partitions(st: Stockage, table: str) -> dict[date, str]:
    """{jour: chemin} des partitions existantes d'une table."""
    resultat: dict[date, str] = {}
    for chemin in st.lister(table):
        nom = chemin.rsplit("/", 1)[-1]
        if nom.endswith(".parquet"):
            resultat[date.fromisoformat(nom.removesuffix(".parquet"))] = chemin
    return resultat


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
    st: Stockage, table: str, jour: date, lignes: Iterable[dict[str, Any]], depuis: date
) -> int:
    """Écrit `lignes` dans la partition `jour` en garantissant l'unicité de la clé.

    Les anciennes copies sont cherchées dans les partitions de `depuis` à `jour` (inclus) :
    `depuis` est la première date à laquelle ces objets ont pu être récupérés.
    """
    cle = CLES[table]
    nouvelles = {ligne[cle]: {**ligne, "recupere_le": jour} for ligne in lignes}
    if not nouvelles:
        return 0
    existantes = partitions(st, table)
    for jour_p, chemin in sorted(existantes.items()):
        if jour_p < depuis or jour_p == jour:
            continue
        anciennes = lire_partition(st, chemin)
        gardees = [ligne for ligne in anciennes if ligne[cle] not in nouvelles]
        if len(gardees) == len(anciennes):
            continue
        if gardees:
            _ecrire_partition(st, table, chemin, gardees)
        else:
            st.supprimer([chemin])
    chemin_jour = chemin_partition(table, jour)
    du_jour = lire_partition(st, chemin_jour) if jour in existantes else []
    finales = [ligne for ligne in du_jour if ligne[cle] not in nouvelles]
    finales.extend(nouvelles.values())
    _ecrire_partition(st, table, chemin_jour, finales)
    return len(nouvelles)


def purger(st: Stockage, aujourdhui: date, retention: int = RETENTION_JOURS) -> list[str]:
    """Supprime les partitions de `retention` jours ou plus (texte brut : 30 jours maximum)."""
    limite = aujourdhui - timedelta(days=retention - 1)
    a_supprimer = [
        chemin
        for table in TABLES_BRUTES
        for jour, chemin in partitions(st, table).items()
        if jour < limite
    ]
    st.supprimer(a_supprimer)
    return a_supprimer
