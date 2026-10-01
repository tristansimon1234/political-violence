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
- Personnalités : les candidats déclarés à l'élection présidentielle selon la liste tenue par LCP. Les candidats à une primaire n'entrent qu'après le résultat, et seulement le vainqueur. Chaque candidat est suivi par sa chaîne personnelle ; s'il n'en a pas ou si elle est inactive, par la chaîne officielle de son parti ou mouvement. L'inverse n'existe pas : un parti n'est jamais représenté par la chaîne d'un de ses dirigeants.

**Filtres.**
1. Activité, pour toutes les chaînes sauf les partis : au moins 10 vidéos publiées sur les 90 derniers jours, formats courts (Shorts) compris. Les partis sont gardés quelle que soit leur activité : le silence d'un parti sur YouTube est une donnée.
2. Médias natifs du web : pas de filtre éliminatoire sur le contenu. Leur **taux de politisation** (part de leurs vidéos qui portent sur la politique française) est mesuré et publié ; seules leurs vidéos politiques alimentent les mesures du Radar.

**Chaîne officielle.** Pour chaque nom de la liste, seule la chaîne officielle est retenue. Aucune chaîne de dirigeant ne remplace celle d'un parti : un parti sans chaîne active est signalé comme tel. En cas de doute sur la bonne chaîne, le cas est signalé et tranché à la main, publiquement.

**Équilibre.** Aucune étiquette d'orientation politique n'est attribuée aux chaînes. L'équilibre éditorial d'ensemble est vérifié à la main, à partir de sources externes citées, et documenté.

**Réserve et revue mensuelle.** Les chaînes de la liste qui échouent aux filtres restent en réserve et sont retestées chaque mois. Une chaîne qui passe est proposée, jamais ajoutée automatiquement. Chaque entrée, sortie ou modification de la liste est datée dans le journal des changements.

## Collecte

**Source.** Uniquement l'API officielle YouTube Data v3, avec un seul projet et dans la limite du quota quotidien. Aucune collecte hors API.

**Vidéos.** Pour chaque chaîne active, les nouvelles vidéos sont lues dans la liste de ses mises en ligne. Chaque vidéo porte un **format** : `short` ou `long`. L'API ne fournit pas ce champ : une vidéo est classée `short` si elle dure 3 minutes ou moins et si son lecteur est vertical ou carré. Limite connue : avant octobre 2024, les Shorts duraient au plus 60 secondes, si bien qu'une vidéo verticale de 1 à 3 minutes publiée avant cette date peut être classée `short` à tort.

**Pré-filtre.** Les métadonnées (titre, description, tags) de toutes les vidéos du panel sont lues. Les commentaires ne sont collectés que pour les vidéos dont ces métadonnées contiennent au moins un mot-clé d'une liste publiée (institutions, élections, partis, personnalités candidates, grandes politiques publiques), et pour toutes les vidéos des chaînes politiques. Ce pré-filtre limite la collecte de données personnelles aux vidéos susceptibles de porter sur la politique ; il est volontairement large, le tri fin intervenant ensuite.

**Commentaires.** Les commentaires de premier niveau (sans les réponses) sont lus sous les vidéos retenues publiées dans les 3 derniers jours, une fois par jour : deux pages de 100 commentaires, classés par pertinence par YouTube, par vidéo longue, une page par Short. Pour une vidéo très commentée, le Radar lit donc les commentaires que YouTube met en avant (ordre « pertinence » : likes, réponses, récence), pas tous ses commentaires ; le volume de réactions d'une vidéo est lu dans le total de commentaires publié par YouTube, pas dans cet échantillon. Le taux de couverture (commentaires lus / total) est mesuré et publié.

**Vues.** Les vues des Shorts et des vidéos longues ne sont pas comparables : depuis 2025, YouTube compte chaque relecture d'un Short. Les métriques d'attention et d'intensité séparent donc toujours les deux formats.

**Données personnelles.** Les auteurs de commentaires sont remplacés par un identifiant chiffré ; aucun pseudo n'est conservé. Le texte des commentaires, les titres et les descriptions sont supprimés au plus tard 30 jours après leur récupération ; seuls les résultats agrégés sont conservés au-delà.

## Classification

**Ce qui est classé.** Chaque commentaire collecté est décrit par un modèle de langage selon une grille fermée : s'il parle de politique ou d'un enjeu d'intérêt public, ses thèmes (1 à 3, parmi 14), son émotion dominante et, sous les vidéos d'opinion seulement, son accord avec le propos de la vidéo. Il ne s'agit jamais de l'opinion de son auteur sur le sujet. Sous une vidéo factuelle (journal, reportage), aucune position n'est calculée.

**Neutralité.** Les consignes données aux modèles décrivent ce que dit le commentaire, sans juger s'il a raison et sans tenir compte de l'orientation de la vidéo ou de la chaîne. Les définitions des catégories sont publiées ici avant toute utilisation.

**Données envoyées aux modèles.** Le texte du commentaire, avec les mentions et les liens masqués, et le contexte de la vidéo (titre, chaîne, nature). Jamais l'auteur ni l'identifiant du commentaire. Les prestataires ne conservent pas les données et ne s'en servent pas pour entraîner leurs modèles (liste des sous-traitants publiée).

**Contrôle de qualité.** Avant l'usage, les modèles sont comparés à un étiquetage manuel d'un échantillon stratifié par catégorie de chaîne, format et nature de vidéo.
