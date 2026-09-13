"""Frontend de consultation en lecture seule (cf. doc/userstories_frontend.md,
doc/architecture.md — FastAPI + Jinja2, déployé sur Vercel, le local ne sert qu'au
dev/test). Ce module ne fait strictement que lire le stockage partagé — aucune route
d'écriture."""

import hashlib
import hmac
import logging
import os
import re
import secrets
import threading
import time
import unicodedata
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import date, datetime, time as heure, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import quote, urlencode, urlsplit

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from fakenews.config import (
    COMMENTAIRES_PAR_JOUR_PAR_DEFAUT,
    NOM_ENV_COMMENTAIRES_MAX,
    NOM_ENV_PROPOSITIONS_MAX,
    PROPOSITIONS_PAR_JOUR_PAR_DEFAUT,
    entier_depuis_env,
    seuil_suspicion,
)
from fakenews.contextualiseur.avertissement import AVERTISSEMENT
from fakenews.db import SessionLocal
from fakenews.models import (
    STATUTS_VIVANTS,
    Article,
    Commentaire,
    Compte,
    MiseEnContexte,
    Proposition,
    Score,
)
from fakenews.normalisation import canonicaliser_url

logger = logging.getLogger(__name__)

# Documentation interactive désactivée (cf. audit phase 10). FastAPI expose par
# défaut /docs, /redoc et /openapi.json SANS passer par les dépendances des routes :
# `compte_courant` ne les protège pas. Sur un déploiement dont US-04 frontend fait
# de l'authentification une « condition bloquante », trois URL publiques décrivant
# les routes, leurs paramètres et le formulaire de connexion sont une surface
# offerte pour rien — le frontend n'a aucun consommateur d'API.
app = FastAPI(title="Fake News — Détection", docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def entetes_securite(request: Request, call_next):
    reponse = await call_next(request)
    reponse.headers["X-Content-Type-Options"] = "nosniff"
    reponse.headers["X-Frame-Options"] = "DENY"
    reponse.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    reponse.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; frame-ancestors 'none'"
    )
    return reponse


templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Seuil de la liste par défaut, résolu AU CHARGEMENT DU MODULE — pas à chaque
# requête (cf. audit phase 10, vérifié de bout en bout) :
#
# - une valeur illisible ou hors bornes doit faire échouer le DÉMARRAGE, avec le
#   message de `fakenews.config` : sur Vercel le déploiement passe au rouge, ce qui
#   se voit. Résolue par requête, la même faute de frappe levait un `SystemExit`
#   à l'intérieur d'un gestionnaire ASGI — ce qui ne produit pas une erreur lisible
#   mais casse le groupe de tâches du serveur, page par page ;
# - un changement de variable d'environnement sur Vercel provoque de toute façon un
#   redéploiement : relire à chaque requête n'apportait aucune souplesse réelle.
#
# Même variable et même défaut que le contextualiseur, via `fakenews.config` : les
# deux blocs doivent délimiter le même ensemble d'articles, sans s'appeler l'un
# l'autre (doc/V0/architecture.md).
SEUIL_LISTE = seuil_suspicion()

ARTICLES_PAR_PAGE = 50
NOM_COOKIE = "session"
# Cookie éphémère portant le code provisoire d'une promotion, du POST à la page
# qui l'affiche. Il remplace une query string : un secret à usage unique n'a rien
# à faire dans une URL, qui atterrit dans les journaux d'accès, l'historique du
# navigateur et le cache de la barre d'adresse (audit phase 17, F17-03). Le
# module disait déjà pourquoi — à propos de simples messages d'erreur.
NOM_COOKIE_CODE = "code_provisoire"
DUREE_CODE_PROVISOIRE = 120  # secondes : le temps de le lire et de le transmettre
ROLE_DEFAUT = "spectateur"
DUREE_SESSION = timedelta(days=30)

# Mode local explicite. Auparavant l'absence de FRONTEND_PASSWORD suffisait à
# ouvrir le site en superadmin sans cookie : une variable d'environnement Vercel
# supprimée ou mal orthographiée rendait le site public, alors que
# doc/V0/userstories_frontend.md US-04 qualifie l'authentification de « condition
# bloquante... qui ne peut être levée que par une décision explicite du porteur du
# projet, pas par défaut ». Le défaut est désormais fermé : il faut poser
# FAKENEWS_MODE=local pour désactiver l'auth (cf. audit, finding H4).
MODE_LOCAL = "local"

# Anti-bruteforce sur /login (cf. audit phase 6, finding M6) : le mot de passe
# partagé est un secret unique, l'endpoint n'avait aucune friction. Fenêtre
# glissante en mémoire du process.
#
# Deux limites connues et assumées : sur Vercel chaque instance a sa propre
# mémoire, donc le plafond réel est multiplié par le nombre d'instances tièdes ;
# et c'est un ralentisseur, pas une barrière cryptographique.
#
# Le plafond ne s'applique QU'AUX ÉCHECS : une authentification réussie passe
# toujours, même compteur plein (cf. `connexion`). C'est ce qui empêche le
# plafond de se transformer en déni de service — dix mauvais mots de passe ne
# doivent pas fermer le site aux gens qui connaissent le bon (audit phase 7, N1).
LOGIN_TENTATIVES_MAX = 10
LOGIN_FENETRE_SECONDES = 300

# Ce que le plafond COÛTE réellement à un attaquant : un délai sur les échecs,
# croissant avec le nombre d'échecs récents du même client.
#
# Le plafond seul n'opposait aucune friction — il changeait la page d'erreur, pas
# le sort de la tentative : 60 essais mesurés en 0,10 s, tous vérifiés, puis le
# bon mot de passe accepté compteur plein (cf. audit phase 14, F4).
#
# Pourquoi ralentir plutôt que refuser : refuser l'évaluation au-delà du plafond
# rendrait celui-ci opposable, mais permettrait aussi de fermer la porte à
# autrui — derrière un proxy non déclaré, l'identifiant client est partagé par
# tous les visiteurs (audit phase 7, N1), et par pseudo un attaquant verrouille
# le compte qu'il vise. Un délai n'enferme personne : un mot de passe CORRECT
# n'est jamais ralenti, un échec ne coûte que du temps.
LOGIN_DELAI_PAR_ECHEC = 0.5
# Plafonne la durée d'occupation d'une place d'attente (cf. LOGIN_DORMEURS_MAX).
# Inerte aux valeurs actuelles — la file est bornée à LOGIN_TENTATIVES_MAX = 10 et
# 0,5 × 10 = 5,0 — c'est un garde-fou de couplage entre ces trois constantes, pas
# une limite qui agit aujourd'hui.
LOGIN_DELAI_MAX = 5.0

# Nombre de tentatives ratées pouvant attendre EN MÊME TEMPS.
#
# Une attente n'est pas gratuite pour le serveur : les routes de ce module sont
# toutes synchrones, donc chacune occupe un fil du pool anyio (40 jetons) pendant
# qu'elle dort — ET la connexion Postgres que `Depends(get_session)` a déjà
# ouverte (pool SQLAlchemy : 5 + 10 de débordement). Sans borne, 40 connexions
# ratées simultanées rendaient le site injoignable : une page publique passait de
# 4 ms à 4,0 s, mesuré (audit phase 15, F15-01).
#
# 4 places sur 15 connexions : il en reste toujours pour le trafic légitime.
# Au-delà, on répond sans attendre — l'attaquant n'obtient rien de plus qu'avant
# le ralentissement, et personne n'est privé du site.
LOGIN_DORMEURS_MAX = 4
_dormeurs = threading.BoundedSemaphore(LOGIN_DORMEURS_MAX)
# Borne dure sur le nombre de clients suivis, pour que la table ne puisse pas
# grossir indéfiniment (audit phase 7, N5). L'éviction est FIFO : `dict` conserve
# l'ordre d'insertion, donc la première clé est la plus anciennement suivie —
# O(1), là où un `min()` sur les horodatages coûtait O(n) à chaque échec sur un
# endpoint public non authentifié (audit phase 8).
LOGIN_CLIENTS_MAX = 10_000
_tentatives_login: dict[str, deque] = {}

# Nombre de proxys de confiance devant l'application. Non définie = aucun, donc
# X-Forwarded-For ignoré (cf. _identifiant_client).
NOM_ENV_PROXYS = "FAKENEWS_PROXYS_DE_CONFIANCE"

# Pseudo : normalisé en minuscules. Jeu de caractères restreint car il est aussi
# un segment de la valeur du cookie signé (« pseudo:expiration:signature ») — pas
# de « : », pas de caractère de contrôle.
_PSEUDO_RE = re.compile(r"^[a-z0-9._-]{1,64}$")

