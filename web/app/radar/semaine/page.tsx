"use client";

// « Cette semaine » : l'accueil éditorial, d'après la maquette « Radar 2027 ». Les sujets
// d'actualité de la semaine, ce qui les distingue (où ça réagit, désaccord, hostilité,
// reprise par les chaînes politiques), le décalage couverture / réactions, et ce qui a changé.
import { useDeferredValue, useEffect, useMemo, useState } from "react";

import Link from "next/link";

import { AccesAdmin } from "@/lib/AccesAdmin";
import {
  type ReactionVideo,
  type Rattachement,
  type SujetVideo,
  type These,
} from "@/lib/agenda";
import {
  type CarteSujet,
  type Periode,
  type Positions as PositionsType,
  type Reprise,
  cartesSujets,
  decaler,
  dernierJour,
  faitsMarquants,
  reprisePolitique,
  semaineDe,
} from "@/lib/cetteSemaine";
import { chargerSujets, chargerTout } from "@/lib/chargement";
import { Entete } from "@/lib/Entete";
import { Explorateur, type Niveau } from "@/lib/Explorateur";
import {
  PourquoiCaBouge,
  type ResumeIA,
  dernierResume,
} from "@/lib/PourquoiCaBouge";
import { LIBELLES_THEMES, type TypeSource } from "@/lib/taxonomie";
import { Legende, Squelette, dateCourte, entier, pc } from "@/lib/ui";
import { pct } from "@/lib/vueEnsemble";

const PUBLICS: TypeSource[] = ["media_traditionnel", "media_natif"];
const COURT: Record<string, string> = {
  media_traditionnel: "Médias trad.",
  media_natif: "Natifs du web",
};
const MIN_PRONONCES_SUJET = 20;
const DEBUT_COLLECTE = "2026-09-01";
const jj = (j: string) => `${j.slice(8, 10)}/${j.slice(5, 7)}`;
const fois = (x: number) => `×${x.toFixed(1).replace(".", ",")}`;
const ecartJours = (a: string, b: string) =>
  Math.round((Date.parse(a) - Date.parse(b)) / 86_400_000);

export default function CetteSemaine() {
  return (
    <AccesAdmin titre="Radar 2027" retour="/radar/semaine">
      {() => <Ecran />}
    </AccesAdmin>
  );
}

