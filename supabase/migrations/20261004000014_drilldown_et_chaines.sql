-- 04/10/2026 : drill-down par vidéo et filtre par chaîne, docs/decisions.md.

-- Commentaires classés des 30 derniers jours, un fichier compressé par vidéo
-- (`videos/<video_id>.json.gz` : texte non modifié, date, étiquettes ; ni pseudo, ni auteur,
-- ni identifiant de commentaire). Écrit et purgé par le job d'agrégats. Lecture admin seulement.
insert into storage.buckets (id, name, public)
values ('radar-drilldown', 'radar-drilldown', false)
on conflict (id) do nothing;

create policy drilldown_admin_select on storage.objects
  for select using (bucket_id = 'radar-drilldown' and public.est_admin());

-- Agrégats par chaîne (même contenu que agregats_themes, avec la source) pour le filtre par
-- chaîne de la Vue d'ensemble. Aucun texte.
create table public.agregats_chaines (
  jour date not null,
  theme text not null check (theme in ('pouvoir_achat', 'securite', 'immigration', 'retraites', 'sante', 'education', 'ecologie_energie', 'economie_emploi', 'logement', 'institutions', 'international_defense', 'agriculture', 'societe', 'autre', 'non_politique')),
  source_id uuid not null references public.sources (id),
  type_source text not null check (type_source in ('media_traditionnel', 'media_natif', 'politique')),
  format text not null check (format in ('short', 'long')),
  commentaires real not null,
  positifs real not null,
  neutres real not null,
  negatifs real not null,
  hostiles real not null,
  sous_opinion real not null,
  accord real not null,
  nuance real not null,
  desaccord real not null,
  hors_sujet real not null,
  version_taxonomie smallint not null,
  maj_at timestamptz not null default now(),
  primary key (jour, theme, source_id, format)
);
alter table public.agregats_chaines enable row level security;
create policy agregats_chaines_admin_select on public.agregats_chaines
  for select using (public.est_admin());
