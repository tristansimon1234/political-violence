"""Clients uniques des modèles : Jev (Vercel AI Gateway, HTTP) et Claude (SDK anthropic).

Chaque appel est journalisé (tokens, coût) et refusé au-delà du budget du run en dollars.
Les entrées sont construites par radar/classification.py (texte masqué, jamais d'auteur ni
d'identifiant de commentaire) ; ce module ne fait que transporter et compter.
"""

import logging
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

import requests
from anthropic import Anthropic
from pydantic import BaseModel, ConfigDict, ValidationError

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class BudgetDepasse(Exception):
    pass


class ReponseInvalide(Exception):
    pass


@dataclass
class Compteur:
    budget_usd: float
    appels: int = 0
    tokens_entree: int = 0
    tokens_sortie: int = 0
    cout_usd: float = 0.0
    erreurs: int = 0
    _nom: str = field(default="", repr=False)
    # Appels en parallèle (classification en masse) : compteurs protégés par un verrou.
    _verrou: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def verifier(self) -> None:
        if self.cout_usd >= self.budget_usd:
            raise BudgetDepasse(f"{self._nom} : {self.cout_usd:.4f} $ / budget {self.budget_usd} $")

    def ajouter(self, entree: int, sortie: int, cout: float) -> None:
        with self._verrou:
            self.appels += 1
            self.tokens_entree += entree
            self.tokens_sortie += sortie
            self.cout_usd += cout
            appels, total = self.appels, self.cout_usd
        # Une ligne par appel en debug ; un point d'étape toutes les 500 requêtes.
        log.log(
            logging.INFO if appels <= 3 or appels % 500 == 0 else logging.DEBUG,
            "%s appel=%d tokens=%d/%d cout=%.6f $ total=%.4f $",
            self._nom,
            appels,
            entree,
            sortie,
            cout,
            total,
        )

    def erreur(self) -> None:
        with self._verrou:
            self.erreurs += 1


# --- Claude ---

MODELE_CLAUDE = "claude-haiku-4-5"
# Tarifs Claude Haiku 4.5 ($ par million de tokens).
PRIX_CLAUDE_ENTREE = 1.0
PRIX_CLAUDE_SORTIE = 5.0


class ClientClaude:
    def __init__(self, budget_usd: float, client: Anthropic | None = None) -> None:
        self._client = client or Anthropic()
        self.compteur = Compteur(budget_usd, _nom="claude")

    def classer(self, systeme: str, message: str, sortie: type[T], max_tokens: int = 2000) -> T:
        self.compteur.verifier()
        r = self._client.messages.parse(
            model=MODELE_CLAUDE,
            max_tokens=max_tokens,
            system=systeme,
            messages=[{"role": "user", "content": message}],
            output_format=sortie,
        )
        u = r.usage
        self.compteur.ajouter(
            u.input_tokens,
            u.output_tokens,
            (u.input_tokens * PRIX_CLAUDE_ENTREE + u.output_tokens * PRIX_CLAUDE_SORTIE) / 1e6,
        )
        if r.stop_reason != "end_turn" or r.parsed_output is None:
            self.compteur.erreur()
            raise ReponseInvalide(f"claude stop_reason={r.stop_reason}")
        return r.parsed_output


# --- Jev ---

# Protocole natif TypeSafe (`POST /v1/systemone`, schéma du paquet officiel typesafe-sdk 0.7.2),
# servi par Vercel AI Gateway sous /typesafe. Surchargeable par JEV_URL / JEV_MODELE.
MODELE_JEV = "typesafe-ai/jev"
URL_JEV = "https://ai-gateway.vercel.sh/typesafe/v1/systemone"
# Prix d'entrée publié par des sources tierces (non vérifié) ; sortie gratuite. Utilisé
# seulement si la Gateway ne renvoie pas le coût réel.
PRIX_JEV_ENTREE = 0.042

# État évalué par Jev : texte ou objet JSON (champs nommés recommandés par TypeSafe).
Etat = str | dict[str, Any]

Transport = Callable[[str, dict[str, str], dict[str, Any]], dict[str, Any]]


def _post(url: str, entetes: dict[str, str], corps: dict[str, Any]) -> dict[str, Any]:
    """Reprise sur 429, 5xx et coupure réseau ; ReponseInvalide après 4 essais."""
    statut = "?"
    for essai in range(4):
        try:
            r = requests.post(url, headers=entetes, json=corps, timeout=60)
        except (requests.ConnectionError, requests.Timeout) as e:
            statut = f"réseau ({type(e).__name__})"
            time.sleep(2**essai)
            continue
        statut = str(r.status_code)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2**essai)
            continue
        if not r.ok:
            # Jamais le corps complet : il pourrait reprendre le texte envoyé.
            raise ReponseInvalide(f"jev HTTP {r.status_code} ({_type_erreur(r)})")
        resultat: dict[str, Any] = r.json()
        return resultat
    raise ReponseInvalide(f"jev {statut} après 4 essais")


def _type_erreur(r: requests.Response) -> str:
    try:
        corps: Any = r.json()
    except ValueError:
        return "réponse non JSON"
    try:
        erreur = _ErreurJev.model_validate(corps).error
    except ValidationError:
        return "?"
    return str(erreur.get("type") or erreur.get("code") or "?")[:80]


class _ErreurJev(BaseModel):
    error: dict[str, str | int | None]


@dataclass(frozen=True)
class QuestionOuiNon:
    instructions: str
    oui: str | None = None  # ce qui compte comme oui
    non: str | None = None  # ce qui compte comme non


@dataclass(frozen=True)
class QuestionChoix:
    instructions: str
    criteres: dict[str, str]


