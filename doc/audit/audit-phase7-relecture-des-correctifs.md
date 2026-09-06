# Audit de relecture des correctifs de la phase 6

Seconde passe d'audit, en lecture seule, sur l'état de `audit/correctifs-codebase`
(`6534a70`). Objet : vérifier que les 33 findings de
[`audit-phase6-codebase-complete.md`](audit-phase6-codebase-complete.md) sont
réellement corrigés, et auditer les correctifs eux-mêmes.

**Verdict : Critique 0 · High 1 · Medium 6 · Low 8 (15 findings).**
32 des 33 findings de la phase 6 sont vérifiés corrigés. Un ne l'est qu'en
apparence. Les 14 autres findings sont **introduits par les correctifs**.

---

## Résumé

| Division | Statut | Synthèse |
| --- | --- | --- |
| Métier | 🟡 Avertissement | Le garde-fou censé implémenter le 3ᵉ critère d'US-04 laisse passer « 42 comments ». Et `non_evaluable`, déclaré ressuscité, est toujours mort. |
| Qualité | 🟡 Avertissement | Le faux vert est éteint — 171 tests, zéro skip. Mais le correctif a ramené un test qui valide une entrée que le pipeline ne produit jamais, et trois imports qui cassent sous le mode d'import recommandé. |
| Architecture | 🟡 Avertissement | Un verrou de threading dans un pipeline séquentiel, un `build-system` que rien n'installe. |
| Cybersécurité Offensive | 🔴 Bloquant | Le plafond anti-bruteforce est probablement clé sur l'IP du proxy Vercel. Auquel cas dix échecs verrouillent le site pour tout le monde. |

| Sous-audit | Crit | High | Med | Low | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| Business Logic | 0 | 0 | 2 | 0 | FAIL |
| Requirements Compliance | 0 | 0 | 1 | 0 | FAIL |
| Doc-Sync | 0 | 0 | 1 | 1 | FAIL |
| A11y/UX | 0 | 0 | 0 | 1 | PASS |
| Clean Code | 0 | 0 | 0 | 2 | PASS |
| Fail-Loud | 0 | 0 | 0 | 2 | PASS (réserve) |
| Test Quality | 0 | 0 | 2 | 2 | FAIL |
| Mutation/Saboteur | 0 | 0 | 1 | 0 | FAIL |
| Layer Enforcer | 0 | 0 | 0 | 0 | PASS |
| YAGNI | 0 | 0 | 0 | 2 | PASS (réserve) |
| SRE/Performance | 0 | 1 | 1 | 1 | FAIL |
| Architecture Consistency | 0 | 0 | 1 | 1 | FAIL |
| Contextual Threat | 0 | 1 | 1 | 0 | FAIL |
| SAST | 0 | 1 | 1 | 0 | FAIL |
| Supply Chain | 0 | 0 | 1 | 0 | PASS (réserve) |
| Privacy/Exfiltration | 0 | 0 | 0 | 0 | PASS |

---

## Findings

### N1 — High [RISQUE] — Le plafond anti-bruteforce peut verrouiller le site entier

- **Preuve** : `src/fakenews/frontend/app.py:158-159`
- **Type** : [RISQUE] (non vérifiable sans déployer)

`_client_de` renvoie `request.client.host` sans consulter `X-Forwarded-For` ni
installer de middleware proxy. Sur Vercel, l'application tourne derrière
l'infrastructure edge : si le pair TCP est ce proxy, **tous les visiteurs
partagent un unique compteur**.

Scénario : dix `POST /login` avec un mauvais mot de passe suffisent alors à
renvoyer 429 à *toute* connexion ultérieure pendant cinq minutes — y compris avec
le bon mot de passe, comportement délibéré et verrouillé par
`tests/test_correctifs_audit.py:151`. Maintenu à deux requêtes par seconde, le
site est indisponible en permanence.

Le durcissement posé pour corriger le finding M6 de la phase 6 devient un déni de
service à dix requêtes.

**Correction attendue** : dériver l'identifiant client du dernier saut de
confiance (`X-Forwarded-For`), ou renoncer au plafond par IP au profit d'un
plafond global assumé et beaucoup plus haut. Un `logger.info` du `host` observé
sur un déploiement de test tranche en une requête.

