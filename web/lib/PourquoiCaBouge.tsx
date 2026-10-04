// « Pourquoi ça bouge » : résumé IA (table `resumes_ia`), avec ses sources numérotées.
// Chaque renvoi [n] pointe vers un chiffre agrégé ou une vidéo (lien). Non relu.
import { Fragment } from "react";

export type ResumeIA = {
  id: string;
  categorie: "sujet" | "theme";
  cible: string;
  semaine: string;
  texte: string;
  sources: { n: number; texte: string; video_id: string | null }[];
};

/** Le résumé le plus récent pour une cible, au plus tard la semaine donnée. */
export function dernierResume(
  resumes: ResumeIA[],
  categorie: "sujet" | "theme",
  cible: string,
  auPlusTard?: string,
): ResumeIA | null {
  let r: ResumeIA | null = null;
  for (const x of resumes)
    if (
      x.categorie === categorie &&
      x.cible === cible &&
      (!auPlusTard || x.semaine <= auPlusTard) &&
      (!r || x.semaine > r.semaine)
    )
      r = x;
  return r;
}

export function PourquoiCaBouge({
  r,
  semaine,
}: {
  r: ResumeIA;
  semaine?: boolean;
}) {
  const morceaux = r.texte.split(/(\[\d+\])/);
  return (
    <div className="pcb">
      <p className="pcb-tete">
        <span className="pcb-badge">Généré par IA</span>
        <span>
          Pourquoi ça bouge · non relu
          {semaine
            ? ` · semaine du ${new Date(`${r.semaine}T12:00:00Z`).toLocaleDateString("fr-FR", { day: "numeric", month: "short" })}`
            : ""}
        </span>
      </p>
      <p className="pcb-texte">
        {morceaux.map((m, i) => {
          const n = /^\[(\d+)\]$/.exec(m)?.[1];
          return n ? (
            <sup key={i} className="pcb-renvoi">
              [{n}]
            </sup>
          ) : (
            <Fragment key={i}>{m}</Fragment>
          );
        })}
      </p>
      <ol className="pcb-sources">
        {r.sources.map((s) => (
          <li key={s.n}>
            <span className="pcb-n">[{s.n}]</span> {s.texte}
            {s.video_id && (
              <>
                {" · "}
                <a
                  href={`https://www.youtube.com/watch?v=${s.video_id}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Voir la vidéo ↗
                </a>
              </>
            )}
          </li>
        ))}
      </ol>
      <p className="pcb-note">
        Écrit par une IA à partir des chiffres agrégés et des vidéos de la
        semaine · aucune citation de commentaire.
      </p>
    </div>
  );
}