function Ecran() {
  const [sujets, setSujets] = useState<SujetVideo[] | null>(null);
  const [rattachements, setRattachements] = useState<Map<string, Rattachement>>(
    new Map(),
  );
  const [reactions, setReactions] = useState<Map<string, ReactionVideo>>(
    new Map(),
  );
  const [theses, setTheses] = useState<Map<string, These>>(new Map());
  const [resumes, setResumes] = useState<ResumeIA[]>([]);
  const [erreur, setErreur] = useState("");
  const [types, setTypes] = useState<TypeSource[]>(PUBLICS);
  const [debut, setDebut] = useState<string | null>(null);
  const [tous, setTous] = useState(false);
  const [pile, setPile] = useState<Niveau[]>([]);

  useEffect(() => {
    const echec = (e: unknown) =>
      setErreur(e instanceof Error ? e.message : String(e));
    chargerSujets().then(setSujets).catch(echec);
    chargerTout<Rattachement>(
      "sujets_videos",
      "video_id,sujet_id,sujets(titre,premier_jour)",
    )
      .then((l) => setRattachements(new Map(l.map((r) => [r.video_id, r]))))
      .catch(echec);
    chargerTout<ReactionVideo>("agregats_videos", "*")
      .then((l) => setReactions(new Map(l.map((r) => [r.video_id, r]))))
      .catch(() => setReactions(new Map()));
    chargerTout<These>("videos_theses", "video_id,these,explicite")
      .then((l) => setTheses(new Map(l.map((t) => [t.video_id, t]))))
      .catch(() => setTheses(new Map()));
    // Résumés IA (migration 15) : facultatifs.
    chargerTout<ResumeIA>("resumes_ia", "*")
      .then(setResumes)
      .catch(() => setResumes([]));
  }, []);

  const dernier = useMemo(
    () => (sujets ? dernierJour(sujets) : null),
    [sujets],
  );
  const periode: Periode | null = useMemo(() => {
    if (!dernier) return null;
    if (debut) return { debut, fin: decaler(debut, 6) };
    // Par défaut : la semaine en cours si elle a au moins 3 jours, sinon la précédente.
    const enCours = semaineDe(dernier);
    return dernier >= decaler(enCours.debut, 2)
      ? enCours
      : semaineDe(decaler(enCours.debut, -1));
  }, [dernier, debut]);
  // Calculs en arrière-plan : le filtre et les flèches répondent tout de suite, le contenu
  // suit dès qu'il est prêt (estompé entre-temps).
  const periodeD = useDeferredValue(periode);
  const typesD = useDeferredValue(types);
  const enCalcul = periodeD !== periode || typesD !== types;
  const cartes = useMemo(
    () =>
      sujets && periodeD
        ? cartesSujets(sujets, periodeD, typesD, rattachements, reactions, theses)
        : [],
    [sujets, periodeD, typesD, rattachements, reactions, theses],
  );
  const avant = useMemo(
    () =>
      sujets && periodeD
        ? cartesSujets(
            sujets,
            {
              debut: decaler(periodeD.debut, -7),
              fin: decaler(periodeD.fin, -7),
            },
            typesD,
            rattachements,
            reactions,
            theses,
          )
        : [],
    [sujets, periodeD, typesD, rattachements, reactions, theses],
  );
  const reprises = useMemo(() => {
    const m = new Map<string, Reprise>();
    if (sujets && periodeD)
      for (const c of cartes)
        m.set(c.id, reprisePolitique(sujets, rattachements, c.id, periodeD.fin));
    return m;
  }, [sujets, periodeD, cartes, rattachements]);
  const decalage = useMemo(() => decalages(cartes), [cartes]);
  const faits = useMemo(
    () => faitsMarquants(cartes, reprises),
    [cartes, reprises],
  );
  const ouvrir = (c: CarteSujet) =>
    setPile([
      {
        type: "sujet",
        c,
        evolution: true,
        resume: periodeD
          ? dernierResume(resumes, "sujet", c.id, periodeD.debut)
          : null,
      },
    ]);
  const incomplete = periode && dernier ? periode.fin > dernier : false;
  const visibles = tous ? cartes : cartes.slice(0, 5);

  return (
    <div className="radar cs">
      <Entete actif="semaine" />

      {erreur && <p className="erreur radar-marge">{erreur}</p>}
      {!sujets && !erreur && <Squelette />}

      {periode && (
        <main className="cs-page">
          <section className="cs-tete">
            <div>
              <p className="cs-surtitre">
                <button
                  className="cs-fleche"
                  onClick={() => setDebut(decaler(periode.debut, -7))}
                  disabled={periode.debut <= DEBUT_COLLECTE}
                  aria-label="Semaine précédente"
                >
                  ‹
                </button>
                Semaine du {dateCourte(periode.debut)} au{" "}
                {dateCourte(periode.fin)}
                {incomplete ? " · en cours" : ""}
                <button
                  className="cs-fleche"
                  onClick={() => setDebut(decaler(periode.debut, 7))}
                  disabled={!dernier || periode.fin >= dernier}
                  aria-label="Semaine suivante"
                >
                  ›
                </button>
              </p>
              <h1>Ce qui a fait réagir cette semaine</h1>
              <p className="cs-chapo">{chapo(cartes, decalage)}</p>
              <p className="cs-note">
                Résumé automatique à partir des chiffres de la semaine · pas
                encore relu par la rédaction
              </p>
            </div>
            <fieldset className="cs-filtre">
              <legend>Réactions sous</legend>
              <div className="cs-segments">
                {(
                  [
                    ["Toutes", PUBLICS],
                    [COURT.media_traditionnel, ["media_traditionnel"]],
                    [COURT.media_natif, ["media_natif"]],
                  ] as [string, TypeSource[]][]
                ).map(([nom, ts]) => {
                  const actif = ts.join() === types.join();
                  return (
                    <button
                      key={nom}
                      className={actif ? "actif" : ""}
                      aria-pressed={actif}
                      onClick={() => setTypes(ts)}
                    >
                      {nom}
                    </button>
                  );
                })}
              </div>
            </fieldset>
          </section>

          <div
            key={`${periodeD?.debut}|${typesD.join()}`}
            className={enCalcul ? "radar-contenu en-calcul" : "radar-contenu"}
            aria-busy={enCalcul}
          >
          {faits.length > 0 && (
            <section className="cs-faits" aria-labelledby="cs-titre-faits">
              <h2 id="cs-titre-faits" className="cs-cache">
                Faits marquants
              </h2>
              {faits.map((f) => (
                <button
                  key={f.cle}
                  className="cs-fait"
                  onClick={() => ouvrir(f.sujet)}
                >
                  <span className="cs-fait-etiquette">{f.etiquette}</span>
                  <span className="cs-fait-valeur">{f.valeur}</span>
                  <span className="cs-fait-texte">{f.texte}</span>
                  <span className="cs-fait-sujet">{f.sujet.titre}</span>
                </button>
              ))}
            </section>
          )}

          <div className="cs-grille">
            <section aria-labelledby="cs-titre-sujets">
              <div className="cs-titre-liste">
                <h2 id="cs-titre-sujets">
                  Les {Math.min(5, cartes.length) || ""} sujets de la semaine
                </h2>
                <span className="discret petit-texte">
                  classés par commentaires
                </span>
              </div>
              {cartes.length === 0 ? (
                <p className="discret">
                  Aucun sujet d'actualité cette semaine (au moins 3 vidéos de 2
                  chaînes).
                </p>
              ) : (
                <ol className="cs-cartes">
                  {visibles.map((c, i) => (
                    <li key={c.id}>
                      <Carte
                        c={c}
                        rang={i + 1}
                        resume={
                          i === 0
                            ? dernierResume(
                                resumes,
                                "sujet",
                                c.id,
                                periodeD?.debut,
                              )
                            : null
                        }
                        reprise={reprises.get(c.id)}
                        ouvrir={() => ouvrir(c)}
                      />
                    </li>
                  ))}
                </ol>
              )}
              {cartes.length > 5 && (
                <button className="cs-lien-bas" onClick={() => setTous(!tous)}>
                  {tous
                    ? "Ne garder que les 5 premiers"
                    : `Voir tous les sujets de la semaine (${cartes.length}) →`}
                </button>
              )}
              <p className="cs-lien-bas">
                <Link href="/radar">La carte des thèmes et les filtres →</Link>
              </p>
            </section>
            <aside className="cs-colonne">
              <Decalage d={decalage} ouvrir={ouvrir} />
              <MediasOuNatifs cartes={cartes.slice(0, 6)} ouvrir={ouvrir} />
              <CeQuiAChange cartes={cartes} avant={avant} ouvrir={ouvrir} />
            </aside>
          </div>
          </div>
        </main>
      )}
      <Explorateur pile={pile} setPile={setPile} />
    </div>
  );
}

