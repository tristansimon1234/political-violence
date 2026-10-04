"use client";

import { useEffect, useMemo, useState } from "react";

import { AccesAdmin } from "@/lib/AccesAdmin";
import {
  type Agenda,
  type SujetVideo,
  MIN_PRONONCES,
  type Rattachement,
  type ReactionVideo,
  type SujetActu,
  type These,
  type VideoDebattue,
  agendaParTheme,
  jourParis,
  sousSujets,
  sujetsActu,
  sujetsFiltres,
  videosDebattues,
  videosQuiReagissent,
} from "@/lib/agenda";
import {
  MIN_COMMENTAIRES_SEMAINE,
  type Semaine,
  changements,
  nouveauxSousSujets,
  semaines,
} from "@/lib/semaines";
import { chargerSujets, chargerTout } from "@/lib/chargement";
import { type CarteSujet, cartesSujets } from "@/lib/cetteSemaine";
import { Entete } from "@/lib/Entete";
import { Explorateur, ListeVideos, type Niveau, versVideo } from "@/lib/Explorateur";
import {
  PourquoiCaBouge,
  type ResumeIA,
  dernierResume,
} from "@/lib/PourquoiCaBouge";
import {
  Barre,
  EnPreparation,
  Legende,
  dateCourte,
  entier,
  fois,
  pc,
} from "@/lib/ui";
import {
  DEFINITIONS_THEMES,
  LIBELLES_THEMES,
  LIBELLES_TYPE,
  THEMES,
  type Theme,
  type TypeSource,
} from "@/lib/taxonomie";
import {
  type Agregat,
  type Filtres,
  type LigneTheme,
  type Mesures,
  additionner,
  dans,
  depuisCollecte,
  fenetres,
  filtrer,
  pct,
  themes,
} from "@/lib/vueEnsemble";

const PUBLICS: TypeSource[] = ["media_traditionnel", "media_natif"];

export default function Radar() {
  return (
    <AccesAdmin titre="Radar 2027" retour="/radar">
      {() => <VueEnsemble />}
    </AccesAdmin>
  );
}

function chargerAgregats(): Promise<Agregat[]> {
  return chargerTout<Agregat>("agregats_themes", "*");
}

