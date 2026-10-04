"""« Pourquoi ça bouge » : résumés IA des 5 premiers sujets et des thèmes de chaque semaine.

    python scripts/resumes.py --dry-run          # résumés à écrire, aucun appel
    python scripts/resumes.py --budget-claude 1

Pour chaque semaine depuis le 1er septembre : chiffres agrégés et vidéos principales envoyés
à Claude, 2 à 3 phrases neutres avec renvois numérotés, validées puis écrites dans
`resumes_ia`. Un résumé n'est régénéré que si ses chiffres ont changé (idempotent).
À lancer après Sujets et Agrégats. Variables : SUPABASE_URL, SUPABASE_SECRET_KEY,
ANTHROPIC_API_KEY.
"""

import argparse
import logging
import os
import sys
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from radar.llm import MODELE_CLAUDE, BudgetDepasse, ClientClaude, ReponseInvalide
from radar.resumes import (
    SYSTEME_RESUME,
    TYPES_PUBLIC,
    Element,
    ReponseResume,
    ResumeInvalide,
    StatsTheme,
    VideoInfo,
    elements_sujet,
    elements_theme,
    empreinte,
    ligne_resume,
    lundi,
    message_resume,
    stats_sujets,
    valider,
)
from radar.schemas import LIBELLES_THEMES, NON_POLITIQUE
from radar.supabase_rest import Supabase

log = logging.getLogger("resumes")
PARIS = ZoneInfo("Europe/Paris")
DEBUT_COLLECTE = date(2026, 9, 1)
LIBELLES: dict[str, str] = {str(k): v for k, v in LIBELLES_THEMES.items()}
SUJETS_PAR_SEMAINE = 5
THEMES_PAR_SEMAINE = 6
MIN_COMMENTAIRES_THEME = 500


