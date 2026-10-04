"use client";

// Drill-down : les commentaires classés d'une vidéo (30 derniers jours), lus dans le bucket
// privé `radar-drilldown` (admin seulement). Texte non modifié, sans pseudo ni auteur.
import { useEffect, useState } from "react";

import { supabase } from "@/lib/supabase";
import {
  LIBELLES_POSITIONS,
  LIBELLES_THEMES,
  LIBELLES_TONALITES,
  type Position,
  type Theme,
  type Tonalite,
} from "@/lib/taxonomie";
import { dateCourte } from "@/lib/ui";

type Commentaire = {
  texte: string;
  publie_at: string;
  politique: boolean;
  themes: Theme[];
  position: Position | null;
  tonalite: Tonalite;
  hostile: boolean;
};

async function charger(videoId: string): Promise<Commentaire[]> {
  const { data, error } = await supabase()
    .storage.from("radar-drilldown")
    .download(`videos/${videoId}.json.gz`);
  if (error || !data) throw new Error(error?.message ?? "fichier absent");
  const flux = data.stream().pipeThrough(new DecompressionStream("gzip"));
  return (await new Response(flux).json()) as Commentaire[];
}

export function CommentairesVideo({ videoId }: { videoId: string }) {
  const [etat, setEtat] = useState<"chargement" | "ouvert" | "absent">(
    "chargement",
  );
  const [liste, setListe] = useState<Commentaire[]>([]);
  const [filtre, setFiltre] = useState<"tous" | "hostiles" | Position>("tous");

  useEffect(() => {
    let actif = true;
    charger(videoId)
      .then((l) => {
        if (!actif) return;
        setListe(l);
        setEtat("ouvert");
      })
      .catch(() => actif && setEtat("absent"));
    return () => {
      actif = false;
    };
  }, [videoId]);

  if (etat === "chargement")
    return <p className="discret petit-texte">Chargement des commentaires…</p>;
  if (etat === "absent")
    return (
      <p className="discret petit-texte">
        Pas de commentaires classés des 30 derniers jours pour cette vidéo (ou
        drill-down pas encore calculé : lancer « Agrégats »).
      </p>
    );
  const compte = (f: "tous" | "hostiles" | Position) =>
    liste.filter((c) =>
      f === "tous" ? true : f === "hostiles" ? c.hostile : c.position === f,
    ).length;
  const visibles = liste.filter((c) =>
    filtre === "tous"
      ? true
      : filtre === "hostiles"
        ? c.hostile
        : c.position === filtre,
  );
  return (
    <div className="radar-drilldown">
      <div
        className="ve-classement"
        role="group"
        aria-label="Filtrer les commentaires"
      >
        {(
          [
            "tous",
            "accord_video",
            "nuance",
            "desaccord_video",
            "hors_sujet",
            "hostiles",
          ] as const
        ).map((f) => (
          <button
            key={f}
            className={filtre === f ? "actif" : ""}
            aria-pressed={filtre === f}
            onClick={() => setFiltre(f)}
          >
            {f === "tous"
              ? "Tous"
              : f === "hostiles"
                ? "Hostiles"
                : f === "accord_video"
                  ? "Accord"
                  : f === "desaccord_video"
                    ? "Désaccord"
                    : LIBELLES_POSITIONS[f]}{" "}
            <span className="ve-compte">{compte(f)}</span>
          </button>
        ))}
      </div>
      {visibles.length === 0 && (
        <p className="discret petit-texte">Aucun commentaire pour ce filtre.</p>
      )}
      <ol className="radar-commentaires">
        {visibles.map((c, i) => (
          <li key={i}>
            <p className="radar-commentaire-texte">{c.texte}</p>
            <p className="radar-commentaire-etiquettes">
              <span>{dateCourte(c.publie_at.slice(0, 10))}</span>
              {!c.politique && <span className="radar-puce">Non politique</span>}
              {c.themes.map((t) => (
                <span key={t} className="radar-puce">
                  {LIBELLES_THEMES[t]}
                </span>
              ))}
              {c.position && (
                <span className="radar-puce">
                  {LIBELLES_POSITIONS[c.position]}
                </span>
              )}
              <span className="radar-puce">
                {LIBELLES_TONALITES[c.tonalite]}
              </span>
              {c.hostile && (
                <span className="radar-puce radar-puce-hostile">Hostile</span>
              )}
            </p>
          </li>
        ))}
      </ol>
      <p className="discret petit-texte">
        Texte non modifié, sans pseudo. Étiquettes attribuées par le modèle
        (Jev) : à vérifier, pas une vérité. Au plus 150 commentaires classés par
        vidéo.
      </p>
    </div>
  );
}
