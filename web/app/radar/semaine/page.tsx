"use client";

import { useEffect, useMemo, useRef, useState } from "react";

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
  type VideoDuSujet,
  cartesSujets,
  decaler,
  dernierJour,
  semaineDe,
  thesesDuSujet,
} from "@/lib/cetteSemaine";
import { chargerSujets, chargerTout } from "@/lib/chargement";
import {
  LIBELLES_THEMES,
  LIBELLES_TYPE,
  type TypeSource,
} from "@/lib/taxonomie";
import {
  Barre,
  EnPreparation,
  Legende,
  dateCourte,
  entier,
  pc,
} from "@/lib/ui";
import { pct } from "@/lib/vueEnsemble";

const PUBLICS: TypeSource[] = ["media_traditionnel", "media_natif"];
const MIN_PRONONCES_SUJET = 20;
const lien = (v: string) => `https://www.youtube.com/watch?v=${v}`;

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
  const [erreur, setErreur] = useState("");
  const [types, setTypes] = useState<TypeSource[]>(PUBLICS);
  const [debut, setDebut] = useState<string | null>(null);
  const [tous, setTous] = useState(false);
  const [ouvert, setOuvert] = useState<CarteSujet | null>(null);

  useEffect(() => {
    chargerSujets()
      .then(setSujets)
      .catch((e: unknown) =>
        setErreur(e instanceof Error ? e.message : String(e)),
      );
    chargerTout<Rattachement>(
      "sujets_videos",
      "video_id,sujet_id,sujets(titre,premier_jour)",
    )
      .then((l) => setRattachements(new Map(l.map((r) => [r.video_id, r]))))
      .catch((e: unknown) =>
        setErreur(e instanceof Error ? e.message : String(e)),
      );
    chargerTout<ReactionVideo>("agregats_videos", "*")
      .then((l) => setReactions(new Map(l.map((r) => [r.video_id, r]))))
      .catch(() => setReactions(new Map()));
    chargerTout<These>("videos_theses", "video_id,these,explicite")
      .then((l) => setTheses(new Map(l.map((t) => [t.video_id, t]))))
      .catch(() => setTheses(new Map()));
  }, []);

  const dernier = useMemo(
    () => (sujets ? dernierJour(sujets) : null),
    [sujets],
  );
  const periode: Periode | null = useMemo(() => {
    if (!dernier) return null;
    return debut ? { debut, fin: decaler(debut, 6) } : semaineDe(dernier);
  }, [dernier, debut]);
  const cartes = useMemo(
    () =>
      sujets && periode
        ? cartesSujets(sujets, periode, types, rattachements, reactions, theses)
        : [],
    [sujets, periode, types, rattachements, reactions, theses],
  );
  const premier = "2026-09-01";
  const incomplete = periode && dernier ? periode.fin > dernier : false;

  const basculer = (t: TypeSource) => {
    const n = types.includes(t) ? types.filter((x) => x !== t) : [...types, t];
    if (n.length) setTypes(n);
  };

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
          <span className="radar-nav-actif">Cette semaine</span>
          <a href="/radar">Vue d'ensemble</a>
          <a href="/admin">Admin</a>
        </nav>
      </header>

      {erreur && <p className="erreur radar-marge">{erreur}</p>}
      {!sujets && !erreur && <p className="discret radar-marge">Chargement…</p>}

      {periode && (
        <>
          <div className="radar-filtres" role="group" aria-label="Filtres">
            <fieldset>
              <legend>Semaine</legend>
              <button
                className="segment"
                onClick={() => setDebut(decaler(periode.debut, -7))}
                disabled={periode.debut <= premier}
                aria-label="Semaine précédente"
              >
                ‹
              </button>
              <span className="radar-semaine-nom">
                Du {dateCourte(periode.debut)} au {dateCourte(periode.fin)}
                {incomplete ? " (en cours)" : ""}
              </span>
              <button
                className="segment"
                onClick={() => setDebut(decaler(periode.debut, 7))}
                disabled={!dernier || periode.fin >= dernier}
                aria-label="Semaine suivante"
              >
                ›
              </button>
            </fieldset>
            <fieldset>
              <legend>Réactions sous</legend>
              {PUBLICS.map((t) => (
                <button
                  key={t}
                  className={types.includes(t) ? "segment actif" : "segment"}
                  aria-pressed={types.includes(t)}
                  onClick={() => basculer(t)}
                >
                  {LIBELLES_TYPE[t]}
                </button>
              ))}
            </fieldset>
          </div>
          <p className="radar-bandeau">
            <span className="radar-badge">
              Données réelles · expérimentation privée
            </span>{" "}
            Ce tableau mesure les réactions des commentateurs YouTube,{" "}
            <strong>pas l'opinion des Français</strong>. Sujets d'actualité :
            vidéos publiées dans la semaine, regroupées par événement par une IA
            (au moins 3 vidéos de 2 chaînes).
          </p>

          <div className="radar-semaine">
            <section aria-labelledby="titre-sujets">
              <h2 id="titre-sujets" className="radar-titre-section">
                Les sujets de la semaine
              </h2>
              {cartes.length === 0 ? (
                <p className="discret">
                  Aucun sujet d'actualité cette semaine (lancer le workflow «
                  Sujets » après la classification des vidéos).
                </p>
              ) : (
                <>
                  <ol className="radar-cartes-sujets">
                    {(tous ? cartes : cartes.slice(0, 5)).map((c, i) => (
                      <li key={c.id}>
                        <CarteDuSujet
                          c={c}
                          rang={i + 1}
                          ouvrir={() => setOuvert(c)}
                        />
                      </li>
                    ))}
                  </ol>
                  {cartes.length > 5 && (
                    <button
                      className="segment"
                      onClick={() => setTous(!tous)}
                      aria-expanded={tous}
                    >
                      {tous
                        ? "Ne garder que les 5 premiers"
                        : `Voir tous les sujets (${cartes.length})`}
                    </button>
                  )}
                </>
              )}
            </section>
            <aside className="radar-colonne">
              <CeQuiAChange cartes={cartes} ouvrir={setOuvert} />
              <CouvertureOuReactions cartes={cartes} ouvrir={setOuvert} />
            </aside>
          </div>
        </>
      )}
      <Modale c={ouvert} fermer={() => setOuvert(null)} />
    </div>
  );
}

