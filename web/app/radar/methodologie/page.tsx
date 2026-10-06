// « Méthodologie » : le texte source `docs/methodologie.md`, lu au build (une seule source,
// jamais recopié à la main). Aucune donnée : seulement la méthode.
import { readFileSync } from "node:fs";
import path from "node:path";
import { Fragment, type ReactNode } from "react";

import { Entete } from "@/lib/Entete";
import { Protege } from "@/lib/Protege";

type Bloc =
  | { type: "titre"; texte: string }
  | { type: "paragraphe"; texte: string }
  | { type: "liste"; ordonnee: boolean; items: string[] };

/** Markdown minimal du fichier : titres ##, paragraphes, listes « - » et « 1. ». */
function lire(md: string): Bloc[] {
  const blocs: Bloc[] = [];
  for (const brut of md.split(/\n\s*\n/)) {
    const lignes = brut.split("\n").filter((l) => l.trim());
    if (lignes.length === 0) continue;
    // Titre de page et note interne : la page a son propre titre.
    if (lignes[0]!.startsWith("# ") || lignes[0]!.startsWith("Texte source")) continue;
    let paragraphe: string[] = [];
    let liste: { ordonnee: boolean; items: string[] } | null = null;
    const vider = () => {
      if (paragraphe.length) blocs.push({ type: "paragraphe", texte: paragraphe.join(" ") });
      if (liste) blocs.push({ type: "liste", ...liste });
      paragraphe = [];
      liste = null;
    };
    for (const l of lignes) {
      const puce = /^\s*(-|\d+\.)\s+(.*)$/.exec(l);
      if (l.startsWith("## ")) {
        vider();
        blocs.push({ type: "titre", texte: l.slice(3) });
      } else if (puce) {
        if (paragraphe.length) {
          blocs.push({ type: "paragraphe", texte: paragraphe.join(" ") });
          paragraphe = [];
        }
        const ordonnee = puce[1] !== "-";
        if (!liste || liste.ordonnee !== ordonnee) {
          if (liste) blocs.push({ type: "liste", ...liste });
          liste = { ordonnee, items: [] };
        }
        liste.items.push(puce[2]!);
      } else if (liste && /^\s+/.test(l)) {
        liste.items[liste.items.length - 1] += ` ${l.trim()}`;
      } else {
        if (liste) {
          blocs.push({ type: "liste", ...liste });
          liste = null;
        }
        paragraphe.push(l.trim());
      }
    }
    vider();
  }
  return blocs;
}

/** **gras** et `code` en ligne. */
function enLigne(texte: string): ReactNode {
  return texte.split(/(\*\*[^*]+\*\*|`[^`]+`)/).map((m, i) =>
    m.startsWith("**") ? (
      <strong key={i}>{m.slice(2, -2)}</strong>
    ) : m.startsWith("`") ? (
      <code key={i}>{m.slice(1, -1)}</code>
    ) : (
      <Fragment key={i}>{m}</Fragment>
    ),
  );
}

const ancre = (t: string) =>
  t
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");

export default function Methodologie() {
  const md = readFileSync(path.join(process.cwd(), "..", "docs", "methodologie.md"), "utf8");
  const blocs = lire(md);
  const titres = blocs.filter((b) => b.type === "titre");
  return (
    <Protege titre="Radar 2027" retour="/radar/methodologie">
      <div className="radar">
        <Entete actif="methodologie" />
        <main className="r-page r-methodo">
          <nav className="r-carte r-sommaire" aria-label="Sommaire">
            <p className="r-surtitre">Sommaire</p>
            {titres.map((t) => (
              <a key={t.texte} href={`#${ancre(t.texte)}`}>
                {t.texte}
              </a>
            ))}
          </nav>
          <article className="r-carte r-texte">
            <h1>Méthodologie</h1>
            {blocs.map((b, i) =>
              b.type === "titre" ? (
                <h2 key={i} id={ancre(b.texte)}>
                  {b.texte}
                </h2>
              ) : b.type === "paragraphe" ? (
                <p key={i}>{enLigne(b.texte)}</p>
              ) : b.ordonnee ? (
                <ol key={i}>
                  {b.items.map((x, j) => (
                    <li key={j}>{enLigne(x)}</li>
                  ))}
                </ol>
              ) : (
                <ul key={i}>
                  {b.items.map((x, j) => (
                    <li key={j}>{enLigne(x)}</li>
                  ))}
                </ul>
              ),
            )}
          </article>
        </main>
      </div>
    </Protege>
  );
}
