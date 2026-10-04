"use client";

import { type ReactNode, useEffect, useMemo, useState } from "react";

import Link from "next/link";

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
import { CommentairesVideo } from "@/lib/Commentaires";
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

  return (
    <div className="radar">
      <header className="radar-entete">
        <div>
          <p className="radar-logo">Radar 2027</p>
          <p className="radar-sous-titre">
            Réactions YouTube · panel v1 · mis à jour à chaque calcul
          </p>
        </div>
        <nav aria-label="Écrans">
          <Link href="/radar/semaine">Cette semaine</Link>
          <span className="radar-nav-actif">Vue d'ensemble</span>
          <a href="/admin">Admin</a>
        </nav>
      </header>

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
              : "Aucun commentaire classé pour ces chaînes."}
        </p>
      )}

      {vue && donnees && actif && (
        <>
          <p className="radar-bandeau">
            <span className="radar-badge">
              Données réelles · expérimentation privée
            </span>{" "}
            Ce tableau mesure les réactions des commentateurs YouTube,{" "}
            <strong>pas l'opinion des Français</strong>. Du{" "}
            {dateCourte(vue.courante.debut)} au {dateCourte(vue.courante.fin)}{" "}
            (jour de publication des commentaires) ·{" "}
            {entier(vue.total.commentaires)} commentaires classés, dont{" "}
            {pc(pct(vue.nonPolitique.commentaires, vue.total.commentaires))} non
            politiques.
          </p>
          <div className="radar-trois">
            <ThemesEnMouvement
              lignes={vue.lignes}
              actif={actif.theme}
              choisir={setChoisi}
            />
            <div className="radar-colonne">
              <AgendaOuReactions
                lignes={vue.lignes}
                agenda={agenda}
                choisir={setChoisi}
              />
              <CarteSujets
                lignes={vue.lignes}
                agenda={agenda}
                actif={actif.theme}
                choisir={setChoisi}
              />
              <SignalEmergent lignes={donnees} filtres={filtresEff} />
              {sansSujets && (
                <p className="discret petit-texte">
                  Thèmes des vidéos indisponibles : {sansSujets}
                </p>
              )}
            </div>
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
            />
          </div>
          <ComparaisonSemaines
            lignes={donnees}
            filtres={filtresEff}
            sujets={sujetsBase}
            choisir={setChoisi}
          />
        </>
      )}
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
            {LIBELLES_TYPE[t]}
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

function ThemesEnMouvement({
  lignes,
  actif,
  choisir,
}: {
  lignes: LigneTheme[];
  actif: Theme;
  choisir: (t: Theme) => void;
}) {
  const parVelocite = lignes.some((l) => l.velocite !== null);
  const tries = parVelocite
    ? [...lignes].sort((a, b) => (b.velocite ?? -1) - (a.velocite ?? -1))
    : lignes;
  return (
    <section className="radar-carte" aria-labelledby="titre-themes">
      <h2 id="titre-themes">Thèmes en mouvement</h2>
      <p className="discret petit-texte">
        {parVelocite
          ? "Classés par vélocité"
          : "Classés par volume (vélocité disponible après 5 semaines de données)"}
      </p>
      <ol className="radar-themes">
        {tries.map((l, i) => (
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
              <Courbe serie={l.serie} />
              <span
                className={
                  l.velocite !== null && l.velocite >= 1.5
                    ? "radar-pastille forte"
                    : "radar-pastille"
                }
                title={
                  l.velocite === null
                    ? `Part des commentaires politiques : ${pc(l.part * 100)}`
                    : "Vélocité provisoire, non pondérée par l'audience"
                }
              >
                {l.velocite === null ? pc(l.part * 100) : fois(l.velocite)}
              </span>
            </button>
          </li>
        ))}
      </ol>
      <div className="radar-definition">
        <strong>Vélocité</strong> · commentaires sur 7 jours ÷ moyenne des 4
        semaines précédentes. ×1,0 = activité habituelle. Provisoire : pas
        encore pondérée par l'audience des sources.
      </div>
    </section>
  );
}

