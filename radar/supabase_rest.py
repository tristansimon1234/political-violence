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
