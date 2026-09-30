# Journal des décisions

Chaque décision validée qui modifie le projet est ajoutée ici, datée, avec sa raison. Le reste de la documentation est mis à jour en conséquence.

- **30/09/2026** · YouTube seule source pour démarrer (API officielle, gratuite ; X en source de contrôle éventuelle plus tard).
- **30/09/2026** · Panel de ~50 chaînes : 25 médias, 12 influenceurs, 13 politiques (partis et personnalités, lus à part). Sélection par quotas et vues à 90 jours.
- **30/09/2026** · Cascade Jev (Vercel AI Gateway) + Claude Haiku 4.5, sorties typées.
- **30/09/2026** · Texte brut 30 jours max, table classée sans texte, auteurs et identifiants hashés, drilldown lu en direct via l'API.
- **30/09/2026** · Position = accord avec la vidéo, calculée seulement sur les vidéos d'opinion ; jamais "pour / contre" un sujet.
- **30/09/2026** · Vidéos multi-thèmes : 3 thèmes max pondérés, commentaires comptés dans leurs propres thèmes, vues réparties selon les commentaires.
- **30/09/2026** · Sujets d'actualité comme unité principale ; thèmes comme grille stable.
- **30/09/2026** · Récupération politique mesurée sur qui publie, pas sur les commentaires ; mobilisation affichée à part.
- **30/09/2026** · Interface : accueil éditorial "Cette semaine", "Vue d'ensemble" pour creuser, Méthodologie et Journal publics.
- **30/09/2026** · Batch sur GitHub Actions, agrégats dans Supabase (UE), interface Next.js sur Vercel.
- **30/09/2026** · Sous-types du panel (taxonomie v1) : `media` = `info_continu`, `tv_radio`, `talk_show`, `presse_nationale`, `pure_player` ; `influenceur` = `vulgarisation`, `commentateur`, `debat` ; `politique` = `parti`, `personnalite`. Source de vérité : `radar/schemas.py`.
- **30/09/2026** · Supabase appelé en REST (PostgREST) via `requests`, sans `supabase-py`, pour limiter les dépendances.
- **30/09/2026** · Taxonomie v2 : ajout du sous-type influenceur `interview_longue` (Thinkerview, Sam Zirah), issu du panel v0.
- **30/09/2026** · Vues et activité des sources calculées sur **30 jours** au lieu de 90 : le parcours complet des chaînes d'info sur 90 jours coûtait trop de quota (≈ 1 300 unités pour une partie du panel). Remplace le critère « vues à 90 jours ».
