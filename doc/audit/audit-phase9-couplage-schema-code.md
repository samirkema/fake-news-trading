# Audit phase 9 — couplage schéma / code, et configuration livrée

Audit en lecture seule sur `e711f65`.

**Verdict : Critique 0 · High 1 · Medium 2 · Low 7 (10 findings).**
Trois des Low sont des reports assumés (périmètre limité à la cybersécurité au
tour précédent). Hors reports : High 1 · Medium 2 · Low 4.

| Division | Statut | Synthèse |
| --- | --- | --- |
| Métier | 🟢 OK | Les signaux honorent le contrat. |
| Qualité | 🟡 Avertissement | Cinq tests sur le proxy, aucun sur la mauvaise configuration. |
| Architecture | 🔴 Bloquant | Déployer sur une base non migrée éteint le site, et rien ne le dit. |
| Cybersécurité Offensive | 🟡 Avertissement | Le code est sain ; le fichier d'exemple rouvre la porte. |

| Sous-audit | Crit | High | Med | Low | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| Business Logic | 0 | 0 | 0 | 1 | PASS |
| Requirements Compliance | 0 | 0 | 0 | 0 | PASS |
| Doc-Sync | 0 | 0 | 0 | 3 | PASS (réserve) |
| A11y/UX | 0 | 0 | 0 | 0 | PASS |
| Clean Code | 0 | 0 | 0 | 1 | PASS |
| Fail-Loud | 0 | 0 | 0 | 0 | PASS |
| Test Quality | 0 | 0 | 1 | 1 | FAIL |
| Mutation/Saboteur | 0 | 0 | 1 | 0 | FAIL |
| Layer Enforcer | 0 | 0 | 0 | 0 | PASS |
| YAGNI | 0 | 0 | 0 | 0 | PASS |
| SRE/Performance | 0 | 1 | 0 | 1 | FAIL |
| Architecture Consistency | 0 | 1 | 0 | 0 | FAIL |
| Contextual Threat | 0 | 0 | 1 | 0 | FAIL |
| SAST | 0 | 0 | 1 | 0 | FAIL |
| Supply Chain | 0 | 0 | 0 | 1 | PASS (réserve) |
| Privacy/Exfiltration | 0 | 0 | 0 | 0 | PASS |

---

## Q1 — High — Schéma et code déployés sans rien qui les synchronise

- **Preuve** : `src/fakenews/models.py:73` ↔ `supabase/migrations/0003_scores_detail_calcul.sql`
- **Type** : Confirmé (vérifié par exécution)

Ce n'est pas un défaut de ligne, c'est un défaut de structure. Les deux artefacts
partent par deux canaux séparés :

| Artefact | Canal | Déclencheur |
| --- | --- | --- |
| Le code | `git push` → Vercel | automatique |
| Le schéma | SQL collé à la main dans Supabase | manuel, hors dépôt |

Aucun outil de migration, aucune table de version de schéma. Le seul endroit du
dépôt qui applique les migrations est `ci.yml:56`, et uniquement contre la base de
**test**. Pour la production, l'ordre repose entièrement sur la mémoire de
l'opérateur.

Vérifié sur une base montée avec 0001+0002 seulement :

```
ProgrammingError — column scores.detail_calcul does not exist
```

`models.Score` déclare `detail_calcul`, donc SQLAlchemy l'inclut dans chaque
`SELECT` : `/` et `/articles/{id}` renvoient 500, il ne reste que `/login`. Le
site est éteint, pas dégradé.

**L'asymétrie qui sauve** : un schéma en avance sur le code est inoffensif
(l'ancien code ignore ce qu'il ne déclare pas, et le frontend n'écrit jamais dans
`comptes`). L'inverse est fatal. D'où la règle « migrer d'abord » — qui n'était
écrite nulle part.

**Corrigé** : `fakenews.schema.verifier_schema`, appelé une fois à la création du
moteur (`db.py`), compare les colonnes déclarées à celles réellement présentes et
lève `SchemaIncomplet` en nommant la colonne manquante et la marche à suivre. Si
l'introspection elle-même échoue, on journalise et on laisse passer : ce contrôle
diagnostique une erreur de déploiement, il ne doit pas en devenir une. La règle
d'ordre est désormais écrite dans la section Déploiement du README.

## Q2 — Medium — Le fichier d'exemple livre une valeur qui neutralise le plafond

- **Preuve** : `.env.example:56` (état `e711f65`)
- **Type** : Confirmé (mesuré)

`FAKENEWS_PROXYS_DE_CONFIANCE=1` était livré **actif**, alors que 1 est une valeur
spécifiquement Vercel et que le README dit « Copier `.env.example` en `.env` ».

Dans tout environnement sans proxy réel, cette valeur fait lire `maillons[-1]` sur
un en-tête que le client écrit : **50 tentatives à en-tête tournant, 0 refus** —
exactement le contournement fermé en phase 8, rouvert par le fichier d'exemple.

Le fichier se contredisait lui-même : `FAKENEWS_MODE=local`, deux lignes plus
haut, est commenté précisément parce qu'il dépend de l'environnement.

