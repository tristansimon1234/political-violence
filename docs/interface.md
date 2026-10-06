# Interface, éditorial et admin

## Interface et éditorial

**État au 02/10/2026** : écran `/radar` (Vue d'ensemble des thèmes, v1), réservé à l'admin. Filtres période (7 j, 30 j, depuis le début), réactions sous (médias traditionnels, médias natifs du web), chaînes politiques (lues à part). Liste des thèmes (part des commentaires politiques, évolution, courbe, vélocité provisoire) et détail du thème choisi (tonalité, part hostile, accord avec la vidéo sous les vidéos d'opinion, par type de source). Source : table `agregats_themes`.

**Organisation de l'information (04/10/2026)**
- **Un seul drill-down** pour les deux écrans : un panneau latéral à niveaux (sujet › vidéo › commentaires classés), avec fil d'Ariane, retour et fermeture (`web/lib/Explorateur.tsx`). Un seul niveau affiché à la fois : plus de blocs dépliables imbriqués dans les listes, plus de modale.
- **Thèmes** (ex-Vue d'ensemble, refonte du 06/10/2026) en maître / détail : à gauche la liste des thèmes, classable par réactions, évolution (vélocité), désaccord ou hostilité ; à droite le thème choisi (5 chiffres clés dont la couverture, résumé IA, onglets Réactions · Médias vs commentaires · Sujets · Vidéos · Thèses). Filtres dans la barre du haut : période, et un menu (réactions sous, chaînes, chaînes politiques lues à part). Dessous, repliée : « Tous les thèmes, semaine par semaine ». La carte attention × intensité et le bloc « Signal émergent » sont retirés (les sujets hors grille restent dans le thème « Autre »).
- **Cette semaine** (refonte du 06/10/2026) : semaine et filtre « Réactions sous » dans la barre du haut ; chapô ; 4 faits marquants ; les sujets en tableau (rang, thème, évolution, courbe par jour, commentaires, barre accord / nuancé / désaccord), une ligne = un clic vers le panneau ; en colonne : décalage couverture / réactions, ce qui a changé, « Pourquoi ça bouge » du premier sujet, médias traditionnels ou natifs.
- **Fluidité** : filtres appliqués en arrière-plan (contenu estompé pendant le calcul), fondu au changement d'onglet, de thème ou de semaine, barres qui glissent vers leurs nouvelles valeurs, panneau qui glisse à l'ouverture et à la fermeture, position retrouvée au retour d'un niveau, silhouette de page au chargement. Animations coupées si le système demande de réduire les animations.

L'interface lit uniquement les agrégats (Supabase). Maquette de référence : artifact "Radar 2027".

**Structure**
- **Cette semaine** (accueil, éditorial) : chapô "le point de la semaine" validé par la rédaction ; les 5 sujets d'actu de la semaine en cartes (thème, courbe, vélocité, où ça réagit, désaccord avec les vidéos, tonalité, part hostile, résumé IA dépliable avec vidéos déclencheuses) ; en colonne : le décalage couverture / réactions, la comparaison médias traditionnels vs médias natifs du web, ce qui a changé depuis la semaine précédente. Un seul filtre : réactions sous toutes les sources, les médias traditionnels ou les médias natifs du web.
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
- Position (accord, nuance ou désaccord avec la vidéo), tonalité et hostilité : les thèmes qui ne correspondent pas sont estompés, pas masqués.

**Drilldown verbatims** (plus tard)
- 30 derniers jours uniquement, texte non modifié, lien vers la vidéo, pas de pseudo, quelques exemples par sujet.
- **Lu dans les données stockées** (décision du 04/10/2026, Tristan), pas d'appel à l'API. Admin (privé) : pour chaque vidéo, tous ses commentaires classés des 30 derniers jours (150 au plus), avec leurs étiquettes, pour vérifier le classement ; fichiers par vidéo dans le bucket privé `radar-drilldown`, lisibles par l'admin seulement, écrits et purgés par le job d'agrégats. Version publique éventuelle : quelques exemples par sujet seulement.
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

## Espace admin : comparatif permanent des modèles (décision du 02/10/2026)

Contrôle qualité continu de la classification, réservé à l'admin (texte brut visible, jamais public).

- **Échantillon** : chaque semaine, 100 commentaires de la semaine écoulée, tirés par strate (catégorie de chaîne × format × nature de vidéo), comme le test de l'étape 4.
- **Trois modèles** sur les mêmes commentaires : Jev (classification en production), Claude Haiku et Claude Sonnet (même sous-traitant qu'Haiku, rien de nouveau dans l'AIPD). Mêmes consignes, même contexte minimisé.
- **Vue par commentaire** : texte, chaîne, titre, nature, lien vers la vidéo ; les trois réponses côte à côte (politique, thèmes, position, tonalité, hostilité), désaccords en évidence.
- **Vue d'ensemble** : taux d'accord par dimension et par paire de modèles, parts agrégées par modèle, évolution semaine après semaine. Une chute d'accord signale un changement (modèle mis à jour, nouveau type de sujet) et déclenche une vérification.
- **Option** : étiquetage ou arbitrage à l'aveugle par Tristan directement dans l'interface (remplace les fichiers CSV), qui alimente la justesse mesurée en continu.
- **Règles** : texte purgé à 30 jours avec le brut, aucun pseudo ni identifiant d'auteur, aucun export.
- **Coût** : quelques centimes par semaine (100 commentaires × 3 modèles).

