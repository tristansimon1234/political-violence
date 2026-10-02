// Calculs de la Vue d'ensemble, à partir de la table `agregats_themes` (aucun texte).
import { NON_POLITIQUE, THEMES, type Theme, type TypeSource } from "@/lib/taxonomie";

export type Agregat = {
  jour: string;
  theme: Theme | typeof NON_POLITIQUE;
  type_source: TypeSource;
  format: "short" | "long";
  commentaires: number;
  positifs: number;
  neutres: number;
  negatifs: number;
  hostiles: number;
  sous_opinion: number;
  accord: number;
  nuance: number;
  desaccord: number;
  hors_sujet: number;
};

export type Mesures = Omit<Agregat, "jour" | "theme" | "type_source" | "format">;
export const MESURES: (keyof Mesures)[] = [
  "commentaires",
  "positifs",
  "neutres",
  "negatifs",
  "hostiles",
  "sous_opinion",
  "accord",
  "nuance",
  "desaccord",
  "hors_sujet",
];

export type Filtres = {
  periode: 7 | 30 | "tout";
  types: TypeSource[]; // réactions du public : jamais `politique` ici
  format: "tous" | "short" | "long";
};

const JOUR_MS = 86_400_000;
export const decaler = (jour: string, n: number) =>
  new Date(Date.parse(`${jour}T00:00:00Z`) + n * JOUR_MS).toISOString().slice(0, 10);

export function vide(): Mesures {
  return Object.fromEntries(MESURES.map((m) => [m, 0])) as Mesures;
}

export function additionner(lignes: Agregat[]): Mesures {
  const s = vide();
  for (const l of lignes) for (const m of MESURES) s[m] += l[m];
  return s;
}

export type Fenetre = { debut: string; fin: string; jours: string[] };

/** Fenêtre courante et précédente, calées sur le dernier jour présent dans les données. */
export function fenetres(
  lignes: Agregat[],
  periode: Filtres["periode"],
): [Fenetre, Fenetre | null] {
  const jours = [...new Set(lignes.map((l) => l.jour))].sort();
  const premier = jours[0];
  const fin = jours[jours.length - 1];
  if (premier === undefined || fin === undefined) return [{ debut: "", fin: "", jours: [] }, null];
  const n =
    periode === "tout"
      ? Math.round((Date.parse(fin) - Date.parse(premier)) / JOUR_MS) + 1
      : periode;
  const liste = (f: string) => Array.from({ length: n }, (_, i) => decaler(f, i - n + 1));
  const courante = { debut: decaler(fin, -n + 1), fin, jours: liste(fin) };
  const finPrec = decaler(fin, -n);
  const precedente =
    periode === "tout" || finPrec < premier
      ? null
      : { debut: decaler(finPrec, -n + 1), fin: finPrec, jours: liste(finPrec) };
  return [courante, precedente];
}

export function filtrer(lignes: Agregat[], f: Filtres, types: TypeSource[] = f.types): Agregat[] {
  return lignes.filter(
    (l) => types.includes(l.type_source) && (f.format === "tous" || l.format === f.format),
  );
}

export const dans = (l: Agregat, w: Fenetre) => l.jour >= w.debut && l.jour <= w.fin;

/**
 * Vélocité provisoire : commentaires des 7 derniers jours ÷ moyenne hebdomadaire des 4 semaines
 * précédentes (non pondérée par l'audience des sources : à valider, docs/donnees.md).
 * null tant que les 4 semaines précédentes ne sont pas toutes couvertes par les données.
 */
export function velocite(
  lignes: Agregat[],
  theme: string,
  fin: string,
  premier: string,
): number | null {
  const debutBase = decaler(fin, -34);
  if (premier > debutBase) return null;
  const somme = (a: string, b: string) =>
    lignes
      .filter((l) => l.theme === theme && l.jour >= a && l.jour <= b)
      .reduce((s, l) => s + l.commentaires, 0);
  const base = somme(debutBase, decaler(fin, -7)) / 4;
  return base > 0 ? somme(decaler(fin, -6), fin) / base : null;
}

export type LigneTheme = {
  theme: Theme;
  courant: Mesures;
  precedent: Mesures | null;
  serie: number[];
  part: number; // part des commentaires politiques de la fenêtre
  velocite: number | null;
};

export function themes(
  lignes: Agregat[],
  f: Filtres,
): { lignes: LigneTheme[]; total: Mesures; nonPolitique: Mesures; courante: Fenetre } {
  const publics = filtrer(lignes, f);
  const [courante, precedente] = fenetres(lignes, f.periode);
  const premier = [...lignes.map((l) => l.jour)].sort()[0] ?? "";
  const dansCourante = publics.filter((l) => dans(l, courante));
  const politiques = dansCourante.filter((l) => l.theme !== NON_POLITIQUE);
  const totalPolitique = additionner(politiques).commentaires;
  const resultat = THEMES.map((theme) => {
    const duTheme = dansCourante.filter((l) => l.theme === theme);
    const parJour = new Map<string, number>();
    for (const l of duTheme) parJour.set(l.jour, (parJour.get(l.jour) ?? 0) + l.commentaires);
    const courant = additionner(duTheme);
    return {
      theme,
      courant,
      precedent: precedente
        ? additionner(publics.filter((l) => l.theme === theme && dans(l, precedente)))
        : null,
      serie: courante.jours.map((j) => parJour.get(j) ?? 0),
      part: totalPolitique > 0 ? courant.commentaires / totalPolitique : 0,
      velocite: velocite(publics, theme, courante.fin, premier),
    };
  });
  resultat.sort((a, b) => b.courant.commentaires - a.courant.commentaires);
  return {
    lignes: resultat,
    total: additionner(dansCourante),
    nonPolitique: additionner(dansCourante.filter((l) => l.theme === NON_POLITIQUE)),
    courante,
  };
}

export const pct = (part: number, total: number) => (total > 0 ? (100 * part) / total : 0);