function evolution(c: CarteSujet): string {
  if (c.nouveau) return "apparu cette semaine";
  if (c.precedent === 0)
    return "aucun commentaire classé la semaine précédente";
  const d = (c.classes / c.precedent - 1) * 100;
  return `${d >= 0 ? "+" : "−"}${Math.abs(Math.round(d))} % sur la semaine précédente`;
}

function Courbe({ jours }: { jours: number[] }) {
  const max = Math.max(1, ...jours);
  return (
    <svg
      viewBox="0 0 70 20"
      className="radar-courbe-jours"
      role="img"
      aria-label={`Vidéos par jour : ${jours.join(", ")}`}
    >
      {jours.map((n, i) => (
        <rect
          key={i}
          x={i * 10 + 1}
          width={8}
          y={20 - (18 * n) / max}
          height={(18 * n) / max}
        />
      ))}
    </svg>
  );
}

function Positions({
  c,
  titre,
}: {
  c: { accord: number; nuance: number; desaccord: number };
  titre: string;
}) {
  const prononces = c.accord + c.nuance + c.desaccord;
  if (prononces < MIN_PRONONCES_SUJET)
    return (
      <p className="discret petit-texte">
        Accord avec les vidéos : trop peu de commentaires qui se prononcent.
      </p>
    );
  return (
    <>
      <p className="radar-rangee-titre">
        <span>Accord avec les vidéos d'opinion</span>
        <span className="radar-mono">
          {Math.round(pct(c.accord, prononces))} /{" "}
          {Math.round(pct(c.nuance, prononces))} /{" "}
          {Math.round(pct(c.desaccord, prononces))}
        </span>
      </p>
      <Barre
        titre={titre}
        total={prononces}
        segments={[
          { libelle: "Accord", valeur: c.accord, couleur: "var(--r-bleu)" },
          { libelle: "Nuance", valeur: c.nuance, couleur: "var(--r-nuance)" },
          {
            libelle: "Désaccord",
            valeur: c.desaccord,
            couleur: "var(--r-orange)",
          },
        ]}
      />
    </>
  );
}

function CarteDuSujet({
  c,
  rang,
  ouvrir,
}: {
  c: CarteSujet;
  rang: number;
  ouvrir: () => void;
}) {
  return (
    <article className="radar-carte radar-carte-sujet">
      <header>
        <span className="radar-rang">{rang}</span>
        <h3>
          <button className="radar-lien radar-titre-sujet" onClick={ouvrir}>
            {c.titre}
          </button>
        </h3>
        {c.nouveau && <span className="radar-etiquette hausse">Nouveau</span>}
      </header>
      <p className="radar-themes-sujet">
        {c.themes.slice(0, 3).map((t) => (
          <span key={t.theme} className="radar-puce">
            {LIBELLES_THEMES[t.theme]}
          </span>
        ))}
      </p>
      <div className="radar-chiffres-sujet">
        <span className="radar-mono">
          {c.videos.length} vidéos · {c.chaines} chaînes · {entier(c.classes)}{" "}
          commentaires classés
        </span>
        <span className="discret petit-texte">{evolution(c)}</span>
        <Courbe jours={c.parJour} />
      </div>
      <OuCaReagit c={c} />
      <Positions c={c} titre={`Accord avec les vidéos, ${c.titre}`} />
      <p className="radar-rangee-titre">
        <span>Commentaires hostiles</span>
        <span className="radar-mono">
          {c.classes ? pc(pct(c.hostiles, c.classes)) : "–"}
        </span>
      </p>
      <button className="segment" onClick={ouvrir}>
        Voir les vidéos et le détail
      </button>
    </article>
  );
}

