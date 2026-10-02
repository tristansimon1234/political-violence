"use client";

import { type ReactNode, useEffect, useMemo, useState } from "react";

import { AccesAdmin } from "@/lib/AccesAdmin";
import { supabase } from "@/lib/supabase";
import { LIBELLES_THEMES, LIBELLES_TYPE, type Theme, type TypeSource } from "@/lib/taxonomie";
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
const entier = (n: number) => Math.round(n).toLocaleString("fr-FR");
const pc = (n: number) => `${Math.round(n)} %`;
const dateCourte = (j: string) =>
  j
    ? new Date(`${j}T12:00:00Z`).toLocaleDateString("fr-FR", { day: "numeric", month: "short" })
    : "–";
const fois = (v: number | null) => (v === null ? "–" : `×${v.toFixed(1).replace(".", ",")}`);

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
  const [filtres, setFiltres] = useState<Filtres>({
    periode: "tout",
    types: PUBLICS,
    format: "tous",
  });
  const [politiques, setPolitiques] = useState(false);
  const [choisi, setChoisi] = useState<Theme | null>(null);

  useEffect(() => {
    chargerAgregats()
      .then((l) => setLignes(depuisCollecte(l)))
      .catch((e: unknown) => setErreur(e instanceof Error ? e.message : String(e)));
  }, []);

  // Table vide : aucun calcul (pas de dernier jour, donc pas de fenêtre).
  const vue = useMemo(
    () => (lignes && lignes.length > 0 ? themes(lignes, filtres) : null),
    [lignes, filtres],
  );
  const actif = vue?.lignes.find((l) => l.theme === choisi) ?? vue?.lignes[0] ?? null;

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
          <span
            className="radar-nav-inactif"
            title="Après la détection des sujets d'actu (étape 6)"
          >
            Cette semaine
          </span>
          <span className="radar-nav-actif">Vue d'ensemble</span>
          <a href="/admin">Admin</a>
        </nav>
      </header>

      {erreur && <p className="erreur radar-marge">{erreur}</p>}
      {!lignes && !erreur && <p className="discret radar-marge">Chargement des agrégats…</p>}
      {lignes && lignes.length === 0 && (
        <p className="discret radar-marge">
          Aucun agrégat : lancer la classification puis le workflow « Agrégats ».
        </p>
      )}

      {vue && lignes && actif && (
        <>
          <BarreFiltres
            filtres={filtres}
            setFiltres={setFiltres}
            politiques={politiques}
            setPolitiques={setPolitiques}
          />
          <p className="radar-bandeau">
            <span className="radar-badge">Données réelles · expérimentation privée</span> Ce tableau
            mesure les réactions des commentateurs YouTube,{" "}
            <strong>pas l'opinion des Français</strong>. Du {dateCourte(vue.courante.debut)} au{" "}
            {dateCourte(vue.courante.fin)} (jour de publication des commentaires) ·{" "}
            {entier(vue.total.commentaires)} commentaires classés, dont{" "}
            {pc(pct(vue.nonPolitique.commentaires, vue.total.commentaires))} non politiques.
          </p>
          <div className="radar-trois">
            <ThemesEnMouvement lignes={vue.lignes} actif={actif.theme} choisir={setChoisi} />
            <div className="radar-colonne">
              <CarteSujets />
              <SignalEmergent lignes={lignes} filtres={filtres} />
            </div>
            <ThemeSelectionne
              ligne={actif}
              lignes={lignes}
              filtres={filtres}
              politiques={politiques}
            />
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
              className={l.theme === actif ? "radar-theme actif" : "radar-theme"}
              onClick={() => choisir(l.theme)}
              aria-pressed={l.theme === actif}
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
        <strong>Vélocité</strong> · commentaires sur 7 jours ÷ moyenne des 4 semaines précédentes.
        ×1,0 = activité habituelle. Provisoire : pas encore pondérée par l'audience des sources.
      </div>
    </section>
  );
}

