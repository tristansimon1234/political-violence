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
- Panel : ~50 chaînes, référentiel dans la table Supabase `sources`, gérée depuis l'espace admin (voir `docs/interface.md`). Le batch quotidien lit les sources actives.
  - `media` (25) : info en continu, télé/radio, talk-shows, presse nationale, pure players
  - `influenceur` (12) : vulgarisation, commentateurs, débat
  - `politique` (13) : partis et personnalités. **Analysées à part** (chambres d'écho militantes), jamais agrégées avec le reste.
- Chaque source porte `type`, `sous_type`, et le critère qui justifie sa présence.
- Critère de sélection : quotas par sous-type, puis classement par **vues sur les 30 derniers jours** (pas par abonnés), sous condition d'activité (publication politique régulière, commentaires ouverts). Diversité éditoriale vérifiée ensuite (public/privé, lignes éditoriales). Vues et activité calculées automatiquement à l'import dans l'admin.
- Pas de champ "orientation politique" sur les médias et influenceurs. L'équilibre du panel se vérifie à la main et se documente.

## Règles non négociables

**YouTube API**
- Jamais `search.list` (100 unités). Passer par la playlist des uploads (1 unité).
- Quota : 10 000 unités/jour, remise à zéro à 9 h (Paris). Cible : 1 500 à 3 000/jour. Logger la consommation à chaque run.
- Un seul projet Google Cloud. Multiplier les projets pour cumuler du quota est interdit.
- Données brutes de l'API (texte des commentaires, titres, descriptions) : 30 jours maximum, puis suppression ou rafraîchissement. Les commentaires supprimés sur YouTube disparaissent chez nous.
- Métriques dérivées (thèmes, sentiment, vélocité) : rien de public ni de commercial avant l'acceptation du cas d'usage par YouTube.
- Pas de scraping hors API.

**RGPD** (opinions politiques = données sensibles)
- Auteurs hashés avec un sel secret (`RADAR_SEL`). Aucun pseudo stocké ni affiché.
- Travail en agrégé uniquement.
- Hébergement en UE.
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
- La position n'est jamais calculée sur une vidéo `info_factuelle`.
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

Maquette de référence : artifact Claude Design "Radar 2027" (écrans Cette semaine, Vue d'ensemble, Méthodologie, Admin).

## Pour Claude

- Réponses courtes et directes, en français.
- Toute sortie de modèle passe par un schéma typé. Pas de parsing de texte libre.
- Avant d'ajouter un appel API YouTube, estimer son coût en quota.
- Signaler toute modification qui toucherait aux règles ci-dessus (30 jours, RGPD, exports, neutralité) au lieu de l'implémenter en silence.
