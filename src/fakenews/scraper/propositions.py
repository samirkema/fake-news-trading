"""US-04 crowdsourcing : collecte des articles dont un contributeur a autorisé
l'entrée (cf. doc/V3/userstories_crowdsourcing.md).

**Pourquoi ce code vit dans le pipeline et pas dans le frontend.** Aller chercher
une URL fournie par un utilisateur depuis la fonction serverless qui sert le site
en ferait un relais vers des ressources que lui seul peut atteindre. Le runner
GitHub Actions, lui, n'a rien d'intéressant à atteindre. Cette séparation EST la
mesure de sécurité, pas une commodité d'organisation (doc/V0/architecture.md,
décision V3).

Une proposition acceptée n'est donc pas un article : c'est une autorisation
d'entrée, que ce collecteur honore à son rythme. L'article créé rejoint ensuite le
parcours commun — évaluateur, puis contextualiseur s'il dépasse le seuil.
"""

import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session
from urllib.parse import urlsplit

from fakenews.config import entier_depuis_env
from fakenews.db import SessionLocal
from fakenews.models import Article, Proposition
from fakenews.normalisation import canonicaliser_url, hacher_contenu
from fakenews.scraper.rss import _telecharger, nettoyer_html

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

NOM_ENV_PLAFOND = "PROPOSITIONS_PLAFOND_COLLECTE"
PLAFOND_PAR_DEFAUT = 20

# Une page d'article fait quelques centaines de Ko. Ces URL viennent des
# utilisateurs : on lit moins large que pour un flux RSS choisi par le projet.
TAILLE_MAX_OCTETS = 2_000_000

_TITRE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
# Quantificateurs BORNÉS dans tous les motifs qui balaient du HTML tiers : un
# `[^>]+` non borné peut backtracker longuement sur une balise démesurée sans
# chevron fermant (audit phase 19, F19-08).
_ATTRS = r"[^>]{0,300}"
_CORPS = re.compile(r"<body[^>]*>(.*)</body>", re.S | re.I)
# Date de publication déclarée par la page. Les deux ordres d'attributs existent
# dans la nature (`property` avant `content` et l'inverse), d'où les deux motifs.
def _meta(noms: str) -> tuple:
    """Deux motifs pour une même métadonnée : les deux ordres d'attributs
    (`property` avant `content` et l'inverse) existent dans la nature."""
    return (
        re.compile(
            rf"""<meta{_ATTRS}(?:property|name)=["'](?:{noms})["']{_ATTRS}content=["']([^"']{{1,500}})["']""",
            re.I,
        ),
        re.compile(
            rf"""<meta{_ATTRS}content=["']([^"']{{1,500}})["']{_ATTRS}(?:property|name)=["'](?:{noms})["']""",
            re.I,
        ),
    )


_DATE_DECLAREE = _meta("article:published_time|datePublished|date")
# US-05 évaluateur pénalise de 20 points « aucun auteur identifiable ». Câbler
# `auteur=None` pénalisait donc SYSTÉMATIQUEMENT tout article entré par
# proposition, quel que soit son contenu — alors que les pages déclarent
# couramment leur auteur, et que le titre et la date étaient déjà extraits par le
# même procédé (audit phase 19, F19-02).
_AUTEUR_DECLARE = _meta("author|article:author|byl")


def _decoder(brut: bytes) -> str:
    """UTF-8 avec remplacement des octets invalides.

    ponytail: pas de détection d'encodage. Une page en latin-1 donnera du texte
    abîmé plutôt qu'une erreur — dégrader, pas bloquer. Si le corpus le justifie,
    la marche suivante est de lire le `charset` de l'en-tête `Content-Type`."""
    return brut.decode("utf-8", errors="replace")


def _extraire_titre(html: str, repli: str) -> str:
    trouve = _TITRE.search(html)
    titre = nettoyer_html(trouve.group(1)) if trouve else ""
    # `articles.titre` est NOT NULL et US-05 évaluateur juge le style sur lui :
    # une page sans <title> exploitable retombe sur l'hôte, jamais sur du vide.
    return titre[:500] or repli


def _extraire_auteur(html: str) -> str | None:
    """Auteur déclaré par la page, ou None — auquel cas la pénalité stylistique
    d'US-05 est méritée, comme pour tout article sans signature."""
    for motif in _AUTEUR_DECLARE:
        trouve = motif.search(html)
        if trouve:
            auteur = nettoyer_html(trouve.group(1))[:200].strip()
            if auteur:
                return auteur
    return None


def _extraire_date(html: str) -> datetime | None:
    """Date déclarée par la page, en UTC, ou None si absente ou illisible."""
    for motif in _DATE_DECLAREE:
        trouve = motif.search(html)
        if not trouve:
            continue
        try:
            date = datetime.fromisoformat(trouve.group(1).strip().replace("Z", "+00:00"))
        except ValueError:
            continue
        return date if date.tzinfo else date.replace(tzinfo=timezone.utc)
    return None


