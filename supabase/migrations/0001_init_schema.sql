-- Phase 0 — schéma de stockage partagé, contrat entre scraper, évaluateur,
-- contextualiseur et frontend (cf. doc/architecture.md, doc/plan_implementation.md).

create extension if not exists pgcrypto;

-- Écrite par le scraper (US-01/US-02/US-04 scraper). Lue par l'évaluateur.
create table if not exists articles (
    id uuid primary key default gen_random_uuid(),
    titre text not null,
    contenu text not null,
    auteur text,
    domaine_source text,
    date_publication timestamptz not null,
    url text not null,
    url_canonique text not null,
    hash_contenu text not null,
    plateforme text not null,
    metadonnees jsonb not null default '{}'::jsonb,
    date_collecte timestamptz not null default now(),

    constraint ck_articles_plateforme check (plateforme in ('rss', 'reddit')),
    constraint uq_articles_url_canonique unique (url_canonique)
);

create index if not exists idx_articles_domaine_source on articles (domaine_source);
create index if not exists idx_articles_date_publication on articles (date_publication);
create index if not exists idx_articles_hash_contenu on articles (hash_contenu);

-- Écrite par l'évaluateur (US-01 à US-08 évaluateur). Lue par le contextualiseur et le frontend.
-- Un seul score par article : pas de rescoring en v1 (cf. doc/architecture.md).
create table if not exists scores (
    id uuid primary key default gen_random_uuid(),
    article_id uuid not null references articles (id) on delete cascade,

    -- {reputation: {valeur, raison, preuve_id}, corroboration: {...}, ...}
    -- cf. interface evaluer(article) dans doc/architecture.md
    sous_scores jsonb not null,
    -- poids réellement appliqués à ce calcul (traçabilité, cf. US-08 évaluateur)
    poids jsonb not null,

    score_final numeric(5, 2),
    non_evaluable boolean not null default false,
    date_calcul timestamptz not null default now(),

    constraint uq_scores_article_id unique (article_id),
    constraint ck_scores_non_evaluable_coherent check (
        (non_evaluable and score_final is null)
        or (not non_evaluable and score_final is not null)
    ),
    constraint ck_scores_score_final_range check (
        score_final is null or (score_final >= 0 and score_final <= 100)
    )
);

create index if not exists idx_scores_score_final on scores (score_final);

-- Écrite par le contextualiseur (US-01 à US-04 contextualiseur), uniquement pour les
-- articles au-dessus du seuil de suspicion. Lue par le frontend.
create table if not exists mise_en_contexte (
    id uuid primary key default gen_random_uuid(),
    article_id uuid not null references articles (id) on delete cascade,

    explication text not null,
    -- items {preuve_id, ...} ancrés sur un preuve_id présent dans scores.sous_scores
    -- pour cet article (cf. US-02 contextualiseur)
    faits_traces jsonb not null default '[]'::jsonb,
    -- items sans preuve_id, ou rejetés de faits_traces faute de preuve_id valide
    deductions_llm jsonb not null default '[]'::jsonb,
    sources_utilisees jsonb not null default '[]'::jsonb,
    -- méthode de calcul non encore définie (cf. US-03/US-04 contextualiseur) ;
    -- stocké en texte libre en attendant qu'une échelle soit tranchée
    niveau_confiance text,
    avertissement text not null,
    date_generation timestamptz not null default now(),

    constraint uq_mise_en_contexte_article_id unique (article_id)
);
