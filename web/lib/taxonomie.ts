// Fichier généré par scripts/generer_taxonomie_ts.py depuis radar/schemas.py.
// Ne pas éditer à la main.

export const VERSION_TAXONOMIE = 5;

export const TYPES_SOURCE = ["media_traditionnel", "media_natif", "politique"] as const;
export type TypeSource = (typeof TYPES_SOURCE)[number];

export const SOUS_TYPES_PAR_TYPE = {"media_traditionnel": ["info_continu", "tv_radio", "talk_show", "presse_nationale"], "media_natif": ["pure_player", "createur"], "politique": ["parti", "personnalite"]} as const;
export type SousType = (typeof SOUS_TYPES_PAR_TYPE)[TypeSource][number];

export const LIBELLES_TYPE: Record<TypeSource, string> = {"media_traditionnel": "Médias traditionnels", "media_natif": "Médias natifs du web", "politique": "Politiques"};

export const SEUIL_ACTIVITE_VIDEOS = 10;
export const FENETRE_ACTIVITE_JOURS = 90;

export const FORMATS_VIDEO = ["short", "long"] as const;
export type FormatVideo = (typeof FORMATS_VIDEO)[number];

export const THEMES = ["pouvoir_achat", "securite", "immigration", "retraites", "sante", "education", "ecologie_energie", "economie_emploi", "logement", "institutions", "international_defense", "agriculture", "societe", "autre"] as const;
export type Theme = (typeof THEMES)[number];

export const NATURES_VIDEO = ["info_factuelle", "opinion_debat"] as const;
export type NatureVideo = (typeof NATURES_VIDEO)[number];

export const POSITIONS = ["accord_video", "nuance", "desaccord_video", "hors_sujet"] as const;
export type Position = (typeof POSITIONS)[number];

export const TONALITES = ["positive", "neutre", "negative"] as const;
export type Tonalite = (typeof TONALITES)[number];