function VueEnsemble() {
  const [lignes, setLignes] = useState<Agregat[] | null>(null);
  const [erreur, setErreur] = useState("");
  const [filtres, setFiltres] = useState<Filtres>({
    periode: "tout",
    types: PUBLICS,
    format: "tous",
  });
  const [politiques, setPolitiques] = useState(false);
  const [choisi, setChoisi] = useState<Theme | null>(null);
  const [onglet, setOnglet] = useState<Onglet>("reactions");
  const [pile, setPile] = useState<Niveau[]>([]);
  const [sujets, setSujets] = useState<SujetVideo[]>([]);
  const [sansSujets, setSansSujets] = useState("");
  const [reactions, setReactions] = useState<Map<string, ReactionVideo>>(
    new Map(),
  );
  const [theses, setTheses] = useState<Map<string, These>>(new Map());
  const [rattachements, setRattachements] = useState<Map<string, Rattachement>>(
    new Map(),
  );
  // Filtre par chaîne : agrégats par chaîne chargés au premier choix (migration 14).
  const [resumes, setResumes] = useState<ResumeIA[]>([]);
  const [chaines, setChaines] = useState<string[]>([]);
  const [sources, setSources] = useState<SourceChaine[]>([]);
  const [parChaine, setParChaine] = useState<Agregat[] | null>(null);
  const [erreurChaines, setErreurChaines] = useState("");

  useEffect(() => {
    chargerAgregats()
      .then((l) => setLignes(depuisCollecte(l)))
      .catch((e: unknown) =>
        setErreur(e instanceof Error ? e.message : String(e)),
      );
    // Thèmes des vidéos : facultatifs (migration 10, remplis par la classification) ; sans
    // eux, les blocs d'agenda restent « en préparation ».
    chargerSujets()
      .then(setSujets)
      .catch((e: unknown) =>
        setSansSujets(e instanceof Error ? e.message : String(e)),
      );
    // Accord par vidéo et thèses (migration 11) : facultatifs également.
    chargerTout<ReactionVideo>("agregats_videos", "*")
      .then((l) => setReactions(new Map(l.map((r) => [r.video_id, r]))))
      .catch(() => setReactions(new Map()));
    chargerTout<These>("videos_theses", "video_id,these,explicite")
      .then((l) => setTheses(new Map(l.map((t) => [t.video_id, t]))))
      .catch(() => setTheses(new Map()));
    // Sujets d'actualité (migration 12) : facultatifs ; sans eux, les sous-sujets bruts.
    chargerTout<Rattachement>(
      "sujets_videos",
      "video_id,sujet_id,sujets(titre)",
    )
      .then((l) => setRattachements(new Map(l.map((r) => [r.video_id, r]))))
      .catch(() => setRattachements(new Map()));
    chargerTout<ResumeIA>("resumes_ia", "*")
      .then(setResumes)
      .catch(() => setResumes([]));
    // Chaînes du public seulement : les chaînes politiques restent lues à part.
    chargerTout<SourceChaine>("sources", "id,nom,type")
      .then((l) =>
        setSources(
          l
            .filter((x) => PUBLICS.includes(x.type))
            .sort((a, b) => a.nom.localeCompare(b.nom, "fr")),
        ),
      )
      .catch(() => setSources([]));
  }, []);

  useEffect(() => {
    if (chaines.length === 0 || parChaine !== null) return;
    chargerTout<Agregat>("agregats_chaines", "*")
      .then((l) => setParChaine(depuisCollecte(l)))
      .catch((e: unknown) => {
        setParChaine([]);
        setErreurChaines(e instanceof Error ? e.message : String(e));
      });
  }, [chaines, parChaine]);

  const donnees = useMemo(
    () =>
      chaines.length === 0
        ? lignes
        : parChaine === null
          ? null
          : parChaine.filter((l) => chaines.includes(l.source_id ?? "")),
    [lignes, chaines, parChaine],
  );
  const filtresEff = useMemo<Filtres>(
    () =>
      chaines.length === 0
        ? filtres
        : {
            ...filtres,
            types: PUBLICS.filter((t) =>
              sources.some((x) => chaines.includes(x.id) && x.type === t),
            ),
          },
    [filtres, chaines, sources],
  );
  const sujetsBase = useMemo(
    () =>
      chaines.length === 0
        ? sujets
        : sujets.filter((x) => chaines.includes(x.videos?.sources?.id ?? "")),
    [sujets, chaines],
  );

  // Table vide : aucun calcul (pas de dernier jour, donc pas de fenêtre).
  const vue = useMemo(
    () => (donnees && donnees.length > 0 ? themes(donnees, filtresEff) : null),
    [donnees, filtresEff],
  );
  const actif =
    vue?.lignes.find((l) => l.theme === choisi) ?? vue?.lignes[0] ?? null;
  const sujetsPeriode = useMemo(
    () => (vue ? sujetsFiltres(sujetsBase, filtresEff, vue.courante) : []),
    [sujetsBase, filtresEff, vue],
  );
  const agenda = useMemo(() => agendaParTheme(sujetsPeriode), [sujetsPeriode]);

  // Sujets d'actualité de la période (format choisi), au format du drill-down.
  const cartes = useMemo(() => {
    if (!vue) return new Map<string, CarteSujet>();
    const base = sujetsBase.filter(
      (x) => filtresEff.format === "tous" || x.videos?.format === filtresEff.format,
    );
    return new Map(
      cartesSujets(
        base,
        vue.courante,
        filtresEff.types,
        rattachements,
        reactions,
        theses,
      ).map((c) => [c.id, c]),
    );
  }, [vue, sujetsBase, filtresEff, rattachements, reactions, theses]);
  const ouvrirSujet = (id: string) => {
    const c = cartes.get(id);
    if (c)
      setPile([
        {
          type: "sujet",
          c,
          resume: vue ? dernierResume(resumes, "sujet", id, vue.courante.fin) : null,
        },
      ]);
  };
  const ouvrirVideo = (s: SujetVideo) =>
    setPile([
      {
        type: "video",
        v: versVideo(s, reactions, theses),
        sujet: rattachements.get(s.video_id)?.sujets?.titre,
      },
    ]);
  const choisirEtMontrer = (t: Theme) => {
    setChoisi(t);
    document
      .getElementById("ve-detail")
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="radar">
      <Entete actif="ensemble" />

      {erreur && <p className="erreur radar-marge">{erreur}</p>}
      {!lignes && !erreur && (
        <p className="discret radar-marge">Chargement des agrégats…</p>
      )}
      {lignes && lignes.length === 0 && (
        <p className="discret radar-marge">
          Aucun agrégat : lancer la classification puis le workflow « Agrégats
          ».
        </p>
      )}

      {lignes && lignes.length > 0 && (
        <BarreFiltres
          filtres={filtres}
          setFiltres={setFiltres}
          politiques={politiques}
          setPolitiques={setPolitiques}
          sources={sources}
          chaines={chaines}
          setChaines={setChaines}
        />
      )}
      {chaines.length > 0 && !vue && (
        <p className="discret radar-marge">
          {donnees === null
            ? "Chargement des agrégats par chaîne…"
            : erreurChaines
              ? `Agrégats par chaîne indisponibles (migration 14 et workflow « Agrégats ») : ${erreurChaines}`
              : parChaine && parChaine.length === 0
                ? "Les agrégats par chaîne ne sont pas encore calculés : lancer le workflow « Agrégats » (version avec le filtre par chaîne)."
                : "Aucun commentaire classé pour ces chaînes sur la période."}
        </p>
      )}

      {vue && donnees && actif && (
        <main className="ve-page">
          <p className="ve-resume-periode">
            Du {dateCourte(vue.courante.debut)} au{" "}
            {dateCourte(vue.courante.fin)} (jour de publication des
            commentaires) · <strong>{entier(vue.total.commentaires)}</strong>{" "}
            commentaires classés, dont{" "}
            {pc(pct(vue.nonPolitique.commentaires, vue.total.commentaires))} non
            politiques
          </p>
          <div className="ve-maitre">
            <ThemesEnMouvement
              lignes={vue.lignes}
              actif={actif.theme}
              choisir={setChoisi}
            />
            <ThemeSelectionne
              key={actif.theme}
              ligne={actif}
              lignes={donnees}
              filtres={filtresEff}
              politiques={politiques}
              sujets={sujetsPeriode}
              reactions={reactions}
              theses={theses}
              rattachements={rattachements}
              resumes={resumes}
              onglet={onglet}
              setOnglet={setOnglet}
              ouvrirSujet={ouvrirSujet}
              ouvrirVideo={ouvrirVideo}
            />
          </div>
          <Panorama
            lignes={vue.lignes}
            agenda={agenda}
            actif={actif.theme}
            choisir={choisirEtMontrer}
            donnees={donnees}
            filtres={filtresEff}
            sujetsBase={sujetsBase}
            horsGrille={sujetsActu(sujetsPeriode, "autre", rattachements, 5)}
            ouvrirSujet={ouvrirSujet}
            sansSujets={sansSujets}
          />
        </main>
      )}
      <Explorateur pile={pile} setPile={setPile} />
    </div>
  );
}

type SourceChaine = { id: string; nom: string; type: TypeSource };