function EnPreparation({
  titre,
  attend,
  children,
}: {
  titre: string;
  attend: string;
  children?: ReactNode;
}) {
  return (
    <div className="radar-preparation">
      <p className="radar-preparation-titre">
        {titre} <span className="radar-badge-gris">En préparation</span>
      </p>
      {children}
      <p className="discret petit-texte">Attend : {attend}</p>
    </div>
  );
}

function CarteSujets() {
  return (
    <section className="radar-carte" aria-labelledby="titre-carte">
      <h2 id="titre-carte">Carte des sujets</h2>
      <p className="discret petit-texte">Attention (vues) × intensité (commentaires par vue)</p>
      <div className="radar-quadrants" aria-hidden="true">
        <div>
          <strong>Minorité mobilisée</strong>
          <span>peu vu, très discuté</span>
        </div>
        <div>
          <strong>Débat de fond</strong>
          <span>très vu, très discuté</span>
        </div>
        <div>
          <strong>Bruit de fond</strong>
          <span>peu vu, peu discuté</span>
        </div>
        <div>
          <strong>Regardé en silence</strong>
          <span>très vu, peu discuté</span>
        </div>
      </div>
      <EnPreparation
        titre="Positions des thèmes sur la carte"
        attend="le thème des vidéos, pour répartir les vues entre thèmes (prochain chantier)."
      />
    </section>
  );
}

function SignalEmergent({ lignes, filtres }: { lignes: Agregat[]; filtres: Filtres }) {
  const [courante, precedente] = fenetres(lignes, filtres.periode);
  const part = (w: typeof courante) => {
    const politiques = filtrer(lignes, filtres).filter(
      (l) => dans(l, w) && l.theme !== "non_politique",
    );
    const total = additionner(politiques).commentaires;
    const autre = additionner(politiques.filter((l) => l.theme === "autre")).commentaires;
    return pct(autre, total);
  };
  const actuelle = part(courante);
  const avant = precedente ? part(precedente) : null;
  return (
    <section className="radar-carte" aria-labelledby="titre-signal">
      <h2 id="titre-signal">Signal émergent</h2>
      <p className="petit-texte">
        Part de « Autre » :{" "}
        <strong className="radar-grand">{actuelle.toFixed(1).replace(".", ",")} %</strong>{" "}
        {avant !== null && (
          <span className={actuelle > avant ? "radar-hausse" : "discret"}>
            {actuelle >= avant ? "+" : ""}
            {(actuelle - avant).toFixed(1).replace(".", ",")} pts sur la période précédente
          </span>
        )}
      </p>
      <p className="discret petit-texte">
        Des commentaires que la taxonomie ne sait pas encore ranger. Quand ça monte, un sujet
        nouveau arrive.
      </p>
      <EnPreparation
        titre="Nouveaux regroupements"
        attend="les sous-sujets (regroupement hebdomadaire des commentaires « Autre »)."
      />
    </section>
  );
}

type Segment = { libelle: string; valeur: number; couleur: string };

function Barre({ segments, total, titre }: { segments: Segment[]; total: number; titre: string }) {
  const description = segments
    .map((s) => `${s.libelle} ${Math.round(pct(s.valeur, total))} %`)
    .join(", ");
  return (
    <div className="radar-barre" role="img" aria-label={`${titre} : ${description}`}>
      {segments.map((s) => (
        <span
          key={s.libelle}
          style={{ width: `${pct(s.valeur, total)}%`, background: s.couleur }}
        />
      ))}
    </div>
  );
}

function Legende({ items }: { items: [string, string][] }) {
  return (
    <p className="radar-legende">
      {items.map(([libelle, couleur]) => (
        <span key={libelle}>
          <i style={{ background: couleur }} aria-hidden="true" /> {libelle}
        </span>
      ))}
    </p>
  );
}

type Rangee = { nom: string; m: Mesures; aPart?: boolean };

