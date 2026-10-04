// Petits composants et formats partagés par les écrans du Radar.
import type { ReactNode } from "react";

import { pct } from "@/lib/vueEnsemble";

export const entier = (n: number) => Math.round(n).toLocaleString("fr-FR");
export const pc = (n: number) => `${Math.round(n)} %`;
export const dateCourte = (j: string) =>
  j
    ? new Date(`${j}T12:00:00Z`).toLocaleDateString("fr-FR", {
        day: "numeric",
        month: "short",
      })
    : "–";
export const fois = (v: number | null) =>
  v === null ? "–" : `×${v.toFixed(1).replace(".", ",")}`;

export function EnPreparation({
  titre,
  attend,
  children,
}: {
  titre: string;
  attend: string;
  children?: ReactNode;
}) {
  return (
    <div className="radar-preparation">
      <p className="radar-preparation-titre">
        {titre} <span className="radar-badge-gris">En préparation</span>
      </p>
      {children}
      <p className="discret petit-texte">Attend : {attend}</p>
    </div>
  );
}

export type Segment = { libelle: string; valeur: number; couleur: string };

export function Barre({
  segments,
  total,
  titre,
}: {
  segments: Segment[];
  total: number;
  titre: string;
}) {
  const description = segments
    .map((s) => `${s.libelle} ${Math.round(pct(s.valeur, total))} %`)
    .join(", ");
  return (
    <div
      className="radar-barre"
      role="img"
      aria-label={`${titre} : ${description}`}
    >
      {segments.map((s) => (
        <span
          key={s.libelle}
          style={{ width: `${pct(s.valeur, total)}%`, background: s.couleur }}
        />
      ))}
    </div>
  );
}

export function Legende({ items }: { items: [string, string][] }) {
  return (
    <p className="radar-legende">
      {items.map(([libelle, couleur]) => (
        <span key={libelle}>
          <i style={{ background: couleur }} aria-hidden="true" /> {libelle}
        </span>
      ))}
    </p>
  );
}
