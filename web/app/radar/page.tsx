"use client";

import { useEffect, useMemo, useState } from "react";

import { AccesAdmin } from "@/lib/AccesAdmin";
import { supabase } from "@/lib/supabase";
import { LIBELLES_THEMES, LIBELLES_TYPE, type Theme, type TypeSource } from "@/lib/taxonomie";
import {
  type Agregat,
  type Filtres,
  type Mesures,
  additionner,
  dans,
  fenetres,
  filtrer,
  pct,
  themes,
} from "@/lib/vueEnsemble";

const PUBLICS: TypeSource[] = ["media_traditionnel", "media_natif"];
const entier = (n: number) => Math.round(n).toLocaleString("fr-FR");
const pc = (n: number) => `${Math.round(n)} %`;
const dateCourte = (j: string) =>
  j
    ? new Date(`${j}T12:00:00Z`).toLocaleDateString("fr-FR", { day: "numeric", month: "short" })
    : "–";

export default function Radar() {
  return (
    <AccesAdmin titre="Radar 2027" retour="/radar">
      {() => <VueEnsemble />}
    </AccesAdmin>
  );
}

async function chargerAgregats(): Promise<Agregat[]> {
  const lignes: Agregat[] = [];
  for (let i = 0; ; i += 1000) {
    const { data, error } = await supabase()
      .from("agregats_themes")
      .select("*")
      .order("jour")
      .range(i, i + 999);
    if (error) throw new Error(error.message);
    lignes.push(...(data as Agregat[]));
    if (!data || data.length < 1000) return lignes;
  }
}

