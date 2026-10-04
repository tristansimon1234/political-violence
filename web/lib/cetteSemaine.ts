// « Cette semaine » : les sujets d'actualité de la semaine (vidéos regroupées par événement),
// avec leurs réactions. Calcul côté client à partir de `videos_sujets`, `sujets_videos`,
// `agregats_videos` et `videos_theses`. Aucun texte de commentaire.
import {
  type ReactionVideo,
  type Rattachement,
  type SujetVideo,
  type These,
  MIN_CHAINES_SUJET,
  MIN_PRONONCES,
  MIN_VIDEOS_SUJET,
  jourParis,
} from "@/lib/agenda";
import type { Theme, TypeSource } from "@/lib/taxonomie";

export type Periode = { debut: string; fin: string }; // AAAA-MM-JJ inclus

export type VideoDuSujet = {
  video_id: string;
  sous_sujet: string; // sous-sujet du thème principal de la vidéo
  chaine: string;
  type: TypeSource;
  jour: string;
  annonces: number; // commentaires annoncés par YouTube
  reaction: ReactionVideo | null;
  these: These | null;
};

export type CarteSujet = {
  id: string;
  titre: string;
  nouveau: boolean; // premier jour du sujet dans la période
  videos: VideoDuSujet[]; // les plus commentées d'abord
  chaines: number;
  themes: { theme: Theme; part: number }[];
  classes: number; // commentaires classés sous ses vidéos
  hostiles: number;
  accord: number;
  nuance: number;
  desaccord: number;
  parType: Partial<Record<TypeSource, number>>; // commentaires classés par type de source
  parJour: number[]; // vidéos publiées par jour de la période
  precedent: number; // commentaires classés la période précédente (même durée)
};

const JOUR_MS = 86_400_000;
export const decaler = (j: string, n: number) =>
  new Date(Date.parse(`${j}T12:00:00Z`) + n * JOUR_MS)
    .toISOString()
    .slice(0, 10);

/** Semaine du lundi au dimanche contenant le jour donné. */
export function semaineDe(jour: string): Periode {
  const d = new Date(`${jour}T12:00:00Z`);
  const debut = decaler(jour, -((d.getUTCDay() + 6) % 7));
  return { debut, fin: decaler(debut, 6) };
}

/** Dernier jour de publication parmi les vidéos chargées. */
export function dernierJour(sujets: SujetVideo[]): string | null {
  let max: string | null = null;
  for (const s of sujets) {
    if (!s.videos) continue;
    const j = jourParis(s.videos.publiee_at);
    if (max === null || j > max) max = j;
  }
  return max;
}

type Acc = {
  carte: CarteSujet;
  vues: Set<string>;
  chaines: Set<string>;
  poids: Map<Theme, number>;
};