function AgendaOuReactions({
  lignes,
  agenda,
  choisir,
}: {
  lignes: LigneTheme[];
  agenda: Map<Theme, Agenda>;
  choisir: (t: Theme) => void;
}) {
  const totalVideos = [...agenda.values()].reduce((a, x) => a + x.videos, 0);
  if (totalVideos === 0)
    return (
      <section className="radar-carte" aria-labelledby="titre-agenda">
        <h2 id="titre-agenda">Agenda des médias ou réactions ?</h2>
        <EnPreparation
          titre="Part de chaque thème dans les vidéos publiées et dans les commentaires"
          attend="le thème des vidéos (relancer la classification après la migration 10)."
        />
      </section>
    );
  const ecarts = lignes
    .filter((l) => l.theme !== "autre")
    .map((l) => {
      const couverture = (agenda.get(l.theme)?.videos ?? 0) / totalVideos;
      return {
        l,
        couverture,
        reactions: l.part,
        ecart: (l.part - couverture) * 100,
      };
    })
    .filter((x) => x.couverture > 0 || x.reactions > 0)
    .sort((a, b) => Math.abs(b.ecart) - Math.abs(a.ecart))
    .slice(0, 8);
  const max = Math.max(
    0.01,
    ...ecarts.flatMap((x) => [x.couverture, x.reactions]),
  );
  return (
    <section className="radar-carte" aria-labelledby="titre-agenda">
      <h2 id="titre-agenda">Agenda des médias ou réactions ?</h2>
      <p className="discret petit-texte">
        Pour chaque thème : sa part dans les vidéos publiées par les médias du
        panel (couverture) et sa part dans les commentaires politiques
        (réactions). Les plus grands écarts d'abord.
      </p>
      <ul className="radar-agenda">
        {ecarts.map(({ l, couverture, reactions, ecart }) => (
          <li key={l.theme}>
            <button
              className="radar-agenda-ligne"
              onClick={() => choisir(l.theme)}
              title={DEFINITIONS_THEMES[l.theme]}
            >
              <span className="radar-agenda-nom">
                {LIBELLES_THEMES[l.theme]}
                <span
                  className={
                    ecart > 0 ? "radar-ecart plus" : "radar-ecart moins"
                  }
                >
                  {ecart > 0
                    ? "plus commenté que couvert"
                    : "plus couvert que commenté"}{" "}
                  · {ecart > 0 ? "+" : "−"}
                  {Math.abs(Math.round(ecart))} pts
                </span>
              </span>
              <span className="radar-agenda-barres" aria-hidden="true">
                <span
                  className="couverture"
                  style={{ width: `${(100 * couverture) / max}%` }}
                />
                <span
                  className="reactions"
                  style={{ width: `${(100 * reactions) / max}%` }}
                />
              </span>
              <span className="radar-agenda-chiffres radar-mono">
                {pc(couverture * 100)} / {pc(reactions * 100)}
              </span>
            </button>
          </li>
        ))}
      </ul>
      <Legende
        items={[
          ["Couverture (vidéos)", "var(--r-couverture)"],
          ["Réactions (commentaires)", "var(--r-orange)"],
        ]}
      />
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
    <section className="radar-carte" aria-labelledby="titre-carte">
      <h2 id="titre-carte">Carte des thèmes</h2>
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
    </section>
  );
}

function SignalEmergent({
  lignes,
  filtres,
}: {
  lignes: Agregat[];
  filtres: Filtres;
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
    <section className="radar-carte" aria-labelledby="titre-signal">
      <h2 id="titre-signal">Signal émergent</h2>
      <p className="petit-texte">
        Part de « Autre » :{" "}
        <strong className="radar-grand">
          {actuelle.toFixed(1).replace(".", ",")} %
        </strong>{" "}
        {avant !== null && (
          <span className={actuelle > avant ? "radar-hausse" : "discret"}>
            {actuelle >= avant ? "+" : ""}
            {(actuelle - avant).toFixed(1).replace(".", ",")} pts sur la période
            précédente
          </span>
        )}
      </p>
      <p className="discret petit-texte">
        Des commentaires que la taxonomie ne sait pas encore ranger. Quand ça
        monte, un sujet nouveau arrive.
      </p>
      <EnPreparation
        titre="Nouveaux regroupements"
        attend="les sous-sujets (regroupement hebdomadaire des commentaires « Autre »)."
      />
    </section>
  );
}

type Rangee = { nom: string; m: Mesures; aPart?: boolean };

