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
--
-- IMPORTANT (correctif d'audit) : cette ligne était auparavant semée avec
-- secret_hash NULL, ce qui rendait FAUX par défaut ce que doc/V1/comptes-3-roles.md
-- présente comme la seule vraie frontière du modèle : avec un secret_hash NULL,
-- quiconque connaît le mot de passe partagé se connecte en superadmin. La
-- contrainte ck_comptes_superadmin_a_un_code ci-dessous rend cet état impossible.
--
-- Le code semé ici est un PLACEHOLDER inutilisable en l'état : gen_random_uuid()
-- produit une valeur que personne ne connaît, donc personne ne peut se connecter
-- en samirkema tant que le vrai code n'a pas été posé. Fail-closed, pas fail-open.
insert into comptes (pseudo, role, secret_hash)
values ('samirkema', 'superadmin', crypt(gen_random_uuid()::text, gen_salt('bf')))
on conflict do nothing;

-- Rattrapage des bases où la version précédente de cette migration a déjà semé
-- samirkema avec secret_hash NULL (l'insert ci-dessus est alors un no-op) : on
-- referme la brèche avant d'ajouter la contrainte, sinon celle-ci échouerait.
update comptes
   set secret_hash = crypt(gen_random_uuid()::text, gen_salt('bf'))
 where role = 'superadmin' and secret_hash is null;

-- Un superadmin DOIT avoir un code personnel : sinon le mot de passe partagé lui
-- donne accès, et la frontière annoncée n'existe pas (cf. audit, finding H3).
alter table comptes drop constraint if exists ck_comptes_superadmin_a_un_code;
alter table comptes add constraint ck_comptes_superadmin_a_un_code
    check (role <> 'superadmin' or secret_hash is not null);

-- Poser le vrai code personnel de samirkema — pgcrypto est activé par 0001.
-- Remplacer 'LE-VRAI-CODE' puis exécuter (ré-exécutable pour changer le code) :
--
--   update comptes
--      set secret_hash = crypt('LE-VRAI-CODE', gen_salt('bf'))
--    where lower(pseudo) = 'samirkema';
--
-- Tant que ce n'est pas fait, le compte superadmin est inaccessible (le
-- placeholder aléatoire n'est connu de personne) — c'est voulu.
