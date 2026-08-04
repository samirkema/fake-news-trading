import logging

from fakenews.db import SessionLocal
from fakenews.scraper.reddit import collecter_reddit

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main():
    with SessionLocal() as session:
        bilan = collecter_reddit(session)
    for nom, resultat in bilan.items():
        print(f"r/{nom}: {resultat}")


if __name__ == "__main__":
    main()
