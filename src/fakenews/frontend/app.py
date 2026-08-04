"""Frontend de consultation en lecture seule (cf. doc/userstories_frontend.md,
doc/architecture.md — FastAPI + Jinja2, déployé sur Vercel, le local ne sert qu'au
dev/test). Ce module ne fait strictement que lire le stockage partagé — aucune route
d'écriture."""

import os
import secrets
import uuid
from datetime import date
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
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

_securite = HTTPBasic(auto_error=False)


def verifier_acces(credentials: Optional[HTTPBasicCredentials] = Depends(_securite)) -> None:
    """US-04 frontend : authentification minimale en version hébergée uniquement.
    Le mode local (FRONTEND_PASSWORD non définie) n'a pas besoin de l'appliquer."""
    mot_de_passe = os.environ.get("FRONTEND_PASSWORD")
    if mot_de_passe is None:
        return
    if credentials is None or not secrets.compare_digest(credentials.password, mot_de_passe):
        raise HTTPException(status_code=401, detail="Accès refusé", headers={"WWW-Authenticate": "Basic"})


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
