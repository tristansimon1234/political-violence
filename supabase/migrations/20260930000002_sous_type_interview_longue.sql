-- Taxonomie v2 : ajout du sous-type influenceur 'interview_longue'.
-- Listes type / sous_type : miroir de radar/schemas.py (vérifié par tests/test_migrations.py).

alter table public.sources drop constraint sources_sous_type_check;
alter table public.sources add constraint sources_sous_type_check check (
  case type
    when 'media' then sous_type in ('info_continu', 'tv_radio', 'talk_show', 'presse_nationale', 'pure_player')
    when 'influenceur' then sous_type in ('vulgarisation', 'commentateur', 'debat', 'interview_longue')
    when 'politique' then sous_type in ('parti', 'personnalite')
    else false
  end
);
