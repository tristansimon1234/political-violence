"""Accès Supabase via l'API REST (PostgREST), avec la clé service role (batch uniquement)."""

import logging
from typing import Any

import requests

log = logging.getLogger(__name__)


class Supabase:
    def __init__(self, url: str, service_key: str) -> None:
        self._base = url.rstrip("/") + "/rest/v1"
        self._headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
        }

    def upsert(self, table: str, lignes: list[dict[str, Any]], conflit: str) -> None:
        """Insère ou met à jour sur la clé `conflit`. Les colonnes absentes restent inchangées."""
        if not lignes:
            return
        r = requests.post(
            f"{self._base}/{table}",
            params={"on_conflict": conflit},
            headers={**self._headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
            json=lignes,
            timeout=30,
        )
        r.raise_for_status()
        log.info("supabase upsert %s lignes=%d", table, len(lignes))
