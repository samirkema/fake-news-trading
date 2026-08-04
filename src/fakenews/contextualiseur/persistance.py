"""US-03 contextualiseur : persistance et traçabilité de la mise en contexte
(cf. doc/userstories_contextualiseur.md)."""

import uuid

from sqlalchemy.orm import Session

from fakenews.models import MiseEnContexte


def enregistrer_mise_en_contexte(
    session: Session,
    article_id: uuid.UUID,
    explication: str,
    faits_traces: list,
    deductions_llm: list,
    sources_utilisees: list,
    niveau_confiance: str | None,
    avertissement: str,
) -> MiseEnContexte:
    """Un seul enregistrement par article (contrainte unique en base, cf. Phase 0) —
    pas de correction/mise à jour prévue en v1 (cf. pas de rescoring, doc/architecture.md)."""
    enregistrement = MiseEnContexte(
        article_id=article_id,
        explication=explication,
        faits_traces=faits_traces,
        deductions_llm=deductions_llm,
        sources_utilisees=sources_utilisees,
        niveau_confiance=niveau_confiance,
        avertissement=avertissement,
    )
    session.add(enregistrement)
    return enregistrement
