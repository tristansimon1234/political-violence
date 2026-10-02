# Résultats des tests de classification (étape 4)

Journal des mesures, en agrégats. Le détail commentaire par commentaire n'est conservé que pour les jeux synthétiques (`evaluation/`). Référence : étiquettes de Tristan. « Tout juste » = toutes les dimensions justes à la fois : politique, thème principal, position, tonalité et hostilité (émotion avant la v5). C'est l'indicateur le plus sévère.

## Démarche

Question : un modèle peut-il classer les commentaires assez bien, et à quel coût, pour que les parts publiées par le Radar (thèmes, tonalité, hostilité, position) soient fiables ?

1. **Référence humaine.** Tristan étiquette à la main un jeu de commentaires selon la grille publiée (`docs/etiquetage.md`). Ses étiquettes servent de référence, sans être tenues pour infaillibles : il signale lui-même des doutes fréquents.
2. **Jeux synthétiques d'abord** (commentaires fictifs, versionnés) : ils permettent de mettre au point la grille et les consignes sans données personnelles, et d'afficher les désaccords mot à mot. Limite : un jeu qui a servi à écrire les règles surestime la justesse ; le jeu v2 (écrit par Tristan, jamais vu) sert de contrôle.
3. **Vrais commentaires ensuite** : 500 commentaires de la semaine 1, tirés par strate (catégorie de chaîne × format × nature de vidéo) pour que chaque type de chaîne et de vidéo soit représenté, pas seulement les plus commentés ; 100 étiquetés par Tristan. Fichiers dans le bucket brut, purgés à 30 jours ; seuls les agrégats sortent.
4. **Mesures** :
   - justesse par dimension face à Tristan, et accord entre Jev et Claude (sur les 500) : un accord faible signale une tâche ambiguë plutôt qu'un modèle défaillant ;
   - justesse de Jev par tranche de confiance : dit si la confiance permet de trier les classements sûrs ;
   - cascade (Jev, puis Claude sous un seuil de confiance) : justesse et coût projeté sur la campagne pour chaque seuil ;
   - **parts agrégées** (à partir du 02/10) : parts par thème, tonalité, hostilité et position selon Tristan, Jev et Claude, et écart en points. C'est ce que le Radar publie : des erreurs individuelles qui se compensent ne faussent pas une part.
5. **Une variable à la fois.** Chaque changement (langue des consignes, grille, contexte de la vidéo) est mesuré sur le même échantillon, avant / après.
6. **Arbitrage à l'aveugle** des désaccords (jeux synthétiques) : les réponses de Tristan, Jev et Claude sont présentées anonymisées ; mesure qui de la référence ou des modèles a raison quand ils divergent.

Limites : 100 étiquettes donnent une marge d'environ ±9 points sur une justesse ; une différence plus petite entre deux options n'est pas significative. Un seul annotateur. Les vidéos ne sont vues qu'à travers leur titre, leur chaîne et (à partir du 02/10) un résumé de leur description : les sous-titres ne sont pas accessibles par l'API.

## 01/10/2026 — Sonde (1 commentaire fictif)

Protocole TypeSafe sur la Gateway confirmé, ZDR respecté (DigitalOcean écarté). Jev ≈ 1 200 tokens d'entrée par commentaire.

## 01/10/2026 — Synthétique v1 (100 commentaires écrits par Claude), consignes en français

| Dimension | Jev | Claude |
|---|---:|---:|
| Politique / non politique | 88 % | 91 % |
| Thème principal | 77 % | 87 % |
| Position | 73 % | 73 % |
| Émotion | 65 % | 79 % |
| Tout juste | 44 % | 60 % |

Confiance de Jev bien calibrée (justesse 13 % sous 0,5 → 100 % au-dessus de 0,9). Coût : Jev 0,05 $ / 1 000, Claude 0,57 $ / 1 000.

## 01/10/2026 — Synthétique v1, consignes en anglais et règles explicites

| Dimension | Jev | Claude |
|---|---:|---:|
| Politique / non politique | 98 % | 92 % |
| Thème principal | 90 % | 88 % |
| Position | 88 % | 92 % |
| Émotion | 75 % | 81 % |
| Tout juste | 62 % | 70 % |

Cascade au seuil 0,7 : 74 % (mieux que Claude seul) pour ~400 $ / million contre 635 $. **Biais** : les règles ont été écrites à partir de ces 100 commentaires ; gain en partie mécanique.

## 01/10/2026 — Synthétique v2 (50 commentaires de Tristan, jamais vus pour écrire les règles)

5 étiquettes alignées sur les règles avant le test (trace dans la colonne `note`).

| Dimension | Jev | Claude |
|---|---:|---:|
| Politique / non politique | 96 % | 80 % |
| Thème principal | 75 % | 69 % |
| Au moins un thème commun | 88 % | 73 % |
| Position | 84 % | 84 % |
| Émotion | 68 % | 78 % |
| Tout juste | 42 % | 50 % |

