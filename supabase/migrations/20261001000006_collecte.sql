-- Étape 2 : état de la collecte (sans aucun texte brut) et bucket privé du stockage brut.

-- Une ligne par vidéo vue. Pas de titre ni de description ici : ils vont dans le Parquet brut
-- (purgé à 30 jours). Seules des métadonnées non textuelles sont conservées.
create table public.videos (
  video_id text primary key,
  source_id uuid not null references public.sources (id),
  publiee_at timestamptz not null,
  format text not null check (format in ('short', 'long')),
  duree_s integer not null,
  vues bigint,
  nb_commentaires bigint,
  prefiltre boolean not null,          -- passe le pré-filtre mots-clés, ou chaîne politique
  prefiltre_version text not null,     -- empreinte de config/mots_cles.txt
  commentaires_fermes boolean not null default false,
  premiere_vue date not null,          -- premier jour où la vidéo a été récupérée
  premiere_collecte date,              -- premier jour de collecte des commentaires
  derniere_collecte date,              -- dernier jour de collecte des commentaires
  nb_collectes integer not null default 0,
  maj_at timestamptz not null default now()
);
create index videos_source_publiee_idx on public.videos (source_id, publiee_at);

-- Reprise du backfill : une ligne par (source, période) dont les uploads ont été parcourus.
create table public.collecte_etat (
  source_id uuid not null references public.sources (id),
  depuis date not null,
  jusqua date not null,
  uploads_parcourus_at timestamptz not null default now(),
  primary key (source_id, depuis, jusqua)
);

-- Journal des runs (quota consommé, volumes).
create table public.collecte_runs (
  id bigint generated always as identity primary key,
  mode text not null check (mode in ('quotidien', 'backfill')),
  dry_run boolean not null,
  debut timestamptz not null,
  fin timestamptz not null,
  budget integer not null,
  quota_consomme integer not null,
  arret_budget boolean not null,
  videos_vues integer not null,
  videos_prefiltre integer not null,
  videos_commentees integer not null,
  commentaires integer not null,
  details jsonb not null default '{}'::jsonb
);

alter table public.videos enable row level security;
alter table public.collecte_etat enable row level security;
alter table public.collecte_runs enable row level security;

create policy videos_admin_select on public.videos for select using (public.est_admin());
create policy collecte_etat_admin_select on public.collecte_etat for select using (public.est_admin());
create policy collecte_runs_admin_select on public.collecte_runs for select using (public.est_admin());

-- Bucket privé du texte brut (commentaires, titres, descriptions), purgé à 30 jours.
-- Aucune policy sur storage.objects : seul le batch, avec la clé secrète, y accède.
insert into storage.buckets (id, name, public)
values ('radar-brut', 'radar-brut', false)
on conflict (id) do nothing;
