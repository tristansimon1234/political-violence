-- 02/10/2026 : sujets d'actualité (étape 6), docs/decisions.md et docs/donnees.md.
-- Les vidéos politiques regroupées par événement par Claude, jour par jour. Une vidéo
-- appartient à 0 ou 1 sujet. Le titre est une donnée dérivée, neutre, écrite par le modèle
-- (jamais un titre de vidéo) : conservé toute la campagne. Lecture admin seulement.
create table public.sujets (
  id text primary key,                    -- AAAA-MM-JJ-NNN (jour de création, rang)
  titre text not null check (char_length(titre) <= 80),
  premier_jour date not null,             -- première vidéo rattachée (publication, Paris)
  dernier_jour date not null,             -- dernière vidéo rattachée
  maj_le date not null
);

-- Une ligne par vidéo examinée ; sujet_id vide : vidéo sans événement précis.
create table public.sujets_videos (
  video_id text primary key references public.videos (video_id) on delete cascade,
  sujet_id text references public.sujets (id) on delete set null,
  rattache_le date not null
);
create index sujets_videos_sujet_idx on public.sujets_videos (sujet_id);

alter table public.sujets enable row level security;
alter table public.sujets_videos enable row level security;
-- Rien de public avant l'accord YouTube.
create policy sujets_admin_select on public.sujets
  for select using (public.est_admin());
create policy sujets_videos_admin_select on public.sujets_videos
  for select using (public.est_admin());
