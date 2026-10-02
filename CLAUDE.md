# Radar 2027

Carte des sujets qui font réagir pendant la présidentielle 2027, construite à partir
des commentaires YouTube d'un panel de ~50 chaînes françaises.

Question testée : **les commentaires racontent-ils autre chose que l'agenda médiatique ?**
Ce que le projet mesure : ce qui fait réagir ceux qui réagissent sur YouTube.
Ce qu'il ne mesure pas : l'opinion des Français. Ne jamais le présenter comme un sondage.

Statut : expérimentation privée. Rien n'est publié ni vendu tant que YouTube n'a pas
accepté le cas d'usage "métriques dérivées" (voir Règles).

## Calendrier

- 1er tour : 18 avril 2027. Collecte jusqu'au second tour.
- Demande d'audit YouTube à déposer dès qu'un prototype fonctionne (délai : semaines à mois).

## Périmètre

- Plateforme : YouTube uniquement (API Data v3). X / TikTok éventuels plus tard, en source de contrôle.
- Panel : référentiel dans la table Supabase `sources`, gérée depuis l'espace admin (voir `docs/interface.md`). Le batch quotidien lit les sources actives. **Liste fermée v1** (`panel/sources/panel_v1_liste_fermee.csv`, `docs/decisions.md` du 01/10/2026) : aucune autre chaîne n'est recherchée ; filtres appliqués mécaniquement ; revue mensuelle. **Pas de cible de nombre** : tout ce qui passe entre, le reste va en réserve.
  - `media_traditionnel` (« Médias traditionnels ») : chaîne rattachée à une télévision, une radio ou un titre de presse. Source : les médias nationaux de l'étude de Lausanne (arXiv 2512.17768, table 14).
  - `media_natif` (« Médias natifs du web ») : nés sur Internet, sans télévision, radio ou titre de presse derrière, incarnés par une personne ou non (pure players et créateurs). Source : pure players de Lausanne et choix éditorial publié dans la méthodologie. Pas de filtre politique éliminatoire : taux de politisation mesuré et publié.
  - `politique` (« Politiques ») : **lues à part** (chambres d'écho militantes), jamais agrégées aux réactions du public.
    - `parti` : chaînes officielles des partis représentés à l'Assemblée, quelle que soit leur activité. Pas de chaîne de dirigeant en substitut ; un parti sans chaîne est noté « sans chaîne active ».
    - `personnalite` : candidats déclarés selon la liste LCP, sans plafond. Chaîne personnelle si elle passe le critère d'activité, sinon chaîne officielle de leur parti ou mouvement (même critère ; pas de doublon si le parti est déjà en `parti`). Candidats à une primaire : seul le vainqueur peut entrer.
- Critère commun d'activité : **≥ 10 vidéos sur 90 jours, Shorts compris** (partis exemptés).
- Chaque source porte `type`, `sous_type`, et le critère (et les sources du vivier) qui justifient sa présence.
- Réserve : chaînes de la liste qui échouent aux filtres, retestées à chaque revue mensuelle ; une chaîne qui passe est proposée, jamais ajoutée automatiquement.
- Shorts inclus partout, avec un champ `format` (`short` / `long`). Tous les commentaires de premier niveau, Shorts compris (décision du 02/10/2026). Vues séparées par format dans les métriques d'attention et d'intensité.
- Pas de champ "orientation politique" sur les médias. L'équilibre du panel se vérifie à la main et se documente.

## Règles non négociables

**YouTube API**
- Jamais `search.list` (100 unités). Passer par la playlist des uploads (1 unité).
- Quota : 10 000 unités/jour, remise à zéro à 9 h (Paris), non achetable (extension seulement après audit YouTube). Cible : ~3 000/jour en régime normal (collecte quotidienne, budget de run 4 000), jusqu'à ~9 000/jour pendant un backfill, jamais plus de 10 000. Logger la consommation à chaque run.
- Un seul projet Google Cloud. Multiplier les projets pour cumuler du quota est interdit.
- Données brutes de l'API (texte des commentaires, titres, descriptions) : 30 jours maximum, puis suppression ou rafraîchissement. Les commentaires supprimés sur YouTube disparaissent chez nous.
- Métriques dérivées (thèmes, sentiment, vélocité) : rien de public ni de commercial avant l'acceptation du cas d'usage par YouTube.
- Pas de scraping hors API.

**RGPD** (opinions politiques = données sensibles)
- Auteurs hashés avec un sel secret (`RADAR_SEL`). Aucun pseudo stocké ni affiché.
- Travail en agrégé uniquement.
- Stockage en UE. Traitement transitoire hors UE autorisé seulement chez un sous-traitant couvert par un DPA avec clauses contractuelles types ou par le Data Privacy Framework, sans conservation ni entraînement, avec des données minimisées (texte masqué, jamais d'auteur ni d'identifiant de commentaire). Chaque sous-traitant est listé dans `docs/sous-traitants.md` et dans l'AIPD.
- Exports et rapports : agrégats seulement, **jamais de texte brut, de citation ni de titre de vidéo**.
- Drilldown verbatims : 30 derniers jours, texte non modifié, lien vers la vidéo source, pas de pseudo, quelques exemples par sujet plutôt que des listes complètes.

**Neutralité**
- Critères du panel et de la taxonomie écrits avant les choix, et publiés avec la méthodologie.
- Prompts de classification neutres, sans jugement sur le fond.
- Pas de chiffres inventés sur de vraies personnalités, y compris dans les maquettes.

## Règles de développement

**Périmètre**
- Une étape à la fois, dans l'ordre des "Prochaines étapes". Ne pas anticiper l'étape suivante ni ajouter de fonctionnalité non demandée.
- Avant de coder une étape : annoncer en 3 à 5 lignes ce qui va être fait et les fichiers touchés. Attendre le feu vert si ça change l'architecture, le schéma de données ou la stack.
- Une étape se termine par une démo vérifiable (commande à lancer, résultat attendu) et un commit.

**Code**
- Python typé partout, vérifié par `pyright` (mode strict) et `ruff`. TypeScript en `strict`.
- Pas de nouvelle dépendance sans le signaler et le justifier. Préférer la bibliothèque standard.
- Simple d'abord : pas d'abstraction, de framework ou de couche générique tant qu'un seul cas l'utilise.
- `schemas.py` est la source de vérité de la taxonomie. Toute modification incrémente `version_taxonomie` et régénère les schémas Zod ; jamais de liste de thèmes dupliquée à la main ailleurs.
- Schéma Supabase modifié uniquement par migration versionnée, jamais à la main.
- Jobs idempotents (relancer un run ne crée pas de doublon) et avec un mode `--dry-run`.
- Chaque appel externe (YouTube, Jev, Claude) passe par un client unique qui journalise coût et quota.

**Invariants testés** (tests automatiques qui doivent échouer si la règle est cassée)
- Aucun texte de commentaire dans la table classée, les agrégats ou les exports.
- Aucune partition brute de plus de 30 jours après la purge.
- Aucun pseudo ni identifiant d'auteur en clair ; hash stable avec le même sel.
- "Où ça réagit" et les réactions du public n'incluent jamais les chaînes politiques.
- Un commentaire multi-thèmes compte pour 1/n dans chacun : les totaux par thème égalent le total des commentaires.
- La position n'est jamais calculée sur une vidéo `info_factuelle` ni `debat`.
- Un run ne dépasse jamais le budget de quota configuré.

**CI** : GitHub Actions lance lint, typage et tests à chaque push. Pas de merge si c'est rouge.

**Décisions**
- Toute décision qui modifie le projet (architecture, métrique, règle) est d'abord proposée, puis, une fois validée, datée dans `docs/decisions.md` et reportée dans le fichier concerné. Ce fichier et `docs/` restent la référence : en cas de doute entre le code et la documentation, demander.
- Ne jamais contourner une règle non négociable pour faire passer un test, une démo ou un délai.

## Documentation détaillée

À lire **avant** de travailler sur la partie concernée, pas besoin de tout relire à chaque session :

- `docs/architecture.md` : pipeline, stack, structure du repo, budget.
- `docs/donnees.md` : taxonomie, sujets d'actualité, métriques (vélocité, attention, intensité, multi-thèmes, récupération politique, décalage).
- `docs/interface.md` : écrans, couche éditoriale, résumés IA, filtres, espace admin.
- `docs/backfill-septembre.md` : premier chantier data.
- `docs/roadmap.md` : étapes dans l'ordre, préalables hors code, points à décider.
- `docs/decisions.md` : journal des décisions datées. Y ajouter toute nouvelle décision validée.
- `docs/methodologie.md` : texte source de la page publique Méthodologie (panel, collecte).
- `docs/etiquetage.md` : étiquetage manuel de la vérité terrain et arbitrage à l'aveugle (étape 4).
- `docs/evaluation-resultats.md` : journal des tests de classification (agrégats).
- `docs/sous-traitants.md` : sous-traitants (localisation, conservation, entraînement, transferts), prêt pour l'AIPD.

Maquette de référence : artifact Claude Design "Radar 2027" (écrans Cette semaine, Vue d'ensemble, Méthodologie, Admin).

## Pour Claude

- Réponses courtes et directes, en français.
- Toute sortie de modèle passe par un schéma typé. Pas de parsing de texte libre.
- Avant d'ajouter un appel API YouTube, estimer son coût en quota.
- Signaler toute modification qui toucherait aux règles ci-dessus (30 jours, RGPD, exports, neutralité) au lieu de l'implémenter en silence.
