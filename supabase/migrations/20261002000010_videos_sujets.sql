-- 02/10/2026 : thèmes des vidéos (l'agenda des médias), docs/decisions.md.
-- 1 à 3 thèmes par vidéo, pondérés (somme 1), avec un sous-sujet court et neutre écrit par
-- Claude à partir du titre et de la description (donnée dérivée : ni titre ni description ici).
-- Sert à comparer ce que les médias couvrent à ce à quoi les commentaires réagissent.
create table public.videos_sujets (
  video_id text not null references public.videos (video_id) on delete cascade,
  theme text not null check (theme in ('pouvoir_achat', 'securite', 'immigration', 'retraites', 'sante', 'education', 'ecologie_energie', 'economie_emploi', 'logement', 'institutions', 'international_defense', 'agriculture', 'societe', 'autre')),
  sous_sujet text not null check (char_length(sous_sujet) <= 60),
  poids real not null check (poids > 0 and poids <= 1),
  principal boolean not null,
  version_taxonomie smallint not null,
  classe_le date not null,
  primary key (video_id, theme)
);
create index videos_sujets_theme_idx on public.videos_sujets (theme);

alter table public.videos_sujets enable row level security;
-- Rien de public avant l'accord YouTube : lecture admin seulement.
create policy videos_sujets_admin_select on public.videos_sujets
  for select using (public.est_admin());
