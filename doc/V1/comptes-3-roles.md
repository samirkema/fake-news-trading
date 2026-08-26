# V1 — Comptes à 3 rôles (fondation)

Statut : **fondation posée**. L'authentification distingue trois rôles, mais
**aucune capacité n'est encore conditionnée au rôle** — c'est la brique de base
sur laquelle les modifications suivantes (soumission d'articles, commentaires,
modération…) viendront s'appuyer.

Demandé par l'utilisateur le 2026-08-26.

## Ce qui change

Avant : la version hébergée demandait un **mot de passe partagé** seul
(cf. `doc/V0/userstories_frontend.md` US-04).

Maintenant : l'écran de connexion demande **un pseudo + un mot de passe**. Le
pseudo détermine le rôle. Le mot de passe :

- **spectateurs et contributeurs** → le **mot de passe partagé** (`FRONTEND_PASSWORD`),
  inchangé, commun à tous ;
- **samirkema (superadmin)** → un **code personnel distinct** ; le mot de passe
  partagé ne lui donne pas accès.

## Les trois rôles

| Rôle | Qui | Résolution | Mot de passe |
|------|-----|------------|--------------|
| `superadmin` | `samirkema` | ligne dédiée dans `comptes` (créée par la migration) | code personnel (`comptes.secret_hash`) |
| `contributeur` | pseudos ajoutés à la main dans `comptes` | ligne `role = 'contributeur'` | mot de passe partagé |
| `spectateur` | tout le monde par défaut | **aucune ligne** dans `comptes` | mot de passe partagé |

**L'utilisateur ne voit jamais son statut.** Le rôle n'est pas affiché, pas
exposé aux gabarits, pas déductible de l'interface : un spectateur et un
contributeur voient exactement le même site aujourd'hui.

## Stockage — table `comptes`

Migration `supabase/migrations/0002_comptes.sql`. Colonnes : `pseudo`, `role`
(`spectateur` | `contributeur` | `superadmin`), `secret_hash`, `date_creation`.
Index unique insensible à la casse sur `lower(pseudo)`.

`secret_hash` : `NULL` → ce pseudo se connecte avec le mot de passe partagé ;
renseigné (hash bcrypt) → ce pseudo **doit** utiliser ce code personnel.

Le frontend **lit** cette table (résolution du rôle, vérification du code via
`crypt()` de Postgres) ; il ne l'écrit jamais — la règle « frontend strictement
en lecture seule » (`doc/V0/architecture.md`) tient toujours. **La gestion des
comptes se fait directement en base :**

```sql
-- ajouter un contributeur (mot de passe partagé)
insert into comptes (pseudo, role) values ('nom_du_contributeur', 'contributeur');

-- (re)définir le code personnel de samirkema — pgcrypto est activé par 0001
update comptes
   set secret_hash = crypt('LE_CODE', gen_salt('bf'))
 where lower(pseudo) = 'samirkema';
```

## Mécanique (frontend)

- `fakenews.frontend.app.compte_courant` : dépendance FastAPI qui sert à la fois
  de garde d'accès et de résolveur de rôle.
  - mode local (`FRONTEND_PASSWORD` non définie) → `superadmin` fictif (le mode
    local est réservé au développeur, cf. US-04) ;
  - cookie absent, mal formé ou signature invalide → redirection `/login` ;
  - pseudo dans `comptes` → rôle associé ; sinon → `spectateur`.
- `POST /login` : si le pseudo a un `secret_hash`, le mot de passe est vérifié
  contre ce hash (`crypt()` côté Postgres) ; sinon contre `FRONTEND_PASSWORD`.
- Cookie de session : `pseudo:HMAC(clé, "fakenews-session:" + pseudo)` où
  `clé = FRONTEND_PASSWORD + "\0" + (secret_hash | "")`. Conséquence : le cookie
  d'un compte à code personnel (samirkema) **ne peut pas** être fabriqué avec le
  seul mot de passe partagé — il faut aussi connaître `secret_hash`, qui ne vit
  qu'en base.
- Le rôle **n'est pas** dans le cookie — relu en base à chaque requête, donc un
  changement de rôle prend effet immédiatement. Changer `secret_hash` invalide
  les cookies existants de ce pseudo (re-connexion).
- Pseudo normalisé en minuscules, `^[a-z0-9._-]{1,64}$`.

## Limite de sécurité résiduelle

Le mot de passe partagé reste partagé : **n'importe qui le connaissant peut se
connecter en tant que `spectateur` ou `contributeur` sous le pseudo de son
choix.** Seul `superadmin` (samirkema) est une vraie frontière, grâce à son code
personnel.

Tant qu'aucune capacité n'est réservée aux `contributeur`, ça n'a pas
d'incidence. **Avant de donner à `contributeur` une action que `spectateur` ne
peut pas faire**, il faudra soit un code contributeur distinct, soit un
`secret_hash` par contributeur (même mécanisme que samirkema — le code est déjà
générique, seule la donnée manque).

## Hors périmètre de cette fondation

- Aucune capacité réservée à un rôle (rien n'est masqué/débloqué selon le rôle).
- Aucune UI de gestion des comptes (tout se fait en SQL).
- Pas de code distinct pour les contributeurs (cf. limite ci-dessus).
- Pas d'auto-inscription : un pseudo inconnu = spectateur, il n'est pas créé en
  base.
