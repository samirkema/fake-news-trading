"""Réglages d'exécution lus dans l'environnement — infrastructure neutre, au même
titre que `fakenews.db` et `fakenews.llm`.

Deux raisons d'être, cf. audit phase 10 :

1. **Rendre configurable ce que les user stories exigent de configurable.** US-01
   contextualiseur pose deux critères d'acceptation explicites — « le seuil est
   configurable sans modification du code » et « le nombre d'appels LLM par run est
   plafonné (valeur configurable) ». Les deux valeurs étaient des constantes de
   module : les changer demandait un commit et un déploiement, et le plafond
   n'était même pas passé à l'appelant.

2. **Donner au seuil un domicile qui n'appartient à aucun bloc.** Le frontend
   importait `SEUIL_PAR_DEFAUT` depuis `contextualiseur.declenchement`, alors que
   `doc/V0/architecture.md` pose que « les blocs ne s'appellent pas entre eux
   directement ». `evaluateur/reputation.py` applique d'ailleurs la règle inverse
   dans le même dépôt : il DUPLIQUE la liste du scraper plutôt que de l'importer.
   Le seuil ne peut pas non plus être dupliqué — frontend et contextualiseur
   doivent afficher et traiter exactement le même ensemble d'articles, sans quoi la
   liste montre des articles dont la mise en contexte n'a jamais été demandée.
   Un module d'infrastructure partagé résout les deux : une seule valeur, aucun
   appel inter-blocs.
"""

import logging
import os

logger = logging.getLogger(__name__)

# Seuil de suspicion (US-01 contextualiseur) : 60/100, point de départ arbitraire à
# recalibrer sur un corpus labellisé. Lu par le contextualiseur (quels articles
# traiter) ET par le frontend (quels articles lister par défaut) — les deux DOIVENT
# lire la même valeur.
SEUIL_SUSPICION_PAR_DEFAUT = 60.0
NOM_ENV_SEUIL = "CONTEXTUALISEUR_SEUIL"

# Appels LLM du contextualiseur par run. Vivait dans `contextualiseur.declenchement`,
# module supprimé une fois son seul comportement (`articles_a_traiter`) remplacé par
# la requête SQL de `selectionner_articles_a_traiter` (audit phase 13).
PLAFOND_APPELS_PAR_DEFAUT = 20

# Propositions d'articles acceptées d'un même compte sur 24 h glissantes (V3,
# US-01 crowdsourcing). Sans plafond, un seul compte remplit la file d'attente et
# rend impraticable le travail des contributeurs. Compté en base plutôt qu'en
# mémoire : sur Vercel chaque instance a la sienne, un compteur en mémoire se
# contournerait en insistant jusqu'à tomber sur une autre instance.
PROPOSITIONS_PAR_JOUR_PAR_DEFAUT = 10
NOM_ENV_PROPOSITIONS_MAX = "PROPOSITIONS_MAX_PAR_JOUR"

# Commentaires d'un même compte sur 24 h glissantes (V3, US-08 crowdsourcing).
# Même raison et même comptage en base que les propositions : un compteur en
# mémoire se contournerait en insistant jusqu'à tomber sur une autre instance.
COMMENTAIRES_PAR_JOUR_PAR_DEFAUT = 20
NOM_ENV_COMMENTAIRES_MAX = "COMMENTAIRES_MAX_PAR_JOUR"


def _brut(nom: str) -> str | None:
    valeur = os.environ.get(nom)
    return None if valeur is None or valeur.strip() == "" else valeur.strip()


def entier_depuis_env(nom: str, defaut: int) -> int:
    """Entier positif ou nul depuis l'environnement.

    Une valeur mal saisie doit échouer, mais avec un diagnostic : `int()` nu levait
    une ValueError qui ne nommait ni la variable ni la valeur attendue (cf. audit
    phase 7, finding N10)."""
    brut = _brut(nom)
    if brut is None:
        return defaut
    try:
        valeur = int(brut)
    except ValueError:
        raise SystemExit(
            f"{nom}={brut!r} n'est pas un entier. Corriger la variable "
            f"d'environnement, ou la retirer pour reprendre le défaut ({defaut})."
        )
    if valeur < 0:
        raise SystemExit(f"{nom}={valeur} doit être positif ou nul.")
    return valeur


def reel_depuis_env(nom: str, defaut: float, minimum: float, maximum: float) -> float:
    """Réel borné depuis l'environnement, même contrat de diagnostic.

    Les bornes ne sont pas décoratives : un seuil hors 0-100 ne peut jamais être
    atteint par un score composite (US-08 le contraint à cet intervalle), donc un
    `CONTEXTUALISEUR_SEUIL=600` mal tapé ne provoquerait aucune erreur — il
    éteindrait silencieusement le contextualiseur et viderait la liste du frontend.
    Échouer au démarrage est le seul comportement honnête."""
    brut = _brut(nom)
    if brut is None:
        return defaut
    try:
        valeur = float(brut)
    except ValueError:
        raise SystemExit(
            f"{nom}={brut!r} n'est pas un nombre. Corriger la variable "
            f"d'environnement, ou la retirer pour reprendre le défaut ({defaut})."
        )
    if not minimum <= valeur <= maximum:
        raise SystemExit(
            f"{nom}={valeur} est hors de l'intervalle attendu [{minimum}, {maximum}]. "
            f"Un seuil hors bornes ne serait jamais atteint : le contextualiseur ne "
            f"traiterait plus rien et la liste du frontend resterait vide."
        )
    return valeur


def seuil_suspicion() -> float:
    """Seuil au-dessus duquel un article est jugé suspect (US-01 contextualiseur)."""
    return reel_depuis_env(NOM_ENV_SEUIL, SEUIL_SUSPICION_PAR_DEFAUT, 0.0, 100.0)