function OuCaReagit({ c }: { c: CarteSujet }) {
  const total = Object.values(c.parType).reduce((a, b) => a + (b ?? 0), 0);
  if (!total) return null;
  return (
    <>
      <p className="radar-rangee-titre">
        <span>Où ça réagit</span>
        <span className="radar-mono">
          {PUBLICS.filter((t) => c.parType[t])
            .map(
              (t) =>
                `${LIBELLES_TYPE[t]} ${Math.round(pct(c.parType[t] ?? 0, total))} %`,
            )
            .join(" · ")}
        </span>
      </p>
      <Barre
        titre={`Commentaires par type de source, ${c.titre}`}
        total={total}
        segments={[
          {
            libelle: LIBELLES_TYPE.media_traditionnel,
            valeur: c.parType.media_traditionnel ?? 0,
            couleur: "var(--r-couverture)",
          },
          {
            libelle: LIBELLES_TYPE.media_natif,
            valeur: c.parType.media_natif ?? 0,
            couleur: "var(--r-bleu)",
          },
        ]}
      />
    </>
  );
}

function CeQuiAChange({
  cartes,
  ouvrir,
}: {
  cartes: CarteSujet[];
  ouvrir: (c: CarteSujet) => void;
}) {
  const nouveaux = cartes.filter((c) => c.nouveau).slice(0, 5);
  const hausses = cartes
    .filter((c) => !c.nouveau && c.precedent > 0 && c.classes > c.precedent)
    .sort((a, b) => b.classes - b.precedent - (a.classes - a.precedent))
    .slice(0, 5);
  return (
    <section className="radar-carte" aria-labelledby="titre-change">
      <h2 id="titre-change">Ce qui a changé</h2>
      <p className="discret petit-texte">
        Face à la semaine précédente, en commentaires classés.
      </p>
      {nouveaux.length + hausses.length === 0 && (
        <p className="discret petit-texte">Rien de notable.</p>
      )}
      <ul className="radar-changements">
        {nouveaux.map((c) => (
          <li key={c.id}>
            <span className="radar-etiquette hausse">Nouveau</span>
            <button className="radar-lien" onClick={() => ouvrir(c)}>
              {c.titre}
            </button>
            <span className="radar-mono">{entier(c.classes)} comm.</span>
          </li>
        ))}
        {hausses.map((c) => (
          <li key={c.id}>
            <span className="radar-etiquette hausse">En hausse</span>
            <button className="radar-lien" onClick={() => ouvrir(c)}>
              {c.titre}
            </button>
            <span className="radar-mono">
              {entier(c.precedent)} → {entier(c.classes)}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function CouvertureOuReactions({
  cartes,
  ouvrir,
}: {
  cartes: CarteSujet[];
  ouvrir: (c: CarteSujet) => void;
}) {
  const videos = cartes.reduce((a, c) => a + c.videos.length, 0);
  const classes = cartes.reduce((a, c) => a + c.classes, 0);
  if (!videos || !classes) return null;
  const lignes = cartes
    .map((c) => ({
      c,
      couverture: c.videos.length / videos,
      reactions: c.classes / classes,
    }))
    .map((x) => ({ ...x, ecart: (x.reactions - x.couverture) * 100 }))
    .sort((a, b) => Math.abs(b.ecart) - Math.abs(a.ecart))
    .slice(0, 6);
  return (
    <section className="radar-carte" aria-labelledby="titre-decalage">
      <h2 id="titre-decalage">Couverture ou réactions ?</h2>
      <p className="discret petit-texte">
        Part de chaque sujet dans les vidéos des sujets de la semaine, face à sa
        part dans leurs commentaires. Les plus grands écarts d'abord.
      </p>
      <ul className="radar-changements">
        {lignes.map(({ c, couverture, reactions, ecart }) => (
          <li key={c.id}>
            <span
              className={
                ecart > 0 ? "radar-etiquette hausse" : "radar-etiquette baisse"
              }
            >
              {ecart > 0 ? "Plus commenté" : "Plus couvert"}
            </span>
            <button className="radar-lien" onClick={() => ouvrir(c)}>
              {c.titre}
            </button>
            <span className="radar-mono">
              {pc(couverture * 100)} / {pc(reactions * 100)}
            </span>
          </li>
        ))}
      </ul>
      <p className="discret petit-texte">Vidéos / commentaires.</p>
    </section>
  );
}

function LigneVideo({ v }: { v: VideoDuSujet }) {
  const r = v.reaction;
  const prononces = r ? r.accord + r.nuance + r.desaccord : 0;
  return (
    <li>
      <a href={lien(v.video_id)} target="_blank" rel="noreferrer">
        {v.sous_sujet}
      </a>
      <span className="discret petit-texte">
        {v.chaine} · {dateCourte(v.jour)} ·{" "}
        {r
          ? `${entier(r.commentaires)} commentaires classés`
          : `${entier(v.annonces)} commentaires annoncés`}
        {prononces >= MIN_PRONONCES_SUJET && r
          ? ` · ${Math.round(pct(r.accord, prononces))} % d'accord`
          : ""}
      </span>
    </li>
  );
}

function Modale({ c, fermer }: { c: CarteSujet | null; fermer: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (c && !d.open) d.showModal();
    if (!c && d.open) d.close();
  }, [c]);
  const theses = c ? thesesDuSujet(c) : [];
  const parAccord = [...theses].sort(
    (a, b) =>
      pct(b.reaction!.accord, b.prononces) -
      pct(a.reaction!.accord, a.prononces),
  );
  return (
    <dialog
      ref={ref}
      className="radar-modale"
      onClose={fermer}
      aria-labelledby="titre-modale"
    >
      {c && (
        <div className="radar">
          <header className="radar-modale-entete">
            <div>
              <p className="discret petit-texte">Sujet d'actualité</p>
              <h2 id="titre-modale">{c.titre}</h2>
              <p className="radar-mono petit-texte">
                {c.videos.length} vidéos · {c.chaines} chaînes ·{" "}
                {entier(c.classes)} commentaires classés · {evolution(c)}
              </p>
            </div>
            <button className="segment" onClick={fermer} aria-label="Fermer">
              ✕
            </button>
          </header>
          <p className="radar-themes-sujet">
            {c.themes.map((t) => (
              <span key={t.theme} className="radar-puce">
                {LIBELLES_THEMES[t.theme]} {pc(t.part * 100)}
              </span>
            ))}
          </p>
          <div className="radar-modale-grille">
            <div>
              <OuCaReagit c={c} />
              <Positions c={c} titre={`Accord avec les vidéos, ${c.titre}`} />
              <p className="radar-rangee-titre">
                <span>Commentaires hostiles</span>
                <span className="radar-mono">
                  {c.classes ? pc(pct(c.hostiles, c.classes)) : "–"}
                </span>
              </p>
              <Legende
                items={[
                  ["Accord", "var(--r-bleu)"],
                  ["Nuance", "var(--r-nuance)"],
                  ["Désaccord", "var(--r-orange)"],
                ]}
              />
              {parAccord.length > 0 && (
                <>
                  <h3>Thèses les plus approuvées et contestées</h3>
                  <ul className="radar-theses">
                    {[
                      ...parAccord.slice(0, 2),
                      ...parAccord
                        .slice(-2)
                        .filter((x) => !parAccord.slice(0, 2).includes(x)),
                    ].map((v) => (
                      <li key={v.video_id}>
                        <p className="radar-these">« {v.these?.these} »</p>
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
                        <p className="discret petit-texte">
                          {Math.round(pct(v.reaction!.accord, v.prononces))} %
                          d'accord · {v.prononces} commentaires se prononcent ·{" "}
                          {v.chaine} ·{" "}
                          <a
                            href={lien(v.video_id)}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Voir la vidéo ↗
                          </a>
                        </p>
                      </li>
                    ))}
                  </ul>
                  <p className="discret petit-texte">
                    Thèse résumée par une IA à partir du titre et de la
                    description, pas du contenu de la vidéo.
                  </p>
                </>
              )}
              <EnPreparation
                titre="Exemples de commentaires"
                attend="quelques commentaires des 30 derniers jours par sujet, lus dans les données stockées, texte non modifié, sans pseudo, avec le lien vers la vidéo."
              />
            </div>
            <div>
              <h3>Les vidéos ({c.videos.length})</h3>
              <ol className="radar-videos">
                {c.videos.map((v) => (
                  <LigneVideo key={v.video_id} v={v} />
                ))}
              </ol>
              <p className="discret petit-texte">
                Libellé neutre écrit par une IA (pas le titre de la vidéo).
              </p>
            </div>
          </div>
        </div>
      )}
    </dialog>
  );
}
