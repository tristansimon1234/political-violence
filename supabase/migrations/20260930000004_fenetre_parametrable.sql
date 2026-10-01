-- Fenêtre de calcul des statistiques paramétrable : colonnes génériques + durée de la fenêtre.
alter table public.sources rename column videos_30j to videos_fenetre;
alter table public.sources rename column vues_30j to vues_fenetre;
alter table public.sources add column fenetre_jours integer;