// --- Décalage couverture / réactions ---

type LigneDecalage = { c: CarteSujet; videos: number; ratio: number };
type Decalages = { couverts: LigneDecalage[]; commentes: LigneDecalage[] };

function decalages(cartes: CarteSujet[]): Decalages {
  // Seulement des sujets dont les réactions sont mesurées : au moins la moitié des vidéos
  // ont des commentaires classés (sinon « peu de réactions » voudrait dire « pas encore classé »).
  const mesures = cartes.filter(
    (c) =>
      c.classes > 0 &&
      c.videos.filter((v) => v.reaction).length >= c.videos.length / 2,
  );
  const videos = mesures.reduce((a, c) => a + c.videos.length, 0);
  const comm = mesures.reduce((a, c) => a + c.classes, 0);
  if (!videos || !comm) return { couverts: [], commentes: [] };
  const tailles = mesures.map((c) => c.videos.length).sort((a, b) => a - b);
  const quantile = (q: number) =>
    tailles[Math.min(tailles.length - 1, Math.floor(q * tailles.length))] ?? 0;
  const lignes = mesures.map((c) => ({
    c,
    videos: c.videos.length,
    ratio: c.classes / comm / (c.videos.length / videos),
  }));
  return {
    // « Très couvert » : parmi le quart des sujets les plus couverts.
    couverts: lignes
      .filter((x) => x.ratio < 0.8 && x.videos >= Math.max(5, quantile(0.75)))
      .sort((a, b) => a.ratio - b.ratio)
      .slice(0, 2),
    // « Peu couvert » : au plus la couverture médiane.
    commentes: lignes
      .filter((x) => x.ratio > 1.25 && x.videos <= quantile(0.5))
      .sort((a, b) => b.ratio - a.ratio)
      .slice(0, 2),
  };
}

