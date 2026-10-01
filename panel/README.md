# Panel

Règles : `docs/methodologie.md` (section Panel) et `docs/decisions.md` (liste fermée v1, 01/10/2026).

- `sources/panel_v1_liste_fermee.csv` : la liste fermée v1 (85 chaînes candidates), telle que fournie. Source de vérité du panel.
- `panel_v1.csv` : **panel v1 figé** (73 chaînes qui entrent), prêt pour l'import dans `sources`.
- `panel_v1_statut.csv` : verdict de chaque chaîne de la liste (entre, réserve, retiré, représenté par son parti…), avec les chiffres de l'audit.
- `vivier_v1.csv`, `vivier_v1_complement.csv` : la même liste, chaînes résolues (handle ou ID) pour l'audit. Les cas douteux sont marqués dans `confiance_handle` ; les doublons « à départager » sont mesurés sans être choisis.
- `archive_v0/` : panel et réserve selon les règles antérieures (taxonomie v2). Ne plus importer.

Audit (lecture seule, ne touche pas la table `sources`) :

    python scripts/audit_panel.py panel/vivier_v1.csv --budget 3000 > audit.md

Puis évaluation de la part de politique française des médias natifs sur `data/audit_titres.txt`, et suppression de ce fichier.
