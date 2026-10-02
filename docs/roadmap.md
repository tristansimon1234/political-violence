# Feuille de route

## Prochaines étapes

1. ~~Espace admin des sources + import initial des chaînes~~ : **fait le 01/10/2026** (panel v1, 73 chaînes, admin sur Vercel).
2. Refactor de `radar_youtube.py` dans la structure cible, avec stockage Parquet et purge à 30 jours.
3. Récupération de septembre (étalée sur 2 à 3 jours de quota), en commençant par la première semaine pour calibrer.
4. Intégration Jev + test de qualité : 500 commentaires (échantillon stratifié) classés par Jev et par Claude, comparés à 100 étiquettes de Tristan (`docs/etiquetage.md`) ; seuil de reprise par Claude et coût projeté. Puis test ponctuel du rattrapage du filtre politique par les commentaires (`docs/backfill-septembre.md`).
5. Calibration du filtre politique sur 200 vidéos étiquetées à la main.
6. Détection des sujets d'actu, vérifiée sur les événements datés de septembre (vérité terrain).
7. Agrégats + interface Next.js (Cette semaine d'abord, puis Vue d'ensemble), à partir de la maquette "Radar 2027". Dans l'admin : comparatif permanent de 100 commentaires par semaine classés par Jev, Claude Haiku et Claude Sonnet (`docs/interface.md`).
8. Politique de confidentialité et CGU, puis dépôt de la demande d'audit YouTube.

**Préalables hors code (avant tout lancement public)** : projet développé sur machine et comptes personnels, situation clarifiée avec l'employeur, AIPD rédigée, acceptation YouTube "métriques dérivées" obtenue.

**À décider** :
- Page publique "Le panel" listant les chaînes avec type et critère d'inclusion.
- ~~Couverture des commentaires~~ : tranché le 02/10/2026, tout prendre (lecture chronologique incrémentale).
- ~~Classification~~ : tranché le 02/10/2026, Jev seul pour toutes les dimensions (à confirmer sur le second échantillon, série 2).
- ~~Émotion~~ : tranché le 01/10/2026, tonalité + hostilité (taxonomie v5).
- Taxonomie des thèmes (remarques de Tristan, 01/10) : justice rangée dans `securite`, Europe dans `international_defense`, pas de thème « finances publiques » (dette rangée dans `economie_emploi`). À trancher avant le test de la semaine 1 : changer la liste casse la comparaison avec les tests déjà faits.
- Contexte vidéo (soulevé par Tristan le 02/10) : résumé neutre d'une phrase par vidéo, rédigé par Claude, testé le 02/10 (180 résumés non vides) : **aucun gain mesurable**. À trancher : le retirer des appels aux modèles, le garder éventuellement dans le fichier d'étiquetage. Sous-titres inaccessibles par l'API pour une chaîne tierce.
- Biais systématiques du test réel (02/10) à traiter avant toute classification en masse : hostilité surestimée par les modèles (13 % Tristan, 43 % Jev, 30 % Claude), position de Jev trop souvent `hors_sujet`, frontière `institutions` / `societe`, Claude trop strict sur « politique ».
- Sentiment par cible (« ABSA ») : proposé par Tristan, déconseillé par Claude (proche d'un sondage, risque de neutralité sur les personnalités) ; non retenu à ce stade.
