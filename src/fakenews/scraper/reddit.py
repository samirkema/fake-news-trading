import logging
import os
from datetime import datetime, timezone

import praw
from sqlalchemy.orm import Session

from fakenews.scraper.normalisation import canonicaliser_url, hacher_contenu
from fakenews.scraper.persistance import enregistrer_ou_mettre_a_jour
from fakenews.scraper.sources_reddit import NB_POSTS_PAR_SUBREDDIT, SUBREDDITS

logger = logging.getLogger(__name__)


def creer_client() -> praw.Reddit:
    """Client Reddit en lecture seule — aucune connexion utilisateur nécessaire, seulement
    un app Reddit de type "script" (gratuit, cf. .env.example)."""
    return praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=os.environ.get("REDDIT_USER_AGENT", "fakenews-scraper/0.1 (script personnel)"),
    )


def normaliser_submission(submission, nom_subreddit: str) -> dict:
    """Traduit un post Reddit (objet PRAW Submission, ou tout objet duck-typé
    équivalent — cf. tests) dans le schéma commun du stockage partagé (US-04 scraper)."""
    titre = submission.title
    contenu = submission.selftext or ""
    date_publication = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)
    url = f"https://www.reddit.com{submission.permalink}"
    auteur = submission.author.name if submission.author else None

    return {
        "titre": titre,
        "contenu": contenu,
        "auteur": auteur,
        "domaine_source": f"reddit.com/r/{nom_subreddit}",
        "date_publication": date_publication,
        "url": url,
        "url_canonique": canonicaliser_url(url),
        "hash_contenu": hacher_contenu(titre, contenu),
        "plateforme": "reddit",
        "metadonnees": {
            "subreddit": nom_subreddit,
            "score": submission.score,
            "nb_commentaires": submission.num_comments,
        },
    }


def collecter_reddit(session: Session, client: "praw.Reddit | None" = None) -> dict:
    """Collecte les posts des subreddits configurés (US-02 scraper) et les persiste dans
    le stockage partagé. Un subreddit indisponible (privé, banni, erreur réseau...) est
    journalisé et n'interrompt pas la collecte des autres, et un post individuel qui
    ferait échouer sa normalisation/persistance est ignoré plutôt que d'interrompre le
    reste du subreddit ou des subreddits suivants (cf. doc/architecture.md, dégrader
    jamais bloquer — appliqué au grain du post, pas seulement du subreddit).

    La création du client (identifiants absents/invalides) est protégée au même titre :
    Reddit tout entier est alors marqué indisponible plutôt que de faire planter
    l'appelant (cf. audit de suivi — un run_scraper.py qui plante ici empêchait
    évaluateur/contextualiseur de s'exécuter dans le pipeline hebdomadaire)."""
    if client is None:
        try:
            client = creer_client()
        except Exception as exc:
            logger.warning("Reddit indisponible : échec de création du client (%s)", exc)
            return {
                nom: {"statut": "indisponible", "ajoutes": 0, "mis_a_jour": 0, "ignores": 0}
                for nom in SUBREDDITS
            }

    bilan = {}
    for nom_subreddit in SUBREDDITS:
        try:
            posts = list(client.subreddit(nom_subreddit).new(limit=NB_POSTS_PAR_SUBREDDIT))
        except Exception as exc:
            logger.warning("subreddit indisponible: r/%s (%s)", nom_subreddit, exc)
            bilan[nom_subreddit] = {"statut": "indisponible", "ajoutes": 0, "mis_a_jour": 0, "ignores": 0}
            continue

        compteurs = {"ajoutes": 0, "mis_a_jour": 0, "ignores": 0}
        for submission in posts:
            try:
                resultat = enregistrer_ou_mettre_a_jour(session, normaliser_submission(submission, nom_subreddit))
            except Exception as exc:
                logger.warning("post ignoré (r/%s): %s", nom_subreddit, exc)
                compteurs["ignores"] += 1
                continue
            if resultat == "ajoute":
                compteurs["ajoutes"] += 1
            elif resultat == "mis_a_jour":
                compteurs["mis_a_jour"] += 1

        session.commit()
        bilan[nom_subreddit] = {"statut": "ok", **compteurs}
        if compteurs["ignores"]:
            logger.warning(
                "r/%s: %d post(s) ignoré(s) (échec de normalisation/persistance)",
                nom_subreddit, compteurs["ignores"],
            )
        logger.info("r/%s: %s", nom_subreddit, bilan[nom_subreddit])

    return bilan
