// En-tête commun aux écrans du Radar : logo, navigation, rappel de ce que mesure le Radar.
import Link from "next/link";

export function Entete({ actif }: { actif: "semaine" | "ensemble" }) {
  const lien = (cle: "semaine" | "ensemble", href: string, nom: string) =>
    actif === cle ? (
      <span className="radar-nav-actif" aria-current="page">
        {nom}
      </span>
    ) : (
      <Link href={href}>{nom}</Link>
    );
  return (
    <>
      <header className="radar-entete">
        <div>
          <p className="radar-logo">Radar 2027</p>
          <p className="radar-sous-titre">
            Réactions YouTube · panel v1 · mis à jour à chaque calcul
          </p>
        </div>
        <nav aria-label="Écrans">
          {lien("semaine", "/radar/semaine", "Cette semaine")}
          {lien("ensemble", "/radar", "Vue d'ensemble")}
          <a href="/admin">Admin</a>
        </nav>
      </header>
      <p className="cs-bandeau">
        <span className="cs-badge">Données réelles · expérimentation privée</span>
        <span>
          Ce que mesure le Radar : les réactions des commentateurs YouTube,{" "}
          <strong>pas l'opinion des Français</strong>.
        </span>
      </p>
    </>
  );
}
