# Méthodologie

Texte source de la page publique « Méthodologie ». Toute modification passe par `docs/decisions.md`.

Le Radar mesure ce qui fait réagir les personnes qui commentent sous les vidéos YouTube d'un panel de chaînes françaises. Il ne mesure pas l'opinion des Français et n'est pas un sondage.

## Panel

**Composition.** Une cinquantaine de chaînes YouTube, réparties en trois catégories. Les effectifs cibles (environ 25 médias, 12 influenceurs, 13 chaînes politiques) sont indicatifs : si trop peu de chaînes remplissent les critères, le panel reste en dessous plutôt que d'abaisser les critères.

**Catégories.**
- **Média** : marque éditoriale qui n'est pas incarnée par une seule personne (rédaction, plusieurs intervenants). Sous-types : info en continu, télé et radio, talk-show, presse nationale, pure player.
- **Influenceur** : chaîne incarnée par une personne identifiée (par son nom ou son visage), indépendante d'un groupe de presse. Sous-types : vulgarisation, commentateur, débat, interview longue.
- **Politique** : chaînes de partis et de personnalités. Elles sont **analysées à part** et jamais additionnées aux médias et influenceurs, car leurs commentaires viennent surtout de soutiens.
  - **Partis** : chaînes officielles des partis représentés à l'Assemblée nationale, quelle que soit leur activité. Aucune chaîne de dirigeant n'est utilisée en remplacement : un parti sans chaîne active est signalé comme tel.
  - **Personnalités** : toutes les personnalités candidates déclarées à l'élection présidentielle dont la chaîne passe le seuil d'activité, sans plafond.

**Critères d'entrée** (médias et influenceurs), appliqués dans cet ordre :
1. Contenu portant principalement sur la politique française.
2. Activité : au moins 10 vidéos publiées sur les 90 derniers jours, formats courts (Shorts) compris.
3. Commentaires ouverts sur la majorité des vidéos.
4. Classement par vues sur les 90 derniers jours (et non par nombre d'abonnés), dans la limite des effectifs par sous-type.

Les personnalités suivent le même seuil d'activité. Les partis en sont dispensés : l'inactivité d'un parti sur YouTube est elle-même une information.

**Équilibre.** Aucune étiquette d'orientation politique n'est attribuée aux chaînes. L'équilibre éditorial du panel (public / privé, lignes éditoriales) est vérifié à la main, à partir de sources externes citées, et documenté.

**Réserve.** Les chaînes écartées restent en réserve et sont retestées chaque mois avec les mêmes critères. Une chaîne de réserve qui passe les critères est proposée, jamais ajoutée automatiquement. Chaque entrée, sortie ou reclassement est daté dans le journal des changements.

## Collecte

**Source.** Uniquement l'API officielle YouTube Data v3, avec un seul projet et dans la limite du quota quotidien. Aucune collecte hors API.

**Vidéos.** Pour chaque chaîne active, les nouvelles vidéos sont lues dans la liste de ses mises en ligne. Chaque vidéo porte un **format** : `short` ou `long`. L'API ne fournit pas ce champ : une vidéo est classée `short` si elle dure 3 minutes ou moins et si son lecteur est vertical ou carré. Limite connue : avant octobre 2024, les Shorts duraient au plus 60 secondes, si bien qu'une vidéo verticale de 1 à 3 minutes publiée avant cette date peut être classée `short` à tort.

**Commentaires.** Les commentaires sont lus sous les vidéos récentes, à plusieurs reprises pendant quelques jours après la publication. Une seule page de commentaires est lue par Short.

**Vues.** Les vues des Shorts et des vidéos longues ne sont pas comparables : depuis 2025, YouTube compte chaque relecture d'un Short. Les métriques d'attention et d'intensité séparent donc toujours les deux formats.

**Données personnelles.** Les auteurs de commentaires sont remplacés par un identifiant chiffré ; aucun pseudo n'est conservé. Le texte des commentaires, les titres et les descriptions sont supprimés au plus tard 30 jours après leur récupération ; seuls les résultats agrégés sont conservés au-delà.
