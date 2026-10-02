-- 02/10/2026 : classification en masse (docs/decisions.md).
-- Nature de chaque vidéo (Claude, un appel par vidéo) : la position n'est calculée que sous
-- une vidéo `opinion`. Métadonnée non textuelle, conservée toute la campagne.
alter table public.videos
  add column nature text check (nature in ('info_factuelle', 'opinion', 'debat')),
  add column nature_classee_le date;

-- Bucket privé des commentaires classés : une ligne par commentaire, sans aucun texte
-- (identifiant et auteur hashés). Conservé toute la campagne ; seul le batch y accède
-- (aucune policy sur storage.objects).
insert into storage.buckets (id, name, public)
values ('radar-classe', 'radar-classe', false)
on conflict (id) do nothing;
