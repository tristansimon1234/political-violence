# Feuille de route

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
