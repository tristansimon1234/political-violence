# Backfill de septembre 2026

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

## Test : rattrapage du filtre politique par les commentaires (à évaluer, pas à intégrer)

Question : le filtre politique (titres, descriptions, tags) laisse-t-il passer des vidéos classées `hors_sujet` sous lesquelles le public parle en fait de politique ?

- **Quand** : une seule fois, sur les données du backfill de septembre, dès que la classification Jev est branchée (étape 4 de la feuille de route).
- **Échantillon** : vidéos classées `hors_sujet` appartenant au top 20 % de leur chaîne en nombre de commentaires.
- **Mesure** : une page de commentaires par vidéo (100 commentaires, 1 unité de quota), classée par Jev (`est_politique`). Une vidéo est **reclassée** si au moins 1/3 de ses commentaires sont politiques.
- **Livrable pour Tristan** : nombre de vidéos testées, taux de reclassement, 10 exemples reclassés (titre + chaîne) pour vérification manuelle. Usage interne uniquement : les titres ne sont ni commités ni publiés, et suivent la règle des 30 jours.
- **Décision ensuite** : intégration au pipeline seulement si le rattrapage est utile (seuil indicatif : > 5 % de vraies vidéos politiques rattrapées, après vérification manuelle).
- **Coût** : 1 unité YouTube par vidéo testée, plus la classification Jev d'environ 100 commentaires par vidéo.