function chapo(cartes: CarteSujet[], d: Decalages): string {
  const top = cartes[0];
  if (!top) return "Pas encore de sujet d'actualité pour cette semaine.";
  const phrases = [
    `La semaine est dominée par « ${top.titre} » : ${entier(top.classes)} commentaires sous ${top.videos.length} vidéos de ${top.chaines} chaînes.`,
  ];
  const surprise = d.commentes.find((x) => x.c.id !== top.id);
  if (surprise)
    phrases.push(
      `À l'inverse, « ${surprise.c.titre} », peu couvert (${surprise.videos} vidéos), fait ${fois(surprise.ratio).replace("×", "")} fois plus réagir que sa part de couverture.`,
    );
  const nouveaux = cartes.slice(0, 5).filter((c) => c.nouveau).length;
  if (nouveaux > 1)
    phrases.push(
      `${nouveaux} des 5 premiers sujets sont apparus cette semaine.`,
    );
  return phrases.join(" ");
}

// --- Carte d'un sujet ---

function Courbe({ jours }: { jours: number[] }) {
  const max = Math.max(1, ...jours);
  const pts = jours
    .map(
      (n, i) =>
        `${(i * 94) / Math.max(1, jours.length - 1) + 3},${30 - (26 * n) / max}`,
    )
    .join(" ");
  return (
    <svg
      viewBox="0 0 100 32"
      className="cs-courbe"
      role="img"
      aria-label={`Commentaires par jour de publication des vidéos : ${jours.map((n) => Math.round(n)).join(", ")}`}
    >
      <polyline points={pts} />
    </svg>
  );
}

function badge(c: CarteSujet): { texte: string; classe: string } {
  if (c.nouveau || c.precedent === 0)
    return { texte: "Nouveau", classe: "cs-pastille nouveau" };
  const r = c.classes / c.precedent;
  return {
    texte: fois(r),
    classe: r >= 1 ? "cs-pastille hausse" : "cs-pastille",
  };
}

function Carte({
  c,
  rang,
  reprise,
  resume,
  ouvrir,
}: {
  c: CarteSujet;
  rang: number;
  reprise: Reprise | undefined;
  resume: ResumeIA | null;
  ouvrir: () => void;
}) {
  const total = PUBLICS.reduce((a, t) => a + (c.parType[t] ?? 0), 0);
  const prononces = c.accord + c.nuance + c.desaccord;
  const b = badge(c);
  const theme = c.themes[0];
  return (
    <article className={rang === 1 ? "cs-carte premiere" : "cs-carte"}>
      <span className="cs-rang">{String(rang).padStart(2, "0")}</span>
      <div className="cs-carte-corps">
        <div className="cs-carte-tete">
          <div>
            <h3>
              <button className="cs-carte-lien" onClick={ouvrir}>
                {c.titre}
              </button>
            </h3>
            <p className="cs-meta">
              {theme ? LIBELLES_THEMES[theme.theme] : ""} · depuis le{" "}
              {jj(c.premierJour)} · {c.videos.length} vidéos sur {c.chaines}{" "}
              chaînes
            </p>
          </div>
          <Courbe jours={c.parJour} />
          <span
            className={b.classe}
            title="Commentaires face à la semaine précédente"
          >
            {b.texte}
          </span>
        </div>
        <div className="cs-indicateurs">
          <div>
            <p className="cs-etiquette">Où ça réagit</p>
            {total > 0 ? (
              <>
                <div
                  className="cs-barre"
                  role="img"
                  aria-label={`${COURT.media_traditionnel} ${Math.round(pct(c.parType.media_traditionnel ?? 0, total))} %, ${COURT.media_natif} ${Math.round(pct(c.parType.media_natif ?? 0, total))} %`}
                >
                  <span
                    className="bleu"
                    style={{
                      width: `${pct(c.parType.media_traditionnel ?? 0, total)}%`,
                    }}
                  />
                  <span
                    className="orange"
                    style={{
                      width: `${pct(c.parType.media_natif ?? 0, total)}%`,
                    }}
                  />
                </div>
                <p className="cs-petit">
                  Trad.{" "}
                  {Math.round(pct(c.parType.media_traditionnel ?? 0, total))} %
                  · Natifs {Math.round(pct(c.parType.media_natif ?? 0, total))}{" "}
                  %
                </p>
              </>
            ) : (
              <p className="cs-petit">pas encore de commentaires classés</p>
            )}
          </div>
          <div>
            <p className="cs-etiquette">Désaccord avec les vidéos</p>
            {prononces >= MIN_PRONONCES_SUJET ? (
              <>
                <div className="cs-barre">
                  <span
                    className="noir"
                    style={{ width: `${pct(c.desaccord, prononces)}%` }}
                  />
                </div>
                <p className="cs-petit">
                  {pc(pct(c.desaccord, prononces))} de ceux qui se prononcent
                </p>
              </>
            ) : (
              <p className="cs-petit">trop peu de vidéos d'opinion</p>
            )}
          </div>
          <div>
            <p className="cs-etiquette">Hostilité</p>
            <p className="cs-valeur">
              {c.classes ? pc(pct(c.hostiles, c.classes)) : "–"}
            </p>
            <p className="cs-petit">des commentaires</p>
          </div>
          <div>
            <p className="cs-etiquette">Repris par les politiques</p>
            <Reprises r={reprise} />
          </div>
        </div>
        {resume && <PourquoiCaBouge r={resume} />}
      </div>
    </article>
  );
}

