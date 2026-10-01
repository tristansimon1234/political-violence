# Panel

Généré depuis `panel_radar_2027_v0.xlsx`, puis ajusté par les décisions datées de `docs/decisions.md`. Critères : `docs/methodologie.md`, section Panel.

- `panel_v0.csv` : médias, influenceurs et partis retenus. À importer.
- `personnalites_a_decider.csv` : vivier des personnalités candidates. Retenues : celles qui passent le seuil (≥ 10 vidéos sur 90 jours, Shorts compris).
- `reserve.csv` : chaînes écartées, avec le motif. Retestées chaque mois. Ne pas importer.
- `candidats.csv` : candidats en cours de test (audit).
- `confiance_handle` : fiabilité du handle trouvé par recherche web. Colonne ignorée par l'import ; le `--dry-run` et l'audit affichent le nom résolu.

Sans chaîne : Reconquête (n'est plus dans la catégorie `parti`), Horizons (sans chaîne active), Marine Tondelier (pas de chaîne personnelle trouvée).