def _construire_article(proposition: Proposition, html: str) -> Article:
    hote = urlsplit(proposition.url).netloc.lower()
    corps = _CORPS.search(html)
    contenu = nettoyer_html(corps.group(1) if corps else html)
    titre = _extraire_titre(html, repli=hote)
    date_declaree = _extraire_date(html)

    return Article(
        titre=titre,
        contenu=contenu,
        auteur=_extraire_auteur(html),
        domaine_source=hote,
        # Repli sur la date de PROPOSITION quand la page n'en déclare pas :
        # `date_publication` est NOT NULL. Limite à connaître — un article daté
        # par défaut du jour décale la fenêtre ±5 jours ouvrés d'US-04 évaluateur
        # (source primaire) et fausse le filtre par date du frontend. D'où la
        # trace en métadonnée : la limite doit être lisible dans la donnée, pas
        # seulement dans ce commentaire.
        date_publication=date_declaree or proposition.date_proposition,
        url=proposition.url,
        url_canonique=proposition.url_canonique,
        hash_contenu=hacher_contenu(titre, contenu),
        plateforme="proposition",
        metadonnees={
            "proposition_id": str(proposition.id),
            "propose_par": proposition.propose_par,
            "decide_par": proposition.decide_par,
            "date_publication_estimee": date_declaree is None,
        },
    )


def _marquer(proposition: Proposition, statut: str, motif: str | None = None, article=None) -> None:
    proposition.statut = statut
    proposition.motif = motif
    if article is not None:
        proposition.article_id = article.id


def _collecter_une(session: Session, proposition: Proposition) -> str:
    """Traite UNE proposition et retourne la clé de bilan correspondante.

    Chaque issue est un `return`, jamais un `continue` : c'est ce qui rend le
    défaut F19-01 impossible à réécrire. La version précédente sortait par
    `continue` depuis l'intérieur du `with begin_nested()`, ce qui sautait le
    `session.commit()` placé APRÈS le bloc — le changement de statut ne survivait
    que si une itération ultérieure commitait. Mesuré : bilan annonçant un échec,
    base répondant toujours `acceptee`, donc page morte retéléchargée à chaque
    run et proposant jamais informé (audit phase 19)."""
    # Re-validation du schéma : la proposition a été contrôlée à la saisie, mais
    # une validation d'entrée ne se délègue pas au maillon précédent — c'est ici
    # qu'on ouvre la connexion.
    if urlsplit(proposition.url).scheme.lower() not in ("http", "https"):
        _marquer(proposition, "echec_collecte", "adresse non http(s)")
        return "echecs"

    # Collecté entre-temps par le scraper automatique : on rattache au lieu de
    # créer un doublon que la contrainte d'unicité refuserait de toute façon.
    existant = session.execute(
        select(Article).where(Article.url_canonique == canonicaliser_url(proposition.url))
    ).scalar_one_or_none()
    if existant is not None:
        _marquer(proposition, "collectee", None, existant)
        return "deja_presentes"

    brut = _telecharger(proposition.url, taille_max=TAILLE_MAX_OCTETS)
    if brut is None:
        _marquer(proposition, "echec_collecte", "page injoignable")
        return "echecs"

    article = _construire_article(proposition, _decoder(brut))
    if not article.contenu.strip():
        # Sans corps, l'évaluateur n'a presque rien à juger et le contextualiseur
        # rien à citer : mieux vaut le dire que produire un score fondé sur du vide.
        _marquer(proposition, "echec_collecte", "page sans texte exploitable")
        return "echecs"

    session.add(article)
    session.flush()  # pour disposer de l'identifiant
    _marquer(proposition, "collectee", None, article)
    return "collectees"


def collecter_propositions(session: Session, plafond: int | None = None) -> dict:
    """Collecte les propositions `acceptee`, les plus anciennement acceptées
    d'abord.

    Un échec sur une proposition n'interrompt pas les suivantes — « dégrader,
    jamais bloquer » (doc/V0/architecture.md) s'applique ici comme aux flux RSS,
    et au grain de l'ENTRÉE, pas du run. Chaque issue est commitée immédiatement :
    un échec non persisté serait pire qu'un échec, puisque tout — bilan, journal,
    interface — affirmerait le contraire."""
    if plafond is None:
        plafond = entier_depuis_env(NOM_ENV_PLAFOND, PLAFOND_PAR_DEFAUT)

    en_attente = (
        session.execute(
            select(Proposition)
            .where(Proposition.statut == "acceptee")
            .order_by(Proposition.date_decision, Proposition.id)
            .limit(plafond)
        )
        .scalars()
        .all()
    )
    bilan = {"collectees": 0, "echecs": 0, "deja_presentes": 0}

    for proposition in en_attente:
        try:
            with session.begin_nested():
                cle = _collecter_une(session, proposition)
            session.commit()
            bilan[cle] += 1
        except Exception as exc:
            session.rollback()
            logger.warning(
                "collecte échouée pour la proposition %s (%s)", proposition.id, type(exc).__name__
            )
            # Marquer l'échec dans sa PROPRE transaction : celle qui vient
            # d'échouer n'est plus utilisable. Avec un motif, comme toutes les
            # autres branches — c'est justement le cas le moins compréhensible
            # pour le proposant (audit phase 19, F19-06).
            try:
                perdue = session.execute(
                    select(Proposition).where(Proposition.id == proposition.id)
                ).scalar_one()
                _marquer(perdue, "echec_collecte", f"erreur inattendue ({type(exc).__name__})")
                session.commit()
                bilan["echecs"] += 1
            except Exception:
                session.rollback()

    logger.info(
        "Propositions : %d collectée(s), %d déjà présente(s), %d en échec (plafond %d).",
        bilan["collectees"], bilan["deja_presentes"], bilan["echecs"], plafond,
    )
    return bilan


def main():
    with SessionLocal() as session:
        collecter_propositions(session)


if __name__ == "__main__":
    main()
