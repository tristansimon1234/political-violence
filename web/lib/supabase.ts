import { createClient, type SupabaseClient } from "@supabase/supabase-js";

import type { SousType, TypeSource } from "@/lib/taxonomie";

// Clé publique (publishable) uniquement : les droits sont portés par la RLS (admin seul).
let instance: SupabaseClient | null = null;

export function supabase(): SupabaseClient {
  if (instance) return instance;
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const cle = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (!url || !cle) {
    throw new Error(
      "NEXT_PUBLIC_SUPABASE_URL et NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY doivent être définies.",
    );
  }
  instance = createClient(url, cle);
  return instance;
}

export type Source = {
  id: string;
  channel_id: string;
  handle: string | null;
  nom: string;
  type: TypeSource;
  sous_type: SousType;
  critere_inclusion: string;
  active: boolean;
  abonnes: number | null;
  fenetre_jours: number | null;
  videos_fenetre: number | null;
  vues_fenetre: number | null;
  part_commentaires_ouverts: number | null;
  derniere_video_at: string | null;
  stats_maj_at: string | null;
};

export type EntreeJournal = {
  id: number;
  source_id: string;
  action: "ajout" | "pause" | "reprise" | "modification";
  details: { nom?: string };
  created_at: string;
};