function VueEnsemble() {
  const [lignes, setLignes] = useState<Agregat[] | null>(null);
  const [erreur, setErreur] = useState("");
  const [filtres, setFiltres] = useState<Filtres>({ periode: 7, types: PUBLICS, format: "tous" });
  const [politiques, setPolitiques] = useState(false);
  const [choisi, setChoisi] = useState<Theme | null>(null);

  useEffect(() => {
    chargerAgregats()
      .then(setLignes)
      .catch((e: unknown) => setErreur(e instanceof Error ? e.message : String(e)));
  }, []);

  // Table vide : aucun calcul (pas de dernier jour, donc pas de fenêtre).
  const vue = useMemo(
    () => (lignes && lignes.length > 0 ? themes(lignes, filtres) : null),
    [lignes, filtres],
  );
  const actif = choisi ?? vue?.lignes[0]?.theme ?? null;

  return (
    <div className="radar">
      <header className="radar-entete">
        <div>
          <p className="radar-logo">Radar 2027</p>
          <p className="radar-sous-titre">
            Réactions YouTube · panel v1 · vue d'ensemble des thèmes
          </p>
        </div>
        <nav aria-label="Écrans">
          <span className="radar-nav-actif">Vue d'ensemble</span>
          <span
            className="radar-nav-inactif"
            title="Après la détection des sujets d'actu (étape 6)"
          >
            Cette semaine
          </span>
          <a href="/admin">Admin</a>
        </nav>
      </header>
      <p className="radar-bandeau">
        Mesure les réactions des commentateurs YouTube, <strong>pas l'opinion des Français</strong>.
        Expérimentation privée : rien n'est publié.
      </p>

      {erreur && <p className="erreur">{erreur}</p>}
      {!lignes && !erreur && <p className="discret radar-marge">Chargement des agrégats…</p>}
      {lignes && lignes.length === 0 && (
        <p className="discret radar-marge">
          Aucun agrégat : lancer la classification puis le workflow « Agrégats ».
        </p>
      )}

      {vue && lignes && lignes.length > 0 && (
        <>
          <BarreFiltres
            filtres={filtres}
            setFiltres={setFiltres}
            politiques={politiques}
            setPolitiques={setPolitiques}
          />
          <p className="discret radar-marge">
            Du {dateCourte(vue.courante.debut)} au {dateCourte(vue.courante.fin)} (jour de
            publication des commentaires) · {entier(vue.total.commentaires)} commentaires classés,
            dont {pc(pct(vue.nonPolitique.commentaires, vue.total.commentaires))} non politiques.
          </p>
          <div className="radar-grille">
            <section className="radar-carte" aria-labelledby="titre-themes">
              <h2 id="titre-themes">Thèmes</h2>
              <p className="discret petit-texte">
                Part des commentaires politiques · évolution sur la période précédente · vélocité 7
                j.
              </p>
              <ol className="radar-themes">
                {vue.lignes.map((l, i) => {
                  const evolution =
                    l.precedent && l.precedent.commentaires > 0
                      ? (l.courant.commentaires / l.precedent.commentaires - 1) * 100
                      : null;
                  return (
                    <li key={l.theme}>
                      <button
                        className={l.theme === actif ? "radar-theme actif" : "radar-theme"}
                        onClick={() => setChoisi(l.theme)}
                        aria-pressed={l.theme === actif}
                      >
                        <span className="radar-rang">{i + 1}</span>
                        <span className="radar-nom">{LIBELLES_THEMES[l.theme]}</span>
                        <Courbe serie={l.serie} />
                        <span className="radar-chiffre">{pc(l.part * 100)}</span>
                        <span
                          className={
                            evolution !== null && evolution > 0
                              ? "radar-chiffre hausse"
                              : "radar-chiffre"
                          }
                        >
                          {evolution === null
                            ? "–"
                            : `${evolution > 0 ? "+" : ""}${Math.round(evolution)} %`}
                        </span>
                        <span
                          className={
                            l.velocite !== null && l.velocite >= 1.5
                              ? "radar-velocite forte"
                              : "radar-velocite"
                          }
                          title={
                            l.velocite === null
                              ? "Historique insuffisant (4 semaines précédentes)"
                              : "Vélocité provisoire, non pondérée par l'audience"
                          }
                        >
                          {l.velocite === null
                            ? "–"
                            : `×${l.velocite.toFixed(1).replace(".", ",")}`}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ol>
            </section>
            {actif && (
              <DetailTheme
                theme={actif}
                lignes={lignes}
                filtres={filtres}
                politiques={politiques}
              />
            )}
          </div>
        </>
      )}
    </div>
  );
}

function BarreFiltres({
  filtres,
  setFiltres,
  politiques,
  setPolitiques,
}: {
  filtres: Filtres;
  setFiltres: (f: Filtres) => void;
  politiques: boolean;
  setPolitiques: (b: boolean) => void;
}) {
  const basculerType = (t: TypeSource) => {
    const types = filtres.types.includes(t)
      ? filtres.types.filter((x) => x !== t)
      : [...filtres.types, t];
    if (types.length) setFiltres({ ...filtres, types });
  };
  return (
    <div className="radar-filtres" role="group" aria-label="Filtres">
      <fieldset>
        <legend>Période</legend>
        {([7, 30, "tout"] as const).map((p) => (
          <button
            key={p}
            className={filtres.periode === p ? "segment actif" : "segment"}
            aria-pressed={filtres.periode === p}
            onClick={() => setFiltres({ ...filtres, periode: p })}
          >
            {p === "tout" ? "Depuis le début" : `${p} jours`}
          </button>
        ))}
      </fieldset>
      <fieldset>
        <legend>Réactions sous</legend>
        {PUBLICS.map((t) => (
          <button
            key={t}
            className={filtres.types.includes(t) ? "segment actif" : "segment"}
            aria-pressed={filtres.types.includes(t)}
            onClick={() => basculerType(t)}
          >
            {LIBELLES_TYPE[t]}
          </button>
        ))}
      </fieldset>
      <fieldset>
        <legend>Format</legend>
        {(["tous", "long", "short"] as const).map((f) => (
          <button
            key={f}
            className={filtres.format === f ? "segment actif" : "segment"}
            aria-pressed={filtres.format === f}
            onClick={() => setFiltres({ ...filtres, format: f })}
          >
            {f === "tous" ? "Tous" : f === "long" ? "Vidéos longues" : "Shorts"}
          </button>
        ))}
      </fieldset>
      <label className="radar-interrupteur">
        <input
          type="checkbox"
          checked={politiques}
          onChange={(e) => setPolitiques(e.target.checked)}
        />
        Chaînes politiques (lues à part)
      </label>
    </div>
  );
}

function Courbe({ serie }: { serie: number[] }) {
  const max = Math.max(1, ...serie);
  const l = 84;
  const h = 22;
  const pas = serie.length > 1 ? l / (serie.length - 1) : 0;
  const points = serie
    .map((v, i) => `${(i * pas).toFixed(1)},${(h - (v / max) * (h - 2) - 1).toFixed(1)}`)
    .join(" ");
  return (
    <svg className="radar-courbe" width={l} height={h} viewBox={`0 0 ${l} ${h}`} aria-hidden="true">
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

type Segment = { libelle: string; valeur: number; couleur: string };

function Barre({ segments, total, titre }: { segments: Segment[]; total: number; titre: string }) {
  return (
    <div className="radar-barre-bloc">
      <div
        className="radar-barre"
        role="img"
        aria-label={`${titre} : ${segments.map((s) => `${s.libelle} ${Math.round(pct(s.valeur, total))} %`).join(", ")}`}
      >
        {segments.map((s) => (
          <span
            key={s.libelle}
            style={{ width: `${pct(s.valeur, total)}%`, background: s.couleur }}
          />
        ))}
      </div>
      <p className="radar-legende">
        {segments.map((s) => (
          <span key={s.libelle}>
            <i style={{ background: s.couleur }} aria-hidden="true" /> {s.libelle}{" "}
            {pc(pct(s.valeur, total))}
          </span>
        ))}
      </p>
    </div>
  );
}

function Ligne({ libelle, m, aPart }: { libelle: string; m: Mesures; aPart?: boolean }) {
  const prononces = m.accord + m.nuance + m.desaccord;
  return (
    <div className={aPart ? "radar-ligne a-part" : "radar-ligne"}>
      <h4>
        {libelle} <span className="discret">· {entier(m.commentaires)} commentaires</span>
      </h4>
      <p className="petit-texte">Tonalité</p>
      <Barre
        titre="Tonalité"
        total={m.commentaires}
        segments={[
          { libelle: "Positive", valeur: m.positifs, couleur: "var(--r-bleu)" },
          { libelle: "Neutre", valeur: m.neutres, couleur: "var(--r-nuance)" },
          { libelle: "Négative", valeur: m.negatifs, couleur: "var(--r-orange)" },
        ]}
      />
      <p className="petit-texte">
        Commentaires hostiles : <strong>{pc(pct(m.hostiles, m.commentaires))}</strong>
      </p>
      <p className="petit-texte">
        Accord avec la vidéo{" "}
        <span className="discret">
          (vidéos d'opinion seulement · {entier(m.sous_opinion)} commentaires, dont{" "}
          {pc(pct(m.hors_sujet, m.sous_opinion))} ne se prononcent pas)
        </span>
      </p>
      {prononces > 0 ? (
        <Barre
          titre="Accord avec la vidéo"
          total={prononces}
          segments={[
            { libelle: "Accord", valeur: m.accord, couleur: "var(--r-bleu)" },
            { libelle: "Nuance", valeur: m.nuance, couleur: "var(--r-nuance)" },
            { libelle: "Désaccord", valeur: m.desaccord, couleur: "var(--r-orange)" },
          ]}
        />
      ) : (
        <p className="discret petit-texte">
          Pas de commentaire qui se prononce sous une vidéo d'opinion.
        </p>
      )}
    </div>
  );
}

function DetailTheme({
  theme,
  lignes,
  filtres,
  politiques,
}: {
  theme: Theme;
  lignes: Agregat[];
  filtres: Filtres;
  politiques: boolean;
}) {
  const [courante] = fenetres(lignes, filtres.periode);
  const du = (types: TypeSource[]) =>
    additionner(
      filtrer(lignes, filtres, types).filter((l) => l.theme === theme && dans(l, courante)),
    );
  return (
    <section className="radar-carte radar-detail" aria-labelledby="titre-detail">
      <h2 id="titre-detail">{LIBELLES_THEMES[theme]}</h2>
      <p className="discret petit-texte">
        Réactions du public sous les médias sélectionnés. Un commentaire sur plusieurs thèmes compte
        pour 1/n dans chacun.
      </p>
      <Ligne libelle="Ensemble" m={du(filtres.types)} />
      {filtres.types.map((t) => (
        <Ligne key={t} libelle={LIBELLES_TYPE[t]} m={du([t])} />
      ))}
      {politiques && (
        <Ligne
          libelle="Chaînes politiques · lues à part, jamais additionnées"
          m={du(["politique"])}
          aPart
        />
      )}
      <p className="discret petit-texte">
        Données réelles, classées par Jev (justesse mesurée sur un échantillon étiqueté : voir la
        méthodologie).
      </p>
    </section>
  );
}
