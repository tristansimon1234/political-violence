// Lecture des tables du Radar (lecture admin, RLS `est_admin`).
//
// Rapide : on compte d'abord les lignes, puis on lit toutes les pages de 1 000 en parallèle
// (6 à la fois), triées sur la clé primaire pour qu'aucune ligne ne soit lue deux fois ou
// oubliée. Les résultats restent en mémoire le temps de la visite : passer d'un écran à
// l'autre ne recharge rien. Rien n'est écrit dans le navigateur (ni stockage local, ni cache).
import type { SujetVideo } from "@/lib/agenda";
import { supabase } from "@/lib/supabase";

const PAGE = 1000;
const EN_PARALLELE = 6;

const CLES: Record<string, string[]> = {
  agregats_themes: ["jour", "theme", "type_source", "format"],
  agregats_chaines: ["jour", "theme", "source_id", "format"],
  agregats_videos: ["video_id"],
  videos_sujets: ["video_id", "theme"],
  videos_theses: ["video_id"],
  sujets_videos: ["video_id"],
  sources: ["id"],
  resumes_ia: ["id"],
};

const memoire = new Map<string, Promise<unknown[]>>();

async function lirePage(
  table: string,
  colonnes: string,
  debut: number,
): Promise<unknown[]> {
  let requete = supabase().from(table).select(colonnes);
  for (const c of CLES[table] ?? []) requete = requete.order(c);
  const { data, error } = await requete.range(debut, debut + PAGE - 1);
  if (error) throw new Error(error.message);
  return (data ?? []) as unknown[];
}

/** Nombre de lignes ; null si le serveur ne le donne pas (lecture séquentielle alors). */
async function compter(table: string): Promise<number | null> {
  const { count, error } = await supabase()
    .from(table)
    .select("*", { count: "exact", head: true });
  return error || count === null ? null : count;
}

async function lireTout(table: string, colonnes: string): Promise<unknown[]> {
  const total = CLES[table] ? await compter(table) : null;
  if (total === null) {
    // Sans clé connue ou sans comptage : lecture séquentielle, page après page.
    const lignes: unknown[] = [];
    for (let i = 0; ; i += PAGE) {
      const page = await lirePage(table, colonnes, i);
      lignes.push(...page);
      if (page.length < PAGE) return lignes;
    }
  }
  const debuts = Array.from(
    { length: Math.max(1, Math.ceil(total / PAGE)) },
    (_, i) => i * PAGE,
  );
  const pages: unknown[][] = new Array<unknown[]>(debuts.length);
  let suivant = 0;
  const travailleur = async () => {
    while (suivant < debuts.length) {
      const i = suivant++;
      pages[i] = await lirePage(table, colonnes, debuts[i] ?? 0);
    }
  };
  await Promise.all(
    Array.from({ length: Math.min(EN_PARALLELE, debuts.length) }, travailleur),
  );
  return pages.flat();
}

export function chargerTout<T>(table: string, colonnes: string): Promise<T[]> {
  const cle = `${table}|${colonnes}`;
  let p = memoire.get(cle);
  if (!p) {
    p = lireTout(table, colonnes);
    memoire.set(cle, p);
    p.catch(() => memoire.delete(cle)); // une erreur n'est pas gardée en mémoire
  }
  return p as Promise<T[]>;
}

/** Sujets des vidéos longues : les Shorts sont exclus de l'analyse (décision du 06/10/2026). */
export function chargerSujets(): Promise<SujetVideo[]> {
  return chargerTout<SujetVideo>(
    "videos_sujets",
    "video_id,theme,sous_sujet,poids,videos(publiee_at,format,vues,nb_commentaires,sources(id,type,sous_type,nom))",
  ).then((xs) => xs.filter((s) => s.videos?.format !== "short"));
}
