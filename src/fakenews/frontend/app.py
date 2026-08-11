"""Frontend de consultation en lecture seule (cf. doc/userstories_frontend.md,
doc/architecture.md — FastAPI + Jinja2, déployé sur Vercel, le local ne sert qu'au
dev/test). Ce module ne fait strictement que lire le stockage partagé — aucune route
d'écriture."""

import hashlib
import hmac
import os
import uuid
from datetime import date
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from fakenews.contextualiseur.avertissement import AVERTISSEMENT
from fakenews.contextualiseur.declenchement import SEUIL_PAR_DEFAUT
from fakenews.db import SessionLocal
from fakenews.models import Article, MiseEnContexte, Score

app = FastAPI(title="Fake News — Détection")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

ARTICLES_PAR_PAGE = 50
NOM_COOKIE = "session"


def _jeton_session(mot_de_passe: str) -> str:
    """Jeton dérivé du mot de passe (HMAC), pas le mot de passe lui-même dans le
    cookie. Quiconque connaît le mot de passe peut recalculer ce jeton — même
    niveau de sécurité que l'authentification HTTP Basic précédente, juste porté
    par un cookie plutôt que par un en-tête envoyé à chaque requête."""
    return hmac.new(mot_de_passe.encode(), b"fakenews-session", hashlib.sha256).hexdigest()


class AccesRefuse(Exception):
    pass


@app.exception_handler(AccesRefuse)
def _rediriger_vers_connexion(request: Request, exc: AccesRefuse):
    return RedirectResponse(url="/login", status_code=303)


def verifier_acces(request: Request) -> None:
    """US-04 frontend : authentification minimale en version hébergée uniquement
    (un seul mot de passe, pas de nom d'utilisateur — cf. /login). Le mode local
    (FRONTEND_PASSWORD non définie) n'a pas besoin de l'appliquer."""
    mot_de_passe = os.environ.get("FRONTEND_PASSWORD")
    if mot_de_passe is None:
        return
    jeton_recu = request.cookies.get(NOM_COOKIE)
    if jeton_recu is None or not hmac.compare_digest(jeton_recu, _jeton_session(mot_de_passe)):
        raise AccesRefuse()


@app.get("/login", response_class=HTMLResponse)
def page_connexion(request: Request):
    return templates.TemplateResponse(request, "login.html", {"erreur": None})


@app.post("/login")
def connexion(request: Request, mot_de_passe: str = Form(...)):
    attendu = os.environ.get("FRONTEND_PASSWORD")
    if attendu is None or not hmac.compare_digest(mot_de_passe, attendu):
        return templates.TemplateResponse(
            request, "login.html", {"erreur": "Mot de passe incorrect."}, status_code=401
        )
    reponse = RedirectResponse(url="/", status_code=303)
    reponse.set_cookie(
        NOM_COOKIE, _jeton_session(attendu), httponly=True, secure=True, samesite="lax", max_age=60 * 60 * 24 * 30
    )
    return reponse


@app.post("/logout")
def deconnexion():
    reponse = RedirectResponse(url="/login", status_code=303)
    reponse.delete_cookie(NOM_COOKIE)
    return reponse


def get_session():
    with SessionLocal() as session:
        yield session


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


@app.get("/", response_class=HTMLResponse)
def liste_articles(
    request: Request,
    score_min: Optional[float] = Query(None, ge=0, le=100),
    date_min: Optional[date] = Query(None),
    date_max: Optional[date] = Query(None),
    tous: bool = Query(False),
    page: int = Query(1, ge=1),
    session: Session = Depends(get_session),
    _acces: None = Depends(verifier_acces),
):
    """US-01 frontend : liste des articles suspects, filtrable, triée par score
    décroissant, paginée. Par défaut seuls les articles au-dessus du seuil
    apparaissent ; `tous=1` lève ce filtre par défaut (mode "tous les articles",
    cf. US-01 frontend). Un article `non_évaluable` n'apparaît jamais (cf. US-08
    évaluateur). `date_min`/`date_max` typés `date` : une valeur malformée est
    rejetée par FastAPI (422) avant d'atteindre la requête SQL, plutôt que de
    planter la route (cf. audit de suivi)."""
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
    _acces: None = Depends(verifier_acces),
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
