import logging

from sqlalchemy import select, or_, and_
from sqlalchemy.orm import Session

from fakenews.models import Article

logger = logging.getLogger(__name__)


def enregistrer_ou_mettre_a_jour(session: Session, champs: dict) -> str:
    """Insère un nouvel article, ou met à jour les métadonnées volatiles d'un article
    déjà présent sans le réinsérer (US-05 scraper). Retourne 'ajoute', 'mis_a_jour' ou
    'inchange'.

    Un article est considéré déjà présent si son URL canonique matche (même source,
    même article re-vu), ou si son hash de contenu matche ET que le domaine source est
    le même (même source republiant le même texte sous une URL différente). Un même
    contenu republié par un domaine DIFFÉRENT n'est PAS traité comme un doublon : c'est
    une corroboration multi-source légitime (ex. dépêche wire, cf. doc/userstories_évaluateur.md
    US-02) que le scraper ne doit pas effacer avant que l'évaluateur ne la compte."""
    existant = session.execute(
        select(Article).where(
            or_(
                Article.url_canonique == champs["url_canonique"],
                and_(
                    Article.hash_contenu == champs["hash_contenu"],
                    Article.domaine_source == champs["domaine_source"],
                ),
            )
        )
    ).scalars().first()

    if existant is None:
        session.add(Article(**champs))
        return "ajoute"

    if existant.metadonnees != champs["metadonnees"]:
        existant.metadonnees = champs["metadonnees"]
        return "mis_a_jour"

    return "inchange"
