import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

PLATEFORMES = ("rss", "reddit")


class Base(DeclarativeBase):
    pass


class Article(Base):
    """Écrite par le scraper (US-01/US-02/US-04 scraper), lue par l'évaluateur."""

    __tablename__ = "articles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    titre: Mapped[str] = mapped_column(Text, nullable=False)
    contenu: Mapped[str] = mapped_column(Text, nullable=False)
    auteur: Mapped[str | None] = mapped_column(Text)
    domaine_source: Mapped[str | None] = mapped_column(Text)
    date_publication: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    url_canonique: Mapped[str] = mapped_column(Text, nullable=False)
    hash_contenu: Mapped[str] = mapped_column(Text, nullable=False)
    plateforme: Mapped[str] = mapped_column(String(20), nullable=False)
    # ex. reddit: {"subreddit", "upvotes", "nb_commentaires"} ; toute plateforme: {"gdelt_event_id"}
    metadonnees: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    date_collecte: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    score: Mapped["Score | None"] = relationship(back_populates="article", uselist=False)
    mise_en_contexte: Mapped["MiseEnContexte | None"] = relationship(back_populates="article", uselist=False)

    __table_args__ = (
        CheckConstraint(f"plateforme in {PLATEFORMES}", name="ck_articles_plateforme"),
        UniqueConstraint("url_canonique", name="uq_articles_url_canonique"),
    )


class Score(Base):
    """Écrite par l'évaluateur (US-01 à US-08 évaluateur). Un seul score par article :
    pas de rescoring en v1 (cf. doc/architecture.md)."""

    __tablename__ = "scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )

    # {"reputation": {"valeur": ..., "raison": ..., "preuve_id": ...}, ...}
    # cf. interface evaluer(article) dans doc/architecture.md
    sous_scores: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # poids réellement appliqués à ce calcul (traçabilité, cf. US-08 évaluateur)
    poids: Mapped[dict] = mapped_column(JSONB, nullable=False)

    score_final: Mapped[float | None] = mapped_column(Numeric(5, 2))
    non_evaluable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    date_calcul: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    article: Mapped["Article"] = relationship(back_populates="score")

    __table_args__ = (
        UniqueConstraint("article_id", name="uq_scores_article_id"),
        CheckConstraint(
            "(non_evaluable AND score_final IS NULL) OR (NOT non_evaluable AND score_final IS NOT NULL)",
            name="ck_scores_non_evaluable_coherent",
        ),
        CheckConstraint(
            "score_final IS NULL OR (score_final >= 0 AND score_final <= 100)",
            name="ck_scores_score_final_range",
        ),
    )


class Compte(Base):
    """Lue par le frontend (jamais écrite par lui — lecture seule stricte, cf.
    doc/V0/architecture.md) pour résoudre le rôle d'un pseudo connecté. Fondation
    V1 de l'authentification à 3 rôles (spectateur / contributeur / superadmin,
    cf. doc/V1/comptes-3-roles.md). Un pseudo absent de la table => rôle
    « spectateur ». L'index unique insensible à la casse sur `lower(pseudo)` est
    porté par la migration 0002 (non déclaré ici : SQLAlchemy ne gère pas
    proprement un index fonctionnel via `__table_args__` sur cette version)."""

    __tablename__ = "comptes"

    ROLES = ("spectateur", "contributeur", "superadmin")

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pseudo: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    # NULL => ce pseudo se connecte avec le mot de passe partagé (FRONTEND_PASSWORD).
    # Renseigné (hash bcrypt via crypt()/gen_salt('bf')) => ce pseudo DOIT utiliser
    # ce code personnel, le mot de passe partagé ne lui donne pas accès. Utilisé
    # pour samirkema/superadmin (cf. doc/V1/comptes-3-roles.md).
    secret_hash: Mapped[str | None] = mapped_column(Text)
    date_creation: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(f"role in {ROLES}", name="ck_comptes_role"),
    )


class MiseEnContexte(Base):
    """Écrite par le contextualiseur (US-01 à US-04 contextualiseur), uniquement pour les
    articles au-dessus du seuil de suspicion. Lue par le frontend."""

    __tablename__ = "mise_en_contexte"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )

    explication: Mapped[str] = mapped_column(Text, nullable=False)
    # items {"preuve_id": ..., ...} ancrés sur un preuve_id présent dans scores.sous_scores
    # pour cet article (cf. US-02 contextualiseur)
    faits_traces: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # items sans preuve_id, ou rejetés de faits_traces faute de preuve_id valide
    deductions_llm: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    sources_utilisees: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # méthode de calcul non encore définie (cf. US-03/US-04 contextualiseur) ; texte libre
    # en attendant qu'une échelle soit tranchée
    niveau_confiance: Mapped[str | None] = mapped_column(Text)
    avertissement: Mapped[str] = mapped_column(Text, nullable=False)
    date_generation: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    article: Mapped["Article"] = relationship(back_populates="mise_en_contexte")

    __table_args__ = (UniqueConstraint("article_id", name="uq_mise_en_contexte_article_id"),)
