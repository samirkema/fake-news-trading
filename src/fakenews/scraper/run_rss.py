import logging

from fakenews.db import SessionLocal
from fakenews.scraper.rss import collecter_rss

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main():
    with SessionLocal() as session:
        bilan = collecter_rss(session)
    for nom, resultat in bilan.items():
        print(f"{nom}: {resultat}")


if __name__ == "__main__":
    main()
