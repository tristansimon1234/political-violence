// Fichier généré par scripts/generer_taxonomie_ts.py depuis radar/schemas.py.
// Ne pas éditer à la main.

export const VERSION_TAXONOMIE = 6;

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

export const NATURES_VIDEO = ["info_factuelle", "opinion", "debat"] as const;
export type NatureVideo = (typeof NATURES_VIDEO)[number];

export const POSITIONS = ["accord_video", "nuance", "desaccord_video", "hors_sujet"] as const;
export type Position = (typeof POSITIONS)[number];

export const TONALITES = ["positive", "neutre", "negative"] as const;
export type Tonalite = (typeof TONALITES)[number];

export const LIBELLES_THEMES: Record<Theme, string> = {"pouvoir_achat": "Pouvoir d'achat", "securite": "Sécurité", "immigration": "Immigration", "retraites": "Retraites", "sante": "Santé", "education": "Éducation", "ecologie_energie": "Écologie et énergie", "economie_emploi": "Économie et emploi", "logement": "Logement", "institutions": "Vie politique et institutions", "international_defense": "International et défense", "agriculture": "Agriculture", "societe": "Société", "autre": "Autre"};
export const DEFINITIONS_THEMES: Record<Theme, string> = {"pouvoir_achat": "Prix, inflation, salaires face au coût de la vie, carburant et factures d'énergie, impôts des ménages.", "securite": "Délinquance, violences, police, justice pénale et peines, terrorisme.", "immigration": "Flux migratoires, asile, obligations de quitter le territoire, intégration, nationalité, régularisation des travailleurs sans papiers.", "retraites": "Âge de départ, système de retraite et ses réformes, montant des pensions.", "sante": "Hôpital et urgences, médecins et déserts médicaux, assurance maladie, soignants, politique de santé.", "education": "École, enseignants et leur rémunération, programmes, examens, université, jeunes en formation.", "ecologie_energie": "Changement climatique, canicules, pollution, sources d'énergie (nucléaire, renouvelables), politique des transports.", "economie_emploi": "Croissance, entreprises, emploi et chômage, pénuries de main-d'œuvre, conditions de travail, dette publique et budget.", "logement": "Loyers, prix de l'immobilier, accès à la propriété, construction.", "institutions": "Élections, candidats, partis et leurs programmes, gouvernement, Parlement, fabrication des lois, Constitution, démocratie.", "international_defense": "Politique étrangère, Union européenne, guerres et conflits, armées, règles du commerce international.", "agriculture": "Agriculteurs, leurs mobilisations et leurs revenus, production alimentaire, normes et aides agricoles.", "societe": "Laïcité, religion, famille, mœurs, discriminations, cohésion sociale.", "autre": "Autre sujet politique ou d'intérêt public qui n'entre dans aucun des thèmes ci-dessus."};
export const LIBELLES_POSITIONS: Record<Position, string> = {"accord_video": "Accord avec la vidéo", "nuance": "Nuance", "desaccord_video": "Désaccord avec la vidéo", "hors_sujet": "Ne se prononce pas"};
export const LIBELLES_TONALITES: Record<Tonalite, string> = {"positive": "Positive", "neutre": "Neutre", "negative": "Négative"};

export const NON_POLITIQUE = "non_politique";