# La signature est TOUJOURS un hexdigest sha256. Le vérifier ici, à la frontière,
# plutôt que de laisser `hmac.compare_digest` recevoir n'importe quoi : un serveur
# ASGI décode les en-têtes en latin-1, donc un octet non-ASCII dans le cookie
# arrivait jusqu'à la comparaison sous forme de `str` non-ASCII — que
# `compare_digest` refuse par un `TypeError`, soit une 500 sur chaque page pour
# qui pose ce cookie (même cause que F2, second site, audit phase 14). Un cookie
# malformé doit rediriger vers /login, comme tous les autres.
_SIGNATURE_RE = re.compile(r"^[0-9a-f]{64}$")


def _mode_local() -> bool:
    return os.environ.get("FAKENEWS_MODE", "").strip().lower() == MODE_LOCAL


def _normaliser_pseudo(brut: str) -> Optional[str]:
    pseudo = brut.strip().lower()
    return pseudo if _PSEUDO_RE.match(pseudo) else None


def _secrets_egaux(attendu: str, recu: str) -> bool:
    """Comparaison à temps constant de deux secrets, quelle que soit leur forme.

    `hmac.compare_digest` refuse deux `str` non-ASCII et lève `TypeError` : un
    refus se transforme alors en 500. Le défaut est apparu TROIS fois — `/login`
    (audit phase 14, F2), la signature du cookie (phase 0), le jeton CSRF
    (phase 17, F17-01) — et les deux premiers correctifs ont traité des LIGNES,
    pas la règle : rien n'empêchait le troisième d'être écrit.

    Ce point de passage unique la traite. Tout site qui compare un secret passe
    par ici, et l'encodage n'est plus l'affaire de celui qui écrit l'appel."""
    return hmac.compare_digest(attendu.encode("utf-8"), recu.encode("utf-8"))


def _normaliser_secret(valeur: str) -> str:
    """Forme NFC d'un mot de passe, avant toute comparaison ou tout hachage.

    « é » s'écrit soit en un codepoint (U+00E9), soit en deux (e + accent
    combinant) selon le clavier et le système — macOS produit couramment la
    seconde forme. Sans normalisation, le MÊME mot de passe à l'écran donne deux
    suites d'octets différentes : mesuré, la forme NFC ouvrait la session (303) et
    la forme NFD était refusée (401), cf. audit phase 15, F15-02.

    C'est la moitié manquante du correctif F2 : celui-ci a supprimé le
    `TypeError` sur les chaînes non-ASCII, sans traiter la question suivante —
    quand deux chaînes différentes désignent-elles le même secret. Appliqué aux
    DEUX chemins (mot de passe partagé et code personnel vérifié par `crypt()`),
    sans quoi US-05 offrirait aux utilisateurs un moyen de se verrouiller dehors
    en choisissant un code accentué."""
    return unicodedata.normalize("NFC", valeur)


def _mot_de_passe_partage() -> Optional[str]:
    """Mot de passe partagé, en forme NFC — lu au SEUL endroit qui le lit.

    Le correctif de normalisation avait été posé au point d'USAGE, dans la route
    de connexion, et pas dans la garde d'accès qui relisait la variable brute.
    Les deux clés divergeaient donc dès que `FRONTEND_PASSWORD` n'était pas en
    forme NFC : la connexion réussissait, signait le cookie avec une clé, et
    chaque page suivante le rejetait avec l'autre. Mesuré — 303 à la connexion,
    puis 303 vers /login à l'infini, sans le moindre message (audit phase 18,
    F18-01).

    Normaliser au point de LECTURE rend la divergence impossible : il n'existe
    plus deux façons d'obtenir cette valeur. Même leçon que `_secrets_egaux`
    pour la comparaison — la règle, pas la ligne."""
    brut = os.environ.get("FRONTEND_PASSWORD")
    return _normaliser_secret(brut) if brut else None


def _cle_signature(mot_de_passe_partage: str, secret_hash: Optional[str]) -> bytes:
    """Clé HMAC du cookie de session. Pour un compte doté d'un code personnel
    (`secret_hash` renseigné en base — cas de samirkema/superadmin), la clé dépend
    de ce hash : impossible alors de forger le cookie de ce pseudo sans le
    connaître, même en connaissant le mot de passe partagé. Pour les autres
    (`secret_hash` absent), seule la connaissance du mot de passe partagé est
    requise — c'est un choix assumé (cf. doc/V1/comptes-3-roles.md)."""
    return f"{mot_de_passe_partage}\x00{secret_hash or ''}".encode()


def _signature(
    pseudo: str, expiration: int, mot_de_passe_partage: str, secret_hash: Optional[str]
) -> str:
    """L'expiration est DANS la charge signée : sans elle, le cookie était un HMAC
    déterministe du seul pseudo, donc valide indéfiniment une fois capté, et
    révocable uniquement en faisant tourner le mot de passe partagé — ce qui
    déconnecte tout le monde (cf. audit, finding M5). `max_age` ne protège rien :
    c'est une indication au navigateur, pas une contrainte serveur."""
    return hmac.new(
        _cle_signature(mot_de_passe_partage, secret_hash),
        f"fakenews-session:{pseudo}:{expiration}".encode(),
        hashlib.sha256,
    ).hexdigest()


def _valeur_cookie(
    pseudo: str,
    mot_de_passe_partage: str,
    secret_hash: Optional[str] = None,
    expiration: Optional[int] = None,
) -> str:
    if expiration is None:
        expiration = int(time.time() + DUREE_SESSION.total_seconds())
    return f"{pseudo}:{expiration}:{_signature(pseudo, expiration, mot_de_passe_partage, secret_hash)}"


def _decomposer_cookie(cookie: Optional[str]) -> Optional[tuple[str, int, str]]:
    """(pseudo, expiration, signature) si la forme du cookie est valide et la
    session non expirée — avant toute vérification cryptographique, qui a besoin du
    `secret_hash` du compte donc d'un accès base (cf. compte_courant)."""
    if not cookie:
        return None
    parties = cookie.split(":")
    if len(parties) != 3:
        return None
    pseudo, expiration_brute, signature_recue = parties
    if not _PSEUDO_RE.match(pseudo) or not _SIGNATURE_RE.match(signature_recue):
        return None
    try:
        expiration = int(expiration_brute)
    except ValueError:
        return None
    if expiration <= time.time():
        return None
    return pseudo, expiration, signature_recue


def _signature_valide(
    pseudo: str,
    expiration: int,
    signature_recue: str,
    mot_de_passe_partage: str,
    secret_hash: Optional[str],
) -> bool:
    return _secrets_egaux(
        _signature(pseudo, expiration, mot_de_passe_partage, secret_hash), signature_recue
    )


def _purger_tentatives(maintenant: float) -> None:
    """Purge globale des clients dont toutes les tentatives sont sorties de la
    fenêtre. Sans elle, `_trop_de_tentatives` ne nettoyait que la clé qu'on lui
    présentait : 50 000 clients échouant une fois chacun laissaient 50 000 entrées
    permanentes (~43 Mo), mesuré (cf. audit phase 7, finding N5)."""
    perimes = [
        cle
        for cle, tentatives in _tentatives_login.items()
        # `not tentatives` d'abord : une file vide n'a pas de `[-1]`.
        if not tentatives or maintenant - tentatives[-1] > LOGIN_FENETRE_SECONDES
    ]
    for identifiant in perimes:
        _tentatives_login.pop(identifiant, None)


def _trop_de_tentatives(identifiant_client: str) -> bool:
    """Fenêtre glissante : purge les tentatives sorties de la fenêtre, puis décide."""
    maintenant = time.monotonic()
    tentatives = _tentatives_login.get(identifiant_client)
    if tentatives is None:
        return False
    while tentatives and maintenant - tentatives[0] > LOGIN_FENETRE_SECONDES:
        tentatives.popleft()
    if not tentatives:
        _tentatives_login.pop(identifiant_client, None)
        return False
    return len(tentatives) >= LOGIN_TENTATIVES_MAX


def _enregistrer_tentative_ratee(identifiant_client: str) -> None:
    maintenant = time.monotonic()
    if identifiant_client not in _tentatives_login and len(_tentatives_login) >= LOGIN_CLIENTS_MAX:
        _purger_tentatives(maintenant)
        while len(_tentatives_login) >= LOGIN_CLIENTS_MAX:
            # Toujours saturé après purge : on sacrifie le suivi le plus
            # anciennement ouvert plutôt que de laisser la table grossir. `dict`
            # garde l'ordre d'insertion, donc `next(iter(...))` est le plus ancien
            # en O(1) — pas de `min()` sur toute la table à chaque échec, et pas
            # d'accès à `deque[-1]` qui supposait la file non vide.
            _tentatives_login.pop(next(iter(_tentatives_login)), None)
    _tentatives_login.setdefault(identifiant_client, deque(maxlen=LOGIN_TENTATIVES_MAX)).append(maintenant)


def _oublier_tentatives(identifiant_client: str) -> None:
    _tentatives_login.pop(identifiant_client, None)


