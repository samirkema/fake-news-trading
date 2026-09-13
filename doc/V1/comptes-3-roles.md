# V1 — Comptes à 3 rôles (fondation)

Statut : **fondation posée le 2026-08-26, activée par la V3 le 2026-09-11.**
L'authentification distinguait trois rôles sans qu'aucune capacité n'y soit
conditionnée. Le crowdsourcing (`doc/V3/`) donne au `contributeur` sa première
capacité — décider quels articles entrent dans la base — ce qui rend opposables
les règles décrites ici. Les passages marqués **MàJ V3** signalent ce qui a
changé à ce moment-là.

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
| `contributeur` | promu par le superadmin depuis `/admin/comptes`, ou ajouté en base | ligne `role = 'contributeur'` | **code personnel** (MàJ V3), **imposé par contrainte** |
| `spectateur` | tout le monde par défaut | **aucune ligne** dans `comptes` | mot de passe partagé |

**Le rôle n'est jamais affiché** — ni libellé, ni étiquette. **MàJ V3 :** il est
en revanche *déductible* de l'interface, puisqu'un contributeur voit des accès
qu'un spectateur n'a pas. C'était le but de la fonctionnalité ; la phrase
d'origine (« un spectateur et un contributeur voient exactement le même site »)
ne vaut plus.

## Stockage — table `comptes`

Migration `supabase/migrations/0002_comptes.sql`. Colonnes : `pseudo`, `role`
(`spectateur` | `contributeur` | `superadmin`), `secret_hash`, `date_creation`.
Index unique insensible à la casse sur `lower(pseudo)`.

`secret_hash` : `NULL` → ce pseudo se connecte avec le mot de passe partagé ;
renseigné (hash bcrypt) → ce pseudo **doit** utiliser ce code personnel.

