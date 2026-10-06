"use client";

import { useDeferredValue, useEffect, useMemo, useState } from "react";

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
  Squelette,
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

  // Filtres appliqués en arrière-plan : la barre répond tout de suite, les calculs suivent
  // (contenu estompé entre-temps).
  const filtresD = useDeferredValue(filtres);
  const chainesD = useDeferredValue(chaines);
  const politiquesD = useDeferredValue(politiques);
  const enCalcul =
    filtresD !== filtres || chainesD !== chaines || politiquesD !== politiques;

  const donnees = useMemo(
    () =>
      chainesD.length === 0
        ? lignes
        : parChaine === null
          ? null
          : parChaine.filter((l) => chainesD.includes(l.source_id ?? "")),
    [lignes, chainesD, parChaine],
  );
  const filtresEff = useMemo<Filtres>(
    () =>
      chainesD.length === 0
        ? filtresD
        : {
            ...filtresD,
            types: PUBLICS.filter((t) =>
              sources.some((x) => chainesD.includes(x.id) && x.type === t),
            ),
          },
    [filtresD, chainesD, sources],
  );
  const sujetsBase = useMemo(
    () =>
      chainesD.length === 0
        ? sujets
        : sujets.filter((x) => chainesD.includes(x.videos?.sources?.id ?? "")),
    [sujets, chainesD],
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

  // Sujets d'actualité de la période (vidéos longues : Shorts exclus au chargement).
  const cartes = useMemo(() => {
    if (!vue) return new Map<string, CarteSujet>();
    return new Map(
      cartesSujets(
        sujetsBase,
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
      ?.scrollIntoView({
        behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "auto"
          : "smooth",
        block: "start",
      });
  };

  const outils = lignes && lignes.length > 0 && (
    <>
      <div className="r-segments" role="group" aria-label="Période">
        {([7, 30, "tout"] as const).map((p) => (
          <button
            key={p}
            className={filtres.periode === p ? "actif" : ""}
            aria-pressed={filtres.periode === p}
            onClick={() => setFiltres({ ...filtres, periode: p })}
          >
            {p === "tout" ? "Campagne" : `${p} jours`}
          </button>
        ))}
      </div>
      <MenuFiltres
        filtres={filtres}
        setFiltres={setFiltres}
        politiques={politiques}
        setPolitiques={setPolitiques}
        sources={sources}
        chaines={chaines}
        setChaines={setChaines}
      />
    </>
  );

  return (
    <div className="radar">
      <Entete actif="ensemble" outils={outils} />

      {erreur && <p className="erreur r-page">{erreur}</p>}
      {!lignes && !erreur && <Squelette />}
      {lignes && lignes.length === 0 && (
        <p className="r-vide r-page">
          Aucun agrégat : lancer la classification puis le workflow « Agrégats ».
        </p>
      )}
      {chainesD.length > 0 && !vue && (
        <p className="r-vide r-page">
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
        <main
          className={enCalcul ? "r-page r-contenu en-calcul" : "r-page r-contenu"}
          aria-busy={enCalcul}
        >
          <p className="r-periode">
            Du {dateCourte(vue.courante.debut)} au {dateCourte(vue.courante.fin)} ·{" "}
            <strong>{entier(vue.total.commentaires)}</strong> commentaires classés,
            dont {pc(pct(vue.nonPolitique.commentaires, vue.total.commentaires))} non
            politiques
            {sansSujets && ` · thèmes des vidéos indisponibles : ${sansSujets}`}
          </p>
          <div className="r-maitre">
            <ListeThemes lignes={vue.lignes} actif={actif.theme} choisir={setChoisi} />
            <ThemeSelectionne
              key={actif.theme}
              ligne={actif}
              lignes={donnees}
              filtres={filtresEff}
              politiques={politiquesD}
              sujets={sujetsPeriode}
              agenda={agenda}
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
          <details className="r-carte r-repli">
            <summary>
              <span>Tous les thèmes, semaine par semaine</span>
              <span className="r-discret">ce qui a changé et part de chaque thème</span>
            </summary>
            <ComparaisonSemaines
              lignes={donnees}
              filtres={filtresEff}
              sujets={sujetsBase}
              choisir={choisirEtMontrer}
            />
          </details>
        </main>
      )}
      <Explorateur pile={pile} setPile={setPile} />
    </div>
  );
}

type SourceChaine = { id: string; nom: string; type: TypeSource };

function MenuFiltres({
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
  const resume =
    chaines.length > 0
      ? chaines.length === 1
        ? (sources.find((x) => x.id === chaines[0])?.nom ?? "1 chaîne")
        : `${chaines.length} chaînes`
      : filtres.types.length === PUBLICS.length
        ? "Tous les médias"
        : LIBELLES_TYPE[filtres.types[0]!];
  return (
    <details className="r-menu">
      <summary className="r-bouton">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          <path d="M4 6h16M7 12h10M10 18h4" />
        </svg>
        {resume}
        {politiques && " · politiques"}
      </summary>
      <div className="r-menu-corps">
        <fieldset>
          <legend>Réactions sous</legend>
          <div className="r-segments">
            {(
              [
                ["Tous", PUBLICS],
                ["Traditionnels", ["media_traditionnel"]],
                ["Natifs du web", ["media_natif"]],
              ] as [string, TypeSource[]][]
            ).map(([nom, ts]) => {
              const actif = chaines.length === 0 && ts.join() === filtres.types.join();
              return (
                <button
                  key={nom}
                  className={actif ? "actif" : ""}
                  aria-pressed={actif}
                  onClick={() => {
                    setChaines([]);
                    setFiltres({ ...filtres, types: ts });
                  }}
                >
                  {nom}
                </button>
              );
            })}
          </div>
        </fieldset>
        <fieldset>
          <legend>Chaînes</legend>
          <input
            type="search"
            placeholder="Chercher une chaîne"
            value={recherche}
            onChange={(e) => setRecherche(e.target.value)}
            aria-label="Chercher une chaîne"
          />
          {chaines.length > 0 && (
            <button className="r-lien" onClick={() => setChaines([])}>
              Tout effacer (revenir au panel)
            </button>
          )}
          <div className="r-menu-liste">
            {PUBLICS.map((t) => (
              <div key={t}>
                <p className="r-surtitre">{LIBELLES_TYPE[t]}</p>
                {visibles
                  .filter((x) => x.type === t)
                  .map((x) => (
                    <label key={x.id} className="r-case">
                      <input
                        type="checkbox"
                        checked={chaines.includes(x.id)}
                        onChange={() => basculerChaine(x.id)}
                      />
                      {x.nom}
                    </label>
                  ))}
              </div>
            ))}
          </div>
        </fieldset>
        <label className="r-case">
          <input
            type="checkbox"
            checked={politiques}
            onChange={(e) => setPolitiques(e.target.checked)}
          />
          Afficher les chaînes politiques (lues à part)
        </label>
      </div>
    </details>
  );
}

type Classement = "volume" | "velocite" | "desaccord" | "hostilite";
const CLASSEMENTS: [Classement, string][] = [
  ["volume", "Réactions"],
  ["velocite", "Évolution"],
  ["desaccord", "Désaccord"],
  ["hostilite", "Hostilité"],
];
const MIN_PRONONCES_THEME = 50;

/** Valeur du thème pour le classement choisi (null si l'échantillon est trop petit). */
function valeurTheme(l: LigneTheme, c: Classement): number | null {
  const m = l.courant;
  if (c === "volume") return l.part * 100;
  if (c === "velocite") return l.velocite;
  if (c === "hostilite")
    return m.commentaires >= MIN_PRONONCES_THEME
      ? pct(m.hostiles, m.commentaires)
      : null;
  const prononces = m.accord + m.nuance + m.desaccord;
  return prononces >= MIN_PRONONCES_THEME ? pct(m.desaccord, prononces) : null;
}

function ListeThemes({
  lignes,
  actif,
  choisir,
}: {
  lignes: LigneTheme[];
  actif: Theme;
  choisir: (t: Theme) => void;
}) {
  const [classement, setClassement] = useState<Classement>("volume");
  const tries = [...lignes]
    .filter((l) => valeurTheme(l, classement) !== null)
    .sort(
      (a, b) =>
        (valeurTheme(b, classement) ?? -1) - (valeurTheme(a, classement) ?? -1),
    );
  const max = Math.max(0.01, ...tries.map((l) => valeurTheme(l, classement) ?? 0));
  const libelle = (l: LigneTheme) => {
    const v = valeurTheme(l, classement);
    if (v === null) return "–";
    return classement === "velocite" ? fois(v) : pc(v);
  };
  return (
    <section className="r-carte r-themes" aria-labelledby="t-themes">
      <div className="r-carte-tete">
        <h2 id="t-themes">{lignes.length} thèmes</h2>
      </div>
      <div className="r-puces-choix" role="group" aria-label="Classer les thèmes par">
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
      <p className="r-discret r-themes-aide">
        {classement === "volume"
          ? "Part des commentaires politiques · vélocité à droite"
          : classement === "velocite"
            ? "Commentaires sur 7 jours ÷ moyenne des 4 semaines d'avant (×1,0 = habituel)"
            : classement === "desaccord"
              ? "Désaccord avec les vidéos d'opinion (au moins 50 commentaires qui se prononcent)"
              : "Part de commentaires hostiles"}
      </p>
      {tries.length === 0 && (
        <p className="r-vide">Pas encore assez de semaines de données pour ce classement.</p>
      )}
      <ol className="r-themes-liste">
        {tries.map((l) => {
          const v = valeurTheme(l, classement) ?? 0;
          return (
            <li key={l.theme}>
              <button
                className={l.theme === actif ? "r-theme actif" : "r-theme"}
                onClick={() => choisir(l.theme)}
                aria-pressed={l.theme === actif}
                title={DEFINITIONS_THEMES[l.theme]}
              >
                <span className="r-theme-corps">
                  <span className="r-theme-nom">{LIBELLES_THEMES[l.theme]}</span>
                  <span className="r-piste">
                    <span className="noir" style={{ width: `${(100 * v) / max}%` }} />
                  </span>
                </span>
                <span className="r-mono">{libelle(l)}</span>
                <span
                  className={
                    l.velocite === null
                      ? "r-mono r-discret"
                      : l.velocite >= 1.2
                        ? "r-mono bleu"
                        : l.velocite <= 0.8
                          ? "r-mono orange"
                          : "r-mono r-discret"
                  }
                  title="Vélocité"
                >
                  {classement === "velocite" ? pc(l.part * 100) : fois(l.velocite)}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </section>
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

type Onglet = "reactions" | "medias" | "sujets" | "videos" | "theses";

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
    <div className="r-onglets" role="tablist" aria-label={libelle}>
      {items.map(([cle, nom, n]) => (
        <button
          key={cle}
          role="tab"
          aria-selected={actif === cle}
          className={actif === cle ? "actif" : ""}
          onClick={() => choisir(cle)}
        >
          {nom}
          {n !== undefined && <span className="r-compte">{n}</span>}
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
  agenda,
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
  agenda: Map<Theme, Agenda>;
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
  const ss = sousSujets(sujets, ligne.theme, 8);
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
    { nom: "Ensemble du public", m: du(filtres.types) },
    ...filtres.types.map((t) => ({ nom: LIBELLES_TYPE[t], m: du([t]) })),
    ...(politiques
      ? [{ nom: "Chaînes politiques", m: du(["politique"]), aPart: true }]
      : []),
  ];
  const ensemble = rangees[0]!.m;
  const prononces = ensemble.accord + ensemble.nuance + ensemble.desaccord;
  const resume = dernierResume(resumes, "theme", ligne.theme, courante.fin);
  // Couverture : part des vidéos du thème parmi les vidéos de la période (agenda des médias).
  const totalVideos = [...agenda.entries()]
    .filter(([t]) => t !== "autre" || ligne.theme === "autre")
    .reduce((a, [, x]) => a + x.videos, 0);
  const couverture = totalVideos ? (agenda.get(ligne.theme)?.videos ?? 0) / totalVideos : null;
  const ratio = couverture ? ligne.part / couverture : null;
  return (
    <section className="r-carte r-detail" id="ve-detail" aria-labelledby="titre-detail">
      <h2 id="titre-detail" className="r-detail-titre">
        {LIBELLES_THEMES[ligne.theme]}
      </h2>
      <p className="r-discret">{DEFINITIONS_THEMES[ligne.theme]}</p>
      <div className="r-tuiles">
        <Tuile valeur={pc(ligne.part * 100)} libelle="des commentaires politiques" />
        <Tuile
          valeur={couverture === null ? "–" : pc(couverture * 100)}
          libelle="des vidéos (couverture)"
        />
        <Tuile
          valeur={fois(ligne.velocite)}
          libelle="vélocité"
          classe={
            ligne.velocite === null ? "" : ligne.velocite >= 1.2 ? "bleu" : ligne.velocite <= 0.8 ? "orange" : ""
          }
        />
        <Tuile
          valeur={
            prononces >= MIN_PRONONCES_THEME ? pc(pct(ensemble.desaccord, prononces)) : "–"
          }
          libelle="désaccord avec les vidéos"
        />
        <Tuile
          valeur={pc(pct(ensemble.hostiles, ensemble.commentaires))}
          libelle="hostiles"
        />
      </div>
      {resume && <PourquoiCaBouge r={resume} semaine />}

      <Onglets
        libelle="Détail du thème"
        actif={onglet}
        choisir={setOnglet}
        items={[
          ["reactions", "Réactions"],
          ["medias", "Médias vs commentaires"],
          ["sujets", "Sujets", rattachements.size > 0 ? actu.length : ss.length],
          ["videos", "Vidéos", toutesVideos.length],
          ["theses", "Thèses", debattues.filter((v) => v.these?.explicite).length],
        ]}
      />
      <div className="r-onglet-corps" role="tabpanel" key={onglet}>
        {onglet === "reactions" && <Reactions rangees={rangees} />}
        {onglet === "medias" && (
          <div className="r-medias">
            <div className="r-medias-barres">
              <div className="r-piste-ligne large">
                <span>Couverture</span>
                <span className="r-piste">
                  <span
                    className="gris"
                    style={{ width: `${Math.min(100, (couverture ?? 0) * 100 * 2)}%` }}
                  />
                </span>
                <span className="r-mono">{couverture === null ? "–" : pc(couverture * 100)}</span>
              </div>
              <div className="r-piste-ligne large">
                <span>Réactions</span>
                <span className="r-piste">
                  <span className="noir" style={{ width: `${Math.min(100, ligne.part * 100 * 2)}%` }} />
                </span>
                <span className="r-mono">{pc(ligne.part * 100)}</span>
              </div>
              <p className="r-discret">
                {ratio === null
                  ? "Couverture inconnue : thèmes des vidéos pas encore calculés."
                  : ratio >= 1.25
                    ? `Le thème fait ${fois(ratio).replace("×", "")} fois plus réagir que sa place dans les vidéos.`
                    : ratio <= 0.8
                      ? `Le thème est plus couvert qu'il ne fait réagir (${fois(ratio)}).`
                      : "Couverture et réactions sont à peu près alignées."}
              </p>
            </div>
            <div>
              <h3 className="r-h3">De quoi parlent les vidéos du thème</h3>
              {ss.length === 0 ? (
                <p className="r-discret">Aucune vidéo du thème sur la période.</p>
              ) : (
                <ul className="r-liste-simple">
                  {ss.map((x) => (
                    <li key={x.libelle}>
                      <span>{x.libelle}</span>
                      <span className="r-mono r-discret">
                        {x.videos} vidéo{x.videos > 1 ? "s" : ""}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              <p className="r-discret petit-texte">
                Sous-sujets neutres écrits par une IA, classés par commentaires
                annoncés. Ce dont parlent les commentaires eux-mêmes n'est pas
                encore mesuré.
              </p>
            </div>
          </div>
        )}
        {onglet === "sujets" &&
          (rattachements.size > 0 ? (
            <>
              <ListeSujets actu={actu} ouvrir={ouvrirSujet} />
              <p className="r-discret petit-texte">
                Vidéos regroupées par événement par une IA (titre neutre, pas
                celui d'une vidéo), à partir de 3 vidéos de 2 chaînes.
              </p>
            </>
          ) : (
            <EnPreparation
              titre="Sujets d'actualité"
              attend="le workflow « Sujets »."
            />
          ))}
        {onglet === "videos" &&
          (videos.length === 0 ? (
            <p className="r-discret">Aucune vidéo sur la période.</p>
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
                  className="r-plus"
                  onClick={() => setToutes(!toutes)}
                  aria-expanded={toutes}
                >
                  {toutes
                    ? "Ne garder que les 10 premières"
                    : `Voir toutes les vidéos du thème (${toutesVideos.length})`}
                </button>
              )}
            </>
          ))}
        {onglet === "theses" && (
          <SurQuoiDaccord debattues={debattues} ouvrir={(v) => ouvrirVideo(v.sujet)} />
        )}
      </div>
    </section>
  );
}

function Tuile({
  valeur,
  libelle,
  classe = "",
}: {
  valeur: string;
  libelle: string;
  classe?: string;
}) {
  return (
    <div className="r-tuile">
      <span className={`r-tuile-valeur ${classe}`}>{valeur}</span>
      <span className="r-tuile-libelle">{libelle}</span>
    </div>
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
    <div className="r-semaines">
      <section aria-labelledby="titre-change">
        <h3 id="titre-change" className="r-h3">Ce qui a changé</h3>
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
        <h3 id="titre-semaines" className="r-h3">Part de chaque thème</h3>
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
      <div className="r-deux">
        <div>
          <h3 className="r-h3">Les plus approuvées</h3>
          <ul className="explo-liste">
            {approuvees.map((v) => (
              <LigneThese key={v.sujet.video_id} v={v} ouvrir={ouvrir} />
            ))}
          </ul>
        </div>
        <div>
          <h3 className="r-h3">Les plus contestées</h3>
          {contestees.length === 0 ? (
            <p className="discret petit-texte">
              Trop peu de thèses explicites pour en distinguer les plus
              contestées : toutes figurent à gauche.
            </p>
          ) : (
            <ul className="explo-liste">
              {contestees.map((v) => (
                <LigneThese key={v.sujet.video_id} v={v} ouvrir={ouvrir} />
              ))}
            </ul>
          )}
        </div>
      </div>
      {autres.length > 0 && (
        <button
          className="r-plus"
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
