"use client";

// Le drill-down du Radar : un panneau latéral à niveaux (sujet › vidéo › commentaires), avec
// un fil d'Ariane et un retour. Un seul niveau affiché à la fois : rien ne s'imbrique dans
// les listes des écrans. Commentaires (texte brut) : admin seulement, 30 derniers jours.
import { useEffect, useLayoutEffect, useRef } from "react";

import type { ReactionVideo, SujetVideo, These } from "@/lib/agenda";
import { jourParis } from "@/lib/agenda";
import {
  type CarteSujet,
  type VideoDuSujet,
  thesesDuSujet,
} from "@/lib/cetteSemaine";
import { CommentairesVideo } from "@/lib/Commentaires";
import { PourquoiCaBouge, type ResumeIA } from "@/lib/PourquoiCaBouge";
import { LIBELLES_THEMES, LIBELLES_TYPE, type TypeSource } from "@/lib/taxonomie";
import { Barre, Legende, dateCourte, entier, pc } from "@/lib/ui";
import { pct } from "@/lib/vueEnsemble";

const MIN_PRONONCES = 20;
const PUBLICS: TypeSource[] = ["media_traditionnel", "media_natif"];
const lienYoutube = (v: string) => `https://www.youtube.com/watch?v=${v}`;

export type Niveau =
  | {
      type: "sujet";
      c: CarteSujet;
      resume: ResumeIA | null;
      evolution?: boolean; // comparaison avec la semaine précédente
    }
  | { type: "video"; v: VideoDuSujet; sujet?: string };

/** Une vidéo de `videos_sujets`, au format du drill-down. */
export function versVideo(
  s: SujetVideo,
  reactions: Map<string, ReactionVideo>,
  theses: Map<string, These>,
): VideoDuSujet {
  return {
    video_id: s.video_id,
    sous_sujet: s.sous_sujet,
    chaine: s.videos?.sources?.nom ?? "",
    type: s.videos?.sources?.type ?? "media_traditionnel",
    jour: s.videos ? jourParis(s.videos.publiee_at) : "",
    annonces: s.videos?.nb_commentaires ?? 0,
    reaction: reactions.get(s.video_id) ?? null,
    these: theses.get(s.video_id) ?? null,
  };
}

const prononces = (r: { accord: number; nuance: number; desaccord: number }) =>
  r.accord + r.nuance + r.desaccord;

export function Explorateur({
  pile,
  setPile,
}: {
  pile: Niveau[];
  setPile: (p: Niveau[]) => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const corps = useRef<HTMLDivElement>(null);
  const ouvert = pile.length > 0;
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (ouvert && !d.open) d.showModal();
    if (!ouvert && d.open) d.close();
  }, [ouvert]);
  // Descendre d'un niveau : haut de page, glissement vers la gauche. Remonter : on retrouve
  // la position de défilement du niveau, glissement vers la droite.
  const positions = useRef<number[]>([]);
  const profondeur = useRef(0);
  useLayoutEffect(() => {
    const el = corps.current;
    const avant = profondeur.current;
    profondeur.current = pile.length;
    if (!el) return;
    el.dataset.sens = pile.length < avant ? "arriere" : "avant";
    el.scrollTop =
      pile.length < avant ? (positions.current[pile.length - 1] ?? 0) : 0;
    positions.current.length = pile.length;
  }, [pile]);
  const courant = pile[pile.length - 1];
  const empiler = (n: Niveau) => setPile([...pile, n]);
  const nom = (n: Niveau) => (n.type === "sujet" ? n.c.titre : n.v.sous_sujet);
  return (
    <dialog
      ref={ref}
      className="explo"
      onClose={() => setPile([])}
      onClick={(e) => e.target === ref.current && setPile([])}
      aria-label="Détail"
    >
      {courant && (
        <div className="radar explo-cadre">
          <header className="explo-barre">
            {pile.length > 1 ? (
              <button
                className="explo-retour"
                onClick={() => setPile(pile.slice(0, -1))}
              >
                ‹ Retour
              </button>
            ) : (
              <span />
            )}
            <nav className="explo-ariane" aria-label="Fil d'Ariane">
              {pile.map((n, i) =>
                i < pile.length - 1 ? (
                  <button key={i} onClick={() => setPile(pile.slice(0, i + 1))}>
                    {nom(n)}
                  </button>
                ) : (
                  <span key={i} aria-current="page">
                    {n.type === "sujet" ? "Sujet" : "Vidéo"}
                  </span>
                ),
              )}
            </nav>
            <button
              className="explo-fermer"
              onClick={() => setPile([])}
              aria-label="Fermer"
            >
              ✕
            </button>
          </header>
          <div
            className="explo-corps"
            ref={corps}
            onScroll={(e) => {
              positions.current[pile.length - 1] = e.currentTarget.scrollTop;
            }}
          >
            <div className="explo-niveau" key={`${pile.length}|${nom(courant)}`}>
              {courant.type === "sujet" ? (
                <Sujet n={courant} empiler={empiler} />
              ) : (
                <Video v={courant.v} sujet={courant.sujet} />
              )}
            </div>
          </div>
        </div>
      )}
    </dialog>
  );
}

