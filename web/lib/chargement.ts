// Lecture paginée des tables du Radar (lecture admin, RLS `est_admin`).
import type { SujetVideo } from "@/lib/agenda";
import { supabase } from "@/lib/supabase";

export async function chargerTout<T>(
  table: string,
  colonnes: string,
): Promise<T[]> {
  const lignes: T[] = [];
  for (let i = 0; ; i += 1000) {
    const { data, error } = await supabase()
      .from(table)
      .select(colonnes)
      .range(i, i + 999);
    if (error) throw new Error(error.message);
    lignes.push(...(data as unknown as T[]));
    if (!data || data.length < 1000) return lignes;
  }
}

export async function chargerSujets(): Promise<SujetVideo[]> {
  const lignes: SujetVideo[] = [];
  for (let i = 0; ; i += 1000) {
    const { data, error } = await supabase()
      .from("videos_sujets")
      .select(
        "video_id,theme,sous_sujet,poids,videos(publiee_at,format,vues,nb_commentaires,sources(id,type,nom))",
      )
      .range(i, i + 999);
    if (error) throw new Error(error.message);
    lignes.push(...(data as unknown as SujetVideo[]));
    if (!data || data.length < 1000) return lignes;
  }
}
