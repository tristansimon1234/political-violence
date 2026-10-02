-- 02/10/2026 : agrégats par thème pour l'interface (Vue d'ensemble), docs/decisions.md.
-- Aucune donnée par commentaire, aucun texte : des sommes par jour × thème × type de source
-- × format. Un commentaire multi-thèmes compte 1/n dans chacun de ses thèmes (les sommes
-- sur les thèmes égalent le nombre de commentaires) ; les non politiques forment la ligne
-- `non_politique`. Position : seulement les commentaires sous une vidéo d'opinion.
-- Les chaînes politiques ont leurs propres lignes (type_source = 'politique') et ne sont
-- jamais additionnées aux réactions du public par l'interface.
create table public.agregats_themes (
  jour date not null,                     -- jour de publication du commentaire (Paris)
  theme text not null check (theme in ('pouvoir_achat', 'securite', 'immigration', 'retraites', 'sante', 'education', 'ecologie_energie', 'economie_emploi', 'logement', 'institutions', 'international_defense', 'agriculture', 'societe', 'autre', 'non_politique')),
  type_source text not null check (type_source in ('media_traditionnel', 'media_natif', 'politique')),
  format text not null check (format in ('short', 'long')),
  commentaires real not null,
  positifs real not null,
  neutres real not null,
  negatifs real not null,
  hostiles real not null,
  sous_opinion real not null,             -- commentaires sous une vidéo d'opinion
  accord real not null,
  nuance real not null,
  desaccord real not null,
  hors_sujet real not null,
  version_taxonomie smallint not null,
  maj_at timestamptz not null default now(),
  primary key (jour, theme, type_source, format)
);

alter table public.agregats_themes enable row level security;
-- Rien de public avant l'accord YouTube (« métriques dérivées ») : lecture admin seulement.
create policy agregats_themes_admin_select on public.agregats_themes
  for select using (public.est_admin());
