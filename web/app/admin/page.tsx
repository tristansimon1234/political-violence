"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { AccesAdmin } from "@/lib/AccesAdmin";
import { type EntreeJournal, type Source, supabase } from "@/lib/supabase";
import {
  LIBELLES_TYPE,
  SEUIL_ACTIVITE_VIDEOS,
  SOUS_TYPES_PAR_TYPE,
  TYPES_SOURCE,
  type TypeSource,
} from "@/lib/taxonomie";

type Onglet = "panel" | "equilibre" | "journal";

const nombre = (n: number | null) => (n === null ? "–" : n.toLocaleString("fr-FR"));
const date = (d: string | null) => (d ? new Date(d).toLocaleDateString("fr-FR") : "–");

export default function Admin() {
  return (
    <AccesAdmin titre="Radar 2027 · Admin" retour="/admin">
      {(email) => <Espace email={email} />}
    </AccesAdmin>
  );
}

function Espace({ email }: { email: string }) {
  const [admin, setAdmin] = useState<boolean | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [journal, setJournal] = useState<EntreeJournal[]>([]);
  const [onglet, setOnglet] = useState<Onglet>("panel");
  const [erreur, setErreur] = useState("");

  const charger = useCallback(async () => {
    const client = supabase();
    const { data: estAdmin, error: e1 } = await client.rpc("est_admin");
    if (e1) return setErreur(e1.message);
    setAdmin(Boolean(estAdmin));
    if (!estAdmin) return;
    const [s, j] = await Promise.all([
      client.from("sources").select("*").order("type").order("sous_type").order("nom"),
      client
        .from("sources_journal")
        .select("*")
        .order("created_at", { ascending: false })
        .limit(200),
    ]);
    if (s.error) return setErreur(s.error.message);
    if (j.error) return setErreur(j.error.message);
    setSources(s.data as Source[]);
    setJournal(j.data as EntreeJournal[]);
  }, []);

  useEffect(() => {
    void charger();
  }, [charger]);

  async function basculer(source: Source) {
    const action = source.active ? "Mettre en pause" : "Réactiver";
    if (!window.confirm(`${action} « ${source.nom} » ?`)) return;
    const { error } = await supabase()
      .from("sources")
      .update({ active: !source.active })
      .eq("id", source.id);
    if (error) return setErreur(error.message);
    await charger();
  }

  return (
    <main>
      <h1>Radar 2027 · Admin</h1>
      <p className="discret">
        {email} ·{" "}
        <button className="petit" onClick={() => void supabase().auth.signOut()}>
          Se déconnecter
        </button>
      </p>
      {erreur && <p className="erreur">{erreur}</p>}
      {admin === false && (
        <p className="erreur">Ce compte n'est pas administrateur (table `admins`).</p>
      )}
      {admin && (
        <>
          <nav className="onglets">
            {(
              [
                ["panel", `Panel (${sources.length})`],
                ["equilibre", "Équilibre"],
                ["journal", "Journal"],
              ] as const
            ).map(([cle, libelle]) => (
              <button
                key={cle}
                className={onglet === cle ? "actif" : ""}
                onClick={() => setOnglet(cle)}
              >
                {libelle}
              </button>
            ))}
          </nav>
          {onglet === "panel" && <Panel sources={sources} basculer={basculer} />}
          {onglet === "equilibre" && <Equilibre sources={sources} />}
          {onglet === "journal" && <Journal journal={journal} />}
        </>
      )}
    </main>
  );
}

function Panel({
  sources,
  basculer,
}: {
  sources: Source[];
  basculer: (s: Source) => Promise<void>;
}) {
  const [filtre, setFiltre] = useState<TypeSource | "tous">("tous");
  const visibles = sources.filter((s) => filtre === "tous" || s.type === filtre);
  return (
    <>
      <p>
        <select value={filtre} onChange={(e) => setFiltre(e.target.value as TypeSource | "tous")}>
          <option value="tous">Toutes les catégories</option>
          {TYPES_SOURCE.map((t) => (
            <option key={t} value={t}>
              {LIBELLES_TYPE[t]}
            </option>
          ))}
        </select>
      </p>
      <div className="defile">
        <table>
          <thead>
            <tr>
              <th>Chaîne</th>
              <th>Catégorie</th>
              <th>Sous-type</th>
              <th className="nombre">Abonnés</th>
              <th className="nombre">Vidéos 90 j</th>
              <th className="nombre">Vues 90 j</th>
              <th>Dernière vidéo</th>
              <th>Statut</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {visibles.map((s) => {
              const sousSeuil =
                s.sous_type !== "parti" && (s.videos_fenetre ?? 0) < SEUIL_ACTIVITE_VIDEOS;
              return (
                <tr key={s.id} className={s.active ? "" : "en-pause"} title={s.critere_inclusion}>
                  <td>
                    {s.nom} <span className="discret">{s.handle}</span>
                  </td>
                  <td>{LIBELLES_TYPE[s.type]}</td>
                  <td>{s.sous_type}</td>
                  <td className="nombre">{nombre(s.abonnes)}</td>
                  <td className="nombre">
                    {nombre(s.videos_fenetre)}
                    {sousSeuil && <span className="statut-pause"> ⚠</span>}
                  </td>
                  <td className="nombre">{nombre(s.vues_fenetre)}</td>
                  <td>{date(s.derniere_video_at)}</td>
                  <td className={s.active ? "" : "statut-pause"}>
                    {s.active ? "active" : "en pause"}
                  </td>
                  <td>
                    <button className="petit" onClick={() => void basculer(s)}>
                      {s.active ? "Pause" : "Réactiver"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}

function Equilibre({ sources }: { sources: Source[] }) {
  const lignes = useMemo(
    () =>
      TYPES_SOURCE.flatMap((t) =>
        SOUS_TYPES_PAR_TYPE[t].map((st) => {
          const groupe = sources.filter((s) => s.type === t && s.sous_type === st && s.active);
          return {
            t,
            st,
            n: groupe.length,
            abonnes: groupe.reduce((a, s) => a + (s.abonnes ?? 0), 0),
            vues: groupe.reduce((a, s) => a + (s.vues_fenetre ?? 0), 0),
          };
        }),
      ),
    [sources],
  );
  return (
    <div className="defile">
      <p className="discret">
        Sources actives uniquement. Aucune orientation politique n'est stockée.
      </p>
      <table>
        <thead>
          <tr>
            <th>Catégorie</th>
            <th>Sous-type</th>
            <th className="nombre">Chaînes</th>
            <th className="nombre">Abonnés cumulés</th>
            <th className="nombre">Vues 90 j cumulées</th>
          </tr>
        </thead>
        <tbody>
          {lignes.map((l) => (
            <tr key={`${l.t}-${l.st}`}>
              <td>{LIBELLES_TYPE[l.t]}</td>
              <td>{l.st}</td>
              <td className="nombre">{l.n}</td>
              <td className="nombre">{nombre(l.abonnes)}</td>
              <td className="nombre">{nombre(l.vues)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Journal({ journal }: { journal: EntreeJournal[] }) {
  return (
    <div className="defile">
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Action</th>
            <th>Chaîne</th>
          </tr>
        </thead>
        <tbody>
          {journal.map((e) => (
            <tr key={e.id}>
              <td>{new Date(e.created_at).toLocaleString("fr-FR")}</td>
              <td>{e.action}</td>
              <td>{e.details.nom ?? e.source_id}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
