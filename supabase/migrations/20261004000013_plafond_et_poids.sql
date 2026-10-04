-- 04/10/2026 : plafond de 150 commentaires classés par vidéo, docs/decisions.md.
-- Nombre réel de commentaires (premier niveau, non vides) collectés par vidéo : sert à
-- pondérer chaque commentaire classé par (commentaires de la vidéo) / (commentaires classés).
-- Aucun texte. Jamais revu à la baisse par le batch.
create table public.volumes_videos (
  video_id text primary key references public.videos (video_id) on delete cascade,
  commentaires integer not null check (commentaires >= 0),
  maj_le date not null
);
alter table public.volumes_videos enable row level security;
create policy volumes_videos_admin_select on public.volumes_videos
  for select using (public.est_admin());

-- Poids des commentaires classés de chaque vidéo (1 si tout est classé). Les comptes de
-- `agregats_videos` restent des comptes réels de commentaires classés ; une somme sur plusieurs
-- vidéos les multiplie par ce poids.
alter table public.agregats_videos add column poids real not null default 1 check (poids >= 1);
