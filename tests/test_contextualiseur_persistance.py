from datetime import datetime, timezone

from sqlalchemy import select

from fakenews.contextualiseur.avertissement import AVERTISSEMENT
from fakenews.contextualiseur.persistance import enregistrer_mise_en_contexte
from fakenews.models import Article, MiseEnContexte


def _inserer_article(session):
    article = Article(
        titre="Titre",
        contenu="Contenu",
        domaine_source="test-contextualiseur.invalid",
        date_publication=datetime.now(timezone.utc),
        url="https://test-contextualiseur.invalid/x",
        url_canonique="https://test-contextualiseur.invalid/x",
        hash_contenu="hash-contextualiseur",
        plateforme="rss",
        metadonnees={},
    )
    session.add(article)
    session.flush()
    return article


def test_enregistrer_mise_en_contexte_persiste_tous_les_champs(db_session):
    article = _inserer_article(db_session)

    enregistrer_mise_en_contexte(
        db_session,
        article_id=article.id,
        explication="Explication de test",
        faits_traces=[{"preuve_id": "fact_checking:url", "texte": "démenti"}],
        deductions_llm=[{"texte": "déduction"}],
        sources_utilisees=[{"origine": "fact_checking"}],
        niveau_confiance="moyen",
        avertissement=AVERTISSEMENT,
    )
    db_session.flush()

    enregistrement = db_session.execute(
        select(MiseEnContexte).where(MiseEnContexte.article_id == article.id)
    ).scalar_one()
    assert enregistrement.explication == "Explication de test"
    assert enregistrement.faits_traces == [{"preuve_id": "fact_checking:url", "texte": "démenti"}]
    assert enregistrement.avertissement == AVERTISSEMENT
