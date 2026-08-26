"""Frontend de consultation en lecture seule (cf. doc/userstories_frontend.md,
doc/architecture.md — FastAPI + Jinja2, déployé sur Vercel, le local ne sert qu'au
dev/test). Ce module ne fait strictement que lire le stockage partagé — aucune route
d'écriture."""

import hashlib
import hmac
import os
import re
import uuid
from dataclasses import dataclass
from datetime import date
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

app = FastAPI(title="Fake News — Détection")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

ARTICLES_PAR_PAGE = 50
NOM_COOKIE = "session"
ROLE_DEFAUT = "spectateur"
# Pseudo : normalisé en minuscules. Jeu de caractères restreint car il est aussi
# une moitié de la valeur du cookie signé (« pseudo:signature ») — pas de « : »,
# pas de caractère de contrôle.
_PSEUDO_RE = re.compile(r"^[a-z0-9._-]{1,64}$")


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


def _signature(pseudo: str, mot_de_passe_partage: str, secret_hash: Optional[str]) -> str:
    return hmac.new(
        _cle_signature(mot_de_passe_partage, secret_hash),
        f"fakenews-session:{pseudo}".encode(),
        hashlib.sha256,
    ).hexdigest()


def _valeur_cookie(pseudo: str, mot_de_passe_partage: str, secret_hash: Optional[str] = None) -> str:
    return f"{pseudo}:{_signature(pseudo, mot_de_passe_partage, secret_hash)}"


def _pseudo_revendique(cookie: Optional[str]) -> Optional[str]:
    """Pseudo revendiqué par le cookie, avant vérification de la signature (celle-ci
    a besoin du `secret_hash` du compte, donc d'un accès base — cf. compte_courant)."""
    if not cookie or ":" not in cookie:
        return None
    pseudo, _signature_recue = cookie.rsplit(":", 1)
    return pseudo if _PSEUDO_RE.match(pseudo) else None


def _cookie_valide(
    cookie: str, pseudo: str, mot_de_passe_partage: str, secret_hash: Optional[str]
) -> bool:
    _pseudo, signature_recue = cookie.rsplit(":", 1)
    return hmac.compare_digest(
        signature_recue, _signature(pseudo, mot_de_passe_partage, secret_hash)
    )


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

    - mode local (FRONTEND_PASSWORD non définie) : superadmin fictif — le mode
      local est réservé au développeur (cf. US-04 frontend) ;
    - cookie absent, mal formé ou signature invalide : accès refusé (redirection
      vers /login) ;
    - pseudo présent dans la table `comptes` : rôle associé ;
    - pseudo inconnu : « spectateur » (défaut).

    La signature du cookie est liée au `secret_hash` du compte quand il en a un
    (samirkema) : un cookie superadmin ne peut pas être fabriqué avec le seul mot
    de passe partagé. Aucune capacité n'est encore conditionnée au rôle — c'est la
    fondation. Le rôle n'est jamais renvoyé aux gabarits : l'utilisateur ne voit
    pas son statut."""
    mot_de_passe = os.environ.get("FRONTEND_PASSWORD")
    if mot_de_passe is None:
        return CompteCourant(pseudo="local", role="superadmin")
    cookie = request.cookies.get(NOM_COOKIE)
    pseudo = _pseudo_revendique(cookie)
    if pseudo is None:
        raise AccesRefuse()
    ligne = session.execute(
        select(Compte.role, Compte.secret_hash).where(func.lower(Compte.pseudo) == pseudo)
    ).one_or_none()
    role = (ligne.role if ligne else None) or ROLE_DEFAUT
    secret_hash = ligne.secret_hash if ligne else None
    if not _cookie_valide(cookie, pseudo, mot_de_passe, secret_hash):
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
    pseudos utilisent le mot de passe partagé FRONTEND_PASSWORD."""
    partage = os.environ.get("FRONTEND_PASSWORD")
    pseudo_normalise = _normaliser_pseudo(pseudo)
    if pseudo_normalise is None:
        return _erreur_login(
            request, "Pseudo invalide (lettres, chiffres, « . _ - », 64 caractères max)."
        )
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
        mot_de_passe_ok = partage is not None and hmac.compare_digest(mot_de_passe, partage)
    if not mot_de_passe_ok:
        return _erreur_login(request, "Identifiants incorrects.")
    reponse = RedirectResponse(url="/", status_code=303)
    reponse.set_cookie(
        NOM_COOKIE,
        _valeur_cookie(pseudo_normalise, partage or "", secret_hash),
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
    )
    return reponse


@app.post("/logout")
def deconnexion():
    reponse = RedirectResponse(url="/login", status_code=303)
    reponse.delete_cookie(NOM_COOKIE)
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
        stmt = stmt.where(Article.date_publication >= date_min)
    if date_max:
        stmt = stmt.where(Article.date_publication <= date_max)
    stmt = stmt.order_by(Score.score_final.desc()).limit(ARTICLES_PAR_PAGE + 1).offset((page - 1) * ARTICLES_PAR_PAGE)

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