**Contrainte `ck_comptes_role_privilegie_a_un_code`** (migration `0004` ; elle
s'appelait `ck_comptes_superadmin_a_un_code` et ne visait que le superadmin
jusqu'à la V3) : **aucun rôle autre que `spectateur`** ne peut avoir
`secret_hash = NULL`. Sans elle, la propriété annoncée plus haut était
fausse par défaut — la migration semait `samirkema` sans code, donc le mot de
passe partagé suffisait à obtenir le rôle `superadmin`. La migration pose
maintenant un code aléatoire inconnu de tous ; le vrai code doit être posé à la
main (commande en fin de `0002_comptes.sql`). Tant qu'il ne l'est pas, le compte
superadmin est **inaccessible**, ce qui est le bon défaut.

**MàJ V3 — le frontend écrit désormais cette table** : enregistrement du pseudo à
la première connexion réussie (US-07), changement de code par son titulaire
(US-05), promotion et rétrogradation par le superadmin (US-06). La règle
« frontend strictement en lecture seule » est remplacée par une frontière plus
précise : il écrit des intentions humaines, jamais un verdict
(`doc/V0/architecture.md`, décision V3).

La gestion en SQL direct reste possible et documentée — l'écran ne la remplace
pas, il évite d'y recourir pour l'opération courante :

```sql
-- ajouter un contributeur : la contrainte 0004 EXIGE un code personnel
insert into comptes (pseudo, role, secret_hash)
values ('nom_du_contributeur', 'contributeur', crypt('LE_CODE', gen_salt('bf')));

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
  **Ce plafond ne refuse rien** : il déclenche un **délai croissant** sur les
  échecs (0,5 s par échec récent, 5 s au plafond). Seul, il ne changeait que la
  page d'erreur — 60 essais mesurés en 0,10 s, tous évalués (audit phase 14, F4).
  Avec le délai : 278 s pour les mêmes 60 essais.
  Le nombre d'attentes SIMULTANÉES est borné à 4 : une attente immobilise un fil
  et une connexion Postgres, et 40 essais concurrents rendaient le site
  injoignable (phase 15, F15-01). Au-delà de 4, on répond sans attendre — ce qui
  laisse à l'attaquant un moyen de désactiver le délai en saturant lui-même les
  places (phase 16, F16-01, ouvert). Le remède durable est un coût **intrinsèque**
  par tentative : hacher lentement le mot de passe partagé, comme les codes
  personnels le sont déjà.
  Ralentisseur, pas barrière : sur Vercel chaque instance a son propre compteur.
  Deux propriétés à ne pas casser en y touchant :
  - le plafond ne s'applique **qu'aux échecs** — un mot de passe correct ouvre la
    session même compteur plein, sinon dix mauvaises tentatives fermeraient le
    site à tous ceux qui connaissent le bon ;
  - `X-Forwarded-For` est **ignoré par défaut**, car c'est le client qui l'écrit.
    Le lire sans condition rendait le plafond entièrement contournable (mesuré :
    50 tentatives avec en-tête tournant, 0 refus). Il n'est pris en compte que si
    `FAKENEWS_PROXYS_DE_CONFIANCE` déclare combien de proxys se trouvent devant
    l'application. **Sur Vercel, cette valeur est 1** : la plateforme écrase
    `X-Forwarded-For` au lieu d'y ajouter un maillon, précisément « to prevent IP
    spoofing » ([doc Vercel](https://vercel.com/docs/headers/request-headers)), et
    n'y laisse que l'IP publique réelle du visiteur.
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
- Pseudo normalisé en minuscules, `^[a-z0-9._-]{1,64}$`. La **signature** du
  cookie est validée de la même façon (`^[0-9a-f]{64}$`) : sans cela, un octet
  non-ASCII dans le cookie atteignait `compare_digest` et produisait une 500 sur
  chaque page (phase 14, F2, second site).
- Tout mot de passe est comparé en **forme NFC** et sur des **octets**, par un
  point de passage unique (`_secrets_egaux`) : « é » s'écrit en un ou deux
  codepoints selon le clavier, et `compare_digest` refuse deux `str` non-ASCII.
  Ce défaut est apparu trois fois avant d'être traité comme une règle.
- **Codes personnels : 12 caractères minimum, 72 octets maximum.** La borne haute
  n'est pas décorative — bcrypt ignore tout ce qui dépasse 72 octets, donc deux
  codes partageant ce préfixe ouvriraient le même compte (phase 17, F17-02).

## Ce que chaque rôle peut faire (V3)

| Capacité | spectateur | contributeur | superadmin |
|---|---|---|---|
| Consulter articles, scores, mises en contexte | ✅ | ✅ | ✅ |
| Proposer un article à analyser (US-01) | ✅ | ✅ | ✅ |
| Voir la file d'attente et décider (US-02, US-03) | ❌ | ✅ | ✅ |
| Nommer / rétrograder un contributeur (US-06) | ❌ | ❌ | ✅ |
| Changer son code personnel (US-05) | — (mot de passe partagé) | ✅ | ✅ |

Les gardes comparent un **ordre** de rôles, jamais une égalité : le superadmin
est aussi contributeur. Un accès refusé rend **404**, pas 403 — un spectateur n'a
pas à apprendre que la file de modération existe.

Le rôle n'est toujours **pas affiché** : il se manifeste par les accès offerts.
C'est la lecture V3 de « l'utilisateur ne voit jamais son statut ».

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

> **MàJ V3 (2026-09-10) — cette échéance est arrivée.** Le crowdsourcing
> (`doc/V3/`) donne au contributeur le pouvoir de décider quels articles entrent
> dans la base. La voie retenue est la seconde : **un `secret_hash` par
> contributeur**, imposé par une contrainte de schéma étendue (un rôle autre que
> `spectateur` ne peut pas avoir `secret_hash = NULL`), et modifiable par son
> titulaire depuis un espace compte. Deux autres règles de ce document changent
> alors : le frontend **écrit** la table `comptes` (enregistrement à la première
> connexion, changement de code, promotion), et « l'utilisateur ne voit jamais son
> statut » cesse d'être vrai — un contributeur voit un accès que le spectateur n'a
> pas. C'est le but même de la fonctionnalité, pas un effet de bord.

## Hors périmètre de cette fondation

- Aucune capacité réservée à un rôle (rien n'est masqué/débloqué selon le rôle).
- Aucune UI de gestion des comptes (tout se fait en SQL).
- Pas de code distinct pour les contributeurs (cf. limite ci-dessus).
- Pas d'auto-inscription : un pseudo inconnu = spectateur, il n'est pas créé en
  base.
