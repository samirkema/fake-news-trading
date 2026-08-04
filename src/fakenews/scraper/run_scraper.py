"""Point d'entrée unique pour l'exécution hebdomadaire planifiée (US-06 scraper) :
lance la collecte RSS puis Reddit dans le même run. Chaque collecteur journalise déjà
son propre bilan par source (cf. rss.py, reddit.py)."""

import logging

from fakenews.db import SessionLocal
from fakenews.scraper.reddit import collecter_reddit
from fakenews.scraper.rss import collecter_rss

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    with SessionLocal() as session:
        logger.info("=== collecte RSS ===")
        bilan_rss = collecter_rss(session)
        logger.info("=== collecte Reddit ===")
        bilan_reddit = collecter_reddit(session)

    print("--- RSS ---")
    for nom, resultat in bilan_rss.items():
        print(f"{nom}: {resultat}")
    print("--- Reddit ---")
    for nom, resultat in bilan_reddit.items():
        print(f"r/{nom}: {resultat}")


if __name__ == "__main__":
    main()
