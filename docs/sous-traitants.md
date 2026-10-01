# Sous-traitants

Section prête à reporter dans l'AIPD. État au 01/10/2026.

Règle (`CLAUDE.md`, décision du 01/10/2026) : stockage en UE. Un traitement transitoire hors UE n'est autorisé que chez un sous-traitant couvert par un DPA avec clauses contractuelles types (CCT) ou par le Data Privacy Framework (DPF), sans conservation ni entraînement, et avec des données minimisées.

**Données envoyées aux modèles** (Jev, Claude) : le texte d'un commentaire, avec les mentions @ et les URL masquées, et le contexte de sa vidéo (titre, nom de la chaîne, nature factuelle / opinion). Jamais l'auteur, même hashé, ni l'identifiant du commentaire : dans une requête, les commentaires sont numérotés 1..n. Catégorie de données : opinions politiques potentielles (article 9 RGPD), rendues publiques par les personnes concernées sur YouTube.

**Niveau de vérification.** **Vérifié** : lu sur la page officielle ou dans le code des paquets officiels. **Non vérifié** : seulement vu dans des extraits de recherche ou sur des sites tiers. Le proxy de la session de travail bloquait vercel.com, typesafe.ai et trust.anthropic.com. Tout ce qui est « non vérifié » est à confirmer à la main avant l'AIPD.

## Vue d'ensemble

| Sous-traitant | Rôle | Localisation du traitement | Conservation | Entraînement | Transfert hors UE |
|---|---|---|---|---|---|
| Supabase | Base de données et stockage brut | UE (région du projet) | Brut purgé à 30 jours, agrégats sur la durée de la campagne | Sans objet | Aucun pour les données (hébergement UE) |
| Vercel (AI Gateway) | Routage des appels à Jev | Global par défaut (non vérifié) ; avec ZDR, Jev servi par TypeSafe (vérifié, sonde du 01/10) | Prompts et réponses non conservés, métadonnées 30 jours (non vérifié) | Option « disallow prompt training » (non vérifié) | DPA avec CCT 2021/914 et certification DPF déclarée (non vérifié) |
| TypeSafe AI (Jev) | Classement des commentaires | États-Unis, aucune région UE documentée | Zéro conservation via la Gateway, à confirmer | Pas d'entraînement selon leur politique, mais clause de « télémétrie » (non vérifié) | DPA avec CCT selon des sources tierces (non vérifié) |
| Anthropic (Claude Haiku 4.5) | Nature des vidéos et classement des commentaires | « global » ou États-Unis ; stockage au repos aux États-Unis ; pas d'option UE | Contenu non conservé par défaut selon la doc API (vérifié), mais 30 jours selon la politique de confidentialité commerciale | Interdit par les conditions commerciales (vérifié) | DPA avec CCT modules 2 et 3, intégré d'office (vérifié) ; certification DPF non vérifiée |
| GitHub (Actions) | Exécution des batchs | États-Unis | Journaux sans données personnelles : agrégats seulement, jamais de texte ni de titre | Sans objet | Aucune donnée personnelle transmise hors exécution |

## Vercel AI Gateway

- **Localisation** : routage global par défaut. Une option de région par requête existe (`inferenceRegion` avec `geoRegion: "eu"`). Si elle ne peut pas être respectée, la requête échoue (non vérifié). Elle n'aide pas pour Jev, qui n'a pas de région UE documentée.
- **Conservation** : prompts et réponses non conservés, métadonnées (modèle, tokens, coût) gardées 30 jours (non vérifié). Zéro conservation par requête avec `providerOptions.gateway.zeroDataRetention: true` (vérifié dans le code du paquet `@ai-sdk/gateway`) : la requête échoue si le fournisseur ne garantit pas le ZDR. Cette option est réservée aux plans Pro et Enterprise. Elle existe aussi pour toute l'équipe dans le tableau de bord (non vérifié). **Vérifié par la sonde du 01/10/2026** : le champ `providerOptions.gateway.zeroDataRetention` est respecté sur `/typesafe/v1/systemone`. La Gateway a écarté DigitalOcean, autre hébergeur de Jev (« zdr_ineligible_model »), et a servi la requête par TypeSafe. **Sans ce champ, Jev peut être servi par DigitalOcean** : le Radar l'envoie donc à chaque appel. Pas de surcoût de la Gateway (`surchargeCost` = 0). Jev est appelé avec le protocole natif TypeSafe (`/typesafe/v1/systemone`), dont le schéma est vérifié dans le paquet officiel `typesafe-sdk` 0.7.2.
- **Entraînement** : option « disallow prompt training », incluse dans le ZDR (non vérifié).
- **Transfert** : DPA (vercel.com/legal/dpa) avec CCT 2021/914 et certification DPF déclarée (non vérifié).
- **Sous-traitants ultérieurs** : security.vercel.com (non vérifié).

