"""Test de qualité Jev / Claude / vérité terrain (étape 4).

    python scripts/evaluation.py sonde      # 1 appel Jev + 1 appel Claude sur un texte fictif
    python scripts/evaluation.py preparer   # échantillon + fichier d'étiquetage dans le bucket
    python scripts/evaluation.py evaluer    # classement Jev et Claude, rapport en agrégats
    python scripts/evaluation.py evaluer --contexte  # idem avec le résumé de chaque vidéo
    python scripts/evaluation.py synthetique  # commentaires fictifs étiquetés (versionnés)
    python scripts/evaluation.py arbitrage --fichier arbitrage_x.csv --cle cle_x.json

Variables : SUPABASE_URL, SUPABASE_SECRET_KEY, ANTHROPIC_API_KEY, AI_GATEWAY_API_KEY.
Fichiers dans le bucket privé `radar-brut`, dossier `evaluation/` (purgés à 30 jours avec le brut) :
- AAAA-MM-JJ-echantillon.parquet     échantillon (texte masqué, contexte vidéo)
- AAAA-MM-JJ-etiquetage.csv          à télécharger, remplir, puis déposer sous le nom
- AAAA-MM-JJ-etiquetage-rempli.csv   (voir docs/etiquetage.md)
- AAAA-MM-JJ-resultats.parquet       étiquettes de Jev et de Claude (aucun texte)
- AAAA-MM-JJ-resumes.json            résumé de chaque vidéo (--contexte, dérivé du brut)
- AAAA-MM-JJ-resultats-contexte.parquet  étiquettes avec le résumé (--contexte)
Rien n'est affiché ni écrit hors du bucket, sauf des agrégats.
"""

import argparse
import json
import logging
import os
import random
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from radar.classification import (
    SYSTEME_COMMENTAIRES,
    Classement,
    ContexteVideo,
    ReponseCommentaires,
    etat_jev,
    message_commentaires,
    questions_jev,
)
from radar.evaluation import (
    Candidate,
    Couts,
    Ligne,
    Modele,
    Volume,
    avec_resumes,
    candidates,
    charger_synthetique,
    chemin,
    classer_claude,
    classer_jev,
    classer_videos,
    comparaison_contexte,
    dernier_echantillon,
    desaccords,
    echantillonner,
    ecrire_echantillon,
    ecrire_json,
    ecrire_resultats,
    fichier_arbitrage,
    fichier_etiquetage,
    lire_echantillon,
    lire_etiquettes,
    lire_json,
    lire_resultats,
    rapport,
    rapport_arbitrage,
)
from radar.llm import (
    ClientClaude,
    ClientJev,
    ReponseInvalide,
    cle_gateway,
    cout_jev,
    lire_reponse_jev,
)
from radar.schemas import NatureVideo
from radar.storage import Stockage, StockageLocal, StockageSupabase, lire_partition, partitions
from radar.supabase_rest import Supabase

log = logging.getLogger("evaluation")
BUCKET = "radar-brut"

# Texte fictif, sans donnée personnelle, pour vérifier les clés et le format des réponses.
SONDE_CONTEXTE = ContexteVideo("Mon avis sur le budget de l'État", "Chaîne fictive", "opinion")
SONDE_TEXTE = "Encore des impôts en plus, ça ne finira jamais. Bravo pour le débat quand même."


