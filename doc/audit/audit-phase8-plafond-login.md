# Audit phase 8 — relecture des correctifs de la phase 7

Audit en lecture seule sur `4c1a4cc`. Objet : vérifier les 15 findings de
[`audit-phase7-relecture-des-correctifs.md`](audit-phase7-relecture-des-correctifs.md)
et auditer les correctifs eux-mêmes.

**Verdict : Critique 0 · High 1 · Medium 2 · Low 6 (9 findings).**
Les 15 findings de la phase 7 sont vérifiés corrigés ; 7 des 9 ci-dessous sont
introduits ou révélés par ces correctifs.

| Division | Statut |
| --- | --- |
| Métier | 🟢 OK |
| Qualité | 🟡 Avertissement |
| Architecture | 🟢 OK |
| Cybersécurité Offensive | 🔴 Bloquant |

| Sous-audit | Crit | High | Med | Low | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| Business Logic | 0 | 0 | 0 | 1 | PASS |
| Requirements Compliance | 0 | 0 | 0 | 0 | PASS |
| Doc-Sync | 0 | 0 | 1 | 0 | FAIL |
| A11y/UX | 0 | 0 | 0 | 0 | PASS |
| Clean Code | 0 | 0 | 0 | 2 | PASS |
| Fail-Loud | 0 | 0 | 0 | 0 | PASS |
| Test Quality | 0 | 0 | 1 | 1 | FAIL |
| Mutation/Saboteur | 0 | 0 | 0 | 0 | PASS |
| Layer Enforcer | 0 | 0 | 0 | 0 | PASS |
| YAGNI | 0 | 0 | 0 | 0 | PASS |
| SRE/Performance | 0 | 0 | 0 | 2 | PASS |
| Architecture Consistency | 0 | 0 | 0 | 0 | PASS |
| Contextual Threat | 0 | 1 | 0 | 0 | FAIL |
| SAST | 0 | 1 | 0 | 0 | FAIL |
| Supply Chain | 0 | 0 | 0 | 1 | PASS (réserve) |
| Privacy/Exfiltration | 0 | 0 | 0 | 0 | PASS |

---

## P1 — High — Le plafond de `/login` est entièrement contournable

- **Preuve** : `src/fakenews/frontend/app.py:190-206` (état `4c1a4cc`)
- **Type** : Confirmé (mesuré)

`_identifiant_client` faisait confiance à `X-Forwarded-For` sans aucune notion de
proxy de confiance. Or cet en-tête est posé par le client.

**Mesuré : 50 tentatives de connexion avec un `X-Forwarded-For` tournant → 0
refus.** Trois caractères d'en-tête suffisaient à obtenir un compteur neuf à
chaque requête.

Le correctif de la phase 7 avait échangé un déni de service contre un
contournement total. Un contrôle présent à l'écran et absent dans les faits est
pire qu'un contrôle manquant : on croit protégé ce qui ne l'est pas.

**Corrigé en `a2df7a1`** : `X-Forwarded-For` est ignoré par défaut, lu seulement
si `FAKENEWS_PROXYS_DE_CONFIANCE` déclare la topologie. Après correctif, le même
scénario donne 40 refus sur 50, et un mot de passe correct passe toujours (303).

**Écart documentaire associé** : le commentaire justifiait la falsifiabilité par
« une authentification réussie n'est jamais bloquée » — exact sur la
disponibilité, muet sur le fait que l'usurpation annule aussi le contrôle.

## P2 — Medium — Un test certifiait le comportement vulnérable

- **Preuve** : `tests/test_correctifs_audit.py:165-190` (état `4c1a4cc`)

`test_l_identifiant_client_suit_l_en_tete_de_transfert` affirmait qu'un
`X-Forwarded-For` différent obtient son propre compteur — c'est-à-dire exactement
le mécanisme du contournement. Le test était vert, la protection nulle. Un test
qui verrouille une vulnérabilité rend la correction « cassante ».