function Reprises({ r }: { r: Reprise | undefined }) {
  if (!r || r.partis + r.personnalites === 0)
    return (
      <>
        <p className="cs-valeur">Aucune chaîne</p>
        <p className="cs-petit">politique du panel</p>
      </>
    );
  const morceaux = [
    r.partis ? `${r.partis} parti${r.partis > 1 ? "s" : ""}` : "",
    r.personnalites
      ? `${r.personnalites} personnalité${r.personnalites > 1 ? "s" : ""}`
      : "",
  ].filter(Boolean);
  let quand = "";
  let avant = false;
  if (r.premierPolitique && r.premierMedia) {
    const e = ecartJours(r.premierPolitique, r.premierMedia);
    avant = e < 0;
    quand =
      e === 0
        ? "le jour même que les médias"
        : e > 0
          ? `${e} jour${e > 1 ? "s" : ""} après les médias`
          : "avant les médias : lancé par une chaîne politique";
  }
  return (
    <>
      <p className="cs-valeur">{morceaux.join(" · ")}</p>
      {r.premierPolitique && (
        <p className={avant ? "cs-petit cs-alerte" : "cs-petit"}>
          1er le {jj(r.premierPolitique)}
          {quand ? `, ${quand}` : ""}
        </p>
      )}
    </>
  );
}

// --- Colonne ---

function Decalage({
  d,
  ouvrir,
}: {
  d: Decalages;
  ouvrir: (c: CarteSujet) => void;
}) {
  const toutes = [...d.couverts, ...d.commentes];
  if (toutes.length === 0) return null;
  const maxV = Math.max(1, ...toutes.map((x) => x.videos));
  const maxR = Math.max(1, ...toutes.map((x) => x.ratio));
  const bloc = (titre: string, lignes: LigneDecalage[]) =>
    lignes.length > 0 && (
      <>
        <p className="cs-sous-titre">{titre}</p>
        {lignes.map((x) => (
          <div key={x.c.id} className="cs-decalage">
            <button className="cs-nom" onClick={() => ouvrir(x.c)}>
              {x.c.titre}
            </button>
            <span className="cs-petit">Couverture</span>
            <span className="cs-piste">
              <span
                className="gris"
                style={{ width: `${(100 * x.videos) / maxV}%` }}
              />
            </span>
            <span className="cs-chiffre">{x.videos} vidéos</span>
            <span className="cs-petit">Réactions</span>
            <span className="cs-piste">
              <span
                className="orange"
                style={{ width: `${(100 * x.ratio) / maxR}%` }}
              />
            </span>
            <span className="cs-chiffre">{fois(x.ratio)}</span>
          </div>
        ))}
      </>
    );
  return (
    <section className="cs-encart" aria-labelledby="cs-titre-decalage">
      <h2 id="cs-titre-decalage">Le décalage de la semaine</h2>
      <p className="cs-petit">
        Couverture par les chaînes du panel face aux réactions suscitées (part
        des commentaires ÷ part des vidéos)
      </p>
      {bloc("Très couvert, peu de réactions", d.couverts)}
      {bloc("Peu couvert, beaucoup de réactions", d.commentes)}
    </section>
  );
}

function partDesaccord(p: PositionsType | undefined): number | null {
  if (!p) return null;
  const n = p.accord + p.nuance + p.desaccord;
  return n >= MIN_PRONONCES_SUJET ? pct(p.desaccord, n) : null;
}