def _stockage(args: argparse.Namespace) -> Stockage:
    if args.stockage_local:
        return StockageLocal(args.stockage_local)
    return StockageSupabase(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"], BUCKET)


def sonde(args: argparse.Namespace) -> int:
    """Un appel Jev et un appel Claude sur un texte fictif ; réponse brute affichée."""
    import requests

    jev = ClientJev(budget_usd=0.05)
    questions = questions_jev("opinion")
    corps = jev.corps(etat_jev(SONDE_CONTEXTE, SONDE_TEXTE), questions)
    entetes = {"Authorization": f"Bearer {cle_gateway()}", "Content-Type": "application/json"}
    r = requests.post(jev.url, headers=entetes, json=corps, timeout=60)
    print(f"## Jev (texte fictif) : HTTP {r.status_code}\n```\n{r.text[:4000]}\n```")
    if r.ok:
        brut: dict[str, Any] = r.json()
        try:
            reps = lire_reponse_jev(questions, brut)
            print("Format compris :", {k: type(v).__name__ for k, v in reps.items()})
        except ReponseInvalide as e:
            print("Format non compris :", e)
        entree, cout = cout_jev(brut)
        print(f"Coût Jev : {cout:.6f} $ ({entree} tokens d'entrée)")
    print("\n## Claude (texte fictif)\n")
    try:
        claude = ClientClaude(budget_usd=0.05)
        rep = claude.classer(
            SYSTEME_COMMENTAIRES,
            message_commentaires(SONDE_CONTEXTE, [SONDE_TEXTE]),
            ReponseCommentaires,
        )
        print("Réponse :", rep.model_dump())
        print(f"Coût Claude : {claude.compteur.cout_usd:.6f} $")
    except Exception as e:  # diagnostic : on affiche toute erreur
        print("Erreur Claude :", type(e).__name__, str(e)[:500])
    return 0 if r.ok else 1


def preparer(args: argparse.Namespace) -> int:
    st = _stockage(args)
    base = Supabase(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
    sources = {str(s["id"]): s for s in base.select("sources", {})}
    videos = base.select("videos", {"derniere_collecte": "not.is.null"})
    bruts_videos: dict[str, dict[str, Any]] = {}
    for c in partitions(st, "videos").values():
        for v in lire_partition(st, c):
            bruts_videos[str(v["video_id"])] = v
    commentaires: dict[str, list[dict[str, Any]]] = {}
    total = 0
    for c in partitions(st, "commentaires").values():
        for x in lire_partition(st, c):
            commentaires.setdefault(str(x["video_id"]), []).append(x)
            total += 1
    nb = {vid: len(xs) for vid, xs in commentaires.items()}
    if dernier_echantillon(st) is not None and not args.remplacer:
        print("Un échantillon existe déjà (--remplacer pour en tirer un nouveau).")
        return 1
    rng = random.Random(args.graine)
    cands = candidates(videos, sources, bruts_videos, nb, rng)
    print(f"Vidéos collectées : {len(videos)}, candidates : {len(cands)}, commentaires : {total}")

    claude = ClientClaude(budget_usd=args.budget_claude)
    videos_classees = classer_videos(claude, cands)
    natures: dict[str, NatureVideo] = {v: r.nature_video for v, r in videos_classees.items()}
    resumes = {v: r.resume for v, r in videos_classees.items()}
    lignes = echantillonner(natures, cands, commentaires, rng, resumes=resumes)
    if not lignes:
        print("Aucun commentaire à échantillonner.")
        return 1
    jour = min(li.recupere_le for li in lignes)
    ecrire_echantillon(st, jour, lignes)
    st.ecrire(chemin(jour, "etiquetage.csv"), fichier_etiquetage(lignes))
    jours_pub = {str(v["publiee_at"])[:10] for v in videos}
    ecrire_json(
        st,
        jour,
        "preparation.json",
        {
            "commentaires": total,
            "jours": len(jours_pub),
            "graine": args.graine,
            "natures_usd": claude.compteur.cout_usd,
        },
    )
    print(
        f"Échantillon : {len(lignes)} commentaires, {sum(li.verite for li in lignes)} à étiqueter, "
        f"natures classées : {len(natures)}, coût Claude {claude.compteur.cout_usd:.4f} $."
    )
    print(f"Fichier d'étiquetage : {BUCKET}/{chemin(jour, 'etiquetage.csv')}")
    print(f"À déposer une fois rempli : {BUCKET}/{chemin(jour, 'etiquetage-rempli.csv')}")
    return 0


def _resumes(st: Stockage, jour: date, lignes: list[Ligne], claude: ClientClaude) -> list[Ligne]:
    """Résumé de chaque vidéo de l'échantillon (calculé une fois, gardé dans le bucket).

    La nature déjà attribuée est conservée : seul le résumé est repris de la réponse.
    """
    deja = {c.rsplit("/", 1)[-1] for c in st.lister("evaluation")}
    if f"{jour.isoformat()}-resumes.json" in deja:
        return avec_resumes(lignes, lire_json(st, jour, "resumes.json"))
    descriptions: dict[str, str] = {}
    for c in partitions(st, "videos").values():
        for v in lire_partition(st, c):
            descriptions[str(v["video_id"])] = str(v.get("description") or "")
    par_video = {li.video_id: li for li in lignes}
    cands = [
        Candidate(v, li.type_source, li.format, li.chaine, li.titre, descriptions.get(v, ""))
        for v, li in sorted(par_video.items())
    ]
    resumes = {v: r.resume for v, r in classer_videos(claude, cands).items()}
    ecrire_json(st, jour, "resumes.json", resumes)
    sans_description = sum(1 for c in cands if not c.description.strip())
    print(
        f"Résumés : {len(resumes)}/{len(cands)} vidéos, {sans_description} sans description, "
        f"coût Claude {claude.compteur.cout_usd:.4f} $.\n"
    )
    return avec_resumes(lignes, resumes)


def evaluer(args: argparse.Namespace) -> int:
    st = _stockage(args)
    jour = dernier_echantillon(st)
    if jour is None:
        print("Aucun échantillon : lancer d'abord `preparer`.")
        return 1
    lignes = lire_echantillon(st, jour)
    prep = lire_json(st, jour, "preparation.json")
    suffixe = "-contexte" if args.contexte else ""
    fichier_res, fichier_couts = f"resultats{suffixe}.parquet", f"couts{suffixe}.json"
    claude_client = ClientClaude(budget_usd=args.budget_claude)
    if args.contexte:
        lignes = _resumes(st, jour, lignes, claude_client)
    deja = {c.rsplit("/", 1)[-1] for c in st.lister("evaluation")}
    if f"{jour.isoformat()}-{fichier_res}" in deja and not args.reclasser:
        res = lire_resultats(st, jour, fichier_res)
        couts_brut = lire_json(st, jour, fichier_couts)
    else:
        jev_client = ClientJev(budget_usd=args.budget_jev)
        avant = claude_client.compteur.cout_usd  # résumés exclus du coût par commentaire
        res: dict[Modele, dict[str, Classement]] = {
            "jev": classer_jev(jev_client, lignes),
            "claude": classer_claude(claude_client, lignes),
        }
        ecrire_resultats(st, jour, res, fichier_res)
        couts_brut = {
            "jev_usd": jev_client.compteur.cout_usd,
            "jev_n": len(res["jev"]),
            "jev_erreurs": jev_client.compteur.erreurs,
            "claude_usd": claude_client.compteur.cout_usd - avant,
            "claude_n": len(res["claude"]),
            "claude_erreurs": claude_client.compteur.erreurs,
        }
        ecrire_json(st, jour, fichier_couts, couts_brut)
    rempli = f"{jour.isoformat()}-etiquetage-rempli.csv"
    etiquettes = (
        lire_etiquettes(st.lire(chemin(jour, "etiquetage-rempli.csv")), lignes)
        if rempli in deja
        else {}
    )
    couts = Couts(
        float(couts_brut["jev_usd"]),
        int(couts_brut["jev_n"]),
        float(couts_brut["claude_usd"]),
        int(couts_brut["claude_n"]),
        float(prep["natures_usd"]),
    )
    volume = Volume(int(prep["commentaires"]), int(prep["jours"]))
    if args.contexte:
        print("Avec le résumé de chaque vidéo (titre, chaîne, nature et résumé envoyés).\n")
    print(rapport(lignes, res["jev"], res["claude"], etiquettes, couts, volume, date.today()))
    if args.contexte and etiquettes and f"{jour.isoformat()}-resultats.parquet" in deja:
        print("\n" + comparaison_contexte(lire_resultats(st, jour), res, etiquettes))
    erreurs = int(couts_brut.get("jev_erreurs", 0)) + int(couts_brut.get("claude_erreurs", 0))
    if erreurs:
        print(f"\nAppels en erreur (ignorés) : {erreurs}")
    return 0


def synthetique(args: argparse.Namespace) -> int:
    """Commentaires fictifs étiquetés par Tristan (fichier versionné) : Jev et Claude comparés."""
    donnees = args.fichier.read_bytes()
    aujourdhui = date.today()
    lignes = charger_synthetique(donnees, aujourdhui)
    etiquettes = lire_etiquettes(donnees, lignes)
    if not etiquettes:
        print(f"Aucune étiquette dans {args.fichier} : voir docs/etiquetage.md.")
        return 1
    jev_client = ClientJev(budget_usd=args.budget_jev)
    claude_client = ClientClaude(budget_usd=args.budget_claude)
    jev = classer_jev(jev_client, lignes)
    claude = classer_claude(claude_client, lignes)
    couts = Couts(
        jev_client.compteur.cout_usd,
        len(jev),
        claude_client.compteur.cout_usd,
        len(claude),
        0.0,
    )
    print(rapport(lignes, jev, claude, etiquettes, couts, Volume(0, 0), aujourdhui))
    print()
    print(desaccords(lignes, jev, claude, etiquettes))
    # Arbitrage à l'aveugle : fichier à remplir et clé séparée (ne pas ouvrir avant d'arbitrer).
    a_remplir, cle = fichier_arbitrage(lignes, jev, claude, etiquettes, random.Random(args.graine))
    args.sortie.mkdir(parents=True, exist_ok=True)
    base = args.fichier.stem
    (args.sortie / f"arbitrage_{base}.csv").write_bytes(a_remplir)
    (args.sortie / f"cle_{base}.json").write_text(json.dumps(cle, indent=1))
    print(
        f"\nArbitrage : {len(cle)} désaccords dans {args.sortie}/arbitrage_{base}.csv "
        f"(clé : cle_{base}.json, à ne pas ouvrir avant d'avoir arbitré)."
    )
    return 0


def arbitrage(args: argparse.Namespace) -> int:
    """Taux de victoires après arbitrage à l'aveugle (aucun appel aux modèles)."""
    if args.cle is None:
        print("--cle obligatoire (fichier cle_*.json produit par synthetique).")
        return 1
    cle: dict[str, dict[str, list[str]]] = json.loads(args.cle.read_text())
    print(rapport_arbitrage(args.fichier.read_bytes(), cle))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("commande", choices=["sonde", "preparer", "evaluer", "synthetique", "arbitrage"])
    p.add_argument("--cle", type=Path, help="arbitrage : clé produite par synthetique")
    p.add_argument(
        "--sortie", type=Path, default=Path("arbitrage"), help="synthetique : dossier d'arbitrage"
    )
    p.add_argument(
        "--fichier",
        type=Path,
        default=Path(__file__).parents[1] / "evaluation" / "synthetique_v1.csv",
        help="synthetique : fichier de commentaires fictifs étiquetés",
    )
    p.add_argument("--budget-claude", type=float, default=3.0, help="dollars max pour Claude")
    p.add_argument("--budget-jev", type=float, default=1.0, help="dollars max pour Jev")
    p.add_argument("--graine", type=int, default=20260901, help="graine du tirage")
    p.add_argument("--remplacer", action="store_true", help="preparer : écraser l'échantillon")
    p.add_argument("--reclasser", action="store_true", help="evaluer : refaire les appels")
    p.add_argument(
        "--contexte", action="store_true", help="evaluer : ajouter le résumé de chaque vidéo"
    )
    p.add_argument("--stockage-local", type=Path, help="dossier local au lieu du bucket")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    log.info("début %s", datetime.now(UTC).isoformat())
    commandes = {
        "sonde": sonde,
        "preparer": preparer,
        "evaluer": evaluer,
        "synthetique": synthetique,
        "arbitrage": arbitrage,
    }
    return commandes[args.commande](args)


if __name__ == "__main__":
    sys.exit(main())