**Corrigé** : remplacé par cinq tests couvrant le défaut, la configuration
explicite, les maillons forgés en amont du proxy, et la configuration invalide.

## P3 — Medium — La garde réseau annonce plus qu'elle ne couvre

- **Preuve** : `tests/conftest.py:44-72`

La docstring annonçait « Interdit **toute** connexion sortante non locale ».
Vérifié : `socket`, `httpx` et `urllib` sont bien bloqués, mais **psycopg2 ne
l'est pas** — libpq ouvre sa socket en C, hors de portée d'un monkeypatch sur
`socket.socket.connect`. Le garde-fou est réel et utile, sa description est trop
large. **Corrigé en phase 9.**

## Low

| # | Preuve | Finding | Statut |
| --- | --- | --- | --- |
| P4 | `source_primaire.py:196` | `\b\d{5,}\b` qualifie un code postal (94043), une référence (100234) ou un identifiant de post de « claim factuelle précise ». Coût borné : la requête de contrôle décide ensuite. | corrigé phase 9 |
| P5 | `app.py:143-166` | Purge O(n) + `min()` O(n) à chaque échec, sur un endpoint public. Mesuré : 1,2 ms par tentative à 10 000 entrées. | corrigé `a2df7a1` (FIFO O(1)) |
| P6 | `app.py:165` | `min(..., key=…[-1])` suppose la deque non vide ; vrai aujourd'hui, non garanti structurellement. | corrigé `a2df7a1` |
| P7 | `test_correctifs_audit.py:17` | `POIDS_PAR_DEFAUT` et `calculer_score_composite` importés et jamais utilisés. | corrigé `a2df7a1` |
| P8 | `tests/conftest.py:66` | Le message de refus nomme l'IP résolue, pas l'hôte demandé. | accepté |
| P9 | `requirements.txt` | Pas de lockfile ; dérive rendue observable par l'artefact CI, pas empêchée. | atténué |

---

## Points conformes vérifiés

- **179 tests, 0 skip**, verts en 4,3 s sur base neuve — et verts sous
  `--import-mode=importlib`, dont la phase 7 montrait qu'il cassait la collecte.
- La garde réseau bloque effectivement `socket.create_connection`, `httpx` et
  `urllib` (sondes jetables).
- Le test de `non_evaluable` passe par le pipeline et affirme l'état persisté :
  la mutation « retirer la branche d'exclusion de `style` » est tuée.
- Le déni de service de la phase 7 est fermé et gardé par un test.
- La porte à claims est validée sur 12 cas.
- Verrou `threading` supprimé, métadonnées de packaging décoratives supprimées.

## Limites de vérification

- Le finding High était confirmé côté code, pas côté plateforme : ce que Vercel
  fait de `X-Forwarded-For` n'avait pas été observé à ce stade. **Tranché depuis**
  (commit `e711f65`) : la documentation Vercel indique que la plateforme écrase
  l'en-tête « to prevent IP spoofing », d'où `FAKENEWS_PROXYS_DE_CONFIANCE=1`.
- `api/requirements.txt` : priorité du fichier adjacent au point d'entrée non
  vérifiée sans déploiement.
- Instance Supabase de production non consultée.

### Commandes exécutées

| Commande | Résultat |
| --- | --- |
| `pytest -q` sur Postgres neuf (0001→0003) | 179 passed, 0 skipped |
| `pytest --import-mode=importlib` | 179 passed |
| Sonde : `socket`, `httpx`, `urllib` vers un hôte distant | bloqués |
| Sonde : `psycopg2` vers un hôte distant | **non bloqué** |
| Sonde : 50 `POST /login` à `X-Forwarded-For` tournant | **0 refus** |
| Coût d'une tentative ratée à 10 000 entrées | 1,2 ms |
| `_porte_une_claim_verifiable` sur 16 cas | 12 conformes, 3 faux positifs |
| Détection d'imports morts par AST | 2 |
