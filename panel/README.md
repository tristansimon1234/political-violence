# Panel

Règles : `docs/methodologie.md` (section Panel), décisions du 01/10/2026 dans `docs/decisions.md`.

- `candidats_declares.csv` : candidats déclarés à la présidentielle, entrée de la recherche standardisée (source c).
- `vivier.csv` : toutes les chaînes à auditer, avec leur catégorie et leur(s) source(s) du vivier.
- `archive_v0/` : panel et réserve selon les règles antérieures au 01/10/2026 (taxonomie v2), conservés pour la liste des changements. Ne plus importer.

Workflow :
1. `python scripts/recherche_vivier.py panel/candidats_declares.csv --budget 1500 > recherche.md`
2. Construction de `vivier.csv` (sources a à e), exclusion des médias traditionnels et des partis trouvés par la recherche.
3. `python scripts/audit_panel.py panel/vivier.csv --budget <reste> > audit.md`
4. Évaluation de la part de politique française des médias natifs sur `data/audit_titres.txt`, puis suppression de ce fichier.
5. Validation par Tristan, puis seulement import dans `sources`.
