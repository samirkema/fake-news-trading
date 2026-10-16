-- Budget mensuel LLM (plafond 2 €/mois, cf. fakenews.budget_llm).
-- CHANGEMENT DE SCHÉMA PARTAGÉ : nouvelle table, écrite par le client LLM commun
-- (évaluateur + contextualiseur), lue par lui seul. Non déclarée dans
-- fakenews.models : le frontend (Vercel) n'en dépend donc pas. À appliquer AVANT
-- d'activer le pipeline : sans elle, les appels LLM sont refusés (échec fermé).
create table if not exists usage_llm (
    id bigserial primary key,
    cree_le timestamptz not null default now(),
    modele text not null,
    tokens_entree integer not null default 0 check (tokens_entree >= 0),
    tokens_sortie integer not null default 0 check (tokens_sortie >= 0),
    cout_eur numeric(10, 6) not null default 0 check (cout_eur >= 0)
);

create index if not exists idx_usage_llm_cree_le on usage_llm (cree_le);

-- Même posture que salle_messages : RLS sans politique, invisible de l'API REST publique.
alter table usage_llm enable row level security;