## TypeSafe AI (Jev)

- **Société** : TypeSafe AI, San Francisco (non vérifié, presse). Paquet Python officiel `typesafe-sdk`, API native `api.typesafe.ai` (vérifié). Modèle `typesafe-ai/jev` sur la Gateway.
- **Localisation** : États-Unis, aucune région UE documentée.
- **Conservation** : listé comme fournisseur ZDR de la Gateway (non vérifié).
- **Entraînement** : pas d'entraînement sur les données clients selon leur politique de confidentialité, mais leurs conditions mentionneraient une « télémétrie » d'amélioration du service (non vérifié).
- **Transfert** : DPA avec CCT modules 2 et 3 selon des sources tierces (non vérifié).
- **À obtenir avant tout usage au-delà du test** : DPA signé ou intégré aux conditions, liste de leurs sous-traitants, confirmation écrite du ZDR et de la non-utilisation pour l'entraînement (y compris la télémétrie).

## Anthropic (Claude)

- **Localisation** (vérifié, platform.claude.com/docs/en/manage-claude/data-residency) : `inference_geo` accepte `global` (défaut) ou `us`. Le stockage au repos est uniquement aux États-Unis. Il n'existe pas d'option UE en accès direct. Claude est disponible en région UE via Google Vertex AI ou AWS Bedrock : c'est une alternative si la règle se durcit.
- **Conservation** (vérifié, platform.claude.com/docs/en/manage-claude/api-and-data-retention) : « Conversation content is not retained by default » pour l'API, sauf pour les modèles Fable et Mythos (non utilisés ici). La politique de confidentialité commerciale parle de 30 jours, et jusqu'à 2 ans en cas de violation des règles d'usage (non vérifié). Contradiction à lever. Le ZDR se demande au service commercial.
- **Entraînement** (vérifié, conditions commerciales du 17/06/2025) : « Anthropic may not train models on Customer Content from Services ».
- **Transfert** (vérifié, DPA du 24/02/2025) : CCT modules 2 et 3, avec avenants UK et suisse, droit irlandais. Entité responsable pour l'EEE : Anthropic Ireland, Limited. Le DPA est intégré d'office aux conditions commerciales. Certification DPF non vérifiée.
- **Sous-traitants ultérieurs** : anthropic.com/subprocessors (renvoie vers trust.anthropic.com).

## Supabase

- Projet `yqzgtkaeodibfujienyj`, région UE. Bucket privé `radar-brut` : pas de versionnage d'objets, suppression définitive, sauvegardes limitées aux métadonnées (voir `docs/architecture.md`).

## Points ouverts pour l'AIPD

0. DigitalOcean héberge aussi Jev sur la Gateway mais n'est pas éligible au ZDR : il n'est jamais utilisé tant que le champ ZDR est envoyé (vérifié). À mentionner dans l'AIPD comme sous-traitant exclu.

1. Vérifier sur dataprivacyframework.gov la certification DPF de Vercel et d'Anthropic.
2. Obtenir le DPA de TypeSafe et la confirmation du ZDR pour Jev via la Gateway. Vérifier que le plan Vercel permet le ZDR par requête : sans lui, les appels à Jev échouent.
3. Lever la contradiction sur la conservation chez Anthropic (« non conservé » dans la doc API, 30 jours dans la politique commerciale). Demander le ZDR si nécessaire.
4. Décider après le test si Jev est gardé. Sinon, la classification passe entièrement par Claude, en accès direct ou en région UE via Vertex AI.
