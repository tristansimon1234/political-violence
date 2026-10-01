# Étiquetage manuel (vérité terrain, étape 4)

100 commentaires de la semaine 1, tirés par strate (catégorie de source × format × nature de vidéo), à étiqueter par Tristan. Le rapport compare Jev et Claude à ces étiquettes.

## Circuit du fichier

1. Workflow « Évaluation Jev / Claude », commande `preparer`. Le fichier est déposé dans le bucket privé `radar-brut`, dossier `evaluation/`, sous le nom `AAAA-MM-JJ-etiquetage.csv`.
2. Le télécharger depuis Supabase (Storage → `radar-brut` → `evaluation`), le remplir dans Excel ou Numbers (séparateur `;`, UTF-8).
3. Le redéposer au même endroit sous le nom **`AAAA-MM-JJ-etiquetage-rempli.csv`** (même date), puis **supprimer la copie locale**.
4. Commande `evaluer` : le rapport intègre les étiquettes.

Le fichier contient du texte brut : il reste dans le bucket, il est purgé avec lui (30 jours après la récupération des commentaires), et il ne va jamais dans Git ni dans le rapport.

## Colonnes à remplir

Ne modifier que les trois dernières colonnes. Les autres servent de contexte : `ref`, catégorie, format, nature de la vidéo (classée par Claude), chaîne, titre, commentaire (mentions et liens masqués, comme pour les modèles).

- **`themes`** : le ou les thèmes **du commentaire lui-même** (pas de la vidéo), du plus au moins important, séparés par `+` (3 au plus). Exemple : `retraites+economie_emploi`. Écrire `aucun` si le commentaire ne parle pas de politique ni d'un enjeu d'intérêt public.
  Valeurs : `pouvoir_achat`, `securite`, `immigration`, `retraites`, `sante`, `education`, `ecologie_energie`, `economie_emploi`, `logement`, `institutions`, `international_defense`, `agriculture`, `societe`, `autre`.
- **`position`** : accord avec le **propos de la vidéo**, pas opinion sur le sujet. Seulement pour les vidéos `opinion_debat`. Pour les vidéos factuelles, la case contient déjà `-` : ne pas la modifier.
  Valeurs : `accord_video`, `nuance`, `desaccord_video`, `hors_sujet` (ne se prononce pas sur le propos).
- **`tonalite`** : ton général du commentaire.
  Valeurs : `positive`, `neutre`, `negative`.
- **`hostilite`** : `oui` ou `non` (vide = pas encore tranché, la dimension est alors ignorée).
  Oui : insulte, attaque personnelle, mépris ou déshumanisation visant une personne ou un groupe, menace, appel à la violence, colère agressive contre quelqu'un. Non : désaccord même ferme, critique d'une politique ou d'une institution, ironie légère sur une situation, indignation sans attaque (« c'est un scandale »).

## Règles de lecture (01/10/2026)

Tirées du premier étiquetage, et données telles quelles aux modèles :

1. **Politique** : un commentaire est politique s'il parle de politique ou d'un enjeu d'intérêt public, **y compris quand il réagit à l'événement d'intérêt public montré dans la vidéo sans nommer le sujet**. Il ne l'est pas s'il ne parle que de la vidéo elle-même (compliment, son, graphiques, musique, choix des invités), de la vie personnelle, de sport, d'un produit ou d'une publicité.
2. **Thèmes** : ceux du commentaire, pas ceux de la vidéo. Un commentaire qui réagit à l'événement de la vidéo sans nommer de sujet prend le thème de cet événement.
3. **Position** : accord avec la vidéo, jamais l'opinion sur le sujet. Elle s'applique à **tout** commentaire sous une vidéo d'opinion, y compris un commentaire sur la vidéo elle-même (compliment = accord ; critique de la vidéo, des invités ou de l'équilibre = désaccord). Pour un débat à plusieurs voix, on juge par rapport à la question ou à la thèse du titre.
4. **Tonalité** : une opinion exprimée calmement est `neutre`, même en désaccord.
5. **Hostilité** : la moquerie n'est hostile que si elle vise une personne ou un groupe avec mépris (« les boomers… ») ; pas si c'est une ironie sur une situation (« Génial, merci pour ce cadeau »).

Définitions complètes : celles des prompts (`radar/classification.py`, en anglais), publiées avec la méthodologie. Une ligne laissée vide est ignorée. Une valeur inconnue fait échouer `evaluer`, qui liste les lignes à corriger.

## Test synthétique (avant les vraies données)

`evaluation/synthetique_v1.csv` : 100 commentaires **fictifs**, écrits par Claude, sous 25 vidéos fictives (chaînes et titres inventés, aucun nom réel). Mêmes colonnes et mêmes valeurs que ci-dessus. Les données sont fictives : le fichier est versionné dans Git, et le rapport détaille les désaccords commentaire par commentaire.

1. Remplir `themes`, `position`, `tonalite`, `hostilite` sans regarder les réponses des modèles.
2. Remplacer le fichier sur la branche de travail (GitHub → Add file → Upload files, même chemin), ou l'envoyer à Claude.
3. Workflow « Évaluation Jev / Claude », commande `synthetique`.

Limites : des commentaires écrits par Claude sont probablement plus faciles pour Claude que de vrais commentaires ; pas de projection de coût de campagne (coût exprimé pour 1 million de commentaires). Le test sur la semaine 1 reste la référence.

## Arbitrage à l'aveugle (données synthétiques)

Quand Tristan, Jev et Claude ne sont pas d'accord, qui a raison ? La commande `synthetique` produit en plus, dans l'artefact « arbitrage » du workflow :
- `arbitrage_<fichier>.csv` : une ligne par désaccord (commentaire et dimension : thèmes, position, tonalité ou hostilité), les réponses en lice mélangées sous A, B, C, sans dire qui a répondu quoi ;
- `cle_<fichier>.json` : la clé. **Ne pas l'ouvrir avant d'avoir arbitré.**

Remplir la colonne `choix` : la lettre de la meilleure réponse, plusieurs lettres (`A+B`) si elles se valent, `aucune` si aucune ne convient. Puis `python scripts/evaluation.py arbitrage --fichier arbitrage_<fichier>.csv --cle cle_<fichier>.json` (aucun appel aux modèles) : part des désaccords gagnés par Tristan (premier jet), Jev et Claude, par dimension.

**Passage à la taxonomie v5 (01/10/2026).** Les étiquettes `emotion` des fichiers synthétiques ont été converties automatiquement : enthousiasme → positive ; neutre → neutre ; inquiétude, lassitude → negative, non hostile ; colère, moquerie → negative, **hostilité laissée vide** (à trancher par Tristan, colonne `note`). Claude n'a pas tranché ces cas, pour ne pas biaiser la comparaison.
