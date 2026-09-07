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
| `superadmin` | `samirkema` | ligne dédiée dans `comptes` (créée par la migration) | code personnel (`comptes.secret_hash`), **imposé par contrainte** |
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

**Contrainte `ck_comptes_superadmin_a_un_code`** : un `superadmin` ne peut pas
avoir `secret_hash = NULL`. Sans elle, la propriété annoncée plus haut était
fausse par défaut — la migration semait `samirkema` sans code, donc le mot de
passe partagé suffisait à obtenir le rôle `superadmin`. La migration pose
maintenant un code aléatoire inconnu de tous ; le vrai code doit être posé à la
main (commande en fin de `0002_comptes.sql`). Tant qu'il ne l'est pas, le compte
superadmin est **inaccessible**, ce qui est le bon défaut.

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
  - mode local **explicite** (`FAKENEWS_MODE=local`) → `superadmin` fictif (le
    mode local est réservé au développeur, cf. US-04) ;
  - hors mode local, `FRONTEND_PASSWORD` absente → **accès refusé** (le défaut est
    fermé : une variable d'environnement oubliée sur Vercel ne doit pas ouvrir le
    site, cf. US-04 « condition bloquante ») ;
  - cookie absent, mal formé, **expiré** ou signature invalide → redirection `/login` ;
  - pseudo dans `comptes` → rôle associé ; sinon → `spectateur`.
- `POST /login` est plafonné à 10 tentatives ratées par client sur 5 minutes.
  Ralentisseur, pas barrière : sur Vercel chaque instance a son propre compteur.
  Deux propriétés à ne pas casser en y touchant :
  - le plafond ne s'applique **qu'aux échecs** — un mot de passe correct ouvre la
    session même compteur plein, sinon dix mauvaises tentatives fermeraient le
    site à tous ceux qui connaissent le bon ;
  - `X-Forwarded-For` est **ignoré par défaut**, car c'est le client qui l'écrit.
    Le lire sans condition rendait le plafond entièrement contournable (mesuré :
    50 tentatives avec en-tête tournant, 0 refus). Il n'est pris en compte que si
    `FAKENEWS_PROXYS_DE_CONFIANCE` déclare combien de proxys se trouvent devant
    l'application (cf. `.env.example`).
- `POST /login` : si le pseudo a un `secret_hash`, le mot de passe est vérifié
  contre ce hash (`crypt()` côté Postgres) ; sinon contre `FRONTEND_PASSWORD`.
- Cookie de session : `pseudo:expiration:HMAC(clé, "fakenews-session:" + pseudo + ":" + expiration)`
  où `clé = FRONTEND_PASSWORD + "\0" + (secret_hash | "")`. Conséquences : le cookie
  d'un compte à code personnel (samirkema) **ne peut pas** être fabriqué avec le
  seul mot de passe partagé — il faut aussi connaître `secret_hash`, qui ne vit
  qu'en base ; et l'expiration étant **dans la charge signée**, un cookie capté
  cesse de valoir au bout de 30 jours et ne peut pas être rallongé. (Auparavant la
  signature ne portait que le pseudo : le cookie était valide indéfiniment, et
  seule une rotation du mot de passe partagé — qui déconnecte tout le monde —
  pouvait le révoquer.)
- Le rôle **n'est pas** dans le cookie — relu en base à chaque requête, donc un
  changement de rôle prend effet immédiatement. Changer `secret_hash` invalide
  les cookies existants de ce pseudo (re-connexion).
- Pseudo normalisé en minuscules, `^[a-z0-9._-]{1,64}$`.

## Limite de sécurité résiduelle

Le mot de passe partagé reste partagé : **n'importe qui le connaissant peut se
connecter en tant que `spectateur` ou `contributeur` sous le pseudo de son
choix.** Seul `superadmin` (samirkema) est une vraie frontière, grâce à son code
personnel — et cette fois la base le garantit, au lieu de dépendre d'un `update`
manuel que rien ne vérifiait.

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