function regrouper(
  sujets: SujetVideo[],
  p: Periode,
  types: TypeSource[],
  rattachements: Map<string, Rattachement>,
  reactions: Map<string, ReactionVideo>,
  theses: Map<string, These>,
): Map<string, Acc> {
  // Sous-sujet du thème principal (poids le plus fort) de chaque vidéo.
  const principal = new Map<string, SujetVideo>();
  for (const s of sujets) {
    const x = principal.get(s.video_id);
    if (!x || s.poids > x.poids) principal.set(s.video_id, s);
  }
  const m = new Map<string, Acc>();
  for (const s of sujets) {
    const v = s.videos;
    const r = rattachements.get(s.video_id);
    if (!v || !v.sources || !r?.sujet_id || !r.sujets) continue;
    const jour = jourParis(v.publiee_at);
    if (jour < p.debut || jour > p.fin || !types.includes(v.sources.type))
      continue;
    const id = r.sujet_id;
    const acc = m.get(id) ?? {
      carte: {
        id,
        titre: r.sujets.titre,
        nouveau: (r.sujets.premier_jour ?? "") >= p.debut,
        videos: [],
        chaines: 0,
        themes: [],
        classes: 0,
        hostiles: 0,
        accord: 0,
        nuance: 0,
        desaccord: 0,
        parType: {},
        parJour: Array.from({ length: 7 }, () => 0),
        precedent: 0,
      },
      vues: new Set<string>(),
      chaines: new Set<string>(),
      poids: new Map<Theme, number>(),
    };
    acc.poids.set(s.theme, (acc.poids.get(s.theme) ?? 0) + s.poids);
    if (!acc.vues.has(s.video_id)) {
      acc.vues.add(s.video_id);
      acc.chaines.add(v.sources.nom);
      const reaction = reactions.get(s.video_id) ?? null;
      const c = acc.carte;
      c.videos.push({
        video_id: s.video_id,
        sous_sujet: principal.get(s.video_id)?.sous_sujet ?? s.sous_sujet,
        chaine: v.sources.nom,
        type: v.sources.type,
        jour,
        annonces: v.nb_commentaires ?? 0,
        reaction,
        these: theses.get(s.video_id) ?? null,
      });
      const i = Math.round((Date.parse(jour) - Date.parse(p.debut)) / JOUR_MS);
      if (i >= 0 && i < c.parJour.length)
        c.parJour[i] = (c.parJour[i] ?? 0) + 1;
      if (reaction) {
        c.classes += reaction.commentaires;
        c.hostiles += reaction.hostiles;
        c.accord += reaction.accord;
        c.nuance += reaction.nuance;
        c.desaccord += reaction.desaccord;
        c.parType[v.sources.type] =
          (c.parType[v.sources.type] ?? 0) + reaction.commentaires;
      }
    }
    m.set(id, acc);
  }
  return m;
}

/**
 * Sujets de la période (au moins 3 vidéos de 2 chaînes parmi les vidéos affichées), classés
 * par commentaires classés, puis par commentaires annoncés.
 */
export function cartesSujets(
  sujets: SujetVideo[],
  p: Periode,
  types: TypeSource[],
  rattachements: Map<string, Rattachement>,
  reactions: Map<string, ReactionVideo>,
  theses: Map<string, These>,
): CarteSujet[] {
  const courant = regrouper(sujets, p, types, rattachements, reactions, theses);
  const avant = regrouper(
    sujets,
    { debut: decaler(p.debut, -7), fin: decaler(p.fin, -7) },
    types,
    rattachements,
    reactions,
    theses,
  );
  const annonces = (c: CarteSujet) =>
    c.videos.reduce((a, v) => a + v.annonces, 0);
  return [...courant.values()]
    .filter(
      (a) =>
        a.vues.size >= MIN_VIDEOS_SUJET && a.chaines.size >= MIN_CHAINES_SUJET,
    )
    .map(({ carte, chaines, poids }) => {
      const total = [...poids.values()].reduce((a, b) => a + b, 0);
      carte.chaines = chaines.size;
      carte.themes = [...poids.entries()]
        .map(([theme, w]) => ({ theme, part: w / total }))
        .sort((a, b) => b.part - a.part);
      carte.videos.sort(
        (a, b) =>
          (b.reaction?.commentaires ?? b.annonces) -
          (a.reaction?.commentaires ?? a.annonces),
      );
      carte.precedent = avant.get(carte.id)?.carte.classes ?? 0;
      return carte;
    })
    .sort((a, b) => b.classes - a.classes || annonces(b) - annonces(a));
}

/** Thèses explicites des vidéos du sujet avec assez de commentaires qui se prononcent. */
export function thesesDuSujet(
  c: CarteSujet,
): (VideoDuSujet & { prononces: number })[] {
  return c.videos
    .filter((v) => v.these?.explicite && v.reaction)
    .map((v) => {
      const r = v.reaction!;
      return { ...v, prononces: r.accord + r.nuance + r.desaccord };
    })
    .filter((v) => v.prononces >= MIN_PRONONCES);
}
