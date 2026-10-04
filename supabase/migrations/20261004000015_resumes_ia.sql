-- 04/10/2026 : « Pourquoi ça bouge », résumés IA par sujet et par thème, docs/decisions.md.
-- Écrits par Claude à partir de chiffres agrégés et de métadonnées de vidéos (sous-sujet
-- neutre, chaîne, date, commentaires) ; jamais de texte de commentaire ni de pseudo. Chaque
-- affirmation renvoie à une source (`sources` : numéro, chiffre ou vidéo). Non relus :
-- l'interface l'indique. Lecture admin seulement.
create table public.resumes_ia (
  id text primary key,                       -- sujet:<id>:<lundi> ou theme:<thème>:<lundi>
  categorie text not null check (categorie in ('sujet', 'theme')),
  cible text not null,
  semaine date not null,                     -- lundi de la semaine
  texte text not null check (char_length(texte) <= 900),
  sources jsonb not null,
  empreinte text not null,                   -- des chiffres envoyés : régénéré s'ils changent
  modele text not null,
  cree_le date not null
);
create index resumes_ia_semaine_idx on public.resumes_ia (semaine);
alter table public.resumes_ia enable row level security;
create policy resumes_ia_admin_select on public.resumes_ia
  for select using (public.est_admin());