**Corrigé** : ligne commentée, valeur Vercel conservée dans le commentaire, et un
test lit `.env.example` pour empêcher la régression.

## Q3 — Medium — Aucun test ne couvre la mauvaise configuration

- **Preuve** : `tests/test_correctifs_audit.py:178-249` (état `e711f65`)

Cinq tests couvrent le proxy ; tous déclarent un nombre de hops qui correspond à
la topologie qu'ils simulent. Le cas « hops déclaré, aucun proxy en face » —
celui que le fichier d'exemple installait — n'était exercé nulle part. C'est
précisément par ce trou que Q2 est passé.

**Mutation non tuée** : poser `FAKENEWS_PROXYS_DE_CONFIANCE=1` sans proxy réel ne
faisait échouer aucun test.

**Corrigé** : deux tests ajoutés — un qui garde le template, un qui documente
explicitement le danger de la configuration mensongère.

## Low

| # | Preuve | Finding | Statut |
| --- | --- | --- | --- |
| Q4 | `doc/audit/` | Les phases 8 et 9 n'existaient que dans la conversation, alors que le dossier est la convention de traçabilité du projet. | corrigé (ce fichier) |
| Q5 | `test_correctifs_audit.py:165` | `_marteler(client, nombre, entete=None)` : `nombre` vaut 0 aux six sites d'appel. Paramètre mort. | corrigé |
| Q6 | `app.py:110-128` | Déployer la branche invalide tous les cookies existants (format 2 → 3 segments). Bénin, non documenté. | documenté |
| Q7 | `README.md` | La section Déploiement ne listait pas `FAKENEWS_PROXYS_DE_CONFIANCE`. | corrigé |
| Q8 | `requirements.txt` | Pas de lockfile (report phase 8). | atténué |
| Q9 | `tests/conftest.py` | La garde réseau annonce « toute connexion » mais ne couvre pas libpq (report phase 8). | corrigé |
| Q10 | `source_primaire.py:196` | `\b\d{5,}\b` prend un code postal pour un chiffre d'affaires (report phase 8). | corrigé |
| Q11 | `main` vs branche | `main` (`a620c27`) tourne sur Vercel, la branche est 4 commits devant et non poussée, pendant que la base de production a été migrée en avance. | à refermer |

---

## Thèmes transverses

1. **Le code est corrigé, la configuration ne l'est pas.** Le finding de sécurité
   de cette passe n'est pas dans `app.py` — il est dans `.env.example`. Un
   contrôle vaut ce que vaut sa configuration par défaut.
2. **Les tests valident le nominal, jamais la dérive.** Cinq tests prouvent que le
   mécanisme marche bien configuré ; aucun ne demande ce qui se passe quand il est
   mal configuré, alors que c'est le mode de défaillance réel.
3. **Le socle tient.** Aucun Critique, une seule division bloquante, et le motif
   bloquant est un ordre de déploiement, pas un défaut de logique. La trajectoire
   33 → 15 → 9 → 10 s'est stabilisée : ce qui reste tient à l'exploitation.

## Points conformes vérifiés

- 179 tests, 0 skip, deux modes d'import.
- Le code du plafond est sain : rotation d'en-tête bloquée, maillons forgés
  ignorés, configuration illisible retombant sur le pair TCP, mot de passe correct
  jamais plafonné.
- La valeur Vercel est sourcée sur la documentation officielle plutôt que devinée.
- Contrainte superadmin, fail-closed, expiration signée, absence d'injection SQL
  et de XSS : tout tient.
- Trois migrations idempotentes et rejouables ; cinq workflows valides.

## Limites de vérification

- **Base de production non consultée.** Le script SQL fourni contenait bien
  l'ajout de `detail_calcul`, sans moyen de confirmer son exécution.
- Le finding Q2 est mesuré en local, sur le mécanisme réel. Sur Vercel, la valeur
  1 reste correcte : le risque porte sur tout autre environnement.
- `api/requirements.txt` : priorité du fichier adjacent non vérifiée sans
  déploiement.
- Aucune modification du code audité pendant la passe d'audit.

### Commandes exécutées

| Commande | Résultat |
| --- | --- |
| `pytest -q` sur Postgres neuf (0001→0003) | 179 passed, 0 skipped |
| Base 0001+0002 seulement, puis `select(Score)` | **`ProgrammingError — column scores.detail_calcul does not exist`** |
| Sonde : `hops=1` sans proxy, 50 tentatives à en-tête tournant | **0 refus** (contre 40 sans la variable) |
| `grep` des valeurs actives de `.env.example` | `FAKENEWS_PROXYS_DE_CONFIANCE=1` actif, `FAKENEWS_MODE` commenté |
| Sites d'appel de `_marteler` | 6, tous avec `nombre=0` |
| `grep -rl alembic\|schema_migrations` sur `supabase/` | aucun outil, aucune table de version |
| `grep -i migration README.md` | énumérées sous Installation, aucun ordre vis-à-vis du déploiement |
