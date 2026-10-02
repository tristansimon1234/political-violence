// L'agenda des médias : thèmes des vidéos publiées (table `videos_sujets`), à comparer aux
// thèmes des commentaires. Aucun titre ni description : un sous-sujet neutre par thème.
import type { Theme, TypeSource } from "@/lib/taxonomie";
import type { Fenetre, Filtres } from "@/lib/vueEnsemble";

export type SujetVideo = {
  video_id: string;
  theme: Theme;
  sous_sujet: string;
  poids: number;
  videos: {
    publiee_at: string;
    format: "short" | "long";
    vues: number | null;
    nb_commentaires: number | null;
    sources: { type: TypeSource; nom: string } | null;
  } | null;
};

const PARIS = new Intl.DateTimeFormat("fr-CA", { timeZone: "Europe/Paris" });
export const jourParis = (iso: string) => PARIS.format(new Date(iso)); // AAAA-MM-JJ

/** Sujets des vidéos publiées dans la fenêtre, sous les types et le format choisis. */
export function sujetsFiltres(sujets: SujetVideo[], f: Filtres, w: Fenetre): SujetVideo[] {
  return sujets.filter((s) => {
    const v = s.videos;
    if (!v || !v.sources) return false;
    const jour = jourParis(v.publiee_at);
    return (
      f.types.includes(v.sources.type) &&
      (f.format === "tous" || v.format === f.format) &&
      jour >= w.debut &&
      jour <= w.fin
    );
  });
}

export type Agenda = { videos: number; vues: number };

/** Par thème : vidéos (somme des poids) et vues réparties selon les poids. */
export function agendaParTheme(sujets: SujetVideo[]): Map<Theme, Agenda> {
  const m = new Map<Theme, Agenda>();
  for (const s of sujets) {
    const a = m.get(s.theme) ?? { videos: 0, vues: 0 };
    a.videos += s.poids;
    a.vues += (s.videos?.vues ?? 0) * s.poids;
    m.set(s.theme, a);
  }
  return m;
}

export type SousSujet = { libelle: string; commentaires: number; videos: number };

/** Sous-sujets d'un thème, classés par commentaires annoncés par YouTube (pondérés). */
export function sousSujets(sujets: SujetVideo[], theme: Theme, n = 5): SousSujet[] {
  const m = new Map<string, SousSujet>();
  for (const s of sujets) {
    if (s.theme !== theme) continue;
    const cle = s.sous_sujet.toLowerCase();
    const x = m.get(cle) ?? { libelle: s.sous_sujet, commentaires: 0, videos: 0 };
    x.commentaires += (s.videos?.nb_commentaires ?? 0) * s.poids;
    x.videos += 1;
    m.set(cle, x);
  }
  return [...m.values()]
    .filter((x) => x.libelle !== "hors politique")
    .sort((a, b) => b.commentaires - a.commentaires)
    .slice(0, n);
}

/** Vidéos du thème qui font le plus réagir (commentaires annoncés × poids du thème). */
export function videosQuiReagissent(sujets: SujetVideo[], theme: Theme, n = 5): SujetVideo[] {
  return sujets
    .filter((s) => s.theme === theme)
    .sort(
      (a, b) =>
        (b.videos?.nb_commentaires ?? 0) * b.poids - (a.videos?.nb_commentaires ?? 0) * a.poids,
    )
    .slice(0, n);
}