function SujetsDuTheme({ actu }: { actu: SujetActu[] }) {
  if (actu.length === 0)
    return (
      <p className="discret petit-texte">
        Aucun sujet d'actualité de 3 vidéos et 2 chaînes sur ce thème pour la
        période.
      </p>
    );
  return (
    <>
      <ul className="radar-sujets-actu">
        {actu.map((x) => (
          <li key={x.id}>
            <details>
              <summary>
                <span>{x.titre}</span>
                <span className="radar-mono discret">
                  {x.videos.length} vidéo{x.videos.length > 1 ? "s" : ""} ·{" "}
                  {x.chaines} chaînes · {entier(x.commentaires)} comm.
                </span>
              </summary>
              <ol className="radar-videos">
                {x.videos.map((v) => (
                  <li key={v.video_id}>
                    <a
                      href={`https://www.youtube.com/watch?v=${v.video_id}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {v.sous_sujet}
                    </a>
                    <span className="discret petit-texte">
                      {v.videos?.sources?.nom} ·{" "}
                      {v.videos
                        ? dateCourte(jourParis(v.videos.publiee_at))
                        : ""}{" "}
                      · {entier(v.videos?.nb_commentaires ?? 0)} commentaires
                      annoncés
                    </span>
                    <CommentairesVideo videoId={v.video_id} />
                  </li>
                ))}
              </ol>
            </details>
          </li>
        ))}
      </ul>
      <p className="discret petit-texte">
        Sujets d'actualité : vidéos regroupées par événement par une IA (titre
        neutre, pas celui d'une vidéo), à partir de 3 vidéos de 2 chaînes.
        Cliquer pour voir les vidéos.
      </p>
    </>
  );
}

type Onglet = "sujets" | "videos" | "accord" | "ton";
const ONGLETS: [Onglet, string][] = [
  ["sujets", "Sujets"],
  ["videos", "Vidéos"],
  ["accord", "Accord"],
  ["ton", "Ton"],
];

function ThemeSelectionne({
  ligne,
  lignes,
  filtres,
  politiques,
  sujets,
  reactions,
  theses,
  rattachements,
}: {
  ligne: LigneTheme;
  lignes: Agregat[];
  filtres: Filtres;
  politiques: boolean;
  sujets: SujetVideo[];
  reactions: Map<string, ReactionVideo>;
  theses: Map<string, These>;
  rattachements: Map<string, Rattachement>;
}) {
  const [courante] = fenetres(lignes, filtres.periode);
  const debattues = videosDebattues(sujets, ligne.theme, reactions, theses);
  const ss = sousSujets(sujets, ligne.theme);
  const actu = sujetsActu(sujets, ligne.theme, rattachements);
  const [toutes, setToutes] = useState(false);
  const [onglet, setOnglet] = useState<Onglet>("sujets");
  const toutesVideos = videosQuiReagissent(
    sujets,
    ligne.theme,
    Number.POSITIVE_INFINITY,
  );
  const videos = toutes ? toutesVideos : toutesVideos.slice(0, 5);
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
      ? [
          {
            nom: "Chaînes politiques · lues à part",
            m: du(["politique"]),
            aPart: true,
          },
        ]
      : []),
  ];
  return (
    <section className="radar-carte" aria-labelledby="titre-detail">
      <p className="discret petit-texte">Thème sélectionné</p>
      <h2 id="titre-detail">{LIBELLES_THEMES[ligne.theme]}</h2>
      <p className="radar-def-theme">{DEFINITIONS_THEMES[ligne.theme]}</p>
      <p className="radar-mono petit-texte">
        {entier(ligne.courant.commentaires)} commentaires ·{" "}
        {pc(ligne.part * 100)} des commentaires politiques · vélocité{" "}
        {fois(ligne.velocite)}
      </p>

      <EnPreparation
        titre="Pourquoi ça bouge · Généré par IA"
        attend="le résumé par Claude à partir des agrégats et des vidéos de la période (sources numérotées, aucune citation, relu avant publication)."
      />
      <div
        className="radar-onglets"
        role="tablist"
        aria-label="Détail du thème"
      >
        {ONGLETS.map(([cle, libelle]) => (
          <button
            key={cle}
            role="tab"
            id={`onglet-${cle}`}
            aria-selected={onglet === cle}
            aria-controls="panneau-theme"
            className={onglet === cle ? "segment actif" : "segment"}
            onClick={() => setOnglet(cle)}
          >
            {libelle}
          </button>
        ))}
      </div>
      <div
        id="panneau-theme"
        role="tabpanel"
        aria-labelledby={`onglet-${onglet}`}
      >
        {onglet === "sujets" && (
          <>
            <h3>De quoi parlent les vidéos</h3>
            {rattachements.size > 0 ? (
              <SujetsDuTheme actu={actu} />
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
            )}
          </>
        )}
        {onglet === "videos" && videos.length > 0 && (
          <>
            <h3>Vidéos qui font réagir</h3>
            <ol className="radar-videos">
              {videos.map((v) => (
                <li key={v.video_id}>
                  <a
                    href={`https://www.youtube.com/watch?v=${v.video_id}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {v.sous_sujet}
                  </a>
                  {rattachements.get(v.video_id)?.sujets?.titre && (
                    <span className="radar-sujet-video">
                      Sujet : {rattachements.get(v.video_id)?.sujets?.titre}
                    </span>
                  )}
                  <span className="discret petit-texte">
                    {v.videos?.sources?.nom} ·{" "}
                    {v.videos ? dateCourte(jourParis(v.videos.publiee_at)) : ""}{" "}
                    · {entier(v.videos?.nb_commentaires ?? 0)} commentaires
                    annoncés
                  </span>
                  <CommentairesVideo videoId={v.video_id} />
                </li>
              ))}
            </ol>
            {toutesVideos.length > 5 && (
              <button
                className="segment"
                onClick={() => setToutes(!toutes)}
                aria-expanded={toutes}
              >
                {toutes
                  ? "Ne garder que les 5 premières"
                  : `Voir toutes les vidéos du thème (${toutesVideos.length})`}
              </button>
            )}
            <p className="discret petit-texte">
              Libellé neutre du sujet (pas le titre de la vidéo) ; commentaires
              annoncés par YouTube, réponses comprises.
            </p>
          </>
        )}

        {onglet === "accord" && (
          <>
            <SurQuoiDaccord debattues={debattues} />

            <h3>Accord avec les vidéos commentées</h3>
            <p className="discret petit-texte">
              Chaque commentaire est comparé à la vidéo sous laquelle il est
              écrit, puis on additionne sur toutes les vidéos d'opinion du
              thème.
            </p>
            {rangees.map((r) => {
              const prononces = r.m.accord + r.m.nuance + r.m.desaccord;
              return (
                <div
                  key={r.nom}
                  className={r.aPart ? "radar-rangee a-part" : "radar-rangee"}
                >
                  <p className="radar-rangee-titre">
                    <span>{r.nom}</span>
                    <span className="radar-mono">
                      {prononces > 0
                        ? `${Math.round(pct(r.m.accord, prononces))} / ${Math.round(pct(r.m.nuance, prononces))} / ${Math.round(pct(r.m.desaccord, prononces))}`
                        : "–"}
                    </span>
                  </p>
                  <Barre
                    titre={`Accord avec les vidéos commentées, ${r.nom}`}
                    total={prononces}
                    segments={[
                      {
                        libelle: "Accord",
                        valeur: r.m.accord,
                        couleur: "var(--r-bleu)",
                      },
                      {
                        libelle: "Nuance",
                        valeur: r.m.nuance,
                        couleur: "var(--r-nuance)",
                      },
                      {
                        libelle: "Désaccord",
                        valeur: r.m.desaccord,
                        couleur: "var(--r-orange)",
                      },
                    ]}
                  />
                </div>
              );
            })}
            <Legende
              items={[
                ["Accord", "var(--r-bleu)"],
                ["Nuance", "var(--r-nuance)"],
                ["Désaccord", "var(--r-orange)"],
              ]}
            />
            <p className="discret petit-texte">
              Vidéos d'opinion uniquement (une seule thèse à approuver ou
              contester) ; les commentaires qui ne se prononcent pas sont
              exclus. Ne dit pas si les gens sont pour ou contre un sujet.
            </p>
          </>
        )}

        {onglet === "ton" && (
          <>
            <h3>Tonalité et hostilité</h3>
            {rangees.map((r) => (
              <div
                key={r.nom}
                className={r.aPart ? "radar-rangee a-part" : "radar-rangee"}
              >
                <p className="radar-rangee-titre">
                  <span>{r.nom}</span>
                  <span className="radar-mono">
                    {pc(pct(r.m.hostiles, r.m.commentaires))} hostiles
                  </span>
                </p>
                <Barre
                  titre={`Tonalité, ${r.nom}`}
                  total={r.m.commentaires}
                  segments={[
                    {
                      libelle: "Positive",
                      valeur: r.m.positifs,
                      couleur: "var(--r-bleu)",
                    },
                    {
                      libelle: "Neutre",
                      valeur: r.m.neutres,
                      couleur: "var(--r-nuance)",
                    },
                    {
                      libelle: "Négative",
                      valeur: r.m.negatifs,
                      couleur: "var(--r-orange)",
                    },
                  ]}
                />
              </div>
            ))}
            <Legende
              items={[
                ["Positive", "var(--r-bleu)"],
                ["Neutre", "var(--r-nuance)"],
                ["Négative", "var(--r-orange)"],
              ]}
            />
          </>
        )}
      </div>
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
      <section className="radar-carte" aria-labelledby="titre-change">
        <h2 id="titre-change">Ce qui a changé</h2>
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
      <section className="radar-carte" aria-labelledby="titre-semaines">
        <h2 id="titre-semaines">Semaine par semaine</h2>
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

function LigneThese({ v }: { v: VideoDebattue }) {
  const r = v.reaction;
  const lien = `https://www.youtube.com/watch?v=${v.sujet.video_id}`;
  return (
    <li className="radar-these">
      <p className="radar-these-texte">
        {v.these ? `« ${v.these.these} »` : v.sujet.sous_sujet}
        {!v.these && (
          <span className="discret"> (thèse effacée après 30 jours)</span>
        )}
      </p>
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
      <p className="discret petit-texte">
        {pc(v.partAccord * 100)} d'accord · {pc(v.partDesaccord * 100)} en
        désaccord · {entier(v.prononces)} commentaires se prononcent ·{" "}
        {v.sujet.videos?.sources?.nom} ·{" "}
        {v.sujet.videos ? dateCourte(jourParis(v.sujet.videos.publiee_at)) : ""}{" "}
        ·{" "}
        <a href={lien} target="_blank" rel="noreferrer">
          Voir la vidéo ↗
        </a>
      </p>
    </li>
  );
}

function SurQuoiDaccord({ debattues }: { debattues: VideoDebattue[] }) {
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
  return (
    <>
      <h3>Sur quoi les commentaires sont d'accord ou pas</h3>
      {debattues.length === 0 ? (
        <EnPreparation
          titre="Thèses des vidéos d'opinion"
          attend={`les thèses et l'accord vidéo par vidéo (migration 11, relance de la classification puis des agrégats), et au moins ${MIN_PRONONCES} commentaires qui se prononcent par vidéo.`}
        />
      ) : (
        <>
          {approuvees.length > 0 && (
            <>
              <p className="radar-sous-titre-bloc">
                Thèses les plus approuvées
              </p>
              <ul className="radar-theses">
                {approuvees.map((v) => (
                  <LigneThese key={v.sujet.video_id} v={v} />
                ))}
              </ul>
            </>
          )}
          {contestees.length > 0 && (
            <>
              <p className="radar-sous-titre-bloc">
                Thèses les plus contestées
              </p>
              <ul className="radar-theses">
                {contestees.map((v) => (
                  <LigneThese key={v.sujet.video_id} v={v} />
                ))}
              </ul>
            </>
          )}
          {autres.length > 0 && (
            <button
              className="segment"
              onClick={() => setIncertaines(!incertaines)}
              aria-expanded={incertaines}
            >
              {incertaines
                ? "Masquer les thèses incertaines"
                : `Thèses incertaines ou effacées (${autres.length})`}
            </button>
          )}
          {incertaines && (
            <ul className="radar-theses">
              {autres.map((v) => (
                <LigneThese key={v.sujet.video_id} v={v} />
              ))}
            </ul>
          )}
          <p className="discret petit-texte">
            Thèse résumée par une IA à partir du titre et de la description, pas
            du contenu de la vidéo : vérifier avec le lien. Seules les thèses
            explicites sont classées ; vidéos d'au moins {MIN_PRONONCES}{" "}
            commentaires qui se prononcent.
          </p>
        </>
      )}
    </>
  );
}
