-- 02/10/2026 : « sur quoi les commentaires sont d'accord ou pas », docs/decisions.md.

-- Thèse des vidéos d'opinion, résumée par Claude à partir du titre et de la description.
-- Dérivée du texte brut : effacée 30 jours après la récupération de la vidéo (purge à chaque
-- run de classification). Lecture admin seulement.
create table public.videos_theses (
  video_id text primary key references public.videos (video_id) on delete cascade,
  these text not null check (char_length(these) <= 400),
  explicite boolean not null,            -- dite clairement dans le titre ou la description
  recupere_le date not null,             -- récupération du titre et de la description
  classe_le date not null
);
create index videos_theses_recupere_idx on public.videos_theses (recupere_le);

-- Réactions par vidéo (aucun texte) : commentaires classés, hostiles, et position sous les
-- vidéos d'opinion. Recalculé par le job d'agrégats ; conservé toute la campagne.
create table public.agregats_videos (
  video_id text primary key references public.videos (video_id) on delete cascade,
  commentaires integer not null,
  hostiles integer not null,
  accord integer not null,
  nuance integer not null,
  desaccord integer not null,
  hors_sujet integer not null,
  maj_at timestamptz not null default now()
);

alter table public.videos_theses enable row level security;
alter table public.agregats_videos enable row level security;
create policy videos_theses_admin_select on public.videos_theses
  for select using (public.est_admin());
create policy agregats_videos_admin_select on public.agregats_videos
  for select using (public.est_admin());
