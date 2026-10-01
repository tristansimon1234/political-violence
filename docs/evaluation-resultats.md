# Résultats des tests de classification (étape 4)

Journal des mesures, en agrégats. Le détail commentaire par commentaire n'est conservé que pour les jeux synthétiques (`evaluation/`). Référence : étiquettes de Tristan. « Tout juste » = politique, thème principal, position et émotion tous justes (indicateur le plus sévère).

## 01/10/2026 — Sonde (1 commentaire fictif)

Protocole TypeSafe sur la Gateway confirmé, ZDR respecté (DigitalOcean écarté). Jev ≈ 1 200 tokens d'entrée par commentaire.

## 01/10/2026 — Synthétique v1 (100 commentaires écrits par Claude), consignes en français

| Dimension | Jev | Claude |
|---|---:|---:|
| Politique / non politique | 88 % | 91 % |
| Thème principal | 77 % | 87 % |
| Position | 73 % | 73 % |
| Émotion | 65 % | 79 % |
| Tout juste | 44 % | 60 % |

Confiance de Jev bien calibrée (justesse 13 % sous 0,5 → 100 % au-dessus de 0,9). Coût : Jev 0,05 $ / 1 000, Claude 0,57 $ / 1 000.

## 01/10/2026 — Synthétique v1, consignes en anglais et règles explicites

| Dimension | Jev | Claude |
|---|---:|---:|
| Politique / non politique | 98 % | 92 % |
| Thème principal | 90 % | 88 % |
| Position | 88 % | 92 % |
| Émotion | 75 % | 81 % |
| Tout juste | 62 % | 70 % |

Cascade au seuil 0,7 : 74 % (mieux que Claude seul) pour ~400 $ / million contre 635 $. **Biais** : les règles ont été écrites à partir de ces 100 commentaires ; gain en partie mécanique.

## 01/10/2026 — Synthétique v2 (50 commentaires de Tristan, jamais vus pour écrire les règles)

5 étiquettes alignées sur les règles avant le test (trace dans la colonne `note`).

| Dimension | Jev | Claude |
|---|---:|---:|
| Politique / non politique | 96 % | 80 % |
| Thème principal | 75 % | 69 % |
| Au moins un thème commun | 88 % | 73 % |
| Position | 84 % | 84 % |
| Émotion | 68 % | 78 % |
| Tout juste | 42 % | 50 % |

Constats : Jev meilleur que Claude sauf sur l'émotion ; Claude manque la règle « réaction à l'événement = politique ». Beaucoup de désaccords sont des ambiguïtés (thème principal vs secondaire, colère / lassitude), et Tristan signale lui-même des doutes fréquents. Confiance de Jev non interprétable sur 50 commentaires (tranches de 8 à 20). Coût : Jev 0,06 $ / 1 000, Claude 0,70 $ / 1 000.

**Suite** : arbitrage à l'aveugle des désaccords (`docs/etiquetage.md`), puis test sur la semaine 1 réelle.

**Note (taxonomie v5, 01/10/2026)** : les résultats ci-dessus portent sur l'émotion en six catégories, abandonnée depuis ; les prochains tests mesurent la tonalité et l'hostilité.