### N2 — Medium — `non_evaluable` est toujours inatteignable

- **Preuve** : `src/fakenews/evaluateur/style.py:78-84`, `src/fakenews/scraper/rss.py:120`
- **Type** : Confirmé (vérifié par exécution)

`evaluer_style` ne s'exclut que si titre **et** contenu sont vides. Or `rss.py:120`
rejette toute entrée sans titre, et Reddit impose un titre à tout post : aucun
article persisté ne peut avoir un titre vide.

```
evaluer_style('Un titre', '', None)  ->  20.0
evaluer_style('T', '', None)         ->  20.0
evaluer_style('', '', None)          ->  None   # inatteignable via le scraper
```

Le finding M3 de la phase 6 n'est donc pas corrigé, et les cinq mécanismes qui
défendent cet état — contrainte `ck_scores_non_evaluable_coherent`, filtre
`app.py:281`, garde `declenchement.py:24`, exigence US-08, test
`test_frontend.py:67` — restent du code mort.

**Correction attendue** : soit exclure `style` sur un critère réellement
atteignable (contenu vide **et** aucun signal détecté hors « pas d'auteur »), soit
retirer l'exigence et le code qui la défend.

### N3 — Medium — Le test de N2 donne une fausse confiance

- **Preuve** : `tests/test_correctifs_audit.py:227-241`
- **Type** : Confirmé

Le test qui atteste de la correction appelle `evaluer_style("", "")` directement
et n'emprunte jamais le pipeline. Il valide une entrée que le système ne produit
pas. C'est exactement le motif que la phase 6 reprochait au dépôt, réintroduit par
son propre correctif.

**Mutation non tuée** : revenir à l'état d'avant le correctif — vider
`evaluer_style` de sa branche d'exclusion — ne fait échouer aucun test empruntant
le pipeline.

### N4 — Medium — La porte à « claim précise et vérifiable » est quasi toujours passante

- **Preuve** : `src/fakenews/evaluateur/source_primaire.py:200-212`
- **Type** : Confirmé (vérifié par exécution)

L'alternative `\d` dans `_MARQUEURS_CLAIM` fait qu'un chiffre quelconque, où qu'il
se trouve dans le titre et les 2000 premiers caractères du contenu, qualifie une
« claim factuelle précise » au sens d'US-04 :

| Entrée | Qualifiée ? |
| --- | --- |
| `Posted 3 hours ago \| 42 comments` | oui |
| `J'ai 2 actions, je sais pas quoi faire` | oui |
| `Why I still hold Meta in 2026` | oui |
| `Ford thread #12` | oui |
| `Nvidia` / `lol` | non |

Le garde-fou présenté comme l'implémentation du 3ᵉ critère d'acceptation d'US-04
est largement décoratif. La protection réelle contre le faux positif de masse
vient entièrement de la requête de contrôle, un étage plus loin — la défense en
profondeur tient, mais son premier étage est en carton.

### N5 — Medium — `_tentatives_login` croît sans borne

- **Preuve** : `src/fakenews/frontend/app.py:57,143-155`
- **Type** : Confirmé (mesuré)

`_trop_de_tentatives` ne purge que la clé qu'on lui présente ; les autres ne le
sont jamais. Mesuré : 50 000 clients distincts échouant une fois chacun laissent
50 000 entrées permanentes (~43 Mo), inchangées après consultation d'une clé.

Fuite mémoire sur tout process durable (uvicorn local, instance Vercel tiède).
À noter : ce finding et N1 se contredisent dans leurs effets — si l'identifiant
client collapse sur le proxy, il n'y a pas de croissance mais il y a le DoS.
Aucun des deux ne disparaît pour autant.

### N6 — Medium — Trois imports cassent sous `--import-mode=importlib`

- **Preuve** : `tests/test_frontend.py:5`, `tests/test_comptes.py:11`, `tests/test_correctifs_audit.py:11`
- **Type** : Confirmé (vérifié par exécution)

`from conftest import _mode_heberge` échoue sous le mode d'import recommandé par
pytest et destiné à devenir le défaut :

```
pytest --import-mode=importlib --co
-> 3 errors during collection (ModuleNotFoundError: No module named 'conftest')
```

Les voisins du même dossier utilisent `from tests._llm_factice import`, qui
fonctionne dans les deux modes. Deux conventions concurrentes, dont une fragile.

### N7 — Medium — Toujours pas de lockfile

- **Preuve** : `requirements.txt`, `api/requirements.txt`
- **Type** : Confirmé (report de la phase 6, atténué)

Les bornes hautes ajoutées réduisent la dérive mais ne rendent pas deux exécutions
du même commit identiques.

### Low

| # | Preuve | Finding |
| --- | --- | --- |
| N8 | `tests/test_run_evaluateur.py:26` | « `evaluer_articles_non_scores()` les traite tous, par conception » est faux depuis le plafond de 300 (`run_evaluateur.py:37`). Le test survit uniquement parce que le tri `date_publication DESC` place son article fraîchement inséré dans la fenêtre ; un test daté d'il y a un an échouerait sans indice exploitable. |
| N9 | `tests/conftest.py` | Aucune garde réseau. `test_le_detail_du_calcul_est_persiste` appelle le vrai `evaluer_articles_non_scores` ; il ne sort aujourd'hui que parce qu'aucun titre de test ne cite une entreprise de la table. |
| N10 | `src/fakenews/evaluateur/run_evaluateur.py:137-140` | Deux `int(os.environ.get(...))` non protégés : une valeur non numérique fait planter le run sur une `ValueError` nue. Fail-loud acceptable, diagnostic pauvre. |
| N11 | `src/fakenews/evaluateur/source_primaire.py:34-44` | `_verrou_debit` protège un compteur qu'aucune concurrence n'atteint, et le `sleep` est fait à l'intérieur du verrou. Le pipeline est strictement séquentiel. |
| N12 | `.github/workflows/ci.yml:69` | `ET.parse("rapport.xml")` sans garde : une erreur de collecte pytest ne produit pas de rapport, et le step `if: always()` remonte une `FileNotFoundError` nue au lieu du diagnostic. |
| N13 | `pyproject.toml:1-12` | `build-system` et `packages.find` déclarés, mais rien n'installe le paquet — CI, pipeline et Vercel passent tous par `PYTHONPATH=src` ou `sys.path.insert`. |
| N14 | `src/fakenews/frontend/templates/detail.html:4` | Le `<title>` reprend le titre d'article brut, correctement échappé mais non tronqué. |
| N15 | `src/fakenews/evaluateur/source_primaire.py:322` | Le cas le plus fréquent (aucune correspondance) coûte deux requêtes SEC au lieu d'une, chacune précédée de 0,15 s de throttle. Compromis assumé pour la justesse. |

### Écart documentaire

`doc/audit/audit-phase6-codebase-complete.md:113` déclare M3 corrigé, et `:37`
donne « un commentaire d'humeur citant Apple » comme exemple désormais écarté. Ni
l'un ni l'autre n'est exact (cf. N2 et N4).

---

## Thèmes transverses

1. **Le correctif qui se croit sur parole.** Trois des six Medium viennent du même
   geste : écrire la correction, écrire le test qui la confirme, écrire le rapport
   qui la proclame — sans vérifier que le chemin corrigé est atteignable depuis le
   pipeline réel. La phase 6 reprochait au dépôt de tester ses mocks ; son
   correctif teste ses propres fonctions en isolation.
2. **Le durcissement qui ouvre une autre porte.** Le plafond `/login` et le verrou
   de débit SEC ajoutent tous deux un état partagé en mémoire de process à une
   application qui, sur Vercel, n'a ni process stable ni IP client fiable. Les
   deux hypothèses implicites sont fausses dans l'environnement cible.
3. **Ce qui a été vérifié pour de vrai tient.** Les correctifs adossés à une
   exécution — contrainte SQL rejouée en base, garde-fou CI testé dans les deux
   sens, graphe d'imports du frontend tracé, API SEC interrogée — ne présentent
   aucun défaut. Les défauts restants sont exactement ceux qu'aucune exécution
   n'est venue contredire.

---

## Points conformes vérifiés

**Findings de la phase 6 réellement corrigés :**

- **C1** — 171 tests, **0 skip**, 0 échec sur une base créée de zéro avec les
  migrations 0001→0003. Garde-fou CI exécuté tel que bash le reçoit, dans les deux
  sens : 0 skip → exit 0, 72 skips → bloque.
- **H2** — la clé Google n'apparaît plus dans `raison` (testé).
- **H3** — contrainte `ck_comptes_superadmin_a_un_code` vérifiée en base, avec
  rattrapage des bases héritées et idempotence du rejeu.
- **H4, H5, H6** — fail-closed, encadrement du contenu tiers, matching par jetons :
  corrigés et testés.
- **M7** — vérifié par traçage de `sys.modules` : le frontend charge **zéro**
  dépendance lourde, et `api/requirements.txt` couvre exactement sa clôture
  d'imports.
- **M1, M2** (pagination, `date_max`) — corrigés avec des tests qui tueraient la
  mutation.
- Zéro lien mort dans README et `doc/`.

**Mutations désormais tuées** : supprimer la clé de tri secondaire de la
pagination ; retirer `forms=8-K` ou `entityName` de la requête SEC ; passer le
titre entier en `q` ; inverser une borne de date ; retirer l'expiration de la
charge signée du cookie ; supprimer la contrainte superadmin.

**Sécurité inchangée et conforme** : zéro injection SQL, zéro XSS (autoescape
actif, aucun `|safe`), pas de désérialisation non sûre, pas de SSRF, pas de secret
en dur ; `hmac.compare_digest` aux deux comparaisons ; pseudo validé par liste
blanche ; bcrypt délégué à pgcrypto ; cookie `httponly`/`secure`/`samesite` posé
**et** supprimé avec les mêmes attributs.

---

## Limites de vérification

- **Le finding High est un [RISQUE], pas un défaut prouvé.** Déterminer ce que
  vaut `request.client.host` derrière Vercel demande un déploiement, non effectué.
  Les deux issues : identifiant correct (le plafond fonctionne, et N5 devient le
  vrai problème) ou identifiant du proxy (déni de service trivial).
- **`api/requirements.txt`** : la clôture d'imports est vérifiée localement, mais
  la règle de priorité de `@vercel/python` (fichier adjacent au point d'entrée
  avant celui de la racine) reste non vérifiée sans déployer.
- **Instance Supabase de production** non consultée. Si `samirkema` y existe
  encore avec `secret_hash` NULL, la migration 0002 doit être rejouée.
- Clés Google Fact Check et Anthropic absentes : chemins nominaux couverts par des
  doubles. SEC EDGAR interrogé pour de vrai.
- Aucune modification du code audité pendant cette passe.

### Commandes exécutées

| Commande | Résultat |
| --- | --- |
| `pytest -q` sur Postgres neuf (migrations 0001→0003) | **171 passed, 0 skipped, 0 failed** en 4,0 s |
| Extraction du step CI depuis le YAML puis `bash` sur le script tel quel | heredoc correct, garde-fou fonctionnel |
| `pytest --import-mode=importlib --co` | **3 erreurs de collecte** |
| `_porte_une_claim_verifiable` sur 6 cas réalistes | 5 sur 6 qualifiés « claim précise » |
| `evaluer_style` sur des titres non vides | valeur toujours numérique |
| 50 000 `_enregistrer_tentative_ratee` puis un `_trop_de_tentatives` | 50 000 entrées avant et après (~43 Mo) |
| Traçage de `sys.modules` à l'import du frontend | zéro dépendance lourde |
| `yaml.safe_load` × 5 workflows, `json.load`, `tomllib` | tous valides |
| `git check-ignore .env.example` | non ignoré (exception fonctionnelle) |
| Rejeu des 3 migrations sur base neuve | idempotent, sans erreur |

---

## Suite recommandée

Deux corrections rendent ce rapport sans objet :

1. Lire `X-Forwarded-For` dans `_client_de` — lève N1, et avec lui le risque de
   disponibilité.
2. Faire porter l'exclusion de `style` sur un état que le scraper produit
   réellement, et corriger le test pour qu'il emprunte le pipeline — lève N2 et N3.

Plus, dans la foulée : rectifier les deux affirmations inexactes de
`audit-phase6-codebase-complete.md`.