function BarreFiltres({
  filtres,
  setFiltres,
  politiques,
  setPolitiques,
  sources,
  chaines,
  setChaines,
}: {
  filtres: Filtres;
  setFiltres: (f: Filtres) => void;
  politiques: boolean;
  setPolitiques: (b: boolean) => void;
  sources: SourceChaine[];
  chaines: string[];
  setChaines: (c: string[]) => void;
}) {
  const [recherche, setRecherche] = useState("");
  const basculerChaine = (id: string) =>
    setChaines(
      chaines.includes(id) ? chaines.filter((x) => x !== id) : [...chaines, id],
    );
  const visibles = sources.filter((x) =>
    x.nom.toLowerCase().includes(recherche.trim().toLowerCase()),
  );
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
            {p === "tout" ? "Depuis le 1er sept." : `${p} jours`}
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
            <i className={`ve-pastille ${t}`} aria-hidden="true" />
            {LIBELLES_TYPE[t]}{" "}
            <span className="ve-compte">
              {sources.filter((x) => x.type === t).length || ""}
            </span>
          </button>
        ))}
      </fieldset>
      <fieldset>
        <legend>Chaînes</legend>
        <details className="radar-choix-chaines">
          <summary className={chaines.length ? "segment actif" : "segment"}>
            {chaines.length === 0
              ? "Toutes les chaînes"
              : chaines.length === 1
                ? (sources.find((x) => x.id === chaines[0])?.nom ?? "1 chaîne")
                : `${chaines.length} chaînes`}
          </summary>
          <div className="radar-choix-chaines-liste">
            <input
              type="search"
              placeholder="Chercher une chaîne"
              value={recherche}
              onChange={(e) => setRecherche(e.target.value)}
              aria-label="Chercher une chaîne"
            />
            {chaines.length > 0 && (
              <button
                className="radar-lien petit-texte"
                onClick={() => setChaines([])}
              >
                Tout effacer (revenir au panel)
              </button>
            )}
            {PUBLICS.map((t) => (
              <div key={t}>
                <p className="discret petit-texte">{LIBELLES_TYPE[t]}</p>
                {visibles
                  .filter((x) => x.type === t)
                  .map((x) => (
                    <label key={x.id}>
                      <input
                        type="checkbox"
                        checked={chaines.includes(x.id)}
                        onChange={() => basculerChaine(x.id)}
                      />{" "}
                      {x.nom}
                    </label>
                  ))}
              </div>
            ))}
            <p className="discret petit-texte">
              Avec des chaînes choisies, le filtre « Réactions sous » est
              ignoré.
            </p>
          </div>
        </details>
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
        Chaînes politiques <span className="discret">(lues à part)</span>
      </label>
    </div>
  );
}

type Classement = "volume" | "desaccord" | "hostilite";
const CLASSEMENTS: [Classement, string][] = [
  ["volume", "Volume"],
  ["desaccord", "Désaccord"],
  ["hostilite", "Hostilité"],
];
const MIN_PRONONCES_THEME = 50;

/** Valeur du thème pour le classement choisi (null si l'échantillon est trop petit). */
function valeurTheme(l: LigneTheme, c: Classement): number | null {
  const m = l.courant;
  if (c === "volume") return l.velocite ?? l.part * 100;
  if (c === "hostilite")
    return m.commentaires >= MIN_PRONONCES_THEME
      ? pct(m.hostiles, m.commentaires)
      : null;
  const prononces = m.accord + m.nuance + m.desaccord;
  return prononces >= MIN_PRONONCES_THEME ? pct(m.desaccord, prononces) : null;
}

