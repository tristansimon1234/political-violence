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
- Panel : ~50 chaînes, référentiel dans la table Supabase `sources`, gérée depuis l'espace admin (voir plus bas). Le batch quotidien lit les sources actives.
  - `media` (25) : info en continu, télé/radio, talk-shows, presse nationale, pure players
  - `influenceur` (12) : vulgarisation, commentateurs, débat
  - `politique` (13) : partis et personnalités. **Analysées à part** (chambres d'écho militantes), jamais agrégées avec le reste.
- Chaque source porte `type`, `sous_type`, et le critère qui justifie sa présence.
- Critère de sélection : quotas par sous-type, puis classement par **vues sur les 90 derniers jours** (pas par abonnés), sous condition d'activité (publication politique régulière, commentaires ouverts). Diversité éditoriale vérifiée ensuite (public/privé, lignes éditoriales). Vues et activité calculées automatiquement à l'import dans l'admin.
- Pas de champ "orientation politique" sur les médias et influenceurs. L'équilibre du panel se vérifie à la main et se documente.

## Architecture

```
YouTube API ─▶ collecte ─▶ filtre politique ─▶ classification ─▶ stockage ─▶ agrégats ─▶ interface
```

1. **Collecte** : playlist des uploads de chaque chaîne → `videos.list` → `commentThreads.list` (ordre pertinence, pages de 100). Repasser sur les vidéos récentes pendant quelques jours.
2. **Filtre politique (entonnoir)** : mots-clés sur titre/description/tags → Jev (`politique_directe` / `enjeu_public` / `hors_sujet`) → Claude si confiance < seuil. Les chaînes politiques ne sont pas filtrées.
3. **Classification (cascade)** :
   - **Jev** (TypeSafe, via Vercel AI Gateway) : classification fermée des commentaires à volume (est_politique, thèmes, position vis-à-vis de la vidéo, émotion, candidat visé dans une liste fermée). Renvoie des probabilités et une confiance.
   - **Claude** (`claude-haiku-4-5`, `client.messages.parse` + Pydantic) : analyse des vidéos (sujets pondérés, `nature_video`), `sous_sujet` libre, `theme_propose`, regroupement hebdomadaire des sous-sujets, et reprise des commentaires où Jev a une confiance faible.
   - **Sujets d'actualité** : regroupement quotidien des vidéos par événement (Claude, sortie typée), voir la section dédiée.
4. **Stockage** :
   - Brut (texte des commentaires) : Parquet partitionné par jour, **30 jours maximum**. Sert à classer, reclasser dans la fenêtre si la taxonomie change, et au drilldown. Job de purge quotidien qui supprime les partitions de plus de 30 jours. Pas de rafraîchissement en boucle pour prolonger la conservation.
   - Classé (une ligne par commentaire, **sans texte**) : DuckDB. Thème, position, émotion, confiance, auteur hashé, date, vidéo. C'est ce qui est conservé sur toute la campagne.
   - Identifiant du commentaire : remplacé par un identifiant interne hashé (même sel que les auteurs) dans la table classée. À vérifier dans les règles YouTube avant de conserver l'ID d'origine au-delà de 30 jours.
   - Agrégats (sujet d'actu × jour × type de source, thème × jour × type de source, récupération politique) : recalculés chaque nuit, poussés dans Supabase (région UE) quand l'interface passe en ligne.
5. **Interface** : lit uniquement les agrégats, plus un drilldown verbatims limité aux 30 derniers jours.

## Taxonomie

Liste fermée pour la comparabilité, texte libre pour capter l'émergence.

- `theme` : `pouvoir_achat`, `securite`, `immigration`, `retraites`, `sante`, `education`, `ecologie_energie`, `economie_emploi`, `logement`, `institutions`, `international_defense`, `agriculture`, `societe`, `autre`
- `sous_sujet` : texte libre court et réutilisable
- `theme_propose` : rempli seulement si `theme == "autre"`
- `nature_video` : `info_factuelle`, `opinion_debat` (classée au niveau de la vidéo)
- `position` : **accord avec le propos de la vidéo**, pas opinion sur le sujet. Valeurs : `accord_video`, `nuance`, `desaccord_video`, `hors_sujet`. Calculée **uniquement sur les vidéos `opinion_debat`** ; `null` pour les vidéos factuelles. Affichée "Accord / Nuance / Désaccord avec la vidéo", jamais "pour / contre" un sujet. Le Radar ne mesure pas l'opinion sur les politiques publiques.
- `emotion` : `colere`, `moquerie`, `inquietude`, `enthousiasme`, `lassitude`, `neutre`
- `tonalite` : `positive`, `neutre`, `negative`
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
- **Métriques par sujet** : couverture (nombre de vidéos et de chaînes), réactions (commentaires, intensité), vélocité, part médias / influenceurs, accord avec la vidéo, émotion dominante.
- **Récupération politique** : indicateur séparé, mesuré sur **qui publie** et non sur les commentaires. Pour chaque sujet : nombre et liste des partis et personnalités du panel qui ont publié une vidéo dessus, date de leur première vidéo, et timing par rapport aux médias (avant : sujet lancé par un parti ; le jour même ; après : sujet repris). Le volume de commentaires sous leurs vidéos est affiché à part comme **mobilisation des soutiens**, jamais mélangé à la réaction du public ("Où ça réagit" = médias + influenceurs uniquement).
- **Décalage** : couverture relative face à réaction relative. "Très couvert, peu de réactions" et "peu couvert, beaucoup de réactions" répondent directement à la question de départ du projet.

## Métriques

- **Vélocité** : commentaires sur 7 jours ÷ moyenne des 4 semaines précédentes, par thème, pondérés par l'audience de la source. ×1,0 = activité habituelle.
- **Attention** : vues (signal large, plus représentatif). Pour une vidéo multi-thèmes, les vues sont réparties selon la **part des commentaires classés dans chaque thème** ; repli sur les `poids` du LLM si la vidéo a moins de 30 commentaires classés.
- **Intensité** : commentaires par vue (signal militant).
- Quadrants de la carte : débat de fond (très vu, très discuté), minorité mobilisée (peu vu, très discuté), regardé en silence (très vu, peu discuté), bruit de fond.
- Toujours comparer une source ou un thème à **sa propre baseline**, jamais des plateformes ou des communautés entre elles.

## Espace admin (gestion des sources)

Page `/admin` de l'app Next.js, réservée à Tristan (Supabase Auth, un seul compte admin, RLS : écriture sur `sources` pour l'admin uniquement).

**Ajouter une source**
1. Coller l'URL ou le handle de la chaîne.
2. Résolution via l'API (`channels.list` avec `forHandle` ou `id`, 1 unité) → aperçu : nom, abonnés, dernière vidéo, fréquence de publication.
3. Choisir `type` et `sous_type` (listes fermées issues de la taxonomie).
4. Saisir le **critère d'inclusion** : champ obligatoire, pas d'ajout sans justification.
5. Enregistrer : la source est active dès le prochain run.

**Règles**
- On ne supprime jamais une source : on la **met en pause** (`active = false`), l'historique déjà classé reste cohérent.
- Chaque ajout, pause ou modification crée une entrée datée dans `sources_journal`, qui alimente automatiquement le **journal des changements public**.
- Vue d'ensemble de l'équilibre du panel : nombre de sources par type et sous-type, audience cumulée, pour vérifier la couverture avant d'ajouter.
- Alerte si une source n'a rien publié depuis 14 jours ou si la résolution échoue.
- Estimation du quota ajouté par la nouvelle source (vidéos par jour × pages de commentaires) avant validation.

## Interface et éditorial

L'interface lit uniquement les agrégats (Supabase). Maquette de référence : artifact "Radar 2027".

**Structure**
- **Cette semaine** (accueil, éditorial) : chapô "le point de la semaine" validé par la rédaction ; les 5 sujets d'actu de la semaine en cartes (thème, courbe, vélocité, où ça réagit, désaccord avec les vidéos, émotion, résumé IA dépliable avec vidéos déclencheuses) ; en colonne : le décalage couverture / réactions, la comparaison médias vs influenceurs, ce qui a changé depuis la semaine précédente. Un seul filtre : réactions sous toutes les sources, les médias ou les influenceurs.
- **Vue d'ensemble** : la lecture par thèmes pour creuser (classement par vélocité, carte attention × intensité avec comparaison à la période précédente, signaux émergents, détail par thème) et tous les filtres avancés (période, chaîne, position, émotion, chaînes politiques).
- **Méthodologie** et **Journal des changements**, accessibles partout.
- Bandeau permanent : "mesure les réactions des commentateurs YouTube, pas l'opinion des Français".
- Principe : l'accueil raconte, la vue d'ensemble outille. Ne pas recharger l'accueil.

**Couche éditoriale**
- "Le point de la semaine" est écrit ou validé par un humain, daté, signé "la rédaction".
- Page Méthodologie accessible partout : panel et critères, taxonomie et version, définitions des métriques, limites.
- Journal des changements public : ajouts ou retraits de chaînes, versions de taxonomie, incidents de collecte.

**Résumé IA ("Pourquoi ça bouge")**
- 3 ou 4 phrases par thème, générées par Claude à partir des agrégats et des métadonnées de vidéos de moins de 30 jours.
- Aucune citation de commentaire, aucun pseudo.
- Prompt neutre : décrire les chiffres, ne jamais attribuer d'opinion à une personnalité, pas d'adjectifs évaluatifs.
- Chaque affirmation renvoie à sa source ([1], [2]…) : un chiffre du tableau ou une vidéo déclencheuse.
- Label "Généré par IA" toujours visible. Relecture humaine avant toute publication publique.
- Sortie typée (Pydantic) : texte + liste de références, pour vérifier que chaque référence existe.

**Filtres**
- Période : 7 jours, 30 jours, depuis le début de la campagne. Comparaison avec la période précédente.
- Types de source : médias, influenceurs.
- Chaînes politiques : **exclues par défaut**, affichables via un interrupteur, toujours présentées à part, jamais agrégées.
- Chaîne précise : vue "cette chaîne face au panel".
- Position (accord, nuance ou désaccord avec la vidéo) et émotion : les thèmes qui ne correspondent pas sont estompés, pas masqués.

**Drilldown verbatims** (plus tard)
- 30 derniers jours uniquement, texte non modifié, lien vers la vidéo, pas de pseudo, quelques exemples par sujet.
- Récupéré **en direct via l'API** au moment de la consultation plutôt que lu dans le Parquet : les commentaires supprimés disparaissent d'eux-mêmes. Coût : 1 unité de quota par appel, mettre en cache côté serveur quelques heures au maximum.
- Jamais dans les exports PDF.

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

## Stack

- Python 3.11+, typage partout, schémas Pydantic pour toute sortie de modèle
- `anthropic` (structured outputs via `messages.parse(..., output_format=Model)` → `parsed_output`)
- Jev via **Vercel AI Gateway** (`typesafe-ai/jev`), appelé avec `evaluate` d'AI SDK 7 (TypeScript). L'étape de classification Jev est donc un petit worker TypeScript (schémas en Zod, miroirs des modèles Pydantic), ou un appel HTTP à la Gateway depuis Python si l'endpoint le permet : vérifier la doc avant de coder, le modèle est récent
- `requests` pour l'API YouTube
- DuckDB + Parquet (pyarrow)
- Supabase (Postgres, région UE) pour les agrégats servis à l'interface

**Déploiement**
- Interface : Next.js déployé sur **Vercel**, lecture seule sur les tables d'agrégats Supabase.
- Batch quotidien (collecte, classification, agrégation) : **GitHub Actions** en cron, pas des fonctions Vercel (traitement trop long). Lancer après 9 h (remise à zéro du quota YouTube).
- Taxonomie partagée : une seule source de vérité (`radar/schemas.py`), dont les listes fermées sont exportées pour les schémas Zod côté TypeScript.

Variables d'environnement : `ANTHROPIC_API_KEY`, `AI_GATEWAY_API_KEY`, `YOUTUBE_API_KEY`, `RADAR_SEL`. Jamais de secret en dur ni dans le repo.

## Budget indicatif (jusqu'au second tour)

- YouTube : gratuit
- Jev : ~17 $ par million de commentaires
- Claude : l'essentiel du coût, piloté par le seuil de confiance de reprise
- Total : ~200 $ (scénario moyen, ~2,5 M commentaires) à ~1 100 $ (large, ~16 M)

## Structure du repo (cible)

```
radar-2027/
├── CLAUDE.md
├── data/
│   ├── raw/                 # Parquet brut, purgé à 30 jours
│   └── radar.duckdb
├── .github/workflows/
│   └── daily.yml            # cron du batch quotidien (après 9 h)
├── supabase/
│   └── migrations/          # tables sources, sources_journal, stories, agrégats + RLS
├── radar/                   # pipeline Python
│   ├── schemas.py           # taxonomie + modèles Pydantic (source de vérité)
│   ├── youtube.py           # client API + suivi du quota
│   ├── filtre.py            # entonnoir politique
│   ├── classify_jev.py
│   ├── classify_claude.py
│   ├── stories.py           # détection et cycle de vie des sujets d'actu
│   ├── storage.py           # Parquet, DuckDB, purge 30 jours
│   └── aggregate.py         # vélocité, attention, intensité, décalage, récupération politique
├── workers/jev/             # worker TypeScript AI SDK (Jev via Vercel AI Gateway), schémas Zod générés depuis schemas.py
├── web/                     # app Next.js sur Vercel
│   ├── app/(public)/        # Cette semaine, Vue d'ensemble, Méthodologie, Journal
│   └── app/admin/           # gestion des sources et des sujets d'actu
├── scripts/
│   ├── import_sources.py    # import initial du panel dans Supabase
│   └── run_daily.py
└── tests/
```

Existant à reprendre : `radar_youtube.py` (collecte + extraction Claude, à découper dans `radar/`). `radar_2027.py` (RSS presse) est abandonné.

## Premier chantier data : backfill de septembre 2026

Objectif : récupérer tout le mois de septembre (du 1er au 30) pour construire le pipeline, calibrer le filtre et la classification, et constituer la baseline de vélocité d'octobre.

- **Périmètre** : vidéos publiées du 01/09/2026 au 30/09/2026 sur les chaînes actives du panel, et leurs commentaires. Pour les chaînes qui publient beaucoup (info en continu), paginer la playlist des uploads jusqu'au 1er septembre (1 unité par page de 50).
- **Ordre** : d'abord la semaine du 1er au 7 septembre seule. Vérifier le filtre, la qualité Jev vs Claude et le coût réel. Puis le reste du mois.
- **Quota** : ~4 500 vidéos politiques estimées, ~9 000 unités pour les commentaires à 200 par vidéo. Étaler sur 2 à 3 jours, ou plafonner à 100 commentaires par vidéo pour tenir en une journée. Le script doit **reprendre là où il s'est arrêté** (état persistant des vidéos et pages déjà traitées) et s'arrêter proprement avant d'épuiser le quota.
- **Dates** : raisonner sur la date de publication de chaque commentaire, pas sur la date de collecte. Les commentaires récupérés aujourd'hui sur des vidéos de début septembre sont "mûrs" ; le pipeline quotidien, lui, les récupérera à J+1 à J+3. Ne pas comparer septembre et octobre sans en tenir compte.
- **30 jours** : le compteur démarre à la **récupération**, pas à la publication. Le texte récupéré fin septembre sera purgé fin octobre.
- **Usage** : septembre est un mois de **calibrage**. Pas de vélocité exploitable sur septembre (pas de baseline antérieure) ; il sert de baseline pour octobre.
- **Vérité terrain** pour la détection des sujets d'actu : des événements datés de la rentrée, par exemple la candidature officialisée par Fabien Roussel (6 septembre) et celle d'Éric Zemmour (17 septembre). Si le pipeline ne voit pas de pic autour de ces dates, quelque chose cloche.
- **Usage privé uniquement** tant que l'acceptation YouTube n'est pas obtenue : rien n'est publié.

## Prochaines étapes

1. Espace admin des sources + import initial des ~50 chaînes (résolution API, vues 90 jours, activité, critère d'inclusion).
2. Refactor de `radar_youtube.py` dans la structure cible, avec stockage Parquet et purge à 30 jours.
3. Récupération de septembre (étalée sur 2 à 3 jours de quota), en commençant par la première semaine pour calibrer.
4. Intégration Jev + test de qualité : 500 commentaires classés par Jev et par Claude, comparaison.
5. Calibration du filtre politique sur 200 vidéos étiquetées à la main.
6. Détection des sujets d'actu, vérifiée sur les événements datés de septembre (vérité terrain).
7. Agrégats + interface Next.js (Cette semaine d'abord, puis Vue d'ensemble), à partir de la maquette "Radar 2027".
8. Politique de confidentialité et CGU, puis dépôt de la demande d'audit YouTube.

**Préalables hors code (avant tout lancement public)** : projet développé sur machine et comptes personnels, situation clarifiée avec l'employeur, AIPD rédigée, acceptation YouTube "métriques dérivées" obtenue.

**À décider** : page publique "Le panel" listant les 50 chaînes avec type et critère d'inclusion.

## Pour Claude

- Réponses courtes et directes, en français.
- Toute sortie de modèle passe par un schéma typé. Pas de parsing de texte libre.
- Avant d'ajouter un appel API YouTube, estimer son coût en quota.
- Signaler toute modification qui toucherait aux règles ci-dessus (30 jours, RGPD, exports, neutralité) au lieu de l'implémenter en silence.
