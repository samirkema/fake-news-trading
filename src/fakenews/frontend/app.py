"""Frontend de consultation en lecture seule (cf. doc/userstories_frontend.md,
doc/architecture.md — FastAPI + Jinja2, déployé sur Vercel, le local ne sert qu'au
dev/test). Ce module ne fait strictement que lire le stockage partagé — aucune route
d'écriture."""

import hashlib
import hmac
import logging
import os
import re
import time
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import date, datetime, time as heure, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fakenews.contextualiseur.avertissement import AVERTISSEMENT
from fakenews.contextualiseur.declenchement import SEUIL_PAR_DEFAUT
from fakenews.db import SessionLocal
from fakenews.models import Article, Compte, MiseEnContexte, Score

logger = logging.getLogger(__name__)

app = FastAPI(title="Fake News — Détection")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

ARTICLES_PAR_PAGE = 50
NOM_COOKIE = "session"
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


def _mode_local() -> bool:
    return os.environ.get("FAKENEWS_MODE", "").strip().lower() == MODE_LOCAL


def _normaliser_pseudo(brut: str) -> Optional[str]:
    pseudo = brut.strip().lower()
    return pseudo if _PSEUDO_RE.match(pseudo) else None


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
    if not _PSEUDO_RE.match(pseudo):
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
    return hmac.compare_digest(
        signature_recue, _signature(pseudo, expiration, mot_de_passe_partage, secret_hash)
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
    _tentatives_login.setdefault(identifiant_client, deque()).append(maintenant)


def _oublier_tentatives(identifiant_client: str) -> None:
    _tentatives_login.pop(identifiant_client, None)


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


def compte_courant(request: Request, session: Session = Depends(get_session)) -> CompteCourant:
    """Fondation V1 de l'auth à 3 rôles (cf. doc/V1/comptes-3-roles.md). Sert de
    garde d'accès (US-04 frontend) ET résout le rôle du visiteur connecté :

    - mode local EXPLICITE (FAKENEWS_MODE=local) : superadmin fictif — réservé au
      développeur (cf. US-04 frontend) ;
    - cookie absent, mal formé, expiré ou signature invalide : accès refusé
      (redirection vers /login) ;
    - pseudo présent dans la table `comptes` : rôle associé ;
    - pseudo inconnu : « spectateur » (défaut).

    Le défaut est FERMÉ : hors mode local explicite, une FRONTEND_PASSWORD absente
    ne rend pas le site public, elle le rend inaccessible. C'est l'inverse du
    comportement précédent, qui transformait une variable d'environnement oubliée
    en ouverture d'accès public (cf. audit, finding H4).

    La signature du cookie est liée au `secret_hash` du compte quand il en a un
    (samirkema) : un cookie superadmin ne peut pas être fabriqué avec le seul mot
    de passe partagé. Aucune capacité n'est encore conditionnée au rôle — c'est la
    fondation. Le rôle n'est jamais renvoyé aux gabarits : l'utilisateur ne voit
    pas son statut."""
    if _mode_local():
        return CompteCourant(pseudo="local", role="superadmin")
    mot_de_passe = os.environ.get("FRONTEND_PASSWORD")
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
    ligne = session.execute(
        select(Compte.role, Compte.secret_hash).where(func.lower(Compte.pseudo) == pseudo)
    ).one_or_none()
    role = (ligne.role if ligne else None) or ROLE_DEFAUT
    secret_hash = ligne.secret_hash if ligne else None
    if not _signature_valide(pseudo, expiration, signature_recue, mot_de_passe, secret_hash):
        raise AccesRefuse()
    return CompteCourant(pseudo=pseudo, role=role)


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
    partage = os.environ.get("FRONTEND_PASSWORD")
    if not partage:
        logger.error("Tentative de connexion alors que FRONTEND_PASSWORD n'est pas définie.")
        return _erreur_login(request, "Authentification non configurée sur ce déploiement.")

    client = _identifiant_client(request)
    plafond_atteint = _trop_de_tentatives(client)

    pseudo_normalise = _normaliser_pseudo(pseudo)
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
            mot_de_passe_ok = hmac.compare_digest(mot_de_passe, partage)

    if not mot_de_passe_ok:
        _enregistrer_tentative_ratee(client)
        if plafond_atteint:
            logger.warning("Trop de tentatives ratées depuis %s — refus temporaire.", client)
            return templates.TemplateResponse(
                request,
                "login.html",
                {"erreur": "Trop de tentatives. Réessayer dans quelques minutes."},
                status_code=429,
            )
        if pseudo_normalise is None:
            return _erreur_login(
                request, "Pseudo invalide (lettres, chiffres, « . _ - », 64 caractères max)."
            )
        return _erreur_login(request, "Identifiants incorrects.")

    _oublier_tentatives(client)
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
def deconnexion():
    reponse = RedirectResponse(url="/login", status_code=303)
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
    _compte: CompteCourant = Depends(compte_courant),
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
    seuil_effectif = score_min if score_min is not None else (None if tous else SEUIL_PAR_DEFAUT)

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
        {
            "resultats": resultats,
            "avertissement": AVERTISSEMENT,
            "score_min": score_min,
            "date_min": date_min.isoformat() if date_min else None,
            "date_max": date_max.isoformat() if date_max else None,
            "tous": tous,
            "url_page_precedente": _url_liste(score_min, date_min, date_max, tous, page - 1) if page > 1 else None,
            "url_page_suivante": _url_liste(score_min, date_min, date_max, tous, page + 1) if a_page_suivante else None,
        },
    )


@app.get("/articles/{article_id}", response_class=HTMLResponse)
def detail_article(
    request: Request,
    article_id: uuid.UUID,
    session: Session = Depends(get_session),
    _compte: CompteCourant = Depends(compte_courant),
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

    return templates.TemplateResponse(
        request,
        "detail.html",
        {
            "article": article,
            "score": score,
            "mise_en_contexte": mise_en_contexte,
            "avertissement": AVERTISSEMENT,
        },
    )
