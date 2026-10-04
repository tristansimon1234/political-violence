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
  classes: number; // commentaires sous ses vidéos (estimés : classés × poids de la vidéo)
  hostiles: number;
  accord: number;
  nuance: number;
  desaccord: number;
  parType: Partial<Record<TypeSource, number>>; // commentaires par type de source
  positionsParType: Partial<Record<TypeSource, Positions>>; // accord par type de source
  parJour: number[]; // commentaires par jour de publication des vidéos, sur la période
  precedent: number; // commentaires la période précédente (même durée)
  premierJour: string; // premier jour du sujet (toutes vidéos)
};

export type Positions = { accord: number; nuance: number; desaccord: number };

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
        premierJour: r.sujets.premier_jour ?? jour,
        videos: [],
        chaines: 0,
        themes: [],
        classes: 0,
        hostiles: 0,
        accord: 0,
        nuance: 0,
        desaccord: 0,
        parType: {},
        positionsParType: {},
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
      if (i >= 0 && i < c.parJour.length && reaction)
        c.parJour[i] =
          (c.parJour[i] ?? 0) + (reaction.poids ?? 1) * reaction.commentaires;
      if (reaction) {
        // Plafond par vidéo : on additionne des estimations pondérées par vidéo.
        const w = reaction.poids ?? 1;
        c.classes += w * reaction.commentaires;
        c.hostiles += w * reaction.hostiles;
        c.accord += w * reaction.accord;
        c.nuance += w * reaction.nuance;
        c.desaccord += w * reaction.desaccord;
        c.parType[v.sources.type] =
          (c.parType[v.sources.type] ?? 0) + w * reaction.commentaires;
        const pt = c.positionsParType[v.sources.type] ?? {
          accord: 0,
          nuance: 0,
          desaccord: 0,
        };
        pt.accord += w * reaction.accord;
        pt.nuance += w * reaction.nuance;
        pt.desaccord += w * reaction.desaccord;
        c.positionsParType[v.sources.type] = pt;
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

// --- Récupération politique : qui, parmi les chaînes politiques, publie sur le sujet ---

export type Reprise = {
  partis: number;
  personnalites: number;
  premierPolitique: string | null;
  premierMedia: string | null;
};

/** Chaînes politiques ayant publié sur le sujet jusqu'à la fin de la période (lues à part). */
export function reprisePolitique(
  sujets: SujetVideo[],
  rattachements: Map<string, Rattachement>,
  sujetId: string,
  fin: string,
): Reprise {
  const partis = new Set<string>();
  const personnalites = new Set<string>();
  let premierPolitique: string | null = null;
  let premierMedia: string | null = null;
  const vues = new Set<string>();
  for (const s of sujets) {
    if (vues.has(s.video_id)) continue;
    if (rattachements.get(s.video_id)?.sujet_id !== sujetId) continue;
    const v = s.videos;
    if (!v?.sources) continue;
    vues.add(s.video_id);
    const jour = jourParis(v.publiee_at);
    if (jour > fin) continue;
    if (v.sources.type === "politique") {
      (v.sources.sous_type === "parti" ? partis : personnalites).add(
        v.sources.nom,
      );
      if (!premierPolitique || jour < premierPolitique) premierPolitique = jour;
    } else if (!premierMedia || jour < premierMedia) premierMedia = jour;
  }
  return {
    partis: partis.size,
    personnalites: personnalites.size,
    premierPolitique,
    premierMedia,
  };
}

// --- Faits marquants : ce qui sort du lot cette semaine (pas des totaux) ---

export type Fait = {
  cle: string;
  etiquette: string; // « Le plus contesté »…
  valeur: string; // chiffre mis en avant
  texte: string; // une phrase
  sujet: CarteSujet;
};

const MIN_PRONONCES_FAIT = 50;
const MIN_COMMENTAIRES_FAIT = 200;
const pc0 = (x: number) => `${Math.round(x)} %`;
const fois1 = (x: number) => `×${x.toFixed(1).replace(".", ",")}`;

function partPos(
  p: Positions | undefined,
  cle: keyof Positions,
): number | null {
  if (!p) return null;
  const n = p.accord + p.nuance + p.desaccord;
  return n >= MIN_PRONONCES_FAIT ? (100 * p[cle]) / n : null;
}

/**
 * Les constats de la semaine, chacun appuyé sur un sujet : le plus commenté, le plus
 * contesté, le plus consensuel, le plus hostile, la plus forte hausse, le plus grand écart
 * médias traditionnels / natifs, un sujet lancé par une chaîne politique, un sujet peu couvert
 * mais très commenté. Seuils minimaux pour ne pas mettre en avant un petit échantillon.
 */
export function faitsMarquants(
  cartes: CarteSujet[],
  reprises: Map<string, Reprise>,
): Fait[] {
  const faits: Fait[] = [];
  const max = <T>(xs: T[], f: (x: T) => number | null): [T, number] | null => {
    let best: [T, number] | null = null;
    for (const x of xs) {
      const v = f(x);
      if (v !== null && (best === null || v > best[1])) best = [x, v];
    }
    return best;
  };
  const top = cartes[0];
  if (top)
    faits.push({
      cle: "commente",
      etiquette: "Le plus commenté",
      valeur: Math.round(top.classes).toLocaleString("fr-FR"),
      texte: `commentaires sous « ${top.titre} » (${top.videos.length} vidéos).`,
      sujet: top,
    });
  const tous = (c: CarteSujet) => ({
    accord: c.accord,
    nuance: c.nuance,
    desaccord: c.desaccord,
  });
  const conteste = max(cartes, (c) => partPos(tous(c), "desaccord"));
  if (conteste && conteste[1] >= 50)
    faits.push({
      cle: "conteste",
      etiquette: "Le plus contesté",
      valeur: pc0(conteste[1]),
      texte: `de désaccord avec les vidéos sur « ${conteste[0].titre} ».`,
      sujet: conteste[0],
    });
  const consensuel = max(cartes, (c) => partPos(tous(c), "accord"));
  if (consensuel && consensuel[1] >= 50 && consensuel[0] !== conteste?.[0])
    faits.push({
      cle: "consensuel",
      etiquette: "Le plus approuvé",
      valeur: pc0(consensuel[1]),
      texte: `d'accord avec les vidéos sur « ${consensuel[0].titre} ».`,
      sujet: consensuel[0],
    });
  const hostile = max(
    cartes.filter((c) => c.classes >= MIN_COMMENTAIRES_FAIT),
    (c) => (100 * c.hostiles) / c.classes,
  );
  if (hostile)
    faits.push({
      cle: "hostile",
      etiquette: "Le plus hostile",
      valeur: pc0(hostile[1]),
      texte: `de commentaires hostiles sur « ${hostile[0].titre} ».`,
      sujet: hostile[0],
    });
  const hausse = max(
    cartes.filter((c) => c.precedent >= MIN_COMMENTAIRES_FAIT && !c.nouveau),
    (c) => c.classes / c.precedent,
  );
  if (hausse && hausse[1] >= 1.5)
    faits.push({
      cle: "hausse",
      etiquette: "La plus forte hausse",
      valeur: fois1(hausse[1]),
      texte: `de commentaires sur « ${hausse[0].titre} » face à la semaine précédente.`,
      sujet: hausse[0],
    });
  const clivage = max(cartes, (c) => {
    const a = partPos(c.positionsParType.media_traditionnel, "desaccord");
    const b = partPos(c.positionsParType.media_natif, "desaccord");
    return a === null || b === null ? null : Math.abs(a - b);
  });
  if (clivage && clivage[1] >= 15) {
    const c = clivage[0];
    const a = partPos(c.positionsParType.media_traditionnel, "desaccord") ?? 0;
    const b = partPos(c.positionsParType.media_natif, "desaccord") ?? 0;
    faits.push({
      cle: "clivage",
      etiquette: "Médias trad. ou natifs ?",
      valeur: `${Math.round(Math.abs(a - b))} pts`,
      texte: `d'écart de désaccord sur « ${c.titre} » : ${pc0(a)} sous les médias traditionnels, ${pc0(b)} sous les natifs du web.`,
      sujet: c,
    });
  }
  const lance = cartes.find((c) => {
    const r = reprises.get(c.id);
    return (
      r?.premierPolitique &&
      r.premierMedia &&
      r.premierPolitique < r.premierMedia
    );
  });
  if (lance)
    faits.push({
      cle: "politique",
      etiquette: "Lancé par les politiques",
      valeur: "1er",
      texte: `« ${lance.titre} » : une chaîne politique en a parlé avant les médias du panel.`,
      sujet: lance,
    });
  const videos = cartes.reduce((a, c) => a + c.videos.length, 0);
  const comm = cartes.reduce((a, c) => a + c.classes, 0);
  const sous = max(
    cartes.filter((c) => c !== top && c.classes >= MIN_COMMENTAIRES_FAIT),
    (c) =>
      videos && comm ? c.classes / comm / (c.videos.length / videos) : null,
  );
  if (sous && sous[1] >= 2)
    faits.push({
      cle: "sous_couvert",
      etiquette: "Peu couvert, très commenté",
      valeur: fois1(sous[1]),
      texte: `plus de réactions que sa part de couverture pour « ${sous[0].titre} » (${sous[0].videos.length} vidéos).`,
      sujet: sous[0],
    });
  return faits;
}