def _ralentir_apres_echec(identifiant_client: str) -> None:
    """Délai imposé APRÈS un échec, proportionnel aux échecs récents du client.

    À appeler une fois la tentative enregistrée, et seulement sur un échec : c'est
    ce qui garantit qu'un mot de passe correct n'est jamais ralenti, y compris
    compteur plein (la propriété que l'audit phase 7, N1, avait imposée).

    Le nombre de dormeurs simultanés est borné (`LOGIN_DORMEURS_MAX`) : au-delà,
    on répond sans attendre. Une attente immobilise un fil ET une connexion
    Postgres ; sans cette borne, quarante essais concurrents fermaient le site à
    tout le monde (audit phase 15, F15-01).

    ponytail: le délai est par requête, donc un attaquant qui parallélise ses
    essais n'est ralenti que d'un facteur borné — désormais explicitement par
    `LOGIN_DORMEURS_MAX`. Marche suivante si ça ne suffit plus : hacher lentement
    le mot de passe partagé (bcrypt, comme les codes personnels), ce qui rend
    chaque essai coûteux quelle que soit la parallélisation, sans immobiliser
    quoi que ce soit — pas un refus, qui rouvrirait N1.
    """
    tentatives = _tentatives_login.get(identifiant_client)
    if not tentatives or LOGIN_DELAI_PAR_ECHEC <= 0:
        return
    if not _dormeurs.acquire(blocking=False):
        return
    try:
        time.sleep(min(LOGIN_DELAI_MAX, LOGIN_DELAI_PAR_ECHEC * len(tentatives)))
    finally:
        _dormeurs.release()


def _proxys_de_confiance() -> int:
    """Nombre de proxys de confiance placés devant l'application.

    0 (défaut) = aucun : `X-Forwarded-For` est ignoré. C'est le seul défaut sûr,
    puisque cet en-tête est posé par le client tant qu'aucun proxy ne le réécrit."""
    brut = os.environ.get(NOM_ENV_PROXYS, "").strip()
    if not brut:
        return 0
    try:
        nombre = int(brut)
    except ValueError:
        logger.error(
            "%s=%r n'est pas un entier — X-Forwarded-For sera ignoré.", NOM_ENV_PROXYS, brut
        )
        return 0
    if nombre < 0:
        logger.error("%s=%d doit être positif — X-Forwarded-For sera ignoré.", NOM_ENV_PROXYS, nombre)
        return 0
    return nombre


def _identifiant_client(request: Request) -> str:
    """Identifie l'appelant pour le plafond de `/login`.

    `X-Forwarded-For` n'est PAS digne de confiance par défaut : c'est le client
    qui l'écrit tant qu'aucun proxy ne le réécrit. La version précédente lisait
    son premier maillon sans condition, ce qui rendait le plafond entièrement
    contournable — mesuré : 50 tentatives avec un en-tête tournant, zéro refus
    (cf. audit phase 8). Un contrôle présent à l'écran et absent dans les faits
    est pire qu'un contrôle manquant.

    L'en-tête n'est donc lu que si l'opérateur a DÉCLARÉ combien de proxys de
    confiance se trouvent devant l'application, via FAKENEWS_PROXYS_DE_CONFIANCE.
    Chaque proxy ajoute en queue l'adresse dont il a reçu la requête : avec N
    proxys de confiance, l'adresse du visiteur est le N-ième maillon en partant
    de la fin. Tout ce qui précède a été écrit par le client et ne vaut rien.

    Sur Vercel — la cible de déploiement du projet — la valeur est 1. La
    plateforme ne se contente pas d'ajouter un maillon : elle ÉCRASE l'en-tête,
    « to prevent IP spoofing », et n'y laisse que l'IP publique réelle
    (https://vercel.com/docs/headers/request-headers). Un seul maillon, digne de
    confiance : `maillons[-1]`.

    Sans déclaration, on retombe sur le pair TCP. Derrière un proxy, cela signifie
    un compteur partagé par tous les visiteurs — ce qui reste sans danger pour la
    disponibilité, puisqu'une authentification RÉUSSIE n'est jamais plafonnée
    (cf. `connexion`) : le partage ne prive personne d'accès, il rend seulement le
    plafond global au lieu d'être par client."""
    proxys = _proxys_de_confiance()
    if proxys > 0:
        transfere = request.headers.get("x-forwarded-for")
        if transfere:
            maillons = [m.strip() for m in transfere.split(",") if m.strip()]
            # Le maillon posé par le proxy de confiance le plus externe. S'il en
            # manque (en-tête tronqué ou forgé trop court), on ne devine pas : on
            # retombe sur le pair TCP.
            if len(maillons) >= proxys:
                return maillons[-proxys]
    return request.client.host if request.client else "inconnu"


class AccesRefuse(Exception):
    pass


@app.exception_handler(AccesRefuse)
def _rediriger_vers_connexion(request: Request, exc: AccesRefuse):
    return RedirectResponse(url="/login", status_code=303)


def get_session():
    with SessionLocal() as session:
        yield session


@dataclass(frozen=True)
class CompteCourant:
    pseudo: str
    role: str
    # Jeton anti-CSRF de CETTE session, résolu en même temps que le compte : il
    # dérive de la même clé que le cookie, donc il change avec le code personnel
    # et avec l'expiration (cf. `_calculer_csrf`, audit phase 17, F17-04).
    csrf: str = ""


_CACHE_COMPTES_TTL = 60.0  # secondes
_CACHE_COMPTES_MAX = 500
_cache_comptes: dict[str, tuple[float, tuple[Optional[str], Optional[str]]]] = {}


def _recuperer_compte_en_cache(session: Session, pseudo: str) -> tuple[Optional[str], Optional[str]]:
    """Cache court pour les couples (role, secret_hash) par pseudo : évite une
    requête SQL par requête HTTP sur les cookies bien formés (audit phase 12)."""
    maintenant = time.monotonic()
    entree = _cache_comptes.get(pseudo)
    if entree is not None:
        expire_a, donnees = entree
        if maintenant < expire_a:
            return donnees
    ligne = session.execute(
        select(Compte.role, Compte.secret_hash).where(func.lower(Compte.pseudo) == pseudo)
    ).one_or_none()
    donnees = (ligne.role, ligne.secret_hash) if ligne else (None, None)
    if len(_cache_comptes) >= _CACHE_COMPTES_MAX:
        _cache_comptes.pop(next(iter(_cache_comptes)), None)
    _cache_comptes[pseudo] = (maintenant + _CACHE_COMPTES_TTL, donnees)
    return donnees


def compte_courant(
    request: Request,
    session: Session = Depends(get_session),
) -> CompteCourant:
    """Valide le cookie de session et résout le compte courant.

    Le défaut est FERMÉ : hors mode local explicite, une FRONTEND_PASSWORD absente
    ne rend pas le site public, elle le rend inaccessible. C'est l'inverse du
    comportement précédent, qui transformait une variable d'environnement oubliée
    en ouverture d'accès public (cf. audit, finding H4)."""
    if _mode_local():
        return CompteCourant(
            pseudo="local", role="superadmin", csrf=_calculer_csrf("local", 0, _SECRET_LOCAL.hex(), None)
        )
    mot_de_passe = _mot_de_passe_partage()
    if not mot_de_passe:
        logger.error(
            "FRONTEND_PASSWORD absente hors mode local : tout accès est refusé. "
            "Définir la variable, ou poser FAKENEWS_MODE=local pour du développement."
        )
        raise AccesRefuse()
    decompose = _decomposer_cookie(request.cookies.get(NOM_COOKIE))
    if decompose is None:
        raise AccesRefuse()
    pseudo, expiration, signature_recue = decompose
    # Aucun plafond ici, délibérément : l'identifiant client est partagé par tous les
    # visiteurs derrière le proxy (cf. `_identifiant_client`), donc plafonner cette
    # route fermait le site entier à qui présentait pourtant un cookie valide.
    # La charge base d'un cookie forgé est absorbée par le cache ci-dessous.
    # ponytail: si la rotation de pseudos devient un vrai problème, plafonner les
    # MISS de cache par pseudo, jamais par identifiant client.
    role_brut, secret_hash = _recuperer_compte_en_cache(session, pseudo)
    role = role_brut or ROLE_DEFAUT
    if not _signature_valide(pseudo, expiration, signature_recue, mot_de_passe, secret_hash):
        raise AccesRefuse()
    return CompteCourant(
        pseudo=pseudo, role=role, csrf=_calculer_csrf(pseudo, expiration, mot_de_passe, secret_hash)
    )


ROLES_ORDRE = {"spectateur": 0, "contributeur": 1, "superadmin": 2}


