-- V3, phase 2 — file d'attente des articles proposés
-- (cf. doc/V3/userstories_crowdsourcing.md US-01 à US-04).
--
-- Écrite par le frontend (création par tout compte connecté, décision par un
-- contributeur), relue par le pipeline qui collecte les propositions acceptées.
-- Le frontend n'écrit toujours ni `articles`, ni `scores`, ni `mise_en_contexte` :
-- il enregistre une intention, pas un verdict (cf. doc/V0/architecture.md,
-- décision V3).

create table if not exists propositions (
    id uuid primary key default gen_random_uuid(),
    url text not null,
    url_canonique text not null,
    note text,
    propose_par text not null,
    date_proposition timestamptz not null default now(),
    statut text not null default 'en_attente',
    decide_par text,
    date_decision timestamptz,
    motif text,
    article_id uuid references articles (id) on delete set null,

    constraint ck_propositions_statut check (statut in
        ('en_attente', 'acceptee', 'refusee', 'collectee', 'echec_collecte')),
    -- Un refus sans motif est un mur, pas une décision (US-03).
    constraint ck_propositions_refus_motive check (
        statut <> 'refusee' or (motif is not null and length(trim(motif)) > 0)),
    -- Une décision trace toujours son auteur et sa date.
    constraint ck_propositions_decision_tracee check (
        statut = 'en_attente' or (decide_par is not null and date_decision is not null))
);

-- Une seule proposition VIVANTE par URL (US-01), sans gêner l'historique des
-- refus : un article refusé peut être reproposé plus tard.
create unique index if not exists uq_propositions_en_cours
    on propositions (url_canonique)
    where statut in ('en_attente', 'acceptee');

create index if not exists idx_propositions_statut on propositions (statut, date_proposition);
create index if not exists idx_propositions_propose_par on propositions (propose_par);

-- Un article peut désormais entrer par proposition humaine (US-04). La
-- contrainte d'origine n'autorisait que 'rss' et 'reddit' : l'insertion aurait
-- échoué.
alter table articles drop constraint if exists ck_articles_plateforme;
alter table articles add constraint ck_articles_plateforme
    check (plateforme in ('rss', 'reddit', 'proposition'));
