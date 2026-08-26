-- V1 — fondation « comptes à 3 rôles » du frontend
-- (cf. doc/V1/comptes-3-roles.md).
--
-- Le frontend LIT cette table (jamais d'écriture — il reste strictement en
-- lecture seule, cf. doc/V0/architecture.md, doc/V0/userstories_frontend.md
-- US-04) pour résoudre le rôle d'un pseudo connecté :
--   - pseudo présent ici        -> rôle associé (contributeur / superadmin) ;
--   - pseudo absent de la table -> rôle « spectateur » (défaut implicite).
--
-- La gestion des comptes (ajouter un contributeur, changer un rôle) se fait
-- directement en base, hors frontend.

create table if not exists comptes (
    id uuid primary key default gen_random_uuid(),
    pseudo text not null,
    role text not null,
    -- NULL  => ce pseudo se connecte avec le mot de passe partagé (FRONTEND_PASSWORD).
    -- Sinon => hash bcrypt d'un code personnel ; ce pseudo DOIT utiliser ce code,
    --          le mot de passe partagé ne lui donne pas accès. Voir plus bas.
    secret_hash text,
    date_creation timestamptz not null default now(),

    constraint ck_comptes_role check (role in ('spectateur', 'contributeur', 'superadmin'))
);

-- (idempotence si la table préexistait sans la colonne)
alter table comptes add column if not exists secret_hash text;

-- Pseudo unique, insensible à la casse (le frontend normalise en minuscules
-- avant toute comparaison).
create unique index if not exists uq_comptes_pseudo_lower on comptes (lower(pseudo));

-- Superadmin unique du projet.
insert into comptes (pseudo, role) values ('samirkema', 'superadmin')
on conflict do nothing;

-- Code personnel de samirkema : le rendre DIFFÉRENT du mot de passe partagé.
-- pgcrypto est déjà activé par 0001. Remplacer 'CHANGE-MOI' par le vrai code,
-- puis exécuter (ré-exécutable pour changer le code) :
--
--   update comptes
--      set secret_hash = crypt('CHANGE-MOI', gen_salt('bf'))
--    where lower(pseudo) = 'samirkema';
--
-- Tant que secret_hash reste NULL, samirkema se connecte avec le mot de passe
-- partagé (comme les autres).
