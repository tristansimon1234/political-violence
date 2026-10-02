# Architecture et stack

## Architecture

```
YouTube API ─▶ collecte ─▶ filtre politique ─▶ classification ─▶ stockage ─▶ agrégats ─▶ interface
```

1. **Collecte** (`radar/collecte.py`, `scripts/collecte.py`, workflow `collecte.yml`) : playlist des uploads de chaque source active (1 unité / 50) → `videos.list` pour toutes les nouvelles vidéos (1 unité / 50 ; format `short` / `long`) → **pré-filtre mots-clés** (`config/mots_cles.txt`, `radar/prefiltre.py`) → `commentThreads.list` (ordre chronologique, pages de 100, commentaires de premier niveau seulement) **uniquement pour les vidéos qui passent le pré-filtre et pour toutes celles des chaînes politiques** : **tous les commentaires** (garde-fou 300 pages par vidéo et par lecture). Quotidien : vidéos publiées dans les 3 derniers jours, revisitées une fois par jour en lecture **incrémentale** (arrêt au premier commentaire antérieur à la lecture précédente, `videos.commentaires_lus_jusqua`, marge 1 h). Backfill : `--depuis` / `--jusqua`, une lecture complète par vidéo ; une vidéo collectée dans l'ancien mode (`mode_commentaires = 'pertinence_200'`) est relue en entier, reprise là où le run s'est arrêté (`collecte_etat`, `videos.derniere_collecte`). Arrêt propre avant le budget de quota (ou sur `quotaExceeded`). Écriture par lots de 250 vidéos commentées, et de ce qui a été collecté en cas d'erreur imprévue : un plantage perd au plus un lot. Vidéo devenue indisponible (404, 403 hors quota, 400) : sautée et marquée. Erreurs passagères (5xx, 429, réseau) : jusqu'à 4 essais.
2. **Filtre politique (entonnoir)** : mots-clés sur titre/description/tags (fait à la collecte, voir 1) → Jev (`politique_directe` / `enjeu_public` / `hors_sujet`) → Claude si confiance < seuil. Les chaînes politiques ne sont pas filtrées.
3. **Classification (cascade)** :
   - **Jev** (TypeSafe, via Vercel AI Gateway) : classification fermée des commentaires à volume (est_politique, thèmes, position vis-à-vis de la vidéo, tonalité, hostilité, candidat visé dans une liste fermée). Renvoie des probabilités et une confiance.
   - **Claude** (`claude-haiku-4-5`, `client.messages.parse` + Pydantic) : analyse des vidéos (sujets pondérés, `nature_video`), `sous_sujet` libre, `theme_propose`, regroupement hebdomadaire des sous-sujets, et reprise des commentaires où Jev a une confiance faible.
   - **Sujets d'actualité** : regroupement quotidien des vidéos par événement (Claude, sortie typée), voir `docs/donnees.md`.
