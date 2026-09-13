-- V3, phase 1 — un rôle privilégié ne peut pas exister sans code personnel
-- (cf. doc/V3/userstories_crowdsourcing.md US-06).
--
-- La migration 0002 imposait déjà cette règle au seul `superadmin`. Elle valait
-- comme garde-fou tant qu'aucune capacité n'était réservée à un rôle. Le
-- crowdsourcing donne au `contributeur` le pouvoir de décider quels articles
-- entrent dans la base : sans code personnel, ce pouvoir appartient à quiconque
-- connaît le mot de passe partagé, sous le pseudo de son choix.
-- `doc/V1/comptes-3-roles.md` avait posé cette échéance mot pour mot.

-- Rattrapage AVANT la contrainte, sinon elle échouerait sur les lignes
-- existantes : un code aléatoire que personne ne connaît (fail-closed — le
-- contributeur en redemande un), même figure que 0002 pour le superadmin.
update comptes
   set secret_hash = crypt(gen_random_uuid()::text, gen_salt('bf'))
 where role <> 'spectateur' and secret_hash is null;

alter table comptes drop constraint if exists ck_comptes_superadmin_a_un_code;
alter table comptes drop constraint if exists ck_comptes_role_privilegie_a_un_code;
alter table comptes add constraint ck_comptes_role_privilegie_a_un_code
    check (role = 'spectateur' or secret_hash is not null);
