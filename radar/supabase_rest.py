"""Accès Supabase via l'API REST (PostgREST), avec la clé secrète (batch uniquement)."""

import logging
from typing import Any

import requests

log = logging.getLogger(__name__)


class Supabase:
    def __init__(self, url: str, cle_secrete: str) -> None:
        self._base = url.rstrip("/") + "/rest/v1"
        self._headers = {"apikey": cle_secrete, "Content-Type": "application/json"}
        # Nouvelle clé secrète (sb_secret_…) : pas un JWT, seulement dans `apikey`.
        # Ancienne clé service_role (JWT) : aussi en Bearer.
        if not cle_secrete.startswith("sb_"):
            self._headers["Authorization"] = f"Bearer {cle_secrete}"

    def select(self, table: str, filtres: dict[str, str]) -> list[dict[str, Any]]:
        """Lecture PostgREST (ex. {"active": "eq.true"}), paginée par 1 000 lignes."""
        lignes: list[dict[str, Any]] = []
        while True:
            r = requests.get(
                f"{self._base}/{table}",
                params={"select": "*", **filtres},
                headers={**self._headers, "Range": f"{len(lignes)}-{len(lignes) + 999}"},
                timeout=60,
            )
            r.raise_for_status()
            page: list[dict[str, Any]] = r.json()
            lignes.extend(page)
            if len(page) < 1000:
                return lignes

    def upsert(self, table: str, lignes: list[dict[str, Any]], conflit: str) -> None:
        """Insère ou met à jour sur la clé `conflit`. Les colonnes absentes restent inchangées."""
        for i in range(0, len(lignes), 500):
            r = requests.post(
                f"{self._base}/{table}",
                params={"on_conflict": conflit},
                headers={**self._headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
                json=lignes[i : i + 500],
                timeout=60,
            )
            r.raise_for_status()
        if lignes:
            log.info("supabase upsert %s lignes=%d", table, len(lignes))

    def modifier(self, table: str, filtres: dict[str, str], valeurs: dict[str, Any]) -> None:
        """Met à jour les lignes qui passent les filtres (ex. {"video_id": "in.(a,b)"})."""
        r = requests.patch(
            f"{self._base}/{table}",
            params=filtres,
            headers={**self._headers, "Prefer": "return=minimal"},
            json=valeurs,
            timeout=60,
        )
        r.raise_for_status()

    def inserer(self, table: str, ligne: dict[str, Any]) -> None:
        r = requests.post(
            f"{self._base}/{table}",
            headers={**self._headers, "Prefer": "return=minimal"},
            json=ligne,
            timeout=30,
        )
        r.raise_for_status()