4. **Stockage** :
   - Brut (texte des commentaires, titres, descriptions, tags) : Parquet partitionné par **jour de récupération** (`commentaires/AAAA-MM-JJ.parquet`, `videos/AAAA-MM-JJ.parquet`) dans le **bucket privé Supabase Storage `radar-brut`** (région UE, aucune policy : accès uniquement par la clé secrète du batch, en secret GitHub). **30 jours maximum** : chaque run de collecte purge les partitions de 30 jours ou plus. Sert à classer, reclasser dans la fenêtre si la taxonomie change, et au drilldown. Pas de rafraîchissement en boucle pour prolonger la conservation.
   - Unicité : un commentaire n'existe qu'une fois, daté de sa dernière récupération (re-récupéré → écrit dans la partition du jour, ancienne copie supprimée). Auteur remplacé par `auteur_hash` (HMAC-SHA256 avec `RADAR_SEL`) avant toute écriture ; le pseudo n'est jamais lu.
   - Sauvegardes et versions : Supabase Storage ne versionne pas les objets et une suppression est définitive ; les sauvegardes de la base ne contiennent que les métadonnées des objets (nom = une date, taille), pas leur contenu. La purge à 30 jours s'applique donc aussi aux sauvegardes. Aucune autre copie du brut n'est faite (pas d'artefact GitHub, pas de cache).
   - État de collecte (Supabase, **sans texte**) : tables `videos` (format, durée, vues, pré-filtre et sa version, dates de collecte), `collecte_etat` (reprise du backfill), `collecte_runs` (quota consommé et volumes de chaque run).
   - Classé (une ligne par commentaire, **sans texte**) : DuckDB. Thème, position, tonalité, hostilité, confiance, auteur hashé, date, vidéo. C'est ce qui est conservé sur toute la campagne.
   - Identifiant du commentaire : remplacé par un identifiant interne hashé (même sel que les auteurs) dans la table classée. À vérifier dans les règles YouTube avant de conserver l'ID d'origine au-delà de 30 jours.
   - Agrégats (sujet d'actu × jour × type de source, thème × jour × type de source, récupération politique) : recalculés chaque nuit, poussés dans Supabase (région UE) quand l'interface passe en ligne.
5. **Interface** : lit uniquement les agrégats, plus un drilldown verbatims limité aux 30 derniers jours.

## Stack

- Python 3.11+, typage partout, schémas Pydantic pour toute sortie de modèle
- `anthropic` (structured outputs via `messages.parse(..., output_format=Model)` → `parsed_output`)
- Jev via **Vercel AI Gateway** (`typesafe-ai/jev`), appelé en HTTP depuis Python (`requests`, protocole natif TypeSafe `/typesafe/v1/systemone`, schéma vérifié dans `typesafe-sdk` 0.7.2 ; zéro conservation exigée au niveau de l'équipe Vercel et redemandée à chaque requête) : un appel par commentaire, questions fermées, probabilités et confiance par question. Client : `radar/llm.py`
- `requests` pour l'API YouTube
- DuckDB + Parquet (pyarrow)
- Supabase (Postgres, région UE) pour les agrégats servis à l'interface

**Déploiement**
- Interface : Next.js déployé sur **Vercel**, lecture seule sur les tables d'agrégats Supabase.
- Batch quotidien (collecte, classification, agrégation) : **GitHub Actions** en cron, pas des fonctions Vercel (traitement trop long). Lancer après 9 h (remise à zéro du quota YouTube).
- Taxonomie partagée : une seule source de vérité (`radar/schemas.py`), dont les listes fermées sont exportées pour les schémas Zod côté TypeScript.

Projet Supabase : `yqzgtkaeodibfujienyj` (`https://yqzgtkaeodibfujienyj.supabase.co`, région UE).

Import du panel : workflow GitHub Actions manuel `import-sources.yml` (modes `dry-run` / `import`), secrets `YOUTUBE_API_KEY` et `SUPABASE_SECRET_KEY` dans le dépôt GitHub.

Variables d'environnement : `ANTHROPIC_API_KEY`, `AI_GATEWAY_API_KEY`, `YOUTUBE_API_KEY`, `RADAR_SEL`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY` (clé secrète `sb_secret_…`, batch uniquement, jamais côté interface). Jamais de secret en dur ni dans le repo.

## Structure du repo (cible)

```
radar-2027/
├── CLAUDE.md
├── docs/                    # documentation détaillée (architecture, données, interface, roadmap, décisions)
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
│   ├── llm.py               # clients Jev et Claude (coût journalisé, budget)
│   ├── classification.py    # prompts neutres, minimisation, sorties typées
│   ├── evaluation.py        # test Jev / Claude / vérité terrain
│   ├── stories.py           # détection et cycle de vie des sujets d'actu
│   ├── storage.py           # Parquet, DuckDB, purge 30 jours
│   └── aggregate.py         # vélocité, attention, intensité, décalage, récupération politique
├── web/                     # app Next.js sur Vercel
│   ├── app/(public)/        # Cette semaine, Vue d'ensemble, Méthodologie, Journal
│   └── app/admin/           # gestion des sources et des sujets d'actu
├── scripts/
│   ├── import_sources.py    # import initial du panel dans Supabase
│   └── run_daily.py
└── tests/
```

Existant à reprendre : `radar_youtube.py` (collecte + extraction Claude, à découper dans `radar/`). `radar_2027.py` (RSS presse) est abandonné.

## Budget indicatif (jusqu'au second tour)

- YouTube : gratuit
- Volume (semaine 1, mesuré le 02/10) : ~356 000 commentaires annoncés par YouTube pour 7 jours de vidéos retenues (réponses comprises), soit ~7 à 8 millions de commentaires de premier niveau sur la campagne en lisant tout ; quota ~900 unités / jour.
- Jev : ~50 $ par million de commentaires mesuré le 01/10 (≈ 1 200 tokens d'entrée par commentaire, surtout les définitions des catégories ; 0,042 $ par million de tokens, sortie gratuite)
- Claude : l'essentiel du coût, piloté par le seuil de confiance de reprise
- Total : ~200 $ (scénario moyen, ~2,5 M commentaires) à ~1 100 $ (large, ~16 M)
