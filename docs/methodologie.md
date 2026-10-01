# Méthodologie

Texte source de la page publique « Méthodologie ». Toute modification passe par `docs/decisions.md`.

Le Radar mesure ce qui fait réagir les personnes qui commentent sous les vidéos YouTube d'un panel de chaînes françaises. Il ne mesure pas l'opinion des Français et n'est pas un sondage.

## Panel

Le panel est constitué par des règles fixes, appliquées mécaniquement à chaque chaîne. Il n'y a **pas de nombre cible** : toute chaîne qui remplit les règles entre dans le panel ; les autres restent en réserve.

**Trois catégories.**
- **Médias traditionnels** : chaînes rattachées à une télévision, une radio ou un titre de presse.
- **Médias natifs du web** : médias nés sur Internet, sans télévision, radio ou titre de presse derrière, qu'ils soient incarnés par une personne ou non (pure players et créateurs).
- **Politiques** : chaînes de partis et de personnalités. Elles sont **lues à part** et jamais additionnées aux réactions du public, car leurs commentaires viennent surtout de soutiens.

**Critère commun d'activité** : au moins 10 vidéos publiées sur les 90 derniers jours, formats courts (Shorts) compris.

**Médias traditionnels.** Base : les 36 médias nationaux retenus par l'étude de l'Université de Lausanne sur YouTube et les élections françaises (Sosnovik, Violot, Humbert, arXiv 2512.17768). Ils sont conservés s'ils passent le critère d'activité.

**Médias natifs du web.** Le vivier réunit, pour chaque chaîne, la ou les sources d'où elle vient :
1. les pure players de l'étude de Lausanne ;
2. les chaînes de créateurs déjà suivies avant la refonte du panel ;
3. une recherche standardisée, identique pour chaque candidat déclaré à la présidentielle : les 25 premières vidéos YouTube pour « <nom> interview », en français, publiées dans les 12 derniers mois ; seules les chaînes qui ne sont ni des médias traditionnels ni des partis sont retenues ;
4. les créateurs cités par l'AFP dans son article du 31 mai 2026 sur les créateurs de contenu et la présidentielle ;
5. en appoint, le classement HypeAuditor « Infos et Politique » France.

Une chaîne du vivier entre si au moins la moitié des titres de ses 20 dernières vidéos porte sur la politique française et si elle passe le critère d'activité.

**Politiques.**
- **Partis** : chaînes officielles des partis représentés à l'Assemblée nationale, quelle que soit leur activité : le silence d'un parti sur YouTube est une donnée. Aucune chaîne de dirigeant n'est utilisée en remplacement ; un parti sans chaîne active est signalé comme tel.
- **Personnalités** : tous les candidats déclarés à l'élection présidentielle dont la chaîne passe le critère d'activité, sans plafond.

**Équilibre.** Aucune étiquette d'orientation politique n'est attribuée aux chaînes. L'équilibre éditorial d'ensemble est vérifié à la main, à partir de sources externes citées, et documenté.

**Réserve.** Les chaînes qui ne remplissent pas les règles restent en réserve et sont retestées chaque mois avec les mêmes règles. Une chaîne de réserve qui passe est proposée, jamais ajoutée automatiquement. Chaque entrée, sortie ou reclassement est daté dans le journal des changements.

## Collecte

**Source.** Uniquement l'API officielle YouTube Data v3, avec un seul projet et dans la limite du quota quotidien. Aucune collecte hors API. La recherche par mots-clés de l'API n'est utilisée qu'une fois, pour constituer le vivier des médias natifs (voir Panel).

**Vidéos.** Pour chaque chaîne active, les nouvelles vidéos sont lues dans la liste de ses mises en ligne. Chaque vidéo porte un **format** : `short` ou `long`. L'API ne fournit pas ce champ : une vidéo est classée `short` si elle dure 3 minutes ou moins et si son lecteur est vertical ou carré. Limite connue : avant octobre 2024, les Shorts duraient au plus 60 secondes, si bien qu'une vidéo verticale de 1 à 3 minutes publiée avant cette date peut être classée `short` à tort.

**Commentaires.** Les commentaires sont lus sous les vidéos récentes, à plusieurs reprises pendant quelques jours après la publication. Une seule page de commentaires est lue par Short.

**Vues.** Les vues des Shorts et des vidéos longues ne sont pas comparables : depuis 2025, YouTube compte chaque relecture d'un Short. Les métriques d'attention et d'intensité séparent donc toujours les deux formats.

**Données personnelles.** Les auteurs de commentaires sont remplacés par un identifiant chiffré ; aucun pseudo n'est conservé. Le texte des commentaires, les titres et les descriptions sont supprimés au plus tard 30 jours après leur récupération ; seuls les résultats agrégés sont conservés au-delà.
