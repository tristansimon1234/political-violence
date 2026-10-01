# Méthodologie

Texte source de la page publique « Méthodologie ». Toute modification passe par `docs/decisions.md`.

Le Radar mesure ce qui fait réagir les personnes qui commentent sous les vidéos YouTube d'un panel de chaînes françaises. Il ne mesure pas l'opinion des Français et n'est pas un sondage.

## Panel

Le panel part d'une **liste fermée** de chaînes candidates, publiée. Aucune autre chaîne n'est recherchée. Des filtres fixes sont appliqués mécaniquement à chaque chaîne de la liste : celles qui passent entrent dans le panel, les autres restent en réserve. Il n'y a **pas de nombre cible**. La liste et les résultats des filtres sont revus chaque mois.

**Trois catégories.**
- **Médias traditionnels** : chaînes rattachées à une télévision, une radio ou un titre de presse.
- **Médias natifs du web** : médias nés sur Internet, sans télévision, radio ou titre de presse derrière, qu'ils soient incarnés par une personne ou non (pure players et créateurs).
- **Politiques** : chaînes de partis et de personnalités. Elles sont **lues à part** et jamais additionnées aux réactions du public, car leurs commentaires viennent surtout de soutiens.

**Origine de la liste.**
- Médias traditionnels : les médias nationaux retenus par l'étude de l'Université de Lausanne sur YouTube et les élections françaises (Sosnovik, Violot, Humbert, arXiv 2512.17768, table 14).
- Médias natifs du web : les pure players de la même étude, complétés par un choix éditorial publié ici avec la liste.
- Partis : les partis représentés à l'Assemblée nationale.
- Personnalités : les candidats déclarés à l'élection présidentielle selon la liste tenue par LCP. Les candidats à une primaire n'entrent qu'après le résultat, et seulement le vainqueur.

**Filtres.**
1. Activité, pour toutes les chaînes sauf les partis : au moins 10 vidéos publiées sur les 90 derniers jours, formats courts (Shorts) compris. Les partis sont gardés quelle que soit leur activité : le silence d'un parti sur YouTube est une donnée.
2. Médias natifs du web : pas de filtre éliminatoire sur le contenu. Leur **taux de politisation** (part de leurs vidéos qui portent sur la politique française) est mesuré et publié ; seules leurs vidéos politiques alimentent les mesures du Radar.

**Chaîne officielle.** Pour chaque nom de la liste, seule la chaîne officielle est retenue. Aucune chaîne de dirigeant ne remplace celle d'un parti : un parti sans chaîne active est signalé comme tel. En cas de doute sur la bonne chaîne, le cas est signalé et tranché à la main, publiquement.

**Équilibre.** Aucune étiquette d'orientation politique n'est attribuée aux chaînes. L'équilibre éditorial d'ensemble est vérifié à la main, à partir de sources externes citées, et documenté.

**Réserve et revue mensuelle.** Les chaînes de la liste qui échouent aux filtres restent en réserve et sont retestées chaque mois. Une chaîne qui passe est proposée, jamais ajoutée automatiquement. Chaque entrée, sortie ou modification de la liste est datée dans le journal des changements.

## Collecte

**Source.** Uniquement l'API officielle YouTube Data v3, avec un seul projet et dans la limite du quota quotidien. Aucune collecte hors API.

**Vidéos.** Pour chaque chaîne active, les nouvelles vidéos sont lues dans la liste de ses mises en ligne. Chaque vidéo porte un **format** : `short` ou `long`. L'API ne fournit pas ce champ : une vidéo est classée `short` si elle dure 3 minutes ou moins et si son lecteur est vertical ou carré. Limite connue : avant octobre 2024, les Shorts duraient au plus 60 secondes, si bien qu'une vidéo verticale de 1 à 3 minutes publiée avant cette date peut être classée `short` à tort.

**Commentaires.** Les commentaires sont lus sous les vidéos récentes, à plusieurs reprises pendant quelques jours après la publication. Une seule page de commentaires est lue par Short.

**Vues.** Les vues des Shorts et des vidéos longues ne sont pas comparables : depuis 2025, YouTube compte chaque relecture d'un Short. Les métriques d'attention et d'intensité séparent donc toujours les deux formats.

**Données personnelles.** Les auteurs de commentaires sont remplacés par un identifiant chiffré ; aucun pseudo n'est conservé. Le texte des commentaires, les titres et les descriptions sont supprimés au plus tard 30 jours après leur récupération ; seuls les résultats agrégés sont conservés au-delà.
