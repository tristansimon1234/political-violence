-- 02/10/2026 : collecte de tous les commentaires de premier niveau (docs/decisions.md).
-- mode_commentaires : 'pertinence_200' (ancien mode, 200 premiers par pertinence) ou 'tout'.
-- Une vidéo collectée dans l'ancien mode est recollectée en entier au prochain backfill.
-- commentaires_lus_jusqua : instant de la dernière lecture ; la revisite quotidienne ne lit que
-- les commentaires publiés depuis (lecture chronologique incrémentale).
alter table public.videos
  add column mode_commentaires text check (mode_commentaires in ('pertinence_200', 'tout')),
  add column commentaires_lus_jusqua timestamptz;

update public.videos
  set mode_commentaires = 'pertinence_200'
  where derniere_collecte is not null;