function ThemeSelectionne({
  ligne,
  lignes,
  filtres,
  politiques,
}: {
  ligne: LigneTheme;
  lignes: Agregat[];
  filtres: Filtres;
  politiques: boolean;
}) {
  const [courante] = fenetres(lignes, filtres.periode);
  const du = (types: TypeSource[]) =>
    additionner(
      filtrer(lignes, filtres, types).filter((l) => l.theme === ligne.theme && dans(l, courante)),
    );
  const rangees: Rangee[] = [
    { nom: "Ensemble", m: du(filtres.types) },
    ...filtres.types.map((t) => ({ nom: LIBELLES_TYPE[t], m: du([t]) })),
    ...(politiques
      ? [{ nom: "Chaînes politiques · lues à part", m: du(["politique"]), aPart: true }]
      : []),
  ];
  return (
    <section className="radar-carte" aria-labelledby="titre-detail">
      <p className="discret petit-texte">Thème sélectionné</p>
      <h2 id="titre-detail">{LIBELLES_THEMES[ligne.theme]}</h2>
      <p className="radar-mono petit-texte">
        {entier(ligne.courant.commentaires)} commentaires · {pc(ligne.part * 100)} des commentaires
        politiques · vélocité {fois(ligne.velocite)}
      </p>

      <EnPreparation
        titre="Pourquoi ça bouge · Généré par IA"
        attend="le résumé par Claude à partir des agrégats et des vidéos de la période (sources numérotées, aucune citation, relu avant publication)."
      />
      <EnPreparation
        titre="Sous-sujets qui portent la hausse"
        attend="le thème et le sous-sujet des vidéos."
      />

      <h3>Accord avec la vidéo, par type de source</h3>
      {rangees.map((r) => {
        const prononces = r.m.accord + r.m.nuance + r.m.desaccord;
        return (
          <div key={r.nom} className={r.aPart ? "radar-rangee a-part" : "radar-rangee"}>
            <p className="radar-rangee-titre">
              <span>{r.nom}</span>
              <span className="radar-mono">
                {prononces > 0
                  ? `${Math.round(pct(r.m.accord, prononces))} / ${Math.round(pct(r.m.nuance, prononces))} / ${Math.round(pct(r.m.desaccord, prononces))}`
                  : "–"}
              </span>
            </p>
            <Barre
              titre={`Accord avec la vidéo, ${r.nom}`}
              total={prononces}
              segments={[
                { libelle: "Accord", valeur: r.m.accord, couleur: "var(--r-bleu)" },
                { libelle: "Nuance", valeur: r.m.nuance, couleur: "var(--r-nuance)" },
                { libelle: "Désaccord", valeur: r.m.desaccord, couleur: "var(--r-orange)" },
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
        Accord avec le propos de la vidéo commentée, sur les vidéos d'opinion uniquement (les
        commentaires qui ne se prononcent pas sont exclus). Ne dit pas si les gens sont pour ou
        contre un sujet.
      </p>

      <h3>Tonalité et hostilité</h3>
      {rangees.map((r) => (
        <div key={r.nom} className={r.aPart ? "radar-rangee a-part" : "radar-rangee"}>
          <p className="radar-rangee-titre">
            <span>{r.nom}</span>
            <span className="radar-mono">{pc(pct(r.m.hostiles, r.m.commentaires))} hostiles</span>
          </p>
          <Barre
            titre={`Tonalité, ${r.nom}`}
            total={r.m.commentaires}
            segments={[
              { libelle: "Positive", valeur: r.m.positifs, couleur: "var(--r-bleu)" },
              { libelle: "Neutre", valeur: r.m.neutres, couleur: "var(--r-nuance)" },
              { libelle: "Négative", valeur: r.m.negatifs, couleur: "var(--r-orange)" },
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

      <EnPreparation
        titre="Exemples de commentaires"
        attend="le drill-down : quelques commentaires des 30 derniers jours, relus en direct sur YouTube, avec un lien vers la vidéo."
      />
    </section>
  );
}

function Courbe({ serie }: { serie: number[] }) {
  const max = Math.max(1, ...serie);
  const l = 52;
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
