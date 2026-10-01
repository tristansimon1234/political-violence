# Taxonomie, sujets d'actualité et métriques

## Taxonomie

Liste fermée pour la comparabilité, texte libre pour capter l'émergence.

- `theme` : `pouvoir_achat`, `securite`, `immigration`, `retraites`, `sante`, `education`, `ecologie_energie`, `economie_emploi`, `logement`, `institutions`, `international_defense`, `agriculture`, `societe`, `autre`
- `sous_sujet` : texte libre court et réutilisable
- `theme_propose` : rempli seulement si `theme == "autre"`
- `nature_video` : `info_factuelle`, `opinion_debat` (classée au niveau de la vidéo)
- `position` : **accord avec le propos de la vidéo**, pas opinion sur le sujet. Valeurs : `accord_video`, `nuance`, `desaccord_video`, `hors_sujet`. Calculée **uniquement sur les vidéos `opinion_debat`** ; `null` pour les vidéos factuelles. Affichée "Accord / Nuance / Désaccord avec la vidéo", jamais "pour / contre" un sujet. Le Radar ne mesure pas l'opinion sur les politiques publiques.
- `tonalite` : `positive`, `neutre`, `negative` (ton général du commentaire ; une opinion calme, même en désaccord, est `neutre`)
- `hostilite` : booléen. Oui : insulte, attaque personnelle, mépris ou déshumanisation visant une personne ou un groupe, menace, appel à la violence, colère agressive contre quelqu'un ; la moquerie seulement si elle vise une personne ou un groupe avec mépris. Non : désaccord même ferme, critique d'une politique ou d'une institution, ironie légère sur une situation, indignation sans attaque.
- Émotions fines (colère, inquiétude, lassitude…) : hors périmètre v1 (taxonomie v5, 01/10/2026).
- Chaque enregistrement porte `version_taxonomie`. Toute évolution de la liste = nouvelle version, reclassement possible tant que le brut existe.

**Vidéos multi-thèmes**
- Niveau vidéo : `sujets` = liste de 1 à 3 `{theme, sous_sujet, poids}`, poids sommant à 1, un `principal = true`.
- Niveau commentaire : chaque commentaire est compté dans **ses propres thèmes**, pas ceux de la vidéo. Un commentaire à n thèmes compte pour 1/n dans chacun, les totaux restent exacts.
- Chapitres de la description : utilisés comme indice pour les sujets quand ils existent.

Signal d'émergence : hausse de la part de `autre` + nouveaux groupes de `sous_sujet` dans le regroupement hebdomadaire.

## Sujets d'actualité

Unité principale du Radar. Les thèmes sont la grille de lecture stable ; les sujets d'actu sont ce à quoi les gens réagissent vraiment (un débat, une annonce, une petite phrase, un fait divers politisé).

- **Détection quotidienne** : Claude regroupe les vidéos politiques des derniers jours par événement, à partir des titres, descriptions et dates (sortie typée : `story_id`, titre neutre, thèmes rattachés, vidéos membres). Une vidéo appartient à 0 ou 1 sujet d'actu.
- **Cycle de vie** : un sujet naît quand au moins 3 vidéos de 2 chaînes différentes s'y rattachent, reste actif tant qu'il reçoit des réactions, s'éteint après 7 jours sans nouvelle vidéo ni hausse de commentaires.
- **Validation** : dans l'admin, Tristan peut renommer, fusionner, scinder ou masquer un sujet. Titre toujours neutre et factuel, sans nom de personne quand ce n'est pas indispensable.
- **Commentaires** : ils héritent du sujet d'actu de leur vidéo (on réagit à l'événement), mais gardent leurs propres thèmes.
- **Métriques par sujet** : couverture (nombre de vidéos et de chaînes), réactions (commentaires, intensité), vélocité, part médias traditionnels / médias natifs du web, accord avec la vidéo, tonalité, part de commentaires hostiles.
- **Récupération politique** : indicateur séparé, mesuré sur **qui publie** et non sur les commentaires. Pour chaque sujet : nombre et liste des partis et personnalités du panel qui ont publié une vidéo dessus, date de leur première vidéo, et timing par rapport aux médias traditionnels et natifs (avant : sujet lancé par un parti ; le jour même ; après : sujet repris). Le volume de commentaires sous leurs vidéos est affiché à part comme **mobilisation des soutiens**, jamais mélangé à la réaction du public ("Où ça réagit" = médias traditionnels + médias natifs du web uniquement).
- **Décalage** : couverture relative face à réaction relative. "Très couvert, peu de réactions" et "peu couvert, beaucoup de réactions" répondent directement à la question de départ du projet.

## Métriques

- **Vélocité** : commentaires sur 7 jours ÷ moyenne des 4 semaines précédentes, par thème, pondérés par l'audience de la source. ×1,0 = activité habituelle.
- **Attention** : vues (signal large, plus représentatif). Pour une vidéo multi-thèmes, les vues sont réparties selon la **part des commentaires classés dans chaque thème** ; repli sur les `poids` du LLM si la vidéo a moins de 30 commentaires classés.
- **Intensité** : commentaires par vue (signal militant).
- Quadrants de la carte : débat de fond (très vu, très discuté), minorité mobilisée (peu vu, très discuté), regardé en silence (très vu, peu discuté), bruit de fond.
- Toujours comparer une source ou un thème à **sa propre baseline**, jamais des plateformes ou des communautés entre elles.
