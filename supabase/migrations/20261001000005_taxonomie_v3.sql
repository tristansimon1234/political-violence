-- Taxonomie v3 (docs/decisions.md, 01/10/2026) : médias traditionnels / médias natifs du web / politiques.
-- La catégorie « influenceur » est supprimée. Listes : miroir de radar/schemas.py (tests/test_migrations.py).

alter table public.sources drop constraint sources_type_check;
alter table public.sources drop constraint sources_sous_type_check;

-- Reprise des lignes éventuelles (taxonomie v2 → v3).
update public.sources set type = 'media_natif'
  where type = 'media' and sous_type = 'pure_player';
update public.sources set type = 'media_traditionnel'
  where type = 'media';
update public.sources set type = 'media_natif', sous_type = 'createur'
  where type = 'influenceur';
update public.sources set version_taxonomie = 3;

alter table public.sources add constraint sources_type_check
  check (type in ('media_traditionnel', 'media_natif', 'politique'));
alter table public.sources add constraint sources_sous_type_check check (
  case type
    when 'media_traditionnel' then sous_type in ('info_continu', 'tv_radio', 'talk_show', 'presse_nationale')
    when 'media_natif' then sous_type in ('pure_player', 'createur')
    when 'politique' then sous_type in ('parti', 'personnalite')
    else false
  end
);
