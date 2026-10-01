# Architecture et stack

## Architecture

```
YouTube API ─▶ collecte ─▶ filtre politique ─▶ classification ─▶ stockage ─▶ agrégats ─▶ interface
```

1. **Collecte** : playlist des uploads de chaque chaîne → `videos.list` → `commentThreads.list` (ordre pertinence, pages de 100). Repasser sur les vidéos récentes pendant quelques jours.
2. **Filtre politique (entonnoir)** : mots-clés sur titre/description/tags → Jev (`politique_directe` / `enjeu_public` / `hors_sujet`) → Claude si confiance < seuil. Les chaînes politiques ne sont pas filtrées.
3. **Classification (cascade)** :
   - **Jev** (TypeSafe, via Vercel AI Gateway) : classification fermée des commentaires à volume (est_politique, thèmes, position vis-à-vis de la vidéo, émotion, candidat visé dans une liste fermée). Renvoie des probabilités et une confiance.
   - **Claude** (`claude-haiku-4-5`, `client.messages.parse` + Pydantic) : analyse des vidéos (sujets pondérés, `nature_video`), `sous_sujet` libre, `theme_propose`, regroupement hebdomadaire des sous-sujets, et reprise des commentaires où Jev a une confiance faible.
   - **Sujets d'actualité** : regroupement quotidien des vidéos par événement (Claude, sortie typée), voir `docs/donnees.md`.
4. **Stockage** :
   - Brut (texte des commentaires) : Parquet partitionné par jour, **30 jours maximum**. Sert à classer, reclasser dans la fenêtre si la taxonomie change, et au drilldown. Job de purge quotidien qui supprime les partitions de plus de 30 jours. Pas de rafraîchissement en boucle pour prolonger la conservation.
   - Classé (une ligne par commentaire, **sans texte**) : DuckDB. Thème, position, émotion, confiance, auteur hashé, date, vidéo. C'est ce qui est conservé sur toute la campagne.
   - Identifiant du commentaire : remplacé par un identifiant interne hashé (même sel que les auteurs) dans la table classée. À vérifier dans les règles YouTube avant de conserver l'ID d'origine au-delà de 30 jours.
   - Agrégats (sujet d'actu × jour × type de source, thème × jour × type de source, récupération politique) : recalculés chaque nuit, poussés dans Supabase (région UE) quand l'interface passe en ligne.
5. **Interface** : lit uniquement les agrégats, plus un drilldown verbatims limité aux 30 derniers jours.

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

Projet Supabase : `yqzgtkaeodibfujienyj` (`https://yqzgtkaeodibfujienyj.supabase.co`, région UE).

Import du panel : workflow GitHub Actions manuel `import-sources.yml` (modes `dry-run` / `import`), secrets `YOUTUBE_API_KEY` et `SUPABASE_SERVICE_ROLE_KEY` dans le dépôt GitHub.

Variables d'environnement : `ANTHROPIC_API_KEY`, `AI_GATEWAY_API_KEY`, `YOUTUBE_API_KEY`, `RADAR_SEL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (batch uniquement, jamais côté interface). Jamais de secret en dur ni dans le repo.

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

## Budget indicatif (jusqu'au second tour)

- YouTube : gratuit
- Jev : ~17 $ par million de commentaires
- Claude : l'essentiel du coût, piloté par le seuil de confiance de reprise
- Total : ~200 $ (scénario moyen, ~2,5 M commentaires) à ~1 100 $ (large, ~16 M)
