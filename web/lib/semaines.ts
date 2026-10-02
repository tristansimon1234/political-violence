// Comparaison semaine par semaine (lundi → dimanche, dates de Paris), à partir des agrégats
// journaliers et des sujets de vidéos. Une semaine trop maigre est exclue des comparaisons.
import { THEMES, type Theme } from "@/lib/taxonomie";
import { jourParis, type SujetVideo } from "@/lib/agenda";
import { type Agregat, type Filtres, decaler, filtrer } from "@/lib/vueEnsemble";

export const MIN_COMMENTAIRES_SEMAINE = 1000; // commentaires politiques

/** Lundi de la semaine d'un jour AAAA-MM-JJ. */
export function lundi(jour: string): string {
  const j = new Date(`${jour}T12:00:00Z`).getUTCDay(); // 0 = dimanche
  return decaler(jour, -((j + 6) % 7));
}

export type Semaine = {
  debut: string; // lundi
  complete: boolean; // les 7 jours sont couverts par les données (ni début ni fin tronqués)
  total: number; // commentaires politiques
  parts: Map<Theme, number>; // part de chaque thème parmi les commentaires politiques
  fiable: boolean;
};

export function semaines(lignes: Agregat[], f: Filtres): Semaine[] {
  const publics = filtrer(lignes, f).filter((l) => l.theme !== "non_politique");
  const dernierJour = lignes.reduce((m, l) => (l.jour > m ? l.jour : m), "");
  const premierJour = lignes.reduce((m, l) => (m === "" || l.jour < m ? l.jour : m), "");
  const parSemaine = new Map<string, Map<Theme, number>>();
  for (const l of publics) {
    const s = lundi(l.jour);
    const m = parSemaine.get(s) ?? new Map<Theme, number>();
    m.set(l.theme as Theme, (m.get(l.theme as Theme) ?? 0) + l.commentaires);
    parSemaine.set(s, m);
  }
  return [...parSemaine.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([debut, m]) => {
      const total = [...m.values()].reduce((a, x) => a + x, 0);
      const parts = new Map<Theme, number>(
        THEMES.map((t) => [t, total > 0 ? (m.get(t) ?? 0) / total : 0]),
      );
      return {
        debut,
        complete: debut >= premierJour && decaler(debut, 6) <= dernierJour,
        total,
        parts,
        fiable: total >= MIN_COMMENTAIRES_SEMAINE,
      };
    });
}

export type Changement = { theme: Theme; avant: number; apres: number; ecart: number };

/** Les deux dernières semaines complètes et fiables, et les plus fortes variations de part. */
export function changements(
  liste: Semaine[],
): { avant: Semaine; apres: Semaine; hausses: Changement[]; baisses: Changement[] } | null {
  const utiles = liste.filter((s) => s.complete && s.fiable);
  const apres = utiles[utiles.length - 1];
  const avant = utiles[utiles.length - 2];
  if (!apres || !avant) return null;
  const tous = THEMES.filter((t) => t !== "autre").map((t) => {
    const a = avant.parts.get(t) ?? 0;
    const b = apres.parts.get(t) ?? 0;
    return { theme: t, avant: a, apres: b, ecart: (b - a) * 100 };
  });
  return {
    avant,
    apres,
    hausses: tous
      .filter((c) => c.ecart >= 1)
      .sort((x, y) => y.ecart - x.ecart)
      .slice(0, 3),
    baisses: tous
      .filter((c) => c.ecart <= -1)
      .sort((x, y) => x.ecart - y.ecart)
      .slice(0, 3),
  };
}

/** Sous-sujets du top 10 de la semaine `apres` absents du top 10 de la semaine `avant`. */
export function nouveauxSousSujets(sujets: SujetVideo[], avant: string, apres: string): string[] {
  const top = (debut: string) => {
    const m = new Map<string, { libelle: string; poids: number }>();
    for (const s of sujets) {
      if (!s.videos || lundi(jourParis(s.videos.publiee_at)) !== debut) continue;
      if (s.sous_sujet === "hors politique") continue;
      const cle = s.sous_sujet.toLowerCase();
      const x = m.get(cle) ?? { libelle: s.sous_sujet, poids: 0 };
      x.poids += (s.videos.nb_commentaires ?? 0) * s.poids;
      m.set(cle, x);
    }
    return [...m.entries()].sort((a, b) => b[1].poids - a[1].poids).slice(0, 10);
  };
  const precedents = new Set(top(avant).map(([cle]) => cle));
  return top(apres)
    .filter(([cle]) => !precedents.has(cle))
    .map(([, x]) => x.libelle)
    .slice(0, 5);
}
