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

# « proposition » : article entré par la file d'attente humaine plutôt que par la
# collecte automatique (V3, cf. doc/V3/userstories_crowdsourcing.md US-04).
PLATEFORMES = ("rss", "reddit", "proposition")

STATUTS_PROPOSITION = ("en_attente", "acceptee", "refusee", "collectee", "echec_collecte")
# Statuts pour lesquels une proposition occupe la place de son URL : on n'en
# accepte pas une seconde tant que celle-ci n'est pas retombée (US-01).
STATUTS_VIVANTS = ("en_attente", "acceptee")


def _liste_sql(valeurs) -> str:
    """Liste SQL `('a', 'b')` à partir d'un tuple Python.

    `f"in {tuple_python}"` s'appuyait sur le `repr` d'un tuple : correct à deux ou
    trois éléments, il produit `in ('rss',)` — syntaxiquement invalide — dès qu'il
    n'en reste qu'un. Une contrainte de schéma ne doit pas dépendre d'un détail de
    formatage de Python (cf. audit phase 10)."""
    return "(" + ", ".join(f"'{v}'" for v in valeurs) + ")"


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
    # ex. reddit: {"subreddit", "score", "nb_commentaires"} ("score" = upvotes nets,
    # nom du champ PRAW, cf. scraper/reddit.py) ; toute plateforme: {"gdelt_event_id"}
    metadonnees: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    date_collecte: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    score: Mapped["Score | None"] = relationship(back_populates="article", uselist=False)
    mise_en_contexte: Mapped["MiseEnContexte | None"] = relationship(back_populates="article", uselist=False)

    __table_args__ = (
        CheckConstraint(f"plateforme in {_liste_sql(PLATEFORMES)}", name="ck_articles_plateforme"),
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

    # Contribution de chaque signal au score final : {signal: {valeur, poids, exclu}}.
    # Exigé explicitement par US-08 évaluateur ; NULL pour les scores calculés avant
    # l'ajout de la colonne (migration 0003, pas de rescoring rétroactif).
    detail_calcul: Mapped[dict | None] = mapped_column(JSONB)

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
    """Résout le rôle d'un pseudo connecté. Fondation
    V1 de l'authentification à 3 rôles (spectateur / contributeur / superadmin,
    cf. doc/V1/comptes-3-roles.md). Un pseudo absent de la table => rôle
    « spectateur ».

    **MàJ V3 :** le frontend ÉCRIT désormais cette table — enregistrement du
    pseudo à la première connexion (US-07), changement de code par son titulaire
    (US-05), promotion et rétrogradation par le superadmin (US-06). La règle
    « frontend en lecture seule stricte » est remplacée par une frontière plus
    précise : il écrit des intentions humaines, jamais un verdict
    (`articles`, `scores`, `mise_en_contexte` lui restent interdites en écriture —
    cf. doc/V0/architecture.md, décision V3).

    L'index unique insensible à la casse sur `lower(pseudo)` est
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
        CheckConstraint(f"role in {_liste_sql(ROLES)}", name="ck_comptes_role"),
    )


class Proposition(Base):
    """Article proposé par un compte connecté, en attente de décision d'un
    contributeur (V3, cf. doc/V3/userstories_crowdsourcing.md US-01 à US-04).

    Seule table, avec `commentaires` et `comptes`, que le frontend écrit. Elle
    porte une INTENTION humaine ; l'article, lui, n'est créé que par le pipeline,
    au moment de la collecte (`article_id` renseigné alors). C'est la frontière
    qui remplace « frontend en lecture seule stricte » (doc/V0/architecture.md,
    décision V3).

    `propose_par` et `decide_par` stockent le pseudo, pas une clé étrangère vers
    `comptes` : un spectateur n'a pas nécessairement de ligne au moment où il
    propose, et la trace doit survivre à la suppression d'un compte."""

    __tablename__ = "propositions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    url_canonique: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    propose_par: Mapped[str] = mapped_column(Text, nullable=False)
    date_proposition: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    statut: Mapped[str] = mapped_column(Text, nullable=False, default="en_attente")
    decide_par: Mapped[str | None] = mapped_column(Text)
    date_decision: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motif: Mapped[str | None] = mapped_column(Text)
    article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="SET NULL")
    )

    # Miroir des contraintes de `0005_propositions.sql`. `verifier_schema` ne
    # contrôle que les colonnes, donc leur absence en base ne se signalerait qu'à
    # la première écriture — les déclarer ici ne referme pas cet écart, mais rend
    # visible en lecture ce que la base garantit (audit phase 17, F17-08).
    # L'index unique partiel sur les statuts vivants n'est PAS déclarable
    # proprement ici : il vit dans la migration seule, comme
    # `uq_comptes_pseudo_lower`.
    __table_args__ = (
        CheckConstraint(f"statut in {_liste_sql(STATUTS_PROPOSITION)}", name="ck_propositions_statut"),
        CheckConstraint(
            "statut <> 'refusee' or (motif is not null and length(trim(motif)) > 0)",
            name="ck_propositions_refus_motive",
        ),
        CheckConstraint(
            "statut = 'en_attente' or (decide_par is not null and date_decision is not null)",
            name="ck_propositions_decision_tracee",
        ),
    )


class Commentaire(Base):
    """Parole d'un visiteur sur l'analyse d'un article (V3, US-08 crowdsourcing).

    Écrite par le frontend, comme `propositions` et `comptes`. Elle ne participe
    à AUCUN calcul : le score composite reste une moyenne pondérée de signaux
    traçables (US-08 évaluateur), et y injecter un retour humain non authentifié
    le rendrait manipulable par quiconque connaît le mot de passe partagé.

    `pseudo` et `retire_par` stockent le pseudo, pas une clé étrangère vers
    `comptes` : la trace doit survivre à la suppression d'un compte."""

    __tablename__ = "commentaires"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    pseudo: Mapped[str] = mapped_column(Text, nullable=False)
    texte: Mapped[str] = mapped_column(Text, nullable=False)
    date_creation: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Retrait = masquage. `retire_le is null` est la condition d'affichage public ;
    # le superadmin, lui, continue de voir le contenu retiré.
    retire_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retire_par: Mapped[str | None] = mapped_column(Text)

    # Miroir des contraintes de `0007_commentaires.sql` (cf. `Proposition`).
    __table_args__ = (
        CheckConstraint("length(trim(texte)) > 0", name="ck_commentaires_texte_non_vide"),
        CheckConstraint(
            "(retire_le is null and retire_par is null) "
            "or (retire_le is not null and retire_par is not null)",
            name="ck_commentaires_retrait_trace",
        ),
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
