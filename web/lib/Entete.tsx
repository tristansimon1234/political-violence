// En-tête commun aux écrans du Radar : logo, navigation, outils de l'écran (semaine, filtres),
// et le rappel de ce que mesure le Radar.
import Link from "next/link";
import type { ReactNode } from "react";

export function Entete({
  actif,
  outils,
}: {
  actif: "semaine" | "ensemble";
  outils?: ReactNode;
}) {
  const lien = (cle: "semaine" | "ensemble", href: string, nom: string) => (
    <Link
      href={href}
      className={actif === cle ? "r-nav-lien actif" : "r-nav-lien"}
      aria-current={actif === cle ? "page" : undefined}
    >
      {nom}
    </Link>
  );
  return (
    <header className="r-barre">
      <div className="r-barre-int">
        <Link href="/radar/semaine" className="r-logo">
          <span className="r-logo-icone" aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
              <circle cx="12" cy="12" r="9" />
              <circle cx="12" cy="12" r="4" />
              <path d="M12 12L19 5" />
            </svg>
          </span>
          Radar 2027
        </Link>
        <nav className="r-nav" aria-label="Écrans">
          {lien("semaine", "/radar/semaine", "Cette semaine")}
          {lien("ensemble", "/radar", "Thèmes")}
          <a href="/admin" className="r-nav-lien">
            Admin
          </a>
        </nav>
        {outils && <div className="r-outils">{outils}</div>}
      </div>
      <p className="r-avert">
        Réactions des commentateurs YouTube, <strong>pas l'opinion des Français</strong> ·
        données réelles · expérimentation privée
      </p>
    </header>
  );
}