def _contexte(compte: CompteCourant, **extra) -> dict:
    """Contexte commun à toute page : navigation et avertissement automatisé.

    Le rôle n'est jamais transmis comme libellé — seulement les capacités qu'il
    ouvre, que la navigation traduit en liens. C'est ce qui rend le rôle visible
    « par ses effets » sans l'afficher (cf. doc/V3, tableau des contrats
    modifiés). `extra` en dernier : la page de détail passe l'avertissement
    PERSISTÉ, qui doit primer sur la constante (US-04 contextualiseur)."""
    rang = ROLES_ORDRE.get(compte.role, 0)
    return {
        "compte": compte,
        "csrf": compte.csrf,
        "peut_decider": rang >= ROLES_ORDRE["contributeur"],
        "peut_administrer": rang >= ROLES_ORDRE["superadmin"],
        "avertissement": AVERTISSEMENT,
        **extra,
    }


def exige_role(minimum: str):
    """Dépendance FastAPI : refuse un compte dont le rôle est en dessous de
    `minimum` (US-02, US-06 crowdsourcing).

    Comparaison sur un ORDRE, jamais sur une égalité : le superadmin est aussi
    contributeur — il propose et décide comme les autres. Une égalité stricte
    l'aurait exclu des écrans qu'il est censé pouvoir utiliser.

    La garde est ici, pas dans les gabarits : masquer un lien n'est pas un
    contrôle d'accès. Un test doit vérifier l'accès direct à l'URL."""
    seuil = ROLES_ORDRE[minimum]

    def _garde(compte: CompteCourant = Depends(compte_courant)) -> CompteCourant:
        if ROLES_ORDRE.get(compte.role, 0) < seuil:
            # 404 plutôt que 403 : un spectateur n'a pas à apprendre que cette
            # page existe. Il n'a rien à en faire, et l'existence d'une file de
            # modération est en soi une information.
            raise HTTPException(status_code=404, detail="Page introuvable")
        return compte

    return _garde


# --- Protection CSRF -----------------------------------------------------------
#
# Jusqu'ici le seul formulaire du site était la connexion, où un CSRF n'a aucun
# intérêt pour l'attaquant. La V3 ouvre des actions qui ENGAGENT le compte :
# accepter un article, changer un code, promouvoir un contributeur. `samesite=lax`
# réduit la surface, il ne la ferme pas (formulaires POST issus d'une navigation
# de premier niveau, navigateurs anciens).
#
# Jeton dérivé du secret de session déjà en place — pas de stockage serveur, donc
# rien à partager entre instances Vercel.
_SECRET_LOCAL = secrets.token_bytes(32)


def _calculer_csrf(
    pseudo: str, expiration: int, mot_de_passe_partage: str, secret_hash: Optional[str]
) -> str:
    """Jeton lié à la SESSION, via la clé qui signe déjà le cookie.

    La première version dérivait du seul couple (mot de passe partagé, pseudo).
    Or ce mot de passe est PARTAGÉ : tout utilisateur légitime pouvait donc
    calculer le jeton de n'importe quel autre pseudo et monter une CSRF contre un
    contributeur — par exemple lui faire accepter une proposition (audit
    phase 17, F17-04).

    `_cle_signature` intègre `secret_hash` : le jeton d'un compte à code personnel
    est désormais incalculable sans ce code, et il cesse de valoir quand le code
    change. L'expiration entre dans la charge, donc le jeton change à chaque
    session.

    ponytail: pour un compte SANS code personnel (spectateur), la clé reste le
    mot de passe partagé et seule l'expiration distingue les sessions — un
    attaquant qui sait à la seconde près quand sa victime s'est connectée peut
    encore la deviner. Le vrai remède est le même que pour le bruteforce : des
    codes personnels pour tout le monde, pas un secret commun."""
    return hmac.new(
        _cle_signature(mot_de_passe_partage, secret_hash),
        f"csrf:{pseudo}:{expiration}".encode(),
        hashlib.sha256,
    ).hexdigest()


def exige_csrf(jeton_recu: str, compte: CompteCourant) -> None:
    """À appeler au début de CHAQUE route d'écriture, avant tout effet de bord.

    Le jeton voyage dans le corps du formulaire (champ caché), pas dans l'URL :
    une URL se retrouve dans les journaux, l'historique et le `Referer`."""
    if not _secrets_egaux(compte.csrf, jeton_recu):
        raise HTTPException(status_code=403, detail="Jeton de formulaire invalide ou expiré.")


def _enregistrer_compte(session: Session, pseudo: str) -> None:
    """US-07 : matérialise un pseudo authentifié en `spectateur`, pour que le
    superadmin puisse choisir un contributeur PARMI les comptes plutôt que de
    deviner des pseudos.

    Seul endroit où le frontend crée une ligne de compte, et seulement après une
    authentification réussie : ce n'est pas une inscription ouverte. Un échec
    n'empêche jamais la connexion — deux onglets qui se connectent en même temps
    perdent la course à l'index unique, ce n'est pas un problème de
    l'utilisateur."""
    try:
        with session.begin_nested():
            existe = session.execute(
                select(Compte.id).where(func.lower(Compte.pseudo) == pseudo)
            ).scalar_one_or_none()
            if existe is None:
                session.add(Compte(pseudo=pseudo, role=ROLE_DEFAUT))
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.warning("Enregistrement du compte %s impossible (%s) — connexion maintenue.", pseudo, type(exc).__name__)


def _erreur_login(request: Request, message: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "login.html", {"erreur": message}, status_code=401
    )


@app.get("/login", response_class=HTMLResponse)
def page_connexion(request: Request):
    return templates.TemplateResponse(request, "login.html", {"erreur": None})


@app.post("/login")
def connexion(
    request: Request,
    pseudo: str = Form(...),
    mot_de_passe: str = Form(...),
    session: Session = Depends(get_session),
):
    """Le pseudo détermine le rôle (cf. doc/V1/comptes-3-roles.md). Mot de passe :
    un compte doté d'un `secret_hash` en base (samirkema/superadmin) doit fournir
    CE code — le mot de passe partagé ne lui donne pas accès. Tous les autres
    pseudos utilisent le mot de passe partagé FRONTEND_PASSWORD.

    Les tentatives ratées sont comptées par client sur une fenêtre glissante
    (cf. audit phase 6, finding M6). Le plafond ne s'applique QU'AUX ÉCHECS : on
    vérifie d'abord les identifiants, et un mot de passe correct ouvre la session
    même compteur plein. Sans cette règle, dix mauvais mots de passe fermaient le
    site à tous ceux qui connaissent le bon — un déni de service à dix requêtes
    (cf. audit phase 7, finding N1)."""
    partage = _mot_de_passe_partage()
    if not partage:
        logger.error("Tentative de connexion alors que FRONTEND_PASSWORD n'est pas définie.")
        return _erreur_login(request, "Authentification non configurée sur ce déploiement.")

    client = _identifiant_client(request)
    plafond_atteint = _trop_de_tentatives(client)

    pseudo_normalise = _normaliser_pseudo(pseudo)
    # Le mot de passe partagé arrive déjà normalisé (`_mot_de_passe_partage`) ;
    # reste la saisie de l'utilisateur, qui dépend de son clavier.
    mot_de_passe = _normaliser_secret(mot_de_passe)
    if pseudo_normalise is None:
        mot_de_passe_ok = False
    else:
        secret_hash = session.execute(
            select(Compte.secret_hash).where(func.lower(Compte.pseudo) == pseudo_normalise)
        ).scalar_one_or_none()
        if secret_hash is not None:
            # Vérification bcrypt déléguée à Postgres (pgcrypto) : crypt(code, hash) == hash.
            mot_de_passe_ok = bool(
                session.execute(
                    select(func.crypt(mot_de_passe, secret_hash) == secret_hash)
                ).scalar_one()
            )
        else:
            # Un mot de passe accentué renvoyait 500 au lieu de 401, et un
            # FRONTEND_PASSWORD accentué rendait le site entièrement
            # inaccessible (audit phase 14, F2). Voir `_secrets_egaux`.
            mot_de_passe_ok = _secrets_egaux(partage, mot_de_passe)

    if not mot_de_passe_ok:
        _enregistrer_tentative_ratee(client)
        _ralentir_apres_echec(client)
        if plafond_atteint:
            logger.warning("Trop de tentatives ratées depuis %s — essais ralentis.", client)
            return templates.TemplateResponse(
                request,
                "login.html",
                # Le message dit ce qui se passe réellement. L'ancien annonçait
                # « réessayer dans quelques minutes » alors que la tentative
                # suivante était évaluée immédiatement : un écran qui décrit un
                # contrôle que le code n'exerce pas (cf. audit phase 14, F4).
                {"erreur": "Trop de tentatives récentes : chaque nouvel essai est ralenti."},
                status_code=429,
            )
        if pseudo_normalise is None:
            return _erreur_login(
                request, "Pseudo invalide (lettres, chiffres, « . _ - », 64 caractères max)."
            )
        return _erreur_login(request, "Identifiants incorrects.")

    _oublier_tentatives(client)
    # Une connexion réussie est le seul moment où l'on sait que le compte vient
    # d'être relu : on repart d'une entrée fraîche plutôt que d'un reliquat de 60 s.
    _cache_comptes.pop(pseudo_normalise, None)
    _enregistrer_compte(session, pseudo_normalise)
    reponse = RedirectResponse(url="/", status_code=303)
    reponse.set_cookie(
        NOM_COOKIE,
        _valeur_cookie(pseudo_normalise, partage, secret_hash),
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=int(DUREE_SESSION.total_seconds()),
    )
    return reponse