function MediasOuNatifs({
  cartes,
  ouvrir,
}: {
  cartes: CarteSujet[];
  ouvrir: (c: CarteSujet) => void;
}) {
  const lignes = cartes
    .map((c) => ({
      c,
      trad: partDesaccord(c.positionsParType.media_traditionnel),
      natif: partDesaccord(c.positionsParType.media_natif),
    }))
    .filter((x) => x.trad !== null || x.natif !== null);
  if (lignes.length === 0) return null;
  return (
    <section className="cs-encart" aria-labelledby="cs-titre-medias">
      <h2 id="cs-titre-medias">Médias traditionnels ou natifs du web ?</h2>
      <p className="cs-petit">
        Part de désaccord avec les vidéos, selon qui en parle
      </p>
      <ul className="cs-haltere">
        {lignes.map(({ c, trad, natif }) => (
          <li key={c.id}>
            <button className="cs-nom" onClick={() => ouvrir(c)}>
              {c.titre}
            </button>
            <span
              className="cs-axe"
              role="img"
              aria-label={`Désaccord : médias traditionnels ${trad === null ? "n.d." : `${Math.round(trad)} %`}, natifs du web ${natif === null ? "n.d." : `${Math.round(natif)} %`}`}
            >
              {trad !== null && natif !== null && (
                <span
                  className="cs-lien-haltere"
                  style={{
                    left: `${Math.min(trad, natif)}%`,
                    width: `${Math.abs(natif - trad)}%`,
                  }}
                />
              )}
              {trad !== null && (
                <span className="cs-point bleu" style={{ left: `${trad}%` }} />
              )}
              {natif !== null && (
                <span
                  className="cs-point orange"
                  style={{ left: `${natif}%` }}
                />
              )}
            </span>
            <span className="cs-chiffre">
              {trad !== null && natif !== null
                ? `${natif - trad >= 0 ? "+" : "−"}${Math.abs(Math.round(natif - trad))}`
                : "–"}
            </span>
          </li>
        ))}
      </ul>
      <Legende
        items={[
          ["Médias traditionnels", "var(--r-bleu)"],
          ["Natifs du web", "var(--r-orange)"],
        ]}
      />
      <p className="cs-petit">
        Écart en points ; vidéos d'opinion avec au moins 20 commentaires qui se
        prononcent.
      </p>
    </section>
  );
}

function CeQuiAChange({
  cartes,
  avant,
  ouvrir,
}: {
  cartes: CarteSujet[];
  avant: CarteSujet[];
  ouvrir: (c: CarteSujet) => void;
}) {
  const rangs = new Map(avant.map((c, i) => [c.id, i + 1]));
  const items: {
    etiquette: string;
    classe: string;
    texte: string;
    c?: CarteSujet; // sujet de cette semaine, s'il y est encore
  }[] = [];
  cartes.slice(0, 5).forEach((c, i) => {
    if (!rangs.has(c.id))
      items.push({
        etiquette: "Nouveau",
        classe: "nouveau",
        c,
        texte: `« ${c.titre} » entre directement en ${i + 1}${i === 0 ? "re" : "e"} position.`,
      });
  });
  const hausse = cartes
    .filter((c) => c.precedent > 0 && rangs.has(c.id))
    .sort((a, b) => b.classes / b.precedent - a.classes / a.precedent)[0];
  if (hausse && hausse.classes > hausse.precedent * 1.2)
    items.push({
      etiquette: "En hausse",
      classe: "hausse",
      c: hausse,
      texte: `« ${hausse.titre} » : ${fois(hausse.classes / hausse.precedent)} de commentaires sur la semaine précédente.`,
    });
  const ici = new Set(cartes.slice(0, 10).map((c) => c.id));
  for (const c of avant.slice(0, 3))
    if (!ici.has(c.id))
      items.push({
        etiquette: "En baisse",
        classe: "baisse",
        c: cartes.find((x) => x.id === c.id),
        texte: `« ${c.titre} », ${rangs.get(c.id) === 1 ? "1er" : `${rangs.get(c.id)}e`} la semaine précédente, sort du classement.`,
      });
  return (
    <section className="cs-encart" aria-labelledby="cs-titre-change">
      <h2 id="cs-titre-change">Ce qui a changé</h2>
      {items.length === 0 ? (
        <p className="cs-petit">
          Rien de notable face à la semaine précédente.
        </p>
      ) : (
        <ul className="cs-changements">
          {items.slice(0, 6).map((x, i) => (
            <li key={i}>
              {x.c ? (
                <button
                  className="cs-changement"
                  onClick={() => x.c && ouvrir(x.c)}
                >
                  <span className={`cs-etiq ${x.classe}`}>{x.etiquette}</span>
                  <span>{x.texte}</span>
                </button>
              ) : (
                <span className="cs-changement">
                  <span className={`cs-etiq ${x.classe}`}>{x.etiquette}</span>
                  <span>{x.texte}</span>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
