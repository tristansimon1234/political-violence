from generer_taxonomie_ts import CIBLE, contenu


def test_taxonomie_ts_a_jour() -> None:
    """Échoue si radar/schemas.py a changé sans régénérer web/lib/taxonomie.ts."""
    assert CIBLE.read_text(encoding="utf-8") == contenu(), (
        "Lancer : python scripts/generer_taxonomie_ts.py"
    )
