"""Pseudonymisation des auteurs (RGPD) : hash à clé secrète, aucun identifiant en clair stocké."""

import hashlib
import hmac
import os


def sel() -> bytes:
    """Sel secret `RADAR_SEL`. Il ne doit jamais changer : sinon les hashs changent."""
    valeur = os.environ.get("RADAR_SEL")
    if not valeur or len(valeur) < 32:
        raise SystemExit("RADAR_SEL absent ou trop court (32 caractères minimum).")
    return valeur.encode()


def hash_auteur(auteur_channel_id: str | None, sel: bytes) -> str | None:
    """HMAC-SHA256 tronqué à 32 caractères hexadécimaux ; stable pour un même sel."""
    if not auteur_channel_id:
        return None
    return hmac.new(sel, auteur_channel_id.encode(), hashlib.sha256).hexdigest()[:32]