Constats : Jev meilleur que Claude sauf sur l'émotion ; Claude manque la règle « réaction à l'événement = politique ». Beaucoup de désaccords sont des ambiguïtés (thème principal vs secondaire, colère / lassitude), et Tristan signale lui-même des doutes fréquents. Confiance de Jev non interprétable sur 50 commentaires (tranches de 8 à 20). Coût : Jev 0,06 $ / 1 000, Claude 0,70 $ / 1 000.

**Suite** : arbitrage à l'aveugle des désaccords (`docs/etiquetage.md`), puis test sur la semaine 1 réelle.

**Note (taxonomie v5, 01/10/2026)** : les résultats ci-dessus portent sur l'émotion en six catégories, abandonnée depuis ; les prochains tests mesurent la tonalité et l'hostilité.

## 01/10/2026 — Synthétique v1 reclassé par Tristan, taxonomie v6

Tonalité et hostilité à la place de l'émotion ; natures `opinion` / `debat` ; position seulement sous `opinion` (28 commentaires étiquetés).

| Dimension | Jev | Claude |
|---|---:|---:|
| Politique / non politique | 96 % | 91 % |
| Thème principal | 90 % | 88 % |
| Au moins un thème commun | 95 % | 90 % |
| Position | 82 % | 96 % |
| Tonalité | 81 % | 80 % |
| Hostilité | 95 % | 95 % |
| Tout juste | 66 % | 66 % |

