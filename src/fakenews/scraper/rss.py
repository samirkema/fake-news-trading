import logging
import urllib.error
import urllib.request
from datetime import datetime, timezone

import feedparser
from sqlalchemy.orm import Session

from fakenews.scraper.normalisation import canonicaliser_url, hacher_contenu
from fakenews.scraper.persistance import enregistrer_ou_mettre_a_jour
from fakenews.scraper.sources_rss import RSS_SOURCES

logger = logging.getLogger(__name__)

TIMEOUT_SECONDES = 10


def _extraire_date_publication(entree) -> datetime | None:
    struct = entree.get("published_parsed") or entree.get("updated_parsed")
    if struct is None:
        return None
    return datetime(*struct[:6], tzinfo=timezone.utc)


def _extraire_contenu(entree) -> str:
    if entree.get("content"):
        return entree["content"][0].get("value", "")
    return entree.get("summary") or entree.get("description") or ""


USER_AGENT = "Mozilla/5.0 (compatible; fakenews-scraper/0.1)"


def _telecharger(url: str) -> bytes | None:
    """Récupère le contenu brut d'une URL avec un timeout explicite (cf. doc/architecture.md,
    "dégrader jamais bloquer" — un flux qui traîne ne doit pas geler tout le run). Un
    User-Agent explicite est nécessaire : plusieurs flux renvoient 403 sur le User-Agent
    par défaut d'urllib."""
    requete = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(requete, timeout=TIMEOUT_SECONDES) as reponse:
            return reponse.read()
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        logger.warning("téléchargement échoué: %s (%s)", url, exc)
        return None


def _flux_utilisable(flux: feedparser.FeedParserDict) -> bool:
    """Un flux est utilisable dès qu'il contient des entrées, même si feedparser a
    levé un avertissement `bozo` non fatal (ex. déclaration d'encodage récupérable) —
    `bozo` seul ne veut pas dire "vide" ou "inexploitable"."""
    return len(flux.entries) > 0


def _recuperer_flux(source: dict) -> tuple[dict, "feedparser.FeedParserDict | None"]:
    """Récupère un flux, avec repli si configuré et si le flux principal échoue.
    Retourne (source effectivement utilisée, flux) ou (source, None) si tout a échoué."""
    brut = _telecharger(source["url"])
    flux = feedparser.parse(brut) if brut is not None else None

    if flux is None or not _flux_utilisable(flux):
        if flux is not None:
            logger.warning(
                "flux indisponible: %s (%s) — bozo=%s entries=%d",
                source["nom"], source["url"], flux.bozo, len(flux.entries),
            )
        repli = source.get("repli")
        if repli is None:
            return source, None
        logger.info("repli sur %s pour %s", repli["nom"], source["nom"])
        brut_repli = _telecharger(repli["url"])
        flux_repli = feedparser.parse(brut_repli) if brut_repli is not None else None
        if flux_repli is None or not _flux_utilisable(flux_repli):
            logger.warning("flux de repli également indisponible: %s", repli["nom"])
            return repli, None
        return repli, flux_repli

    if flux.bozo:
        logger.info("%s: flux exploitable malgré un avertissement bozo (%s)", source["nom"], flux.bozo_exception)
    return source, flux


def collecter_rss(session: Session) -> dict:
    """Collecte tous les flux RSS configurés (US-01 scraper) et persiste les nouveaux
    articles dans le stockage partagé. Une source indisponible est journalisée et
    n'interrompt pas la collecte des autres (cf. doc/architecture.md, dégrader jamais bloquer).

    Retourne un bilan par source ; la journalisation détaillée par run (US-06 scraper)
    est hors périmètre de cette étape."""
    bilan = {}
    for source in RSS_SOURCES:
        source_effective, flux = _recuperer_flux(source)
        if flux is None:
            bilan[source["nom"]] = {"statut": "indisponible", "ajoutes": 0, "mis_a_jour": 0, "ignores_sans_date": 0}
            continue

        compteurs = {"ajoutes": 0, "mis_a_jour": 0, "ignores_sans_date": 0}
        for entree in flux.entries:
            titre = entree.get("title")
            lien = entree.get("link")
            date_publication = _extraire_date_publication(entree)
            if not titre or not lien or date_publication is None:
                compteurs["ignores_sans_date"] += 1
                logger.debug("entrée ignorée (titre/lien/date manquant): %r", entree.get("link"))
                continue

            contenu = _extraire_contenu(entree)
            url_canonique = canonicaliser_url(lien)
            resultat = enregistrer_ou_mettre_a_jour(
                session,
                {
                    "titre": titre,
                    "contenu": contenu,
                    "auteur": entree.get("author"),
                    "domaine_source": source_effective["domaine_source"],
                    "date_publication": date_publication,
                    "url": lien,
                    "url_canonique": url_canonique,
                    "hash_contenu": hacher_contenu(titre, contenu),
                    "plateforme": "rss",
                    "metadonnees": {"flux_nom": source_effective["nom"]},
                },
            )
            if resultat == "ajoute":
                compteurs["ajoutes"] += 1
            elif resultat == "mis_a_jour":
                compteurs["mis_a_jour"] += 1

        session.commit()
        bilan[source_effective["nom"]] = {"statut": "ok", **compteurs}
        if compteurs["ignores_sans_date"]:
            logger.warning(
                "%s: %d entrée(s) ignorée(s) faute de titre/lien/date exploitable",
                source_effective["nom"], compteurs["ignores_sans_date"],
            )
        logger.info("%s: %s", source_effective["nom"], bilan[source_effective["nom"]])

    return bilan
