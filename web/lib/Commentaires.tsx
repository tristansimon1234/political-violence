"use client";

// Drill-down : les commentaires classés d'une vidéo (30 derniers jours), lus dans le bucket
// privé `radar-drilldown` (admin seulement). Texte non modifié, sans pseudo ni auteur.
import { useState } from "react";

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
  const [etat, setEtat] = useState<
    "ferme" | "chargement" | "ouvert" | "absent"
  >("ferme");
  const [liste, setListe] = useState<Commentaire[]>([]);
  const [filtre, setFiltre] = useState<"tous" | "hostiles" | Position>("tous");

  const basculer = () => {
    if (etat === "ouvert" || etat === "absent") return setEtat("ferme");
    setEtat("chargement");
    charger(videoId)
      .then((l) => {
        setListe(l);
        setEtat("ouvert");
      })
      .catch(() => setEtat("absent"));
  };
  const visibles = liste.filter((c) =>
    filtre === "tous"
      ? true
      : filtre === "hostiles"
        ? c.hostile
        : c.position === filtre,
  );
  return (
    <div className="radar-drilldown">
      <button
        className="radar-lien petit-texte"
        onClick={basculer}
        aria-expanded={etat === "ouvert"}
      >
        {etat === "ouvert"
          ? "Masquer les commentaires"
          : etat === "chargement"
            ? "Chargement…"
            : "Voir les commentaires classés"}
      </button>
      {etat === "absent" && (
        <p className="discret petit-texte">
          Pas de commentaires classés des 30 derniers jours pour cette vidéo (ou
          drill-down pas encore calculé : lancer « Agrégats »).
        </p>
      )}
      {etat === "ouvert" && (
        <>
          <p className="radar-drilldown-filtres">
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
                className={filtre === f ? "segment actif" : "segment"}
                aria-pressed={filtre === f}
                onClick={() => setFiltre(f)}
              >
                {f === "tous"
                  ? `Tous (${liste.length})`
                  : f === "hostiles"
                    ? "Hostiles"
                    : LIBELLES_POSITIONS[f]}
              </button>
            ))}
          </p>
          <ol className="radar-commentaires">
            {visibles.map((c, i) => (
              <li key={i}>
                <p className="radar-commentaire-texte">{c.texte}</p>
                <p className="radar-commentaire-etiquettes">
                  <span>{dateCourte(c.publie_at.slice(0, 10))}</span>
                  {!c.politique && (
                    <span className="radar-puce">Non politique</span>
                  )}
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
                    <span className="radar-puce radar-puce-hostile">
                      Hostile
                    </span>
                  )}
                </p>
              </li>
            ))}
          </ol>
          <p className="discret petit-texte">
            Texte non modifié, sans pseudo. Étiquettes attribuées par le modèle
            (Jev) : à vérifier, pas une vérité. Au plus 150 commentaires classés
            par vidéo.
          </p>
        </>
      )}
    </div>
  );
}