Confiance de Jev bien calibrée (47 %, 45 %, 79 %, 94 % par tranche). **Cascade au seuil 0,7 : 75 %**, mieux que chaque modèle seul (66 %), pour ~380 $ / million (Jev seul ~60 $, Claude seul ~690 $). Erreurs de sens opposé, d'où le gain de la cascade : Claude sous-estime le négatif (griefs calmes classés neutres) et rate encore la règle « réaction à l'événement = politique » ; Jev voit du négatif dans des remarques neutres et répond `hors_sujet` sur des nuances. Hostilité : Jev a quelques faux positifs (critique d'une institution), Claude manque des accusations de mauvaise foi.

Correction : la recommandation automatique comparait chaque seuil à Claude seul ; elle retient maintenant l'option la moins chère à 2 points de la meilleure, cascade comprise (ici 0,7).

Réserve : ce jeu a servi à écrire les règles ; à confirmer sur v2 et sur la semaine 1.

## 02/10/2026 — Semaine 1 réelle, sans résumé de vidéo

500 commentaires classés par Jev et Claude, 100 étiquetés par Tristan (17 strates ; corrections d'étiquetage avant le run : 10 hostilités, 19 `societe` → `institutions`, faute de définitions sous les yeux). Contexte envoyé : titre, chaîne, nature.

| Dimension | Jev | Claude | Accord Jev / Claude (500) |
|---|---:|---:|---:|
| Politique / non politique | 90 % | 78 % | 81 % |
| Thème principal | 59 % | 48 % | 76 % |
| Au moins un thème commun | 72 % | 64 % | 87 % |
| Position (36 commentaires) | 44 % | 58 % | 59 % |
| Tonalité | 75 % | 71 % | 77 % |
| Hostilité | 69 % | 80 % | 77 % |
| Tout juste | 23 % | 26 % | 33 % |

Confiance de Jev : justesse « tout juste » 10 %, 21 %, 13 % puis 90 % (9/10) au-dessus de 0,9, soit 7 % des commentaires seulement. Cascade : 24 à 27 % selon le seuil, contre 23 % pour Jev seul, un écart dans la marge d'erreur, pour 5 à 15 fois le coût (Jev seul ~375 $ sur la campagne, cascade à 0,5 ~2 060 $, Claude seul ~5 540 $ ; ~6 M de commentaires projetés). Coût mesuré : Jev 0,06 $ / 1 000, Claude 0,92 $ / 1 000.

Constats :

- Chute nette par rapport aux jeux synthétiques (« tout juste » 66 % → 23-26 %). Jev et Claude ne s'accordent entre eux que sur un tiers des commentaires : sur de vrais commentaires, la tâche est ambiguë pour les modèles comme pour l'étiquetage humain.
- Jev fait mieux sur politique, thème et tonalité ; Claude sur position et hostilité.
- **La position est la dimension la plus faible** (44 % / 58 %) : c'est elle qui dépend le plus de ce que dit la vidéo, que ni Tristan ni les modèles ne voyaient.
- La recommandation automatique (seuil 0,5) n'est pas retenue : le gain de la cascade n'est pas significatif.

**Suite** : même échantillon avec un résumé de chaque vidéo (`evaluer --contexte`), puis lecture des parts agrégées.

## 02/10/2026 — Semaine 1 réelle, avec résumé de la vidéo

Même échantillon et mêmes étiquettes ; résumé d'une phrase par vidéo ajouté au contexte (180 vidéos, 10 sans description, 0,18 $).

| Dimension | Jev sans | Jev avec | Claude sans | Claude avec |
|---|---:|---:|---:|---:|
| Politique / non politique | 90 % | 85 % | 78 % | 74 % |
| Thème principal | 59 % | 56 % | 48 % | 47 % |
| Au moins un thème commun | 72 % | 69 % | 64 % | 59 % |
| Position (36) | 44 % | 44 % | 58 % | 58 % |
| Tonalité | 75 % | 75 % | 71 % | 72 % |
| Hostilité | 69 % | 70 % | 80 % | 81 % |
| Tout juste | 23 % | 22 % | 26 % | 28 % |

~~Le résumé n'apporte rien de mesurable.~~ **Mesure non valable** : le champ `resume` était facultatif dans le format de réponse imposé à Claude, qui a pu l'omettre ; un résumé vide n'est pas transmis. Le compteur « 180/180 » comptait les vidéos traitées, pas les résumés remplis, et la position est restée identique au commentaire près (16/36 et 21/36). Corrigé (champ obligatoire, contrôle des résumés non vides dans le rapport) ; test à refaire avec `--contexte --reclasser`. Les parts agrégées ci-dessous restent valables comme mesure sans contexte effectif.

Parts agrégées (100 commentaires étiquetés, avec résumé) :

| Part | Tristan | Jev | Claude |
|---|---:|---:|---:|
| institutions | 25 % | 38 % | 28 % |
| societe | 17 % | 9 % | 8 % |
| international_defense | 15 % | 10 % | 10 % |
| non politique | 15 % | 16 % | 35 % |
| Écart thèmes (points) | — | 16 | 23 |
| tonalité neutre | 24 % | 9 % | 26 % |
| tonalité négative | 59 % | 69 % | 53 % |
| Écart tonalité (points) | — | 15 | 6 |
| **hostile** | **13 %** | **43 %** | **30 %** |
| position : désaccord | 47 % | 17 % | 28 % |
| position : hors sujet | 19 % | 53 % | 33 % |
| Écart position (points) | — | 33 | 19 |

Constats : les erreurs **ne se compensent pas**, ce sont des biais systématiques, donc corrigeables par la grille plutôt que par le modèle :

- **Hostilité** : 13 % pour Tristan, 43 % pour Jev, 30 % pour Claude. La définition élargie en v6 (accusations de mauvaise foi, généralisations, moquerie) est appliquée beaucoup plus largement par les modèles que par l'étiquetage. En l'état, la part publiée serait 2 à 3 fois trop haute.
- **Position** : Jev classe `hors_sujet` la moitié des commentaires et manque les désaccords ; Claude est plus proche.
- **Thèmes** : frontière `institutions` / `societe` floue (Jev met en `institutions` ce que Tristan met en `societe`) ; Claude classe non politique un commentaire sur trois (règle « réaction à l'événement » toujours mal suivie).
- **Tonalité** : Jev voit du négatif là où Tristan voit du neutre ; Claude proche (6 points).

Recommandation automatique (seuil 0,9) non retenue : bruit sur 100 étiquettes.

## 02/10/2026 — Semaine 1 réelle, avec résumé de la vidéo (test refait)

Résumés contrôlés : 180 non vides sur 180 vidéos, 19 mots en moyenne, aucun « Sujet peu précis » (10 vidéos sans description, résumées depuis le titre seul). Coût des résumés : 0,18 $.

| Dimension | Jev sans | Jev avec | Claude sans | Claude avec |
|---|---:|---:|---:|---:|
| Politique / non politique | 90 % | 85 % | 78 % | 77 % |
| Thème principal | 59 % | 58 % | 48 % | 47 % |
| Au moins un thème commun | 72 % | 69 % | 64 % | 60 % |
| Position (36) | 44 % | 39 % | 58 % | 61 % |
| Tonalité | 75 % | 76 % | 71 % | 66 % |
| Hostilité | 69 % | 70 % | 80 % | 81 % |
| Tout juste | 23 % | 21 % | 26 % | 25 % |

Parts agrégées avec résumé : hostilité 13 % (Tristan) / 43 % (Jev) / 28 % (Claude) ; position `hors_sujet` 19 % / 56 % / 36 %, `desaccord_video` 47 % / 17 % / 28 % ; `institutions` 25 % / 39 % / 30 %, `societe` 17 % / 8 % / 8 % ; non politique 15 % / 16 % / 32 % ; écart tonalité 16 (Jev) et 10 (Claude) points.

**Verdict : le résumé tiré de la description n'apporte rien** (tous les écarts dans la marge, biais inchangés). Le facteur limitant n'est pas le contexte transmis mais la grille (hostilité, position, `institutions` / `societe`) et peut-être la référence elle-même. Prochaine étape proposée : arbitrage à l'aveugle des désaccords sur ces vrais commentaires.

Incident : le run se termine par « terminate called without an active exception » (code 134) après l'écriture du rapport et des résultats ; rien de perdu, cause à chercher (fermeture d'une bibliothèque à la sortie).