@app.post("/logout")
def deconnexion(
    csrf: str = Form(""),
    compte: CompteCourant = Depends(compte_courant),
):
    """Ferme la session courante.

    La route existait depuis l'origine, mais **aucun gabarit n'y renvoyait** : il
    n'y avait donc, en pratique, aucun moyen de se déconnecter — et, la route
    étant un POST, pas même en tapant l'URL. Vingt-trois audits ne l'ont pas vu :
    ils cherchaient des défauts dans ce qui existe, jamais l'absence de ce qui
    devrait exister. C'est un utilisateur qui a essayé de s'en servir.

    Le jeton CSRF est exigé ici comme sur les six autres écritures. Déconnecter
    quelqu'un de force est une nuisance, pas une brèche — mais une route
    d'écriture non protégée au milieu de six qui le sont est une incohérence dont
    personne ne se souviendra dans six mois."""
    exige_csrf(csrf, compte)

    reponse = _redirection("/login")
    # Attributs symétriques de la pose : un navigateur qui applique strictement les
    # règles de correspondance ignore un Set-Cookie de suppression dont les
    # attributs divergent (cf. audit, finding L12).
    reponse.delete_cookie(NOM_COOKIE, httponly=True, secure=True, samesite="lax")
    return reponse


def _url_liste(score_min, date_min, date_max, tous, page) -> Optional[str]:
    if page < 1:
        return None
    params = {}
    if score_min is not None:
        params["score_min"] = score_min
    if date_min:
        params["date_min"] = date_min.isoformat()
    if date_max:
        params["date_max"] = date_max.isoformat()
    if tous:
        params["tous"] = "1"
    if page != 1:
        params["page"] = page
    return f"/?{urlencode(params)}" if params else "/"


def _parser_score_min(brut: Optional[str]) -> Optional[float]:
    """Le formulaire HTML soumet une chaîne vide (pas un paramètre absent) pour un
    champ numérique laissé vide — FastAPI/Pydantic ne convertit pas "" en None pour un
    `Optional[float]`, ce qui faisait échouer TOUT filtrage dès qu'un champ restait
    vide (422 sur un simple clic de "Filtrer"), cf. signalement utilisateur."""
    if not brut:
        return None
    try:
        valeur = float(brut)
    except ValueError:
        raise HTTPException(status_code=422, detail="score_min invalide")
    if not (0 <= valeur <= 100):
        raise HTTPException(status_code=422, detail="score_min doit être entre 0 et 100")
    return valeur


def _parser_date(brut: Optional[str], nom: str) -> Optional[date]:
    """Même raison que _parser_score_min ci-dessus, pour les champs date."""
    if not brut:
        return None
    try:
        return date.fromisoformat(brut)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{nom} invalide")


def _debut_de_journee(jour: date) -> datetime:
    """Minuit UTC du jour donné. Explicite le fuseau plutôt que de laisser Postgres
    coercer une `date` nue selon le TimeZone de la session, qui dépend du serveur."""
    return datetime.combine(jour, heure.min, tzinfo=timezone.utc)


@app.get("/", response_class=HTMLResponse)
def liste_articles(
    request: Request,
    score_min_brut: Optional[str] = Query(None, alias="score_min"),
    date_min_brut: Optional[str] = Query(None, alias="date_min"),
    date_max_brut: Optional[str] = Query(None, alias="date_max"),
    tous: bool = Query(False),
    page: int = Query(1, ge=1),
    session: Session = Depends(get_session),
    compte: CompteCourant = Depends(compte_courant),
):
    """US-01 frontend : liste des articles suspects, filtrable, triée par score
    décroissant, paginée. Par défaut seuls les articles au-dessus du seuil
    apparaissent ; `tous=1` lève ce filtre par défaut (mode "tous les articles",
    cf. US-01 frontend). Un article `non_évaluable` n'apparaît jamais (cf. US-08
    évaluateur). `score_min`/`date_min`/`date_max` reçus en texte brut puis parsés
    manuellement : une valeur vide (champ de formulaire non rempli) devient
    l'absence de filtre, une valeur malformée non vide reste rejetée en 422 (cf.
    audit de suivi)."""
    score_min = _parser_score_min(score_min_brut)
    date_min = _parser_date(date_min_brut, "date_min")
    date_max = _parser_date(date_max_brut, "date_max")
    seuil_effectif = score_min if score_min is not None else (None if tous else SEUIL_LISTE)

    stmt = select(Article, Score).join(Score, Score.article_id == Article.id).where(Score.non_evaluable.is_(False))
    if seuil_effectif is not None:
        stmt = stmt.where(Score.score_final >= seuil_effectif)
    if date_min:
        stmt = stmt.where(Article.date_publication >= _debut_de_journee(date_min))
    if date_max:
        # Borne haute INCLUSIVE : comparer un timestamptz à une `date` la coerce à
        # minuit, ce qui supprimait toute la journée `date_max` alors que le
        # formulaire promet « jusqu'au » (cf. audit, finding M2).
        stmt = stmt.where(Article.date_publication < _debut_de_journee(date_max + timedelta(days=1)))
    # Départage par id : sans clé secondaire stable, deux articles à score égal
    # peuvent changer d'ordre entre la requête de la page 1 et celle de la page 2,
    # ce qui duplique les uns et masque les autres (cf. audit, finding M1). Les
    # scores sont des numeric(5,2) : les ex æquo sont la règle, pas l'exception.
    stmt = (
        stmt.order_by(Score.score_final.desc(), Article.id)
        .limit(ARTICLES_PAR_PAGE + 1)
        .offset((page - 1) * ARTICLES_PAR_PAGE)
    )

    lignes = session.execute(stmt).all()
    a_page_suivante = len(lignes) > ARTICLES_PAR_PAGE
    resultats = lignes[:ARTICLES_PAR_PAGE]

    return templates.TemplateResponse(
        request,
        "liste.html",
        _contexte(
            compte,
            resultats=resultats,
            score_min=score_min,
            date_min=date_min.isoformat() if date_min else None,
            date_max=date_max.isoformat() if date_max else None,
            tous=tous,
            url_page_precedente=_url_liste(score_min, date_min, date_max, tous, page - 1) if page > 1 else None,
            url_page_suivante=_url_liste(score_min, date_min, date_max, tous, page + 1) if a_page_suivante else None,
        ),
    )


@app.get("/articles/{article_id}", response_class=HTMLResponse)
def detail_article(
    request: Request,
    article_id: uuid.UUID,
    session: Session = Depends(get_session),
    compte: CompteCourant = Depends(compte_courant),
    erreur: Optional[str] = Query(None),
):
    """US-02 frontend : détail des sous-scores/justifications/poids.
    US-03 frontend : mise en contexte affichée, ou message explicite si absente."""
    article = session.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article introuvable")

    score = session.execute(select(Score).where(Score.article_id == article_id)).scalar_one_or_none()
    mise_en_contexte = session.execute(
        select(MiseEnContexte).where(MiseEnContexte.article_id == article_id)
    ).scalar_one_or_none()

    # Un commentaire retiré disparaît du public, mais reste consultable par le
    # porteur du projet : c'est ce qui distingue le masquage de la suppression
    # (US-08). Le filtre est côté SERVEUR, pas dans le gabarit.
    commentaires = select(Commentaire).where(Commentaire.article_id == article_id)
    if ROLES_ORDRE.get(compte.role, 0) < ROLES_ORDRE["superadmin"]:
        commentaires = commentaires.where(Commentaire.retire_le.is_(None))
    commentaires = (
        session.execute(commentaires.order_by(Commentaire.date_creation)).scalars().all()
    )

    return templates.TemplateResponse(
        request,
        "detail.html",
        _contexte(
            compte,
            article=article,
            score=score,
            mise_en_contexte=mise_en_contexte,
            # US-04 contextualiseur : « cette mention est portée par la DONNÉE
            # elle-même (persistée en base), pas uniquement ajoutée a posteriori par
            # le frontend ». La colonne `mise_en_contexte.avertissement` était
            # écrite à chaque génération puis jamais relue : la page affichait la
            # constante du code, si bien qu'un changement de formulation aurait
            # réécrit l'avertissement de verdicts déjà rendus — exactement ce que
            # la persistance est censée empêcher (cf. audit phase 10).
            # Repli sur la constante quand aucune mise en contexte n'existe, pour
            # tenir US-04 frontend (« chaque page affichant un score reprend
            # l'avertissement »).
            commentaires=commentaires,
            longueur_max=COMMENTAIRE_LONGUEUR_MAX,
            erreur=_message(erreur),
            avertissement=mise_en_contexte.avertissement if mise_en_contexte else AVERTISSEMENT,
        ),
    )


