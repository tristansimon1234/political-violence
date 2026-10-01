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
- **`emotion`** : émotion dominante.
  Valeurs : `colere`, `moquerie`, `inquietude`, `enthousiasme`, `lassitude`, `neutre`.

Définitions complètes : celles des prompts (`radar/classification.py`), publiées avec la méthodologie. Une ligne laissée vide est ignorée. Une valeur inconnue fait échouer `evaluer`, qui liste les lignes à corriger.

## Test synthétique (avant les vraies données)

`evaluation/synthetique_v1.csv` : 100 commentaires **fictifs**, écrits par Claude, sous 25 vidéos fictives (chaînes et titres inventés, aucun nom réel). Mêmes colonnes et mêmes valeurs que ci-dessus. Les données sont fictives : le fichier est versionné dans Git, et le rapport détaille les désaccords commentaire par commentaire.

1. Remplir `themes`, `position`, `emotion` sans regarder les réponses des modèles.
2. Remplacer le fichier sur la branche de travail (GitHub → Add file → Upload files, même chemin), ou l'envoyer à Claude.
3. Workflow « Évaluation Jev / Claude », commande `synthetique`.

Limites : des commentaires écrits par Claude sont probablement plus faciles pour Claude que de vrais commentaires ; pas de projection de coût de campagne (coût exprimé pour 1 million de commentaires). Le test sur la semaine 1 reste la référence.
