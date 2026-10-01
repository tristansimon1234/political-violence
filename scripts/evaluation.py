"""Test de qualité Jev / Claude / vérité terrain (étape 4).

    python scripts/evaluation.py sonde      # 1 appel Jev + 1 appel Claude sur un texte fictif
    python scripts/evaluation.py preparer   # échantillon + fichier d'étiquetage dans le bucket
    python scripts/evaluation.py evaluer    # classement Jev et Claude, rapport en agrégats

Variables : SUPABASE_URL, SUPABASE_SECRET_KEY, ANTHROPIC_API_KEY, AI_GATEWAY_API_KEY.
Fichiers dans le bucket privé `radar-brut`, dossier `evaluation/` (purgés à 30 jours avec le brut) :
- AAAA-MM-JJ-echantillon.parquet     échantillon (texte masqué, contexte vidéo)
- AAAA-MM-JJ-etiquetage.csv          à télécharger, remplir, puis déposer sous le nom
- AAAA-MM-JJ-etiquetage-rempli.csv   (voir docs/etiquetage.md)
- AAAA-MM-JJ-resultats.parquet       étiquettes de Jev et de Claude (aucun texte)
Rien n'est affiché ni écrit hors du bucket, sauf des agrégats.
"""

import argparse
import logging
import os
import random
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from radar.classification import (
    SYSTEME_COMMENTAIRES,
    ContexteVideo,
    ReponseCommentaires,
    etat_jev,
    message_commentaires,
    questions_jev,
)
from radar.evaluation import (
    Couts,
    Volume,
    candidates,
    chemin,
    classer_claude,
    classer_jev,
    classer_natures,
    dernier_echantillon,
    echantillonner,
    ecrire_echantillon,
    ecrire_json,
    ecrire_resultats,
    fichier_etiquetage,
    lire_echantillon,
    lire_etiquettes,
    lire_json,
    lire_resultats,
    rapport,
)
from radar.llm import (
    ClientClaude,
    ClientJev,
    ReponseInvalide,
    cle_gateway,
    cout_jev,
    lire_reponse_jev,
)
from radar.storage import Stockage, StockageLocal, StockageSupabase, lire_partition, partitions
from radar.supabase_rest import Supabase

log = logging.getLogger("evaluation")
BUCKET = "radar-brut"

# Texte fictif, sans donnée personnelle, pour vérifier les clés et le format des réponses.
SONDE_CONTEXTE = ContexteVideo("Débat sur le budget de l'État", "Chaîne fictive", "opinion_debat")
SONDE_TEXTE = "Encore des impôts en plus, ça ne finira jamais. Bravo pour le débat quand même."


def _stockage(args: argparse.Namespace) -> Stockage:
    if args.stockage_local:
        return StockageLocal(args.stockage_local)
    return StockageSupabase(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"], BUCKET)


def sonde(args: argparse.Namespace) -> int:
    """Un appel Jev et un appel Claude sur un texte fictif ; réponse brute affichée."""
    import requests

    jev = ClientJev(budget_usd=0.05)
    questions = questions_jev("opinion_debat")
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
    natures = classer_natures(claude, cands)
    lignes = echantillonner(natures, cands, commentaires, rng)
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


def evaluer(args: argparse.Namespace) -> int:
    st = _stockage(args)
    jour = dernier_echantillon(st)
    if jour is None:
        print("Aucun échantillon : lancer d'abord `preparer`.")
        return 1
    lignes = lire_echantillon(st, jour)
    prep = lire_json(st, jour, "preparation.json")
    deja = {c.rsplit("/", 1)[-1] for c in st.lister("evaluation")}
    if f"{jour.isoformat()}-resultats.parquet" in deja and not args.reclasser:
        res = lire_resultats(st, jour)
        couts_brut = lire_json(st, jour, "couts.json")
    else:
        jev_client = ClientJev(budget_usd=args.budget_jev)
        claude_client = ClientClaude(budget_usd=args.budget_claude)
        res = {
            "jev": classer_jev(jev_client, lignes),
            "claude": classer_claude(claude_client, lignes),
        }
        ecrire_resultats(st, jour, res)
        couts_brut = {
            "jev_usd": jev_client.compteur.cout_usd,
            "jev_n": len(res["jev"]),
            "jev_erreurs": jev_client.compteur.erreurs,
            "claude_usd": claude_client.compteur.cout_usd,
            "claude_n": len(res["claude"]),
            "claude_erreurs": claude_client.compteur.erreurs,
        }
        ecrire_json(st, jour, "couts.json", couts_brut)
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
    print(rapport(lignes, res["jev"], res["claude"], etiquettes, couts, volume, date.today()))
    erreurs = int(couts_brut.get("jev_erreurs", 0)) + int(couts_brut.get("claude_erreurs", 0))
    if erreurs:
        print(f"\nAppels en erreur (ignorés) : {erreurs}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("commande", choices=["sonde", "preparer", "evaluer"])
    p.add_argument("--budget-claude", type=float, default=3.0, help="dollars max pour Claude")
    p.add_argument("--budget-jev", type=float, default=1.0, help="dollars max pour Jev")
    p.add_argument("--graine", type=int, default=20260901, help="graine du tirage")
    p.add_argument("--remplacer", action="store_true", help="preparer : écraser l'échantillon")
    p.add_argument("--reclasser", action="store_true", help="evaluer : refaire les appels")
    p.add_argument("--stockage-local", type=Path, help="dossier local au lieu du bucket")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    log.info("début %s", datetime.now(UTC).isoformat())
    return {"sonde": sonde, "preparer": preparer, "evaluer": evaluer}[args.commande](args)


if __name__ == "__main__":
    sys.exit(main())
