# Panel

Généré depuis `panel_radar_2027_v0.xlsx` (onglet « Panel v0 »). Critères : onglet « Critères » du même fichier, repris dans `docs/decisions.md`.

- `panel_v0.csv` : chaînes retenues (42). À importer.
- `reserve.csv` : chaînes écartées, avec le motif (ne pas importer).
- `personnalites_a_decider.csv` : 12 personnalités, à passer en `--dry-run` seulement, pour appliquer le critère d'activité (> 10 vidéos sur 3 mois, puis les 4 plus actives).
- `confiance_handle` : fiabilité du handle trouvé par recherche web (non vérifié sur YouTube). Colonne ignorée par l'import ; le `--dry-run` affiche le nom résolu à côté du nom attendu pour contrôle.

Sans chaîne trouvée : Reconquête (pas de chaîne nationale du parti), Marine Tondelier (pas de chaîne personnelle).