def _jour(iso: str) -> date:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(PARIS).date()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="résumés à écrire, aucun appel")
    p.add_argument("--budget-claude", type=float, default=1.0, help="dollars max pour Claude")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    aujourdhui = datetime.now(UTC).date()
    base = Supabase(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

    sources = {str(s["id"]): s for s in base.select("sources", {})}
    videos = {str(v["video_id"]): v for v in base.select("videos", {"prefiltre": "eq.true"})}
    principal: dict[str, dict[str, Any]] = {
        str(s["video_id"]): s for s in base.select("videos_sujets", {"principal": "eq.true"})
    }
    reactions = {str(r["video_id"]): r for r in base.select("agregats_videos", {})}
    titres = {str(s["id"]): str(s["titre"]) for s in base.select("sujets", {})}
    sujet_de = {
        str(r["video_id"]): str(r["sujet_id"])
        for r in base.select("sujets_videos", {"sujet_id": "not.is.null"})
    }
    infos: list[VideoInfo] = []
    for vid, v in videos.items():
        src = sources.get(str(v["source_id"]), {})
        r = reactions.get(vid)
        w = float(r.get("poids") or 1) if r else 0.0
        infos.append(
            VideoInfo(
                vid,
                _jour(str(v["publiee_at"])),
                str(src.get("type", "")),
                str(src.get("nom", "")),
                str(principal.get(vid, {}).get("sous_sujet", "")),
                str(principal.get(vid, {}).get("theme", "autre")),
                w * float(r["commentaires"]) if r else 0.0,
                w * float(r["hostiles"]) if r else 0.0,
                w * float(r["accord"]) if r else 0.0,
                w * float(r["nuance"]) if r else 0.0,
                w * float(r["desaccord"]) if r else 0.0,
            )
        )
    agregats = [a for a in base.select("agregats_themes", {}) if a["type_source"] in TYPES_PUBLIC]
    existants = {str(r["id"]): str(r["empreinte"]) for r in base.select("resumes_ia", {})}

    # Semaines à résumer : du 1er septembre à la dernière vidéo connue.
    dernier = max((i.jour for i in infos), default=DEBUT_COLLECTE)
    semaines: list[date] = []
    s = lundi(DEBUT_COLLECTE)
    while s <= dernier:
        semaines.append(s)
        s += timedelta(days=7)

    a_faire: list[tuple[str, str, str, date, str, list[Element]]] = []
    for sem in semaines:
        stats = stats_sujets(infos, sujet_de, titres, sem)
        for st in stats[:SUJETS_PAR_SEMAINE]:
            els = elements_sujet(st)
            a_faire.append((f"sujet:{st.id}:{sem}", "sujet", st.id, sem, f"Story: {st.titre}", els))
        # Thèmes de la semaine les plus commentés.
        par_theme: defaultdict[str, defaultdict[str, float]] = defaultdict(
            lambda: defaultdict(float)
        )
        avant: defaultdict[str, float] = defaultdict(float)
        for a in agregats:
            j = date.fromisoformat(str(a["jour"]))
            if sem <= j <= sem + timedelta(days=6):
                for m in ("commentaires", "accord", "nuance", "desaccord", "hostiles"):
                    par_theme[str(a["theme"])][m] += float(a[m])
            elif sem - timedelta(days=7) <= j < sem:
                avant[str(a["theme"])] += float(a["commentaires"])
        politiques = sum(c["commentaires"] for t, c in par_theme.items() if t != NON_POLITIQUE)
        themes = sorted(
            (t for t in par_theme if t not in (NON_POLITIQUE, "autre")),
            key=lambda t: -par_theme[t]["commentaires"],
        )
        for t in themes[:THEMES_PAR_SEMAINE]:
            c = par_theme[t]
            if c["commentaires"] < MIN_COMMENTAIRES_THEME:
                continue
            st_t = StatsTheme(
                t,
                LIBELLES.get(t, t),
                c["commentaires"],
                avant[t],
                c["commentaires"] / politiques if politiques else 0.0,
                c["accord"],
                c["nuance"],
                c["desaccord"],
                c["hostiles"],
                [x for x in stats if Counter(v.theme for v in x.videos).most_common(1)[0][0] == t],
            )
            a_faire.append(
                (
                    f"theme:{t}:{sem}",
                    "theme",
                    t,
                    sem,
                    f"Theme: {st_t.libelle}",
                    elements_theme(st_t),
                )
            )
    nouveaux = [x for x in a_faire if existants.get(x[0]) != empreinte(x[5])]

    print("# Résumés IA (Pourquoi ça bouge)" + (" (dry-run)" if args.dry_run else ""))
    print(
        f"\nSemaines : {len(semaines)} ; résumés possibles : {len(a_faire)} ; à écrire ou "
        f"mettre à jour (chiffres changés) : {len(nouveaux)}."
    )
    if args.dry_run:
        print(f"\nCoût estimé : ~{len(nouveaux) * 0.002:.2f} USD. Rien n'a été envoyé.")
        return 0

    claude = ClientClaude(budget_usd=args.budget_claude)
    ecrits, rejetes = 0, 0
    try:
        for cle, type_, cible, sem, sujet, els in nouveaux:
            try:
                rep = claude.classer(SYSTEME_RESUME, message_resume(sujet, els), ReponseResume, 600)
                texte, cites = valider(rep.texte, len(els))
            except (ReponseInvalide, ResumeInvalide) as e:
                rejetes += 1
                log.warning("résumé %s rejeté : %s", cle, e)
                continue
            base.upsert(
                "resumes_ia",
                [
                    ligne_resume(
                        cle, type_, cible, sem, texte, cites, els, MODELE_CLAUDE, aujourdhui
                    )
                ],
                "id",
            )
            ecrits += 1
    except BudgetDepasse as e:
        print(f"\nArrêt au budget Claude ({e}) : relancer pour continuer.")
    print(
        f"\n## Bilan\n\n- Résumés écrits : {ecrits} ; rejetés (renvoi manquant ou inconnu) : "
        f"{rejetes}\n- Coût Claude : {claude.compteur.cout_usd:.2f} USD"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