function evolution(c: CarteSujet): string {
  if (c.nouveau) return "apparu cette semaine";
  if (c.precedent === 0) return "rien la semaine précédente";
  const d = (c.classes / c.precedent - 1) * 100;
  return `${d >= 0 ? "+" : "−"}${Math.abs(Math.round(d))} % sur la semaine précédente`;
}

function Chiffre({
  valeur,
  libelle,
}: {
  valeur: string;
  libelle: string;
}) {
  return (
    <div className="explo-chiffre">
      <span>{valeur}</span>
      <span>{libelle}</span>
    </div>
  );
}

function BarrePositions({
  r,
  titre,
}: {
  r: { accord: number; nuance: number; desaccord: number };
  titre: string;
}) {
  const n = prononces(r);
  return (
    <div className="radar-rangee">
      <p className="radar-rangee-titre">
        <span>{titre}</span>
        <span className="radar-mono">
          {Math.round(pct(r.accord, n))} / {Math.round(pct(r.nuance, n))} /{" "}
          {Math.round(pct(r.desaccord, n))}
        </span>
      </p>
      <Barre
        titre={titre}
        total={n}
        segments={[
          { libelle: "Accord", valeur: r.accord, couleur: "var(--r-bleu)" },
          { libelle: "Nuance", valeur: r.nuance, couleur: "var(--r-nuance)" },
          {
            libelle: "Désaccord",
            valeur: r.desaccord,
            couleur: "var(--r-orange)",
          },
        ]}
      />
    </div>
  );
}