# ==============================================================================
# V3 — Crowdsourcing (cf. doc/V3/userstories_crowdsourcing.md)
#
# Premières routes d'ÉCRITURE du frontend. Elles écrivent `comptes` et
# `propositions` — jamais `articles`, `scores` ni `mise_en_contexte` : le verdict
# reste produit par le pipeline seul (doc/V0/architecture.md, décision V3).
# ==============================================================================

# Longueur minimale d'un code personnel choisi par son titulaire (US-05).
# Volontairement SEULE règle : pas de classe de caractères imposée, qui produit
# surtout des mots de passe prévisibles ("Motdepasse1!") sans ajouter d'entropie
# réelle. La longueur, elle, en ajoute toujours.
CODE_LONGUEUR_MIN = 12
# bcrypt ne prend en compte que les 72 PREMIERS OCTETS de ce qu'on lui donne :
# au-delà, `crypt()` tronque en silence. Accepter 200 caractères promettait donc
# un secret que l'algorithme ne vérifie pas — mesuré : deux codes identiques sur
# 72 octets et différents ensuite ouvrent le MÊME compte (audit phase 17, F17-02).
# En octets et non en caractères : un « é » en compte deux.
CODE_LONGUEUR_MAX_OCTETS = 72

# US-01 : bornes de saisie d'une proposition.
URL_LONGUEUR_MAX = 2000
NOTE_LONGUEUR_MAX = 1000
MOTIF_LONGUEUR_MAX = 500
# US-08 : un commentaire est un apport de contexte, pas une tribune. La borne
# protège autant l'affichage que la base.
COMMENTAIRE_LONGUEUR_MAX = 2000
PROPOSITIONS_PAR_PAGE = 50


def _redirection(url: str) -> RedirectResponse:
    """303 : après un POST, le rechargement de la page ne rejoue pas l'action."""
    return RedirectResponse(url=url, status_code=303)


def _avec_erreur(chemin: str, code: str, ancre: str = "") -> RedirectResponse:
    """Renvoie vers `chemin` en y portant un CODE d'erreur, jamais un texte.

    `ancre` ramène l'utilisateur là où le message s'affiche. Sans elle, un
    commentaire refusé renvoyait en haut de la page alors que l'erreur est rendue
    en bas : le chemin nominal avait son ancre, le chemin d'échec l'avait perdue
    (audit phase 21, F21-02).

    Le texte était auparavant repris tel quel de la query string et rendu dans la
    page : un lien forgé affichait donc un message arbitraire — « votre compte est
    suspendu, appelez le… » — dans une page authentique du site, ce qui est le
    support classique d'un hameçonnage (audit phase 17, F17-05). Le gabarit ne
    reçoit plus que ce que `_message` accepte de traduire."""
    return _redirection(f"{chemin}?erreur={quote(code)}{ancre}")


def _message(code: Optional[str]) -> Optional[str]:
    """Traduit un code d'erreur connu. Un code inconnu ne produit RIEN — c'est ce
    qui referme le vecteur d'hameçonnage."""
    if code is None:
        return None
    # Les deux seuls messages qui dépendent de la configuration la lisent
    # eux-mêmes : la construire pour chaque message obligeait à deux lectures
    # d'environnement à chaque rendu de page (audit phase 21, F21-06).
    if code == "plafond_propositions":
        plafond = entier_depuis_env(NOM_ENV_PROPOSITIONS_MAX, PROPOSITIONS_PAR_JOUR_PAR_DEFAUT)
        return f"Plafond atteint ({plafond} propositions par 24 h)."
    if code == "plafond_commentaires":
        plafond = entier_depuis_env(NOM_ENV_COMMENTAIRES_MAX, COMMENTAIRES_PAR_JOUR_PAR_DEFAUT)
        return f"Plafond atteint ({plafond} commentaires par 24 h)."
    return {
        "code_actuel_faux": "Code actuel incorrect.",
        "sans_code_personnel": "Ce compte n\'a pas de code personnel.",
        "codes_differents": "Les deux saisies ne correspondent pas.",
        "code_trop_court": f"Le code doit faire au moins {CODE_LONGUEUR_MIN} caractères.",
        "code_trop_long": (
            f"Le code ne peut pas dépasser {CODE_LONGUEUR_MAX_OCTETS} octets — "
            "au-delà, l\'algorithme de hachage ignore la fin."
        ),
        "url_invalide": "Adresse invalide (http ou https attendu).",
        "note_trop_longue": "Note trop longue.",
        "deja_dans_la_file": "Cet article est déjà dans la file.",
        "proposition_deja_decidee": "Proposition introuvable ou déjà décidée.",
        "refus_sans_motif": "Un refus doit être motivé.",
        "commentaire_vide": "Un commentaire ne peut pas être vide.",
        "commentaire_trop_long": f"Un commentaire ne peut pas dépasser {COMMENTAIRE_LONGUEUR_MAX} caractères.",
        "commentaire_introuvable": "Commentaire introuvable ou déjà retiré.",
        "compte_introuvable": "Compte introuvable.",
        "superadmin_non_promouvable": "Un superadmin ne se promeut pas.",
        "superadmin_non_retrogradable": "Un superadmin ne se rétrograde pas ici.",
        "deja_contributeur": (
            "Ce compte est déjà contributeur — le promouvoir à nouveau effacerait "
            "le code qu\'il a choisi."
        ),
    }.get(code)


def _hacher_code(session: Session, code: str) -> str:
    """bcrypt via pgcrypto — même mécanisme que la migration 0002, donc un code
    posé à la main en SQL et un code choisi depuis l'écran sont interchangeables."""
    return session.execute(select(func.crypt(code, func.gen_salt("bf")))).scalar_one()


def _valider_code(code: str, confirmation: str) -> Optional[str]:
    """Code d'erreur (cf. `_message`), ou None si le code est acceptable."""
    if code != confirmation:
        return "codes_differents"
    if len(code) < CODE_LONGUEUR_MIN:
        return "code_trop_court"
    if len(code.encode("utf-8")) > CODE_LONGUEUR_MAX_OCTETS:
        return "code_trop_long"
    return None


def _invalider_compte(pseudo: str) -> None:
    """Le cache (role, secret_hash) a 60 s de TTL : sans purge explicite, un
    changement de rôle ou de code resterait sans effet jusqu'à une minute
    (cf. audit phase 14, F13)."""
    _cache_comptes.pop(pseudo, None)


# --- US-05 — Espace compte -----------------------------------------------------


@app.get("/compte", response_class=HTMLResponse)
def espace_compte(
    request: Request,
    session: Session = Depends(get_session),
    compte: CompteCourant = Depends(compte_courant),
    erreur: Optional[str] = Query(None),
    succes: Optional[str] = Query(None),
):
    """US-05 : mes propositions, et le changement de mon code personnel si j'en
    ai un. Un spectateur se connecte avec le mot de passe partagé : il n'a pas de
    code à changer, et l'écran ne lui en propose pas."""
    _, secret_hash = _recuperer_compte_en_cache(session, compte.pseudo)
    mes_propositions = (
        session.execute(
            select(Proposition)
            .where(Proposition.propose_par == compte.pseudo)
            .order_by(Proposition.date_proposition.desc())
            .limit(PROPOSITIONS_PAR_PAGE)
        )
        .scalars()
        .all()
    )
    return templates.TemplateResponse(
        request,
        "compte.html",
        _contexte(
            compte,
            a_un_code=secret_hash is not None,
            propositions=mes_propositions,
            erreur=_message(erreur),
            succes=succes,
            longueur_min=CODE_LONGUEUR_MIN,
        ),
    )


