"use client";

// « Cette semaine » : l'accueil éditorial, d'après la maquette « Radar 2027 ». Les sujets
// d'actualité de la semaine, ce qui les distingue (où ça réagit, désaccord, hostilité,
// reprise par les chaînes politiques), le décalage couverture / réactions, et ce qui a changé.
import { useDeferredValue, useEffect, useMemo, useState } from "react";

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
import { Barre, Legende, Squelette, dateCourte, entier } from "@/lib/ui";
import { pct } from "@/lib/vueEnsemble";

const PUBLICS: TypeSource[] = ["media_traditionnel", "media_natif"];
const MIN_PRONONCES_SUJET = 20;
const DEBUT_COLLECTE = "2026-09-01";
const fois = (x: number) => `×${x.toFixed(1).replace(".", ",")}`;

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
  const visibles = tous ? cartes : cartes.slice(0, 10);

  const resumeTop =
    cartes[0] && periodeD
      ? dernierResume(resumes, "sujet", cartes[0].id, periodeD.debut)
      : null;
  const typesCle = types.join();

  const outils = periode && (
    <>
      <div className="r-semaine">
        <button
          className="r-icone"
          onClick={() => setDebut(decaler(periode.debut, -7))}
          disabled={periode.debut <= DEBUT_COLLECTE}
          aria-label="Semaine précédente"
        >
          ‹
        </button>
        <span className="r-semaine-nom">
          {dateCourte(periode.debut)} – {dateCourte(periode.fin)}
          {incomplete ? <span className="r-discret"> · en cours</span> : ""}
        </span>
        <button
          className="r-icone"
          onClick={() => setDebut(decaler(periode.debut, 7))}
          disabled={!dernier || periode.fin >= dernier}
          aria-label="Semaine suivante"
        >
          ›
        </button>
      </div>
      <label className="r-choix">
        <span>Réactions sous</span>
        <select
          value={typesCle}
          onChange={(e) =>
            setTypes(e.target.value.split(",") as TypeSource[])
          }
        >
          <option value={PUBLICS.join()}>Tous les médias</option>
          <option value="media_traditionnel">Médias traditionnels</option>
          <option value="media_natif">Natifs du web</option>
        </select>
      </label>
    </>
  );

  return (
    <div className="radar">
      <Entete actif="semaine" outils={outils} />

      {erreur && <p className="erreur r-page">{erreur}</p>}
      {!sujets && !erreur && <Squelette />}

      {periode && (
        <main className="r-page">
          <section className="r-hero">
            <h1>Ce qui a fait réagir cette semaine</h1>
            <p className="r-chapo">{chapo(cartes, decalage)}</p>
            <p className="r-note">
              Résumé automatique à partir des chiffres de la semaine · pas encore
              relu
            </p>
          </section>

          <div
            key={`${periodeD?.debut}|${typesD.join()}`}
            className={enCalcul ? "r-contenu en-calcul" : "r-contenu"}
            aria-busy={enCalcul}
          >
            {faits.length > 0 && (
              <section className="r-faits" aria-label="Faits marquants">
                {faits.slice(0, 4).map((f) => (
                  <button
                    key={f.cle}
                    className="r-fait"
                    onClick={() => ouvrir(f.sujet)}
                  >
                    <span className="r-fait-etiquette">{f.etiquette}</span>
                    <span
                      className={
                        f.cle === "conteste" || f.cle === "hostile"
                          ? "r-fait-valeur orange"
                          : "r-fait-valeur"
                      }
                    >
                      {f.valeur}
                    </span>
                    <span className="r-fait-texte">{f.texte}</span>
                    <span className="r-fait-sujet">{f.sujet.titre} ›</span>
                  </button>
                ))}
              </section>
            )}

            <div className="r-grille">
              <section className="r-carte r-sujets" aria-labelledby="t-sujets">
                <div className="r-carte-tete">
                  <h2 id="t-sujets">Les sujets qui font réagir</h2>
                  <span className="r-discret">
                    classés par commentaires · cliquer pour le détail
                  </span>
                </div>
                {cartes.length === 0 ? (
                  <p className="r-vide">
                    Aucun sujet d'actualité cette semaine (au moins 3 vidéos de 2
                    chaînes).
                  </p>
                ) : (
                  <>
                    <div className="r-sujets-entete" aria-hidden="true">
                      <span>#</span>
                      <span>Sujet</span>
                      <span>Par jour</span>
                      <span className="r-droite">Comm.</span>
                      <span>Accord · désaccord avec les vidéos</span>
                    </div>
                    <ol className="r-sujets-liste">
                      {visibles.map((c, i) => (
                        <li key={c.id}>
                          <LigneSujet
                            c={c}
                            rang={i + 1}
                            reprise={reprises.get(c.id)}
                            ouvrir={() => ouvrir(c)}
                          />
                        </li>
                      ))}
                    </ol>
                    <Legende
                      items={[
                        ["D'accord avec la vidéo", "var(--r-bleu)"],
                        ["Nuancé", "var(--r-nuance)"],
                        ["En désaccord", "var(--r-orange)"],
                      ]}
                    />
                  </>
                )}
                {cartes.length > 10 && (
                  <button className="r-plus" onClick={() => setTous(!tous)}>
                    {tous
                      ? "Ne garder que les 10 premiers"
                      : `Voir tous les sujets de la semaine (${cartes.length})`}
                  </button>
                )}
              </section>
              <aside className="r-colonne">
                <Decalage d={decalage} ouvrir={ouvrir} />
                <CeQuiAChange cartes={cartes} avant={avant} ouvrir={ouvrir} />
                {resumeTop && cartes[0] && (
                  <section className="r-carte r-sombre" aria-labelledby="t-pourquoi">
                    <h2 id="t-pourquoi">Pourquoi ça bouge</h2>
                    <p className="r-discret">{cartes[0].titre}</p>
                    <PourquoiCaBouge r={resumeTop} />
                  </section>
                )}
                <MediasOuNatifs cartes={cartes.slice(0, 6)} ouvrir={ouvrir} />
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

// --- Ligne d'un sujet ---

function Courbe({ jours }: { jours: number[] }) {
  const max = Math.max(1, ...jours);
  const pts = jours
    .map(
      (n, i) =>
        `${(i * 104) / Math.max(1, jours.length - 1) + 3},${29 - (25 * n) / max}`,
    )
    .join(" ");
  return (
    <svg
      viewBox="0 0 110 32"
      className="r-courbe"
      role="img"
      aria-label={`Commentaires par jour de publication des vidéos : ${jours.map((n) => Math.round(n)).join(", ")}`}
    >
      <polyline points={pts} />
    </svg>
  );
}

function evolutionSujet(c: CarteSujet): { texte: string; classe: string } {
  if (c.nouveau || c.precedent === 0)
    return { texte: "Nouveau", classe: "r-puce bleu" };
  const r = c.classes / c.precedent;
  return { texte: fois(r), classe: r >= 1 ? "r-puce orange" : "r-puce" };
}

function lecturePositions(p: number, c: CarteSujet): string {
  if (p < MIN_PRONONCES_SUJET) return "trop peu de vidéos d'opinion";
  const a = pct(c.accord, p);
  const d = pct(c.desaccord, p);
  if (d >= 50) return `${Math.round(d)} % en désaccord`;
  if (a >= 50) return `${Math.round(a)} % d'accord`;
  return `partagé · ${Math.round(d)} % en désaccord`;
}

function LigneSujet({
  c,
  rang,
  reprise,
  ouvrir,
}: {
  c: CarteSujet;
  rang: number;
  reprise: Reprise | undefined;
  ouvrir: () => void;
}) {
  const p = c.accord + c.nuance + c.desaccord;
  const e = evolutionSujet(c);
  const theme = c.themes[0];
  const politiques = reprise ? reprise.partis + reprise.personnalites : 0;
  return (
    <button className="r-sujet" onClick={ouvrir} data-ouvre-sujet>
      <span className="r-rang">{rang}</span>
      <span className="r-sujet-corps">
        <span className="r-sujet-titre">{c.titre}</span>
        <span className="r-sujet-meta">
          {theme && (
            <span className="r-puce">{LIBELLES_THEMES[theme.theme]}</span>
          )}
          <span className={e.classe} title="Commentaires face à la semaine précédente">
            {e.texte}
          </span>
          <span>
            {c.videos.length} vidéos · {c.chaines} chaînes
            {politiques > 0 && ` · repris par ${politiques} chaîne${politiques > 1 ? "s" : ""} politique${politiques > 1 ? "s" : ""}`}
          </span>
        </span>
      </span>
      <Courbe jours={c.parJour} />
      <span className="r-sujet-chiffre">{entier(c.classes)}</span>
      <span className="r-sujet-positions">
        {p >= MIN_PRONONCES_SUJET ? (
          <Barre
            titre="Accord avec les vidéos d'opinion"
            total={p}
            segments={[
              { libelle: "Accord", valeur: c.accord, couleur: "var(--r-bleu)" },
              { libelle: "Nuance", valeur: c.nuance, couleur: "var(--r-nuance)" },
              { libelle: "Désaccord", valeur: c.desaccord, couleur: "var(--r-orange)" },
            ]}
          />
        ) : (
          <span className="radar-barre vide" aria-hidden="true" />
        )}
        <span className="r-discret">{lecturePositions(p, c)}</span>
      </span>
      <span className="r-chevron" aria-hidden="true">
        ›
      </span>
    </button>
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
  const toutes = [...d.commentes, ...d.couverts];
  if (toutes.length === 0) return null;
  const maxV = Math.max(1, ...toutes.map((x) => x.videos));
  const maxR = Math.max(1, ...toutes.map((x) => x.ratio));
  return (
    <section className="r-carte" aria-labelledby="t-decalage">
      <h2 id="t-decalage">Médias et commentaires ne suivent pas le même agenda</h2>
      <p className="r-discret">
        Couverture (vidéos du panel) face aux réactions (part des commentaires ÷
        part des vidéos)
      </p>
      <ul className="r-decalages">
        {toutes.map((x) => (
          <li key={x.c.id}>
            <button className="r-decalage" onClick={() => ouvrir(x.c)}>
              <span className="r-decalage-tete">
                <span className="r-decalage-nom">{x.c.titre}</span>
                <span className={x.ratio >= 1 ? "r-chiffre bleu" : "r-chiffre orange"}>
                  {fois(x.ratio)}
                </span>
              </span>
              <span className="r-piste-ligne">
                <span>Couverture</span>
                <span className="r-piste">
                  <span className="gris" style={{ width: `${(100 * x.videos) / maxV}%` }} />
                </span>
                <span className="r-mono">{x.videos} vid.</span>
              </span>
              <span className="r-piste-ligne">
                <span>Réactions</span>
                <span className="r-piste">
                  <span className="noir" style={{ width: `${(100 * x.ratio) / maxR}%` }} />
                </span>
                <span className="r-mono">{fois(x.ratio)}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
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
    .filter((x) => x.trad !== null && x.natif !== null);
  if (lignes.length === 0) return null;
  return (
    <section className="r-carte" aria-labelledby="t-medias">
      <h2 id="t-medias">Médias traditionnels ou natifs du web ?</h2>
      <p className="r-discret">Désaccord avec les vidéos, selon qui en parle</p>
      <ul className="r-halteres">
        {lignes.map(({ c, trad, natif }) => (
          <li key={c.id}>
            <button className="r-haltere" onClick={() => ouvrir(c)}>
              <span className="r-haltere-nom">{c.titre}</span>
              <span
                className="r-axe"
                role="img"
                aria-label={`Désaccord : médias traditionnels ${Math.round(trad!)} %, natifs du web ${Math.round(natif!)} %`}
              >
                <span
                  className="r-axe-lien"
                  style={{
                    left: `${Math.min(trad!, natif!)}%`,
                    width: `${Math.abs(natif! - trad!)}%`,
                  }}
                />
                <span className="r-point bleu" style={{ left: `${trad}%` }} />
                <span className="r-point orange" style={{ left: `${natif}%` }} />
              </span>
            </button>
          </li>
        ))}
      </ul>
      <Legende
        items={[
          ["Médias traditionnels", "var(--r-bleu)"],
          ["Natifs du web", "var(--r-orange)"],
        ]}
      />
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
        classe: "bleu",
        c,
        texte: `« ${c.titre} » entre en ${i + 1}${i === 0 ? "re" : "e"} position.`,
      });
  });
  const hausse = cartes
    .filter((c) => c.precedent > 0 && rangs.has(c.id))
    .sort((a, b) => b.classes / b.precedent - a.classes / a.precedent)[0];
  if (hausse && hausse.classes > hausse.precedent * 1.2)
    items.push({
      etiquette: "En hausse",
      classe: "orange",
      c: hausse,
      texte: `« ${hausse.titre} » : ${fois(hausse.classes / hausse.precedent)} de commentaires.`,
    });
  const ici = new Set(cartes.slice(0, 10).map((c) => c.id));
  for (const c of avant.slice(0, 3))
    if (!ici.has(c.id))
      items.push({
        etiquette: "En baisse",
        classe: "",
        c: cartes.find((x) => x.id === c.id),
        texte: `« ${c.titre} », ${rangs.get(c.id) === 1 ? "1er" : `${rangs.get(c.id)}e`} la semaine précédente, sort du classement.`,
      });
  return (
    <section className="r-carte" aria-labelledby="t-change">
      <h2 id="t-change">Ce qui a changé</h2>
      {items.length === 0 ? (
        <p className="r-discret">Rien de notable face à la semaine précédente.</p>
      ) : (
        <ul className="r-changements">
          {items.slice(0, 6).map((x, i) => {
            const contenu = (
              <>
                <span className={`r-puce ${x.classe}`}>{x.etiquette}</span>
                <span>{x.texte}</span>
              </>
            );
            return (
              <li key={i}>
                {x.c ? (
                  <button className="r-changement" onClick={() => x.c && ouvrir(x.c)}>
                    {contenu}
                  </button>
                ) : (
                  <span className="r-changement">{contenu}</span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
