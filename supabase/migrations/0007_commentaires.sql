-- V3, phase 4 — commentaires sur l'analyse d'un article
-- (cf. doc/V3/userstories_crowdsourcing.md US-08).
--
-- Troisième et dernière table écrite par le frontend. Elle porte la parole des
-- visiteurs, jamais celle du système : les commentaires n'influencent PAS le
-- score composite, et rien dans `scores` ne les lit (non-objectif explicite
-- d'US-08 — un vote humain non authentifié rendrait le score manipulable et lui
-- retirerait son explicabilité).

create table if not exists commentaires (
    id uuid primary key default gen_random_uuid(),
    article_id uuid not null references articles (id) on delete cascade,
    pseudo text not null,
    texte text not null,
    date_creation timestamptz not null default now(),
    -- Retrait = MASQUAGE, pas suppression. Sur un site qui publie des verdicts
    -- nommant des médias, un contenu retiré pour raison juridique doit rester
    -- consultable par le porteur du projet, pas s'évaporer.
    retire_le timestamptz,
    retire_par text,

    constraint ck_commentaires_texte_non_vide check (length(trim(texte)) > 0),
    -- Un retrait trace toujours QUI et QUAND, ou n'existe pas. Même principe que
    -- `ck_propositions_decision_tracee` : l'invariant vit dans la base, pas dans
    -- la seule route qui l'applique aujourd'hui.
    constraint ck_commentaires_retrait_trace check (
        (retire_le is null and retire_par is null)
        or (retire_le is not null and retire_par is not null)
    )
);

-- Lecture systématique : tous les commentaires d'un article, par date.
create index if not exists idx_commentaires_article
    on commentaires (article_id, date_creation);
-- Plafond par compte : comptage sur une fenêtre glissante.
create index if not exists idx_commentaires_pseudo on commentaires (pseudo, date_creation);
