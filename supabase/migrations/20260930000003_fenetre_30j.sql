-- Fenêtre de sélection ramenée de 90 à 30 jours (docs/decisions.md, 30/09/2026).
alter table public.sources rename column videos_90j to videos_30j;
alter table public.sources rename column vues_90j to vues_30j;