function Sujet({
  n,
  empiler,
}: {
  n: Extract<Niveau, { type: "sujet" }>;
  empiler: (n: Niveau) => void;
}) {
  const c = n.c;
  const total = PUBLICS.reduce((a, t) => a + (c.parType[t] ?? 0), 0);
  const p = prononces(c);
  const theses = thesesDuSujet(c).sort(
    (a, b) =>
      pct(b.reaction!.accord, b.prononces) - pct(a.reaction!.accord, a.prononces),
  );
  const extremes = [
    ...theses.slice(0, 2),
    ...theses.slice(-2).filter((x) => !theses.slice(0, 2).includes(x)),
  ];
  const ouvrirVideo = (v: VideoDuSujet) =>
    empiler({ type: "video", v, sujet: c.titre });
  return (
    <>
      <p className="explo-surtitre">Sujet d'actualité</p>
      <h2 className="explo-titre">{c.titre}</h2>
      <p className="radar-themes-sujet">
        {c.themes.map((t) => (
          <span key={t.theme} className="radar-puce">
            {LIBELLES_THEMES[t.theme]} {pc(t.part * 100)}
          </span>
        ))}
      </p>
      <div className="explo-chiffres">
        <Chiffre valeur={entier(c.classes)} libelle="commentaires" />
        <Chiffre
          valeur={`${c.videos.length}`}
          libelle={`vidéos · ${c.chaines} chaînes`}
        />
        <Chiffre
          valeur={c.classes ? pc(pct(c.hostiles, c.classes)) : "–"}
          libelle="hostiles"
        />
        <Chiffre
          valeur={p >= MIN_PRONONCES ? pc(pct(c.desaccord, p)) : "–"}
          libelle="désaccord avec les vidéos"
        />
      </div>
      {n.evolution && <p className="discret petit-texte">{evolution(c)}</p>}
      {n.resume && <PourquoiCaBouge r={n.resume} />}

      <section className="explo-section">
        <h3>Réactions</h3>
        {total > 0 && (
          <div className="radar-rangee">
            <p className="radar-rangee-titre">
              <span>Où ça réagit</span>
              <span className="radar-mono">
                Trad. {Math.round(pct(c.parType.media_traditionnel ?? 0, total))}{" "}
                % · Natifs{" "}
                {Math.round(pct(c.parType.media_natif ?? 0, total))} %
              </span>
            </p>
            <Barre
              titre="Commentaires par type de source"
              total={total}
              segments={[
                {
                  libelle: LIBELLES_TYPE.media_traditionnel,
                  valeur: c.parType.media_traditionnel ?? 0,
                  couleur: "var(--r-bleu)",
                },
                {
                  libelle: LIBELLES_TYPE.media_natif,
                  valeur: c.parType.media_natif ?? 0,
                  couleur: "var(--r-orange)",
                },
              ]}
            />
            <Legende
              items={[
                ["Médias traditionnels", "var(--r-bleu)"],
                ["Natifs du web", "var(--r-orange)"],
              ]}
            />
          </div>
        )}
        {p >= MIN_PRONONCES ? (
          <>
            <BarrePositions r={c} titre="Accord avec les vidéos d'opinion" />
            <Legende
              items={[
                ["Accord", "var(--r-bleu)"],
                ["Nuance", "var(--r-nuance)"],
                ["Désaccord", "var(--r-orange)"],
              ]}
            />
          </>
        ) : (
          <p className="discret petit-texte">
            Accord avec les vidéos : trop peu de commentaires qui se prononcent.
          </p>
        )}
      </section>

      {extremes.length > 0 && (
        <section className="explo-section">
          <h3>Thèses les plus approuvées et contestées</h3>
          <ul className="explo-liste">
            {extremes.map((v) => (
              <li key={v.video_id}>
                <button className="explo-ligne" onClick={() => ouvrirVideo(v)}>
                  <span className="explo-ligne-corps">
                    <span className="explo-ligne-titre">« {v.these?.these} »</span>
                    <Barre
                      titre="Accord avec la thèse"
                      total={v.prononces}
                      segments={[
                        {
                          libelle: "Accord",
                          valeur: v.reaction!.accord,
                          couleur: "var(--r-bleu)",
                        },
                        {
                          libelle: "Nuance",
                          valeur: v.reaction!.nuance,
                          couleur: "var(--r-nuance)",
                        },
                        {
                          libelle: "Désaccord",
                          valeur: v.reaction!.desaccord,
                          couleur: "var(--r-orange)",
                        },
                      ]}
                    />
                    <span className="explo-ligne-meta">
                      {Math.round(pct(v.reaction!.accord, v.prononces))} %
                      d'accord · {v.prononces} se prononcent · {v.chaine}
                    </span>
                  </span>
                  <span className="explo-chevron" aria-hidden="true">
                    ›
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <p className="discret petit-texte">
            Thèse résumée par une IA à partir du titre et de la description, pas
            du contenu de la vidéo.
          </p>
        </section>
      )}

      <section className="explo-section">
        <h3>Les vidéos ({c.videos.length})</h3>
        <ListeVideos videos={c.videos} ouvrir={ouvrirVideo} />
        <p className="discret petit-texte">
          Libellé neutre écrit par une IA (pas le titre de la vidéo).
        </p>
      </section>
    </>
  );
}

/** Lignes cliquables : une vidéo par ligne, ouverte dans le panneau. */
export function ListeVideos({
  videos,
  ouvrir,
  sujetDe,
}: {
  videos: VideoDuSujet[];
  ouvrir: (v: VideoDuSujet) => void;
  sujetDe?: (videoId: string) => string | undefined;
}) {
  return (
    <ul className="explo-liste">
      {videos.map((v) => {
        const r = v.reaction;
        const n = r ? prononces(r) : 0;
        const sujet = sujetDe?.(v.video_id);
        return (
          <li key={v.video_id}>
            <button className="explo-ligne" onClick={() => ouvrir(v)}>
              <span className="explo-ligne-corps">
                <span className="explo-ligne-titre">{v.sous_sujet}</span>
                {sujet && <span className="radar-sujet-video">{sujet}</span>}
                <span className="explo-ligne-meta">
                  {v.chaine} · {dateCourte(v.jour)}
                </span>
              </span>
              <span className="explo-ligne-chiffres">
                <span>
                  {entier(v.annonces)}
                  <small> comm. annoncés</small>
                </span>
                <span className="discret">
                  {r
                    ? `${entier(r.commentaires)} classés${n >= MIN_PRONONCES ? ` · ${Math.round(pct(r.accord, n))} % d'accord` : ""}`
                    : "non classée"}
                </span>
              </span>
              <span className="explo-chevron" aria-hidden="true">
                ›
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function Video({ v, sujet }: { v: VideoDuSujet; sujet?: string }) {
  const r = v.reaction;
  const n = r ? prononces(r) : 0;
  return (
    <>
      <p className="explo-surtitre">Vidéo</p>
      <h2 className="explo-titre">{v.sous_sujet}</h2>
      <p className="discret petit-texte">
        {v.chaine} · {LIBELLES_TYPE[v.type]} · publiée le {dateCourte(v.jour)}
        {sujet ? ` · sujet : ${sujet}` : ""} ·{" "}
        <a href={lienYoutube(v.video_id)} target="_blank" rel="noreferrer">
          Voir sur YouTube ↗
        </a>
      </p>
      <div className="explo-chiffres">
        <Chiffre valeur={entier(v.annonces)} libelle="commentaires annoncés" />
        <Chiffre
          valeur={r ? entier(r.commentaires) : "–"}
          libelle="commentaires classés"
        />
        <Chiffre
          valeur={r && r.commentaires ? pc(pct(r.hostiles, r.commentaires)) : "–"}
          libelle="hostiles"
        />
      </div>
      {v.these && (
        <p className="explo-these">
          <span className="discret petit-texte">
            Thèse de la vidéo {v.these.explicite ? "" : "(incertaine)"} · résumée
            par une IA
          </span>
          « {v.these.these} »
        </p>
      )}
      {r && n >= MIN_PRONONCES && (
        <>
          <BarrePositions r={r} titre="Accord avec la vidéo" />
          <Legende
            items={[
              ["Accord", "var(--r-bleu)"],
              ["Nuance", "var(--r-nuance)"],
              ["Désaccord", "var(--r-orange)"],
            ]}
          />
        </>
      )}
      <section className="explo-section">
        <h3>Commentaires classés</h3>
        <CommentairesVideo videoId={v.video_id} />
      </section>
    </>
  );
}
