-- Panel de chaînes YouTube et journal des changements.
-- Listes type / sous_type : miroir de radar/schemas.py (vérifié par tests/test_migrations.py).

create extension if not exists pgcrypto;

-- Compte(s) admin : alimenté à la main via le service role, jamais depuis l'interface.
create table public.admins (
  user_id uuid primary key references auth.users (id) on delete cascade
);
alter table public.admins enable row level security;

create function public.est_admin() returns boolean
language sql stable security definer set search_path = public
as $$
  select exists (select 1 from public.admins where user_id = auth.uid());
$$;

create table public.sources (
  id uuid primary key default gen_random_uuid(),
  channel_id text not null unique,
  handle text,
  nom text not null,
  type text not null check (type in ('media', 'influenceur', 'politique')),
  sous_type text not null,
  critere_inclusion text not null check (length(trim(critere_inclusion)) > 0),
  active boolean not null default true,
  uploads_playlist_id text not null,
  -- Statistiques calculées à l'import (et rafraîchies ensuite)
  abonnes bigint,
  videos_90j integer,
  vues_90j bigint,
  part_commentaires_ouverts real,
  derniere_video_at timestamptz,
  stats_maj_at timestamptz,
  version_taxonomie integer not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint sources_sous_type_check check (
    case type
      when 'media' then sous_type in ('info_continu', 'tv_radio', 'talk_show', 'presse_nationale', 'pure_player')
      when 'influenceur' then sous_type in ('vulgarisation', 'commentateur', 'debat')
      when 'politique' then sous_type in ('parti', 'personnalite')
      else false
    end
  )
);

create table public.sources_journal (
  id bigint generated always as identity primary key,
  source_id uuid not null references public.sources (id),
  action text not null check (action in ('ajout', 'pause', 'reprise', 'modification')),
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index sources_journal_source_idx on public.sources_journal (source_id, created_at);

-- On ne supprime jamais une source : on la met en pause.
create function public.interdire_suppression_source() returns trigger
language plpgsql
as $$
begin
  raise exception 'Suppression interdite : mettre la source en pause (active = false)';
end;
$$;

create trigger sources_pas_de_suppression
  before delete on public.sources
  for each row execute function public.interdire_suppression_source();

create function public.maj_updated_at() returns trigger
language plpgsql
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

create trigger sources_updated_at
  before update on public.sources
  for each row execute function public.maj_updated_at();

-- Chaque ajout, pause, reprise ou modification éditoriale est journalisé.
-- Les rafraîchissements de statistiques ou du nom ne le sont pas.
create function public.journaliser_source() returns trigger
language plpgsql security definer set search_path = public
as $$
begin
  if tg_op = 'INSERT' then
    insert into public.sources_journal (source_id, action, details)
    values (new.id, 'ajout', jsonb_build_object(
      'nom', new.nom, 'type', new.type, 'sous_type', new.sous_type,
      'critere_inclusion', new.critere_inclusion));
    return new;
  end if;

  if new.active is distinct from old.active then
    insert into public.sources_journal (source_id, action, details)
    values (new.id, case when new.active then 'reprise' else 'pause' end,
            jsonb_build_object('nom', new.nom));
  end if;

  if (new.type, new.sous_type, new.critere_inclusion)
     is distinct from (old.type, old.sous_type, old.critere_inclusion) then
    insert into public.sources_journal (source_id, action, details)
    values (new.id, 'modification', jsonb_build_object(
      'nom', new.nom,
      'avant', jsonb_build_object('type', old.type, 'sous_type', old.sous_type,
                                  'critere_inclusion', old.critere_inclusion),
      'apres', jsonb_build_object('type', new.type, 'sous_type', new.sous_type,
                                  'critere_inclusion', new.critere_inclusion)));
  end if;
  return new;
end;
$$;

create trigger sources_journal_auto
  after insert or update on public.sources
  for each row execute function public.journaliser_source();

-- RLS : lecture et écriture réservées à l'admin. Le batch passe par le service role.
alter table public.sources enable row level security;
alter table public.sources_journal enable row level security;

create policy sources_admin_select on public.sources
  for select using (public.est_admin());
create policy sources_admin_insert on public.sources
  for insert with check (public.est_admin());
create policy sources_admin_update on public.sources
  for update using (public.est_admin()) with check (public.est_admin());

create policy sources_journal_admin_select on public.sources_journal
  for select using (public.est_admin());