Question = QuestionOuiNon | QuestionChoix


@dataclass(frozen=True)
class RepOuiNon:
    probabilite_oui: float
    confiance: float


@dataclass(frozen=True)
class RepChoix:
    choix: str
    probabilites: dict[str, float]
    confiance: float


class _ReponseQuestionJev(BaseModel):
    """Réponse à une question ; champs tolérants (format de la Gateway à confirmer par la sonde)."""

    model_config = ConfigDict(extra="allow")
    choice: str | None = None
    value: str | float | bool | None = None
    noul: float | None = None  # oui/non : probabilité du oui (protocole TypeSafe)
    probability: float | None = None
    score: float | None = None
    probabilities: dict[str, float] = {}
    confidence: float | None = None


class _ReponseJev(BaseModel):
    model_config = ConfigDict(extra="allow")
    answers: dict[str, _ReponseQuestionJev]
    usage: dict[str, int | float | None] = {}
    provider_metadata: dict[str, dict[str, Any]] = {}
    providerMetadata: dict[str, dict[str, Any]] = {}  # variante camelCase


def lire_reponse_jev(
    questions: dict[str, Question], brut: dict[str, Any]
) -> dict[str, RepOuiNon | RepChoix]:
    """Valide la réponse de la Gateway ; lève ReponseInvalide si une question manque."""
    try:
        rep = _ReponseJev.model_validate(brut)
    except ValidationError as e:
        raise ReponseInvalide(f"jev : réponse mal formée ({e.error_count()} erreurs)") from e
    resultat: dict[str, RepOuiNon | RepChoix] = {}
    for nom, q in questions.items():
        r = rep.answers.get(nom)
        if r is None:
            raise ReponseInvalide(f"jev : réponse absente pour {nom}")
        if isinstance(q, QuestionOuiNon):
            p = next(
                (
                    float(v)
                    for v in (r.noul, r.probability, r.value, r.score)
                    if isinstance(v, int | float)
                ),
                r.probabilities.get("true", r.probabilities.get("yes")),
            )
            if p is None or not 0 <= p <= 1:
                raise ReponseInvalide(f"jev : probabilité invalide pour {nom}")
            confiance = r.confidence if r.confidence is not None else max(p, 1 - p)
            resultat[nom] = RepOuiNon(p, confiance)
        else:
            choix = r.choice if r.choice is not None else r.value
            if not isinstance(choix, str) or choix not in q.criteres:
                raise ReponseInvalide(f"jev : choix hors liste pour {nom} : {choix!r}")
            confiance = r.confidence
            if confiance is None:
                confiance = r.probabilities.get(choix, max(r.probabilities.values(), default=0.0))
            resultat[nom] = RepChoix(choix, dict(r.probabilities), confiance)
    return resultat


def cout_jev(brut: dict[str, Any]) -> tuple[int, float]:
    try:
        rep = _ReponseJev.model_validate(brut)
    except ValidationError:
        return 0, 0.0
    entree = int(rep.usage.get("inputTokens") or rep.usage.get("input_tokens") or 0)
    meta = rep.provider_metadata or rep.providerMetadata
    cout: Any = meta.get("gateway", {}).get("cost")
    if isinstance(cout, int | float | str):
        try:
            return entree, float(cout)
        except ValueError:
            pass
    return entree, entree * PRIX_JEV_ENTREE / 1e6


class ClientJev:
    def __init__(
        self,
        budget_usd: float,
        cle: str | None = None,
        url: str | None = None,
        transport: Transport = _post,
    ) -> None:
        self._cle = cle or cle_gateway()
        self.url = url or os.environ.get("JEV_URL") or URL_JEV
        self._modele = os.environ.get("JEV_MODELE") or MODELE_JEV
        self._transport = transport
        self.compteur = Compteur(budget_usd, _nom="jev")

    def corps(self, etat: Etat, questions: dict[str, Question]) -> dict[str, Any]:
        qs: dict[str, Any] = {}
        for nom, q in questions.items():
            if isinstance(q, QuestionOuiNon):
                qs[nom] = {"type": "noul", "instructions": q.instructions}
                if q.oui or q.non:
                    qs[nom]["criteria"] = {"true": q.oui, "false": q.non}
            else:
                qs[nom] = {"type": "choice", "instructions": q.instructions, "criteria": q.criteres}
        # Zéro conservation : exigée au niveau de l'équipe Vercel (AI Gateway > ZDR) et
        # redemandée ici ; si la Gateway refuse ce champ, la sonde le montre.
        return {
            "model": self._modele,
            "state": etat,
            "questions": qs,
            "providerOptions": {"gateway": {"zeroDataRetention": True}},
        }

    def brut(self, etat: Etat, questions: dict[str, Question]) -> dict[str, Any]:
        self.compteur.verifier()
        entetes = {"Authorization": f"Bearer {self._cle}", "Content-Type": "application/json"}
        reponse = self._transport(self.url, entetes, self.corps(etat, questions))
        entree, cout = cout_jev(reponse)
        self.compteur.ajouter(entree, 0, cout)
        return reponse

    def evaluer(
        self, etat: Etat, questions: dict[str, Question]
    ) -> dict[str, RepOuiNon | RepChoix]:
        try:
            return lire_reponse_jev(questions, self.brut(etat, questions))
        except ReponseInvalide:
            self.compteur.erreur()
            raise


def cle_gateway() -> str:
    cle = os.environ.get("AI_GATEWAY_API_KEY")
    if not cle:
        raise SystemExit("AI_GATEWAY_API_KEY absente (clé Vercel AI Gateway).")
    return cle