@app.post("/compte/code")
def changer_code(
    request: Request,
    code_actuel: str = Form(...),
    nouveau_code: str = Form(...),
    confirmation: str = Form(...),
    csrf: str = Form(""),
    session: Session = Depends(get_session),
    compte: CompteCourant = Depends(compte_courant),
):
    """US-05 — changement du code personnel par son titulaire.

    Exige le code ACTUEL : un cookie volé ne doit pas suffire à s'approprier le
    compte définitivement. Le changement invalide au passage toutes les sessions
    de ce pseudo — la clé de signature du cookie dérive de `secret_hash`
    (cf. doc/V1/comptes-3-roles.md) : propriété voulue, pas effet de bord."""
    exige_csrf(csrf, compte)

    _, secret_hash = _recuperer_compte_en_cache(session, compte.pseudo)
    if secret_hash is None:
        # Un spectateur utilise le mot de passe partagé : lui laisser poser un
        # code ici reviendrait à créer une frontière que personne n'a décidée.
        return _avec_erreur("/compte", "sans_code_personnel")

    actuel_ok = bool(
        session.execute(
            select(func.crypt(_normaliser_secret(code_actuel), secret_hash) == secret_hash)
        ).scalar_one()
    )
    if not actuel_ok:
        logger.warning("Changement de code refusé pour %s : code actuel incorrect.", compte.pseudo)
        return _avec_erreur("/compte", "code_actuel_faux")

    nouveau = _normaliser_secret(nouveau_code)
    probleme = _valider_code(nouveau, _normaliser_secret(confirmation))
    if probleme:
        return _avec_erreur("/compte", probleme)

    session.execute(
        update(Compte)
        .where(func.lower(Compte.pseudo) == compte.pseudo)
        .values(secret_hash=_hacher_code(session, nouveau))
    )
    session.commit()
    _invalider_compte(compte.pseudo)
    logger.info("Code personnel changé pour %s — sessions existantes invalidées.", compte.pseudo)
    # Le cookie courant ne vaut plus rien : on renvoie vers la connexion plutôt
    # que de laisser l'utilisateur découvrir sa déconnexion au clic suivant.
    reponse = _redirection("/login")
    reponse.delete_cookie(NOM_COOKIE, httponly=True, secure=True, samesite="lax")
    return reponse


# --- US-06 — Nommer un contributeur --------------------------------------------


@app.get("/admin/comptes", response_class=HTMLResponse)
def administrer_comptes(
    request: Request,
    session: Session = Depends(get_session),
    compte: CompteCourant = Depends(exige_role("superadmin")),
    erreur: Optional[str] = Query(None),
):
    """US-06 : la liste des comptes existants (US-07 les matérialise à la
    connexion) et les deux seules actions offertes — promouvoir, rétrograder.

    Le code provisoire arrive par un cookie éphémère, lu ici puis effacé : il est
    donc affiché UNE fois, sans laisser de trace dans l'URL."""
    comptes = (
        session.execute(select(Compte).order_by(Compte.role.desc(), Compte.pseudo)).scalars().all()
    )
    depot = request.cookies.get(NOM_COOKIE_CODE)
    pseudo_promu, _, code_provisoire = (depot or "").partition(":")
    reponse = templates.TemplateResponse(
        request,
        "admin_comptes.html",
        _contexte(
            compte,
            comptes=comptes,
            code_provisoire=code_provisoire or None,
            pseudo_promu=pseudo_promu or None,
            erreur=_message(erreur),
        ),
    )
    if depot:
        reponse.delete_cookie(NOM_COOKIE_CODE, httponly=True, secure=True, samesite="lax")
    return reponse


