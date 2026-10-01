# Interface, éditorial et admin

## Interface et éditorial

L'interface lit uniquement les agrégats (Supabase). Maquette de référence : artifact "Radar 2027".

**Structure**
- **Cette semaine** (accueil, éditorial) : chapô "le point de la semaine" validé par la rédaction ; les 5 sujets d'actu de la semaine en cartes (thème, courbe, vélocité, où ça réagit, désaccord avec les vidéos, émotion, résumé IA dépliable avec vidéos déclencheuses) ; en colonne : le décalage couverture / réactions, la comparaison médias traditionnels vs médias natifs du web, ce qui a changé depuis la semaine précédente. Un seul filtre : réactions sous toutes les sources, les médias traditionnels ou les médias natifs du web.
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
- Types de source : médias traditionnels, médias natifs du web.
- Chaînes politiques : **exclues par défaut**, affichables via un interrupteur, toujours présentées à part, jamais agrégées.
- Chaîne précise : vue "cette chaîne face au panel".
- Position (accord, nuance ou désaccord avec la vidéo) et émotion : les thèmes qui ne correspondent pas sont estompés, pas masqués.

**Drilldown verbatims** (plus tard)
- 30 derniers jours uniquement, texte non modifié, lien vers la vidéo, pas de pseudo, quelques exemples par sujet.
- Récupéré **en direct via l'API** au moment de la consultation plutôt que lu dans le Parquet : les commentaires supprimés disparaissent d'eux-mêmes. Coût : 1 unité de quota par appel, mettre en cache côté serveur quelques heures au maximum.
- Jamais dans les exports PDF.

## Espace admin (gestion des sources)

Page `/admin` de l'app Next.js, réservée à Tristan (Supabase Auth, un seul compte admin, RLS : écriture sur `sources` pour l'admin uniquement).

**Version 1 (01/10/2026)** : `web/app/admin`, déployée sur Vercel (dossier racine `web`). Connexion par lien e-mail (comptes créés à la main dans Supabase, pas d'inscription libre), accès vérifié par `est_admin()`. Trois vues : Panel (statistiques 90 jours, mise en pause / réactivation), Équilibre (chaînes, abonnés et vues par catégorie et sous-type), Journal (`sources_journal`). L'ajout de source n'est pas dans l'admin : le panel est une liste fermée, modifiée par `panel/` + workflow `import-sources.yml`. Variables Vercel : `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` (jamais la clé secrète). Taxonomie côté TypeScript générée depuis `radar/schemas.py` (`scripts/generer_taxonomie_ts.py`).

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