function ThemesEnMouvement({
  lignes,
  actif,
  choisir,
}: {
  lignes: LigneTheme[];
  actif: Theme;
  choisir: (t: Theme) => void;
}) {
  const [classement, setClassement] = useState<Classement>("volume");
  const parVelocite = lignes.some((l) => l.velocite !== null);
  const tries = [...lignes]
    .filter(
      (l) => classement === "volume" || valeurTheme(l, classement) !== null,
    )
    .sort(
      (a, b) =>
        (valeurTheme(b, classement) ?? -1) - (valeurTheme(a, classement) ?? -1),
    );
  const max = Math.max(1, ...tries.map((l) => valeurTheme(l, classement) ?? 0));
  const libelle = (l: LigneTheme) => {
    const v = valeurTheme(l, classement);
    if (v === null) return "–";
    if (classement === "volume")
      return l.velocite === null ? pc(v) : fois(l.velocite);
    return pc(v);
  };
  return (
    <section className="radar-carte" aria-labelledby="titre-themes">
      <h2 id="titre-themes">Thèmes en mouvement</h2>
      <div
        className="ve-classement"
        role="group"
        aria-label="Classer les thèmes par"
      >
        {CLASSEMENTS.map(([c, nom]) => (
          <button
            key={c}
            className={classement === c ? "actif" : ""}
            aria-pressed={classement === c}
            onClick={() => setClassement(c)}
          >
            {nom}
          </button>
        ))}
      </div>
      <p className="discret petit-texte">
        {classement === "volume"
          ? parVelocite
            ? "Classés par vélocité"
            : "Classés par part des commentaires politiques (vélocité après 5 semaines de données)"
          : classement === "desaccord"
            ? "Part de désaccord avec les vidéos d'opinion, parmi les commentaires qui se prononcent (au moins 50)"
            : "Part de commentaires hostiles"}
      </p>
      <ol className="radar-themes">
        {tries.map((l, i) => {
          const v = valeurTheme(l, classement) ?? 0;
          const fort =
            classement === "volume"
              ? l.velocite !== null && l.velocite >= 1.5
              : v >= 0.8 * max;
          return (
            <li key={l.theme}>
              <button
                className={
                  l.theme === actif ? "radar-theme actif" : "radar-theme"
                }
                onClick={() => choisir(l.theme)}
                aria-pressed={l.theme === actif}
                title={DEFINITIONS_THEMES[l.theme]}
              >
                <span className="radar-rang">{i + 1}</span>
                <span className="radar-nom">{LIBELLES_THEMES[l.theme]}</span>
                {classement === "volume" ? (
                  <Courbe serie={l.serie} />
                ) : (
                  <span className="ve-jauge" aria-hidden="true">
                    <span style={{ width: `${(100 * v) / max}%` }} />
                  </span>
                )}
                <span
                  className={fort ? "radar-pastille forte" : "radar-pastille"}
                >
                  {libelle(l)}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
      <div className="radar-definition">
        <strong>Vélocité</strong> · commentaires sur 7 jours ÷ moyenne des 4
        semaines précédentes. ×1,0 = activité habituelle. Provisoire : pas
        encore pondérée par l'audience des sources.
      </div>
    </section>
  );
}

function CarteSujets({
  lignes,
  agenda,
  actif,
  choisir,
}: {
  lignes: LigneTheme[];
  agenda: Map<Theme, Agenda>;
  actif: Theme;
  choisir: (t: Theme) => void;
}) {
  const points = lignes
    .map((l) => {
      const vues = agenda.get(l.theme)?.vues ?? 0;
      return {
        l,
        vues,
        intensite: vues > 0 ? (1000 * l.courant.commentaires) / vues : 0,
      };
    })
    .filter(
      (p) =>
        p.vues > 0 && p.l.courant.commentaires > 0 && p.l.theme !== "autre",
    );
  const mediane = (xs: number[]) => {
    const t = [...xs].sort((a, b) => a - b);
    return t[Math.floor((t.length - 1) / 2)] ?? 1;
  };
  const L = 560;
  const H = 340;
  const m = 48; // marge : les étiquettes des points restent dans le cadre
  const lx = points.map((p) => Math.log10(p.vues));
  const ly = points.map((p) => Math.log10(p.intensite));
  const x0 = Math.min(...lx);
  const x1 = Math.max(...lx);
  const y0 = Math.min(...ly);
  const y1 = Math.max(...ly);
  const px = (v: number) =>
    m + ((Math.log10(v) - x0) / Math.max(0.01, x1 - x0)) * (L - 2 * m);
  const py = (v: number) =>
    H - m - ((Math.log10(v) - y0) / Math.max(0.01, y1 - y0)) * (H - 2 * m - 16);
  const ancre = (x: number) =>
    x < L * 0.2 ? "start" : x > L * 0.8 ? "end" : "middle";
  const mx = px(mediane(points.map((p) => p.vues)));
  const my = py(mediane(points.map((p) => p.intensite)));
  const maxC = Math.max(1, ...points.map((p) => p.l.courant.commentaires));
  const rayon = (c: number) => 5 + 14 * Math.sqrt(c / maxC);
  return (
    <div>
      <p className="discret petit-texte">
        Attention (vues des vidéos, réparties selon leurs thèmes) × intensité
        (commentaires classés pour 1 000 vues). Échelles logarithmiques,
        séparations à la médiane, taille = commentaires.
      </p>
      {points.length < 3 ? (
        <EnPreparation
          titre="Positions des thèmes sur la carte"
          attend="le thème des vidéos et leurs vues (relancer la classification après la migration 10)."
        />
      ) : (
        <svg
          viewBox={`0 0 ${L} ${H}`}
          className="radar-nuage"
          role="img"
          aria-label="Carte des thèmes : attention en abscisse, intensité en ordonnée"
        >
          <line x1={mx} x2={mx} y1={8} y2={H - 8} className="axe" />
          <line x1={8} x2={L - 8} y1={my} y2={my} className="axe" />
          <text x={12} y={18} className="quadrant">
            Minorité mobilisée
          </text>
          <text x={L - 12} y={18} className="quadrant" textAnchor="end">
            Débat de fond
          </text>
          <text x={12} y={H - 10} className="quadrant">
            Bruit de fond
          </text>
          <text x={L - 12} y={H - 10} className="quadrant" textAnchor="end">
            Regardé en silence
          </text>
          {points.map((p) => {
            const r = rayon(p.l.courant.commentaires);
            return (
              <g
                key={p.l.theme}
                className={p.l.theme === actif ? "point actif" : "point"}
                onClick={() => choisir(p.l.theme)}
              >
                <title>
                  {`${LIBELLES_THEMES[p.l.theme]} (${DEFINITIONS_THEMES[p.l.theme]}) : ${entier(p.vues)} vues, ${p.intensite
                    .toFixed(1)
                    .replace(".", ",")} commentaires pour 1 000 vues`}
                </title>
                <circle cx={px(p.vues)} cy={py(p.intensite)} r={r} />
                <text
                  x={px(p.vues)}
                  y={py(p.intensite) - r - 4}
                  textAnchor={ancre(px(p.vues))}
                >
                  {LIBELLES_THEMES[p.l.theme]}
                </text>
              </g>
            );
          })}
        </svg>
      )}
      <p className="discret petit-texte">Cliquer sur un thème pour afficher son détail.</p>
    </div>
  );
}

function SignalEmergent({
  lignes,
  filtres,
  horsGrille,
  ouvrirSujet,
}: {
  lignes: Agregat[];
  filtres: Filtres;
  horsGrille: SujetActu[];
  ouvrirSujet: (id: string) => void;
}) {
  const [courante, precedente] = fenetres(lignes, filtres.periode);
  const part = (w: typeof courante) => {
    const politiques = filtrer(lignes, filtres).filter(
      (l) => dans(l, w) && l.theme !== "non_politique",
    );
    const total = additionner(politiques).commentaires;
    const autre = additionner(
      politiques.filter((l) => l.theme === "autre"),
    ).commentaires;
    return pct(autre, total);
  };
  const actuelle = part(courante);
  const avant = precedente ? part(precedente) : null;
  return (
    <div className="ve-deux">
      <div>
        <p className="ve-kpi">
          <span className="ve-kpi-valeur">
            {actuelle.toFixed(1).replace(".", ",")} %
          </span>
          <span className="ve-kpi-libelle">des commentaires politiques dans « Autre »</span>
          {avant !== null && (
            <span className={actuelle > avant ? "radar-hausse" : "discret"}>
              {actuelle >= avant ? "+" : "−"}
              {Math.abs(actuelle - avant).toFixed(1).replace(".", ",")} pts sur
              la période précédente
            </span>
          )}
        </p>
        <p className="discret petit-texte">
          Des commentaires que la taxonomie ne sait pas encore ranger. Quand ça
          monte, un sujet nouveau arrive.
        </p>
      </div>
      <div>
        <h3 className="ve-h3">Les sujets hors grille</h3>
        <p className="discret petit-texte">
          Sujets d'actualité de la période rangés dans « Autre » : ce qui fait
          réagir sans entrer dans les 13 thèmes.
        </p>
        <ListeSujets actu={horsGrille} ouvrir={ouvrirSujet} />
      </div>
    </div>
  );
}

type Rangee = { nom: string; m: Mesures; aPart?: boolean };

function ListeSujets({
  actu,
  ouvrir,
}: {
  actu: SujetActu[];
  ouvrir: (id: string) => void;
}) {
  if (actu.length === 0)
    return (
      <p className="discret petit-texte">
        Aucun sujet d'actualité de 3 vidéos et 2 chaînes sur la période.
      </p>
    );
  return (
    <ul className="explo-liste">
      {actu.map((x) => (
        <li key={x.id}>
          <button className="explo-ligne" onClick={() => ouvrir(x.id)}>
            <span className="explo-ligne-corps">
              <span className="explo-ligne-titre">{x.titre}</span>
              <span className="explo-ligne-meta">
                {x.videos.length} vidéo{x.videos.length > 1 ? "s" : ""} ·{" "}
                {x.chaines} chaînes
              </span>
            </span>
            <span className="explo-ligne-chiffres">
              <span>
                {entier(x.commentaires)}
                <small> comm.</small>
              </span>
            </span>
            <span className="explo-chevron" aria-hidden="true">
              ›
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

type Onglet = "reactions" | "sujets" | "videos" | "theses";

function Onglets<T extends string>({
  items,
  actif,
  choisir,
  libelle,
}: {
  items: [T, string, number?][];
  actif: T;
  choisir: (t: T) => void;
  libelle: string;
}) {
  return (
    <div className="ve-onglets" role="tablist" aria-label={libelle}>
      {items.map(([cle, nom, n]) => (
        <button
          key={cle}
          role="tab"
          aria-selected={actif === cle}
          className={actif === cle ? "actif" : ""}
          onClick={() => choisir(cle)}
        >
          {nom}
          {n !== undefined && <span className="ve-compte">{n}</span>}
        </button>
      ))}
    </div>
  );
}

function ThemeSelectionne({
  ligne,
  lignes,
  filtres,
  politiques,
  sujets,
  reactions,
  theses,
  rattachements,
  resumes,
  onglet,
  setOnglet,
  ouvrirSujet,
  ouvrirVideo,
}: {
  ligne: LigneTheme;
  lignes: Agregat[];
  filtres: Filtres;
  politiques: boolean;
  sujets: SujetVideo[];
  reactions: Map<string, ReactionVideo>;
  theses: Map<string, These>;
  rattachements: Map<string, Rattachement>;
  resumes: ResumeIA[];
  onglet: Onglet;
  setOnglet: (o: Onglet) => void;
  ouvrirSujet: (id: string) => void;
  ouvrirVideo: (s: SujetVideo) => void;
}) {
  const [courante] = fenetres(lignes, filtres.periode);
  const debattues = videosDebattues(sujets, ligne.theme, reactions, theses);
  const ss = sousSujets(sujets, ligne.theme);
  const actu = sujetsActu(sujets, ligne.theme, rattachements, 20);
  const [toutes, setToutes] = useState(false);
  const toutesVideos = videosQuiReagissent(
    sujets,
    ligne.theme,
    Number.POSITIVE_INFINITY,
  );
  const videos = toutes ? toutesVideos : toutesVideos.slice(0, 10);
  const du = (types: TypeSource[]) =>
    additionner(
      filtrer(lignes, filtres, types).filter(
        (l) => l.theme === ligne.theme && dans(l, courante),
      ),
    );
  const rangees: Rangee[] = [
    { nom: "Ensemble", m: du(filtres.types) },
    ...filtres.types.map((t) => ({ nom: LIBELLES_TYPE[t], m: du([t]) })),
    ...(politiques
      ? [{ nom: "Chaînes politiques", m: du(["politique"]), aPart: true }]
      : []),
  ];
  const ensemble = rangees[0]!.m;
  const prononces = ensemble.accord + ensemble.nuance + ensemble.desaccord;
  const resume = dernierResume(resumes, "theme", ligne.theme, courante.fin);
  return (
    <section className="radar-carte ve-detail" id="ve-detail" aria-labelledby="titre-detail">
      <p className="explo-surtitre">Thème sélectionné</p>
      <h2 id="titre-detail" className="ve-titre-theme">
        {LIBELLES_THEMES[ligne.theme]}
      </h2>
      <p className="radar-def-theme">{DEFINITIONS_THEMES[ligne.theme]}</p>
      <div className="explo-chiffres">
        <div className="explo-chiffre">
          <span>{entier(ligne.courant.commentaires)}</span>
          <span>commentaires</span>
        </div>
        <div className="explo-chiffre">
          <span>{pc(ligne.part * 100)}</span>
          <span>des commentaires politiques</span>
        </div>
        <div className="explo-chiffre">
          <span>{fois(ligne.velocite)}</span>
          <span>vélocité</span>
        </div>
        <div className="explo-chiffre">
          <span>
            {prononces >= MIN_PRONONCES_THEME
              ? pc(pct(ensemble.desaccord, prononces))
              : "–"}
          </span>
          <span>désaccord avec les vidéos</span>
        </div>
        <div className="explo-chiffre">
          <span>{pc(pct(ensemble.hostiles, ensemble.commentaires))}</span>
          <span>hostiles</span>
        </div>
      </div>
      {resume && <PourquoiCaBouge r={resume} semaine />}

      <Onglets
        libelle="Détail du thème"
        actif={onglet}
        choisir={setOnglet}
        items={[
          ["reactions", "Réactions"],
          ["sujets", "Sujets", rattachements.size > 0 ? actu.length : ss.length],
          ["videos", "Vidéos", toutesVideos.length],
          ["theses", "Thèses", debattues.filter((v) => v.these?.explicite).length],
        ]}
      />
      <div className="ve-onglet-corps" role="tabpanel">
        {onglet === "reactions" && <Reactions rangees={rangees} />}
        {onglet === "sujets" &&
          (rattachements.size > 0 ? (
            <>
              <ListeSujets actu={actu} ouvrir={ouvrirSujet} />
              <p className="discret petit-texte">
                Vidéos regroupées par événement par une IA (titre neutre, pas
                celui d'une vidéo), à partir de 3 vidéos de 2 chaînes.
              </p>
            </>
          ) : ss.length === 0 ? (
            <EnPreparation
              titre="Sous-sujets"
              attend="le thème et le sous-sujet des vidéos."
            />
          ) : (
            <ul className="radar-sous-sujets">
              {ss.map((x) => (
                <li key={x.libelle}>
                  <span>{x.libelle}</span>
                  <span className="radar-mono discret">
                    {x.videos} vidéo{x.videos > 1 ? "s" : ""} ·{" "}
                    {entier(x.commentaires)} comm.
                  </span>
                </li>
              ))}
            </ul>
          ))}
        {onglet === "videos" &&
          (videos.length === 0 ? (
            <p className="discret petit-texte">Aucune vidéo sur la période.</p>
          ) : (
            <>
              <ListeVideos
                videos={videos.map((v) => versVideo(v, reactions, theses))}
                ouvrir={(v) => {
                  const x = videos.find((y) => y.video_id === v.video_id);
                  if (x) ouvrirVideo(x);
                }}
                sujetDe={(id) => rattachements.get(id)?.sujets?.titre}
              />
              {toutesVideos.length > 10 && (
                <button
                  className="cs-lien-bas"
                  onClick={() => setToutes(!toutes)}
                  aria-expanded={toutes}
                >
                  {toutes
                    ? "Ne garder que les 10 premières"
                    : `Voir toutes les vidéos du thème (${toutesVideos.length}) →`}
                </button>
              )}
              <p className="discret petit-texte">
                Classées par commentaires annoncés par YouTube. Libellé neutre
                du sujet (pas le titre de la vidéo).
              </p>
            </>
          ))}
        {onglet === "theses" && (
          <SurQuoiDaccord debattues={debattues} ouvrir={(v) => ouvrirVideo(v.sujet)} />
        )}
      </div>
    </section>
  );
}

function Reactions({ rangees }: { rangees: Rangee[] }) {
  return (
    <>
      <div className="ve-tableau" role="table" aria-label="Réactions par type de source">
        <div className="ve-tableau-tete" role="row">
          <span role="columnheader">Réactions sous</span>
          <span role="columnheader">Accord · nuance · désaccord avec la vidéo</span>
          <span role="columnheader">Tonalité</span>
          <span role="columnheader">Hostiles</span>
        </div>
        {rangees.map((r) => {
          const prononces = r.m.accord + r.m.nuance + r.m.desaccord;
          return (
            <div
              key={r.nom}
              role="row"
              className={r.aPart ? "ve-tableau-ligne a-part" : "ve-tableau-ligne"}
            >
              <span role="cell" className="ve-tableau-nom">
                {r.nom}
                {r.aPart && <small className="discret"> lues à part</small>}
              </span>
              <span role="cell">
                <Barre
                  titre={`Accord avec les vidéos commentées, ${r.nom}`}
                  total={prononces}
                  segments={[
                    { libelle: "Accord", valeur: r.m.accord, couleur: "var(--r-bleu)" },
                    { libelle: "Nuance", valeur: r.m.nuance, couleur: "var(--r-nuance)" },
                    { libelle: "Désaccord", valeur: r.m.desaccord, couleur: "var(--r-orange)" },
                  ]}
                />
                <small className="radar-mono">
                  {prononces > 0
                    ? `${Math.round(pct(r.m.accord, prononces))} / ${Math.round(pct(r.m.nuance, prononces))} / ${Math.round(pct(r.m.desaccord, prononces))}`
                    : "–"}
                </small>
              </span>
              <span role="cell">
                <Barre
                  titre={`Tonalité, ${r.nom}`}
                  total={r.m.commentaires}
                  segments={[
                    { libelle: "Positive", valeur: r.m.positifs, couleur: "var(--r-bleu)" },
                    { libelle: "Neutre", valeur: r.m.neutres, couleur: "var(--r-nuance)" },
                    { libelle: "Négative", valeur: r.m.negatifs, couleur: "var(--r-orange)" },
                  ]}
                />
                <small className="radar-mono">
                  {Math.round(pct(r.m.positifs, r.m.commentaires))} /{" "}
                  {Math.round(pct(r.m.neutres, r.m.commentaires))} /{" "}
                  {Math.round(pct(r.m.negatifs, r.m.commentaires))}
                </small>
              </span>
              <span role="cell" className="ve-tableau-chiffre">
                {pc(pct(r.m.hostiles, r.m.commentaires))}
              </span>
            </div>
          );
        })}
      </div>
      <Legende
        items={[
          ["Accord · positive", "var(--r-bleu)"],
          ["Nuance · neutre", "var(--r-nuance)"],
          ["Désaccord · négative", "var(--r-orange)"],
        ]}
      />
      <p className="discret petit-texte">
        Accord : chaque commentaire est comparé à la vidéo sous laquelle il est
        écrit, sur les vidéos d'opinion seulement (une thèse à approuver ou
        contester) ; ceux qui ne se prononcent pas sont exclus. Ne dit pas si
        les gens sont pour ou contre un sujet.
      </p>
    </>
  );
}

function Panorama({
  lignes,
  agenda,
  actif,
  choisir,
  donnees,
  filtres,
  sujetsBase,
  horsGrille,
  ouvrirSujet,
  sansSujets,
}: {
  lignes: LigneTheme[];
  agenda: Map<Theme, Agenda>;
  actif: Theme;
  choisir: (t: Theme) => void;
  donnees: Agregat[];
  filtres: Filtres;
  sujetsBase: SujetVideo[];
  horsGrille: SujetActu[];
  ouvrirSujet: (id: string) => void;
  sansSujets: string;
}) {
  const [vue, setVue] = useState<"carte" | "semaines" | "hors_grille">("carte");
  return (
    <section className="radar-carte ve-panorama" aria-labelledby="titre-panorama">
      <div className="ve-panorama-tete">
        <h2 id="titre-panorama">Panorama des thèmes</h2>
        <Onglets
          libelle="Panorama"
          actif={vue}
          choisir={setVue}
          items={[
            ["carte", "Carte attention × intensité"],
            ["semaines", "Semaine par semaine"],
            ["hors_grille", "Signal émergent", horsGrille.length],
          ]}
        />
      </div>
      {vue === "carte" && (
        <CarteSujets lignes={lignes} agenda={agenda} actif={actif} choisir={choisir} />
      )}
      {vue === "semaines" && (
        <ComparaisonSemaines
          lignes={donnees}
          filtres={filtres}
          sujets={sujetsBase}
          choisir={choisir}
        />
      )}
      {vue === "hors_grille" && (
        <SignalEmergent
          lignes={donnees}
          filtres={filtres}
          horsGrille={horsGrille}
          ouvrirSujet={ouvrirSujet}
        />
      )}
      {sansSujets && (
        <p className="discret petit-texte">
          Thèmes des vidéos indisponibles : {sansSujets}
        </p>
      )}
    </section>
  );
}

function Courbe({ serie }: { serie: number[] }) {
  const max = Math.max(1, ...serie);
  const l = 52;
  const h = 22;
  const pas = serie.length > 1 ? l / (serie.length - 1) : 0;
  const points = serie
    .map(
      (v, i) =>
        `${(i * pas).toFixed(1)},${(h - (v / max) * (h - 2) - 1).toFixed(1)}`,
    )
    .join(" ");
  return (
    <svg
      className="radar-courbe"
      width={l}
      height={h}
      viewBox={`0 0 ${l} ${h}`}
      aria-hidden="true"
    >
      <polyline
        points={points}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
      />
    </svg>
  );
}

const semaineCourte = (lundi: string) => `sem. du ${dateCourte(lundi)}`;

function ComparaisonSemaines({
  lignes,
  filtres,
  sujets,
  choisir,
}: {
  lignes: Agregat[];
  filtres: Filtres;
  sujets: SujetVideo[];
  choisir: (t: Theme) => void;
}) {
  const liste = semaines(lignes, filtres);
  const c = changements(liste);
  const nouveaux = c
    ? nouveauxSousSujets(sujets, c.avant.debut, c.apres.debut)
    : [];
  const themesTries = [...THEMES].sort(
    (a, b) =>
      liste.reduce((s2, w) => s2 + (w.parts.get(b) ?? 0) * w.total, 0) -
      liste.reduce((s2, w) => s2 + (w.parts.get(a) ?? 0) * w.total, 0),
  );
  const maxPart = Math.max(
    0.01,
    ...liste.flatMap((w) => [...w.parts.values()]),
  );
  return (
    <div className="radar-semaines">
      <section aria-labelledby="titre-change">
        <h3 id="titre-change" className="ve-h3">Ce qui a changé</h3>
        {!c ? (
          <EnPreparation
            titre="Comparaison avec la semaine précédente"
            attend={`deux semaines complètes d'au moins ${entier(MIN_COMMENTAIRES_SEMAINE)} commentaires politiques (backfill de septembre, puis collecte quotidienne).`}
          />
        ) : (
          <>
            <p className="discret petit-texte">
              {semaineCourte(c.apres.debut)} face à la{" "}
              {semaineCourte(c.avant.debut)}, en points de part des commentaires
              politiques.
            </p>
            <ul className="radar-changements">
              {c.hausses.map((x) => (
                <li key={x.theme}>
                  <span className="radar-etiquette hausse">En hausse</span>
                  <button
                    className="radar-lien"
                    onClick={() => choisir(x.theme)}
                    title={DEFINITIONS_THEMES[x.theme]}
                  >
                    {LIBELLES_THEMES[x.theme]}
                  </button>
                  <span className="radar-mono">
                    {pc(x.avant * 100)} → {pc(x.apres * 100)} (+
                    {Math.round(x.ecart)} pts)
                  </span>
                </li>
              ))}
              {c.baisses.map((x) => (
                <li key={x.theme}>
                  <span className="radar-etiquette baisse">En baisse</span>
                  <button
                    className="radar-lien"
                    onClick={() => choisir(x.theme)}
                    title={DEFINITIONS_THEMES[x.theme]}
                  >
                    {LIBELLES_THEMES[x.theme]}
                  </button>
                  <span className="radar-mono">
                    {pc(x.avant * 100)} → {pc(x.apres * 100)} (−
                    {Math.abs(Math.round(x.ecart))} pts)
                  </span>
                </li>
              ))}
              {nouveaux.map((libelle) => (
                <li key={libelle}>
                  <span className="radar-etiquette nouveau">Nouveau</span>
                  <span>{libelle}</span>
                  <span className="discret petit-texte">
                    sous-sujet entré dans le top 10
                  </span>
                </li>
              ))}
            </ul>
            {c.hausses.length + c.baisses.length + nouveaux.length === 0 && (
              <p className="discret petit-texte">
                Aucun mouvement d'au moins 1 point.
              </p>
            )}
          </>
        )}
      </section>
      <section aria-labelledby="titre-semaines">
        <h3 id="titre-semaines" className="ve-h3">Part de chaque thème</h3>
        <p className="discret petit-texte">
          Part de chaque thème parmi les commentaires politiques, par semaine de
          publication des commentaires. Semaines grisées : moins de{" "}
          {entier(MIN_COMMENTAIRES_SEMAINE)} commentaires ou semaine en cours.
        </p>
        <div className="defile">
          <table className="radar-chaleur">
            <thead>
              <tr>
                <th scope="col">Thème</th>
                {liste.map((w) => (
                  <th
                    key={w.debut}
                    scope="col"
                    className={w.fiable && w.complete ? "" : "peu-fiable"}
                    title={`${entier(w.total)} commentaires politiques`}
                  >
                    {dateCourte(w.debut)}
                    {!w.complete && " *"}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {themesTries.map((t) => (
                <tr key={t}>
                  <th scope="row">
                    <button
                      className="radar-lien"
                      onClick={() => choisir(t)}
                      title={DEFINITIONS_THEMES[t]}
                    >
                      {LIBELLES_THEMES[t]}
                    </button>
                  </th>
                  {liste.map((w: Semaine) => {
                    const part = w.parts.get(t) ?? 0;
                    return (
                      <td
                        key={w.debut}
                        className={w.fiable && w.complete ? "" : "peu-fiable"}
                        style={{
                          background: `color-mix(in srgb, var(--r-orange) ${Math.round((70 * part) / maxPart)}%, var(--r-surface))`,
                        }}
                      >
                        {part > 0 ? pc(part * 100) : "–"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="discret petit-texte">
          * semaine incomplète (début de la collecte ou semaine en cours).
        </p>
      </section>
    </div>
  );
}

function LigneThese({
  v,
  ouvrir,
}: {
  v: VideoDebattue;
  ouvrir: (v: VideoDebattue) => void;
}) {
  const r = v.reaction;
  return (
    <li>
      <button className="explo-ligne" onClick={() => ouvrir(v)}>
        <span className="explo-ligne-corps">
          <span className="explo-ligne-titre">
            {v.these ? `« ${v.these.these} »` : v.sujet.sous_sujet}
            {!v.these && (
              <span className="discret"> (thèse effacée après 30 jours)</span>
            )}
          </span>
          <Barre
            titre="Accord avec la vidéo"
            total={v.prononces}
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
          <span className="explo-ligne-meta">
            {pc(v.partAccord * 100)} d'accord · {pc(v.partDesaccord * 100)} en
            désaccord · {entier(v.prononces)} se prononcent ·{" "}
            {v.sujet.videos?.sources?.nom} ·{" "}
            {v.sujet.videos
              ? dateCourte(jourParis(v.sujet.videos.publiee_at))
              : ""}
          </span>
        </span>
        <span className="explo-chevron" aria-hidden="true">
          ›
        </span>
      </button>
    </li>
  );
}

function SurQuoiDaccord({
  debattues,
  ouvrir,
}: {
  debattues: VideoDebattue[];
  ouvrir: (v: VideoDebattue) => void;
}) {
  const [incertaines, setIncertaines] = useState(false);
  const explicites = debattues.filter((v) => v.these?.explicite);
  const autres = debattues.filter((v) => !v.these?.explicite);
  const approuvees = [...explicites]
    .sort((a, b) => b.partAccord - a.partAccord)
    .slice(0, 3);
  const contestees = [...explicites]
    .sort((a, b) => b.partDesaccord - a.partDesaccord)
    .filter((v) => !approuvees.includes(v) || explicites.length > 3)
    .slice(0, 3);
  if (debattues.length === 0)
    return (
      <EnPreparation
        titre="Thèses des vidéos d'opinion"
        attend={`les thèses et l'accord vidéo par vidéo (migration 11, relance de la classification puis des agrégats), et au moins ${MIN_PRONONCES} commentaires qui se prononcent par vidéo.`}
      />
    );
  return (
    <>
      <div className="ve-deux">
        <div>
          <h3 className="ve-h3">Les plus approuvées</h3>
          <ul className="explo-liste">
            {approuvees.map((v) => (
              <LigneThese key={v.sujet.video_id} v={v} ouvrir={ouvrir} />
            ))}
          </ul>
        </div>
        <div>
          <h3 className="ve-h3">Les plus contestées</h3>
          <ul className="explo-liste">
            {contestees.map((v) => (
              <LigneThese key={v.sujet.video_id} v={v} ouvrir={ouvrir} />
            ))}
          </ul>
        </div>
      </div>
      {autres.length > 0 && (
        <button
          className="cs-lien-bas"
          onClick={() => setIncertaines(!incertaines)}
          aria-expanded={incertaines}
        >
          {incertaines
            ? "Masquer les thèses incertaines"
            : `Thèses incertaines ou effacées (${autres.length}) →`}
        </button>
      )}
      {incertaines && (
        <ul className="explo-liste">
          {autres.map((v) => (
            <LigneThese key={v.sujet.video_id} v={v} ouvrir={ouvrir} />
          ))}
        </ul>
      )}
      <p className="discret petit-texte">
        Thèse résumée par une IA à partir du titre et de la description, pas du
        contenu de la vidéo : vérifier avec le lien. Seules les thèses
        explicites sont classées ; vidéos d'au moins {MIN_PRONONCES}{" "}
        commentaires qui se prononcent.
      </p>
    </>
  );
}