@app.post("/admin/comptes/{compte_id}/promouvoir")
def promouvoir(
    compte_id: uuid.UUID,
    csrf: str = Form(""),
    session: Session = Depends(get_session),
    compte: CompteCourant = Depends(exige_role("superadmin")),
):
    """US-06 — passage en `contributeur` avec un code provisoire.

    Le code est TIRÉ AU SORT et affiché une seule fois : le superadmin le
    transmet hors ligne, le titulaire le change dans son espace (US-05). Poser un
    rôle privilégié sans code laisserait le mot de passe partagé ouvrir ce compte
    — c'est précisément ce que la migration 0004 rend impossible."""
    exige_csrf(csrf, compte)

    cible = session.get(Compte, compte_id)
    if cible is None:
        return _avec_erreur("/admin/comptes", "compte_introuvable")
    if cible.role == "superadmin":
        return _avec_erreur("/admin/comptes", "superadmin_non_promouvable")
    if cible.role == "contributeur":
        # Re-promouvoir régénérerait un code provisoire et écraserait en silence
        # celui que le titulaire a choisi (US-05), en le déconnectant au passage.
        # L'interface n'offre pas le bouton dans ce cas ; une opération
        # destructrice ne doit pas dépendre de l'absence d'un bouton
        # (audit phase 17, F17-07).
        return _avec_erreur("/admin/comptes", "deja_contributeur")

    code_provisoire = secrets.token_urlsafe(12)
    cible.role = "contributeur"
    cible.secret_hash = _hacher_code(session, code_provisoire)
    session.commit()
    _invalider_compte(cible.pseudo.lower())
    logger.info("%s a promu %s au rôle contributeur.", compte.pseudo, cible.pseudo)
    reponse = _redirection("/admin/comptes")
    reponse.set_cookie(
        NOM_COOKIE_CODE,
        f"{cible.pseudo}:{code_provisoire}",
        max_age=DUREE_CODE_PROVISOIRE,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return reponse


@app.post("/admin/comptes/{compte_id}/retrograder")
def retrograder(
    compte_id: uuid.UUID,
    csrf: str = Form(""),
    session: Session = Depends(get_session),
    compte: CompteCourant = Depends(exige_role("superadmin")),
):
    """US-06 — retour au rôle `spectateur`. Le code personnel est effacé : le
    compte retombe sur le mot de passe partagé, et ses sessions cessent de valoir
    (la clé du cookie dérivait de ce code)."""
    exige_csrf(csrf, compte)

    cible = session.get(Compte, compte_id)
    if cible is None:
        return _avec_erreur("/admin/comptes", "compte_introuvable")
    if cible.role == "superadmin":
        # Le schéma interdit un superadmin sans code ; et se rétrograder soi-même
        # fermerait la seule porte d'administration du site.
        return _avec_erreur("/admin/comptes", "superadmin_non_retrogradable")

    cible.role = ROLE_DEFAUT
    cible.secret_hash = None
    session.commit()
    _invalider_compte(cible.pseudo.lower())
    logger.info("%s a rétrogradé %s au rôle spectateur.", compte.pseudo, cible.pseudo)
    return _redirection("/admin/comptes")


# --- US-01 — Proposer un article ------------------------------------------------


def _url_proposable(brut: str) -> Optional[str]:
    """URL utilisable, ou None. Schéma http/https UNIQUEMENT : le collecteur ira
    chercher cette adresse depuis le pipeline, et `file://` ou `data:` n'ont rien
    à y faire. Validé ici ET côté collecteur — une validation d'entrée ne se
    délègue pas à l'appelant précédent."""
    url = brut.strip()
    if not url or len(url) > URL_LONGUEUR_MAX:
        return None
    parties = urlsplit(url)
    if parties.scheme.lower() not in ("http", "https") or not parties.netloc:
        return None
    return url


def _propositions_recentes(session: Session, pseudo: str) -> int:
    """Compté en base, pas en mémoire : sur Vercel chaque instance a la sienne,
    un compteur en mémoire se contournerait en insistant jusqu'à tomber sur une
    autre instance."""
    depuis = datetime.now(timezone.utc) - timedelta(days=1)
    return session.execute(
        select(func.count())
        .select_from(Proposition)
        .where(Proposition.propose_par == pseudo, Proposition.date_proposition >= depuis)
    ).scalar_one()


@app.get("/proposer", response_class=HTMLResponse)
def formulaire_proposition(
    request: Request,
    compte: CompteCourant = Depends(compte_courant),
    erreur: Optional[str] = Query(None),
    succes: Optional[str] = Query(None),
    deja_analyse: Optional[uuid.UUID] = Query(None),
):
    return templates.TemplateResponse(
        request,
        "proposer.html",
        _contexte(
            compte,
            erreur=_message(erreur),
            succes=succes,
            deja_analyse=deja_analyse,
        ),
    )


@app.post("/proposer")
def proposer(
    url: str = Form(...),
    note: str = Form(""),
    csrf: str = Form(""),
    session: Session = Depends(get_session),
    compte: CompteCourant = Depends(compte_courant),
):
    """US-01 — tout compte connecté peut proposer un article à analyser.

    Trois refus avant écriture, dans cet ordre : forme de l'URL, plafond du
    compte, doublon. Le doublon en dernier parce qu'il coûte deux requêtes."""
    exige_csrf(csrf, compte)

    propre = _url_proposable(url)
    if propre is None:
        return _avec_erreur("/proposer", "url_invalide")
    if len(note) > NOTE_LONGUEUR_MAX:
        return _avec_erreur("/proposer", "note_trop_longue")

    plafond = entier_depuis_env(NOM_ENV_PROPOSITIONS_MAX, PROPOSITIONS_PAR_JOUR_PAR_DEFAUT)
    if _propositions_recentes(session, compte.pseudo) >= plafond:
        return _avec_erreur("/proposer", "plafond_propositions")

    canonique = canonicaliser_url(propre)
    deja = session.execute(
        select(Article.id).where(Article.url_canonique == canonique)
    ).scalar_one_or_none()
    if deja is not None:
        # Déjà collecté : renvoyer vers la fiche vaut mieux qu'un doublon muet.
        return _redirection(f"/proposer?deja_analyse={deja}")

    en_cours = session.execute(
        select(Proposition.id).where(
            Proposition.url_canonique == canonique,
            Proposition.statut.in_(STATUTS_VIVANTS),
        )
    ).scalar_one_or_none()
    if en_cours is not None:
        return _avec_erreur("/proposer", "deja_dans_la_file")

    session.add(
        Proposition(
            url=propre,
            url_canonique=canonique,
            note=note.strip() or None,
            propose_par=compte.pseudo,
        )
    )
    try:
        session.commit()
    except IntegrityError:
        # Deux propositions simultanées de la même URL : l'index unique partiel
        # tranche, et le perdant reçoit le même message que s'il avait été second.
        session.rollback()
        return _avec_erreur("/proposer", "deja_dans_la_file")
    logger.info("Proposition de %s : %s", compte.pseudo, canonique)
    return _redirection("/proposer?succes=1")


# --- US-02, US-03 — File d'attente et décision ----------------------------------


@app.get("/file", response_class=HTMLResponse)
def file_attente(
    request: Request,
    session: Session = Depends(get_session),
    compte: CompteCourant = Depends(exige_role("contributeur")),
    erreur: Optional[str] = Query(None),
):
    """US-02 — réservé aux contributeurs et au superadmin. Les propositions en
    attente d'abord, puis l'historique des décisions : qui a accepté quoi reste
    consultable (traçabilité)."""
    en_attente = (
        session.execute(
            select(Proposition)
            .where(Proposition.statut == "en_attente")
            .order_by(Proposition.date_proposition, Proposition.id)
        )
        .scalars()
        .all()
    )
    decidees = (
        session.execute(
            select(Proposition)
            .where(Proposition.statut != "en_attente")
            .order_by(Proposition.date_decision.desc(), Proposition.id)
            .limit(PROPOSITIONS_PAR_PAGE)
        )
        .scalars()
        .all()
    )
    return templates.TemplateResponse(
        request,
        "file.html",
        _contexte(
            compte,
            en_attente=en_attente,
            decidees=decidees,
            erreur=_message(erreur),
        ),
    )


def _decider(session: Session, proposition_id: uuid.UUID, compte: CompteCourant, statut: str, motif: Optional[str]):
    """Applique une décision si la proposition est encore en attente.

    Une proposition déjà décidée n'est pas re-décidée (US-03) : la condition est
    DANS le `update`, pas lue puis écrite — deux contributeurs qui cliquent en
    même temps ne doivent pas produire deux décisions successives dont la seconde
    écrase la première."""
    resultat = session.execute(
        update(Proposition)
        .where(Proposition.id == proposition_id, Proposition.statut == "en_attente")
        .values(
            statut=statut,
            decide_par=compte.pseudo,
            date_decision=datetime.now(timezone.utc),
            motif=motif,
        )
    )
    session.commit()
    return resultat.rowcount


@app.post("/file/{proposition_id}/accepter")
def accepter_proposition(
    proposition_id: uuid.UUID,
    csrf: str = Form(""),
    session: Session = Depends(get_session),
    compte: CompteCourant = Depends(exige_role("contributeur")),
):
    """US-03 — l'acceptation est une AUTORISATION D'ENTRÉE, pas une collecte :
    l'article n'existe pas encore. C'est le pipeline qui ira le chercher (US-04),
    au prochain run — et tant que le pipeline hebdomadaire est en pause, la
    proposition reste « acceptée, en attente d'analyse »."""
    exige_csrf(csrf, compte)
    if not _decider(session, proposition_id, compte, "acceptee", None):
        return _avec_erreur("/file", "proposition_deja_decidee")
    logger.info("%s a accepté la proposition %s.", compte.pseudo, proposition_id)
    return _redirection("/file")


@app.post("/file/{proposition_id}/refuser")
def refuser_proposition(
    proposition_id: uuid.UUID,
    motif: str = Form(...),
    csrf: str = Form(""),
    session: Session = Depends(get_session),
    compte: CompteCourant = Depends(exige_role("contributeur")),
):
    """US-03 — le motif est obligatoire et visible par le proposant : un refus
    sans raison est un mur, pas une décision. La base l'exige aussi
    (`ck_propositions_refus_motive`), pour que la règle ne dépende pas de cette
    seule route."""
    exige_csrf(csrf, compte)
    propre = motif.strip()[:MOTIF_LONGUEUR_MAX]
    if not propre:
        return _avec_erreur("/file", "refus_sans_motif")
    if not _decider(session, proposition_id, compte, "refusee", propre):
        return _avec_erreur("/file", "proposition_deja_decidee")
    logger.info("%s a refusé la proposition %s.", compte.pseudo, proposition_id)
    return _redirection("/file")


# --- US-08 — Commentaires -------------------------------------------------------


def _commentaires_recents(session: Session, pseudo: str) -> int:
    """Compté en base, comme les propositions : un compteur en mémoire se
    contournerait en insistant jusqu'à tomber sur une autre instance Vercel.

    Les commentaires RETIRÉS sont comptés aussi. C'est délibéré : les exclure
    rendrait le retrait avantageux pour son auteur — publier, se faire retirer,
    recommencer — alors que le plafond existe précisément pour freiner ce
    cycle (audit phase 21, F21-04)."""
    depuis = datetime.now(timezone.utc) - timedelta(days=1)
    return session.execute(
        select(func.count())
        .select_from(Commentaire)
        .where(Commentaire.pseudo == pseudo, Commentaire.date_creation >= depuis)
    ).scalar_one()


@app.post("/articles/{article_id}/commentaires")
def publier_commentaire(
    article_id: uuid.UUID,
    texte: str = Form(...),
    csrf: str = Form(""),
    session: Session = Depends(get_session),
    compte: CompteCourant = Depends(compte_courant),
):
    """US-08 — tout compte connecté peut commenter l'analyse d'un article.

    Publication immédiate : le choix a été fait d'assumer le risque plutôt que de
    tenir une seconde file de modération (cf. doc/V3/userstories_crowdsourcing.md).
    Le retrait par le superadmin en est la contrepartie.

    Ce commentaire n'entre dans AUCUN calcul. Le score composite reste une moyenne
    pondérée de signaux traçables (US-08 évaluateur) : y mêler un retour humain
    non authentifié le rendrait manipulable par quiconque connaît le mot de passe
    partagé, et retirerait au `detail_calcul` sa propriété d'être reconstituable."""
    exige_csrf(csrf, compte)

    propre = texte.strip()
    if not propre:
        return _avec_erreur(f"/articles/{article_id}", "commentaire_vide", "#commentaires")
    if len(propre) > COMMENTAIRE_LONGUEUR_MAX:
        return _avec_erreur(f"/articles/{article_id}", "commentaire_trop_long", "#commentaires")

    plafond = entier_depuis_env(NOM_ENV_COMMENTAIRES_MAX, COMMENTAIRES_PAR_JOUR_PAR_DEFAUT)
    if _commentaires_recents(session, compte.pseudo) >= plafond:
        return _avec_erreur(f"/articles/{article_id}", "plafond_commentaires", "#commentaires")

    # Un article non encore évalué est commentable : la page l'annonce
    # (« pas encore été évalué ») et le commentaire l'attendra. Décision prise
    # explicitement — US-08 parle de « commenter l'analyse », ce qui laissait le
    # cas au hasard du routage (audit phase 21, F21-03).
    if session.get(Article, article_id) is None:
        raise HTTPException(status_code=404, detail="Article introuvable")

    session.add(Commentaire(article_id=article_id, pseudo=compte.pseudo, texte=propre))
    session.commit()
    logger.info("Commentaire de %s sur l'article %s.", compte.pseudo, article_id)
    return _redirection(f"/articles/{article_id}#commentaires")


@app.post("/commentaires/{commentaire_id}/retirer")
def retirer_commentaire(
    commentaire_id: uuid.UUID,
    csrf: str = Form(""),
    session: Session = Depends(get_session),
    compte: CompteCourant = Depends(exige_role("superadmin")),
):
    """US-08 — retrait par le superadmin.

    MASQUAGE, pas suppression : le contenu, son auteur, sa date, et désormais qui
    l'a retiré et quand, restent en base. Sur un site qui publie des verdicts
    nommant des médias, un contenu retiré pour raison juridique doit rester
    consultable par le porteur du projet plutôt que s'évaporer.

    La condition « pas déjà retiré » est DANS l'`update` : deux retraits
    simultanés ne doivent pas réécrire l'horodatage du premier."""
    exige_csrf(csrf, compte)

    retrait = session.execute(
        update(Commentaire)
        .where(Commentaire.id == commentaire_id, Commentaire.retire_le.is_(None))
        .values(retire_le=datetime.now(timezone.utc), retire_par=compte.pseudo)
        .returning(Commentaire.article_id)
    ).scalar_one_or_none()
    session.commit()

    if retrait is None:
        return _avec_erreur("/", "commentaire_introuvable")
    logger.info("%s a retiré le commentaire %s.", compte.pseudo, commentaire_id)
    return _redirection(f"/articles/{retrait}#commentaires")
