# Audit — Fondations (Phase 0) et Collecteur RSS (Phase 1, US-01)

**Sujet** : documentation complète du projet + code livré (schéma Supabase, modèles SQLAlchemy, collecteur RSS).
**Date** : 2026-08-04.
**Scope exclu** : Reddit (US-02), GDELT (US-03), évaluateur, contextualiseur, frontend — non implémentés, hors périmètre de cet audit.

---

## Resume De L'Audit

| Division | Statut | Synthese |
| --- | --- | --- |
| Métier (Anton Ego) | 🟡 Avertissement | Le code livré respecte fidèlement les critères d'acceptation testables de US-01/US-04 scraper, mais la documentation (fiche projet, plan) n'a pas suivi l'avancement réel et se contredit elle-même sur l'état du code. |
| Qualité (Gordon Ramsay) | 🔴 Bloquant | Zéro test automatisé sur une logique non triviale (repli, dédup, parsing de dates). Un bug de logique confirmé (traitement de `bozo`) passe inaperçu faute de filet de sécurité. |
| Architecture (Steve Jobs) | 🔴 Bloquant | Un appel réseau sans timeout viole directement le principe architectural "dégrader, jamais bloquer" que le projet s'est lui-même fixé — un flux qui traîne peut geler tout le run hebdomadaire. |
| Cybersécurité Offensive (Sherlock Holmes) | 🟡 Avertissement | Pas de faille active trouvée (XXE testé et écarté, pas d'injection SQL). Mais hygiène supply-chain/secrets incomplète pour un projet qui prévoit explicitement de passer par GitHub Actions sans supervision humaine. |

**Totaux normalisés** : Critical **0** · High **2** · Medium **8** · Low **4** (14 défauts confirmés/écarts, hors points conformes et 1 item explicitement testé et écarté).

---

## Index Des Sous-Audits

| Sous-audit | Scope | Crit | High | Medium | Low | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Business Logic Auditor | scraper/rss.py, migration | 0 | 0 | 2 | 0 | AUDIT_FAIL (medium) |
| Requirements Compliance Auditor | doc/userstories_scraper.md vs code | 0 | 0 | 0 | 0 | AUDIT_PASS (voir matrice) |
| Doc-Sync Auditor | 7 fichiers doc/ vs code | 0 | 0 | 3 | 2 | AUDIT_FAIL (medium) |
| A11y/UX Checker | — | — | — | — | — | Non applicable (aucun frontend) |
| Clean Code Auditor | models.py, rss.py | 0 | 0 | 0 | 1 | AUDIT_PASS (mineur) |
| Fail-Loud Auditor | rss.py | 0 | 1 | 0 | 0 | AUDIT_FAIL (high) |
| Test Quality Auditor | tout le projet | 0 | 1 | 0 | 0 | AUDIT_FAIL (high) |
| Mutation/Saboteur Auditor | rss.py, models.py | 0 | 0 | 0 | 0 | Sans objet — dérive directement du zéro-test ci-dessus |
| Layer Enforcer | src/fakenews/ | 0 | 0 | 0 | 0 | AUDIT_PASS |
| YAGNI Auditor | tout le code | 0 | 0 | 0 | 0 | AUDIT_PASS |
| SRE/Performance Auditor | rss.py, db.py | 0 | 1 | 2 | 0 | AUDIT_FAIL (high) |
| Architecture Consistency Auditor | architecture.md vs code, supabase/ | 0 | 0 | 1 | 1 | AUDIT_FAIL (medium) |
| Contextual Threat Analyst | ingestion RSS | 0 | 0 | 0 | 1 | AUDIT_FAIL (low, prospectif) |
| SAST Scanner | tout le code | 0 | 0 | 0 | 1 | AUDIT_FAIL (low) |
| Supply Chain & Artifact Auditor | requirements.txt, .env.example, absence .gitignore | 0 | 0 | 2 | 0 | AUDIT_FAIL (medium) |
| Privacy/Exfiltration Auditor | articles (contenu, auteur) | 0 | 0 | 0 | 0 | AUDIT_PASS (limite déjà documentée par le projet, cf. Limites) |

---

## Matrice De Couverture

| Exigence | Fichier(s) requis | Preuve implémentation | Statut |
| --- | --- | --- | --- |
| US-01 scraper : flux RSS haute réputation + douteux + satire, ≥2 langues | doc/userstories_scraper.md:13-21 | src/fakenews/scraper/sources_rss.py:15-64 | 🟡 Partiel — implémenté mais pendant francophone "douteux" absent (déjà documenté comme non résolu par le projet lui-même) |
| US-01 scraper : repli Reuters si indisponible, sans bloquer les autres flux | doc/userstories_scraper.md:16 | src/fakenews/scraper/rss.py:40-55 ; testé en direct (Reuters bozo=1/0 entries, repli Guardian 45 entrées) | ✅ Conforme |
| US-01 scraper : conserve titre, contenu, domaine, date, URL | doc/userstories_scraper.md:15 | src/fakenews/scraper/rss.py:88-102 | ✅ Conforme |
| US-04 scraper : schéma commun rss/reddit, pas gdelt comme plateforme | doc/userstories_scraper.md:60 | supabase/migrations/0001_init_schema.sql:21 ; models.py:48 | ✅ Conforme (corrigé pendant l'implémentation) |
| Phase 0 : table `articles` | doc/plan_implementation.md:31 | 0001_init_schema.sql:7-27 | 🟡 Schéma livré plus riche que décrit (voir finding DOC-2) |
| Phase 0 : table `scores`, non_evaluable si tous signaux exclus | doc/plan_implementation.md:32 ; userstories_évaluateur.md:119 | 0001_init_schema.sql:31-55, contrainte `ck_scores_non_evaluable_coherent` testée en direct | ✅ Conforme |
| Phase 0 : table `mise_en_contexte`, `preuve_id`/`faits_traces` | doc/plan_implementation.md:33 ; userstories_contextualiseur.md:30 | 0001_init_schema.sql:59-77 | 🟡 Schéma conforme au code, mais plan_implementation.md ne le décrit pas fidèlement (finding DOC-2) |
| US-05 scraper : dédup par URL canonique et/ou hash | doc/userstories_scraper.md:72 | rss.py:81-86 (URL canonique) ; hash calculé mais non utilisé pour dédup | 🟡 Partiel, explicitement scopé "hors périmètre de cette étape" par rss.py:64 — pas un défaut, US-05 est planifiée après US-01 (plan_implementation.md:46) |
| US-06 scraper : journalisation par run | doc/userstories_scraper.md:83-85 | Absent | ⚪ Non implémenté — hors périmètre annoncé (Phase 1 étape 6) |

---

## Top Findings

- **High** `src/fakenews/scraper/rss.py:43,50` — `feedparser.parse(url)` sans timeout réseau : une source qui traîne peut geler tout le run hebdomadaire, en violation directe du principe "dégrader, jamais bloquer" (`doc/architecture.md:67-71`).
- **High** Projet entier — zéro fichier de test, zéro dépendance de test dans `requirements.txt`. Logique non triviale (repli, canonicalisation, extraction de date, dédup) sans filet de régression.
- **Medium (Confirmé)** `src/fakenews/scraper/rss.py:44` — `flux.bozo` traité comme synonyme d'indisponibilité même quand `flux.entries` contient du contenu exploitable. Reproduit par un test XXE local (`bozo=1`, `entries=1`). N'affecte aujourd'hui aucune des 8 sources configurées (vérifié empiriquement), mais masquerait silencieusement une source valide derrière un log indiscernable d'une vraie panne.
- **Medium (Confirmé)** `src/fakenews/scraper/rss.py:77-79` + `run_rss.py:6` — entrées sans date ignorées en `debug` uniquement (invisible en config `INFO`). Reproduit en direct : NaturalNews retourne 31/31 entrées sans date exploitable (dates malformées serveur), donc `articles_ajoutes: 0` sans que rien ne distingue "rien de neuf" de "31 entrées perdues".
- **Medium (Écart documentaire)** `doc/fiche-projet-fake-news-trading.md:18` contredit `:24` du même fichier : "on part de zéro" alors que le code (Phase 0 + US-01 RSS) est livré et fonctionnel.
- **Medium** `.env.example:2` — format connexion directe Supabase (port 5432) alors que l'architecture retenue (Vercel serverless + GitHub Actions) est exactement le cas d'usage où Supabase recommande le pooler (port 6543) pour éviter l'épuisement des connexions en tier gratuit. `[RISQUE]`, non testé contre une vraie instance.
- **Medium** Absence de `.gitignore` alors que le projet prévoit explicitement GitHub (`doc/architecture.md:60`) — un `.env` réel suivant `.env.example` n'a aucune protection contre un commit accidentel du mot de passe Supabase.
- **Medium** `requirements.txt` — dépendances en bornes inférieures non plafonnées, sans lockfile, pour un pipeline destiné à tourner sans supervision humaine (GitHub Actions hebdomadaire).
- **Medium** `src/fakenews/scraper/rss.py:82-86` — vérification de doublon par une requête `SELECT` par entrée (N+1), en tension avec l'ambition affichée "aucune limite de volume n'est imposée arbitrairement" (`doc/userstories_scraper.md:21`).
- **Medium (Écart documentaire)** `doc/userstories_scraper.md:18` liste toujours 4 domaines anglophones "douteux" comme actifs alors que le code n'en implémente que 2 (les 2 autres confirmés cassés à l'implémentation, comme le document le demandait lui-même de vérifier).

---

## Details Par Division

### Division Métier (Anton Ego)

Le code ne trahit pas les critères d'acceptation qu'il prétend couvrir — c'est la documentation qui a cessé de refléter le code qu'elle a elle-même commandé.

- **Medium** `doc/userstories_scraper.md:18` : short-list de domaines douteux non mise à jour après vérification à l'implémentation (finding DOC-1).
- **Medium** `doc/fiche-projet-fake-news-trading.md:18` vs `:24` : auto-contradiction sur l'état du code (finding DOC-2).
- **Low** `doc/plan_implementation.md:100-102` : "prochaine étape" obsolète, aucun mécanisme de suivi d'avancement (finding DOC-3).
- **Low** `doc/plan_implementation.md:31,33` : description du schéma Phase 0 incomplète par rapport au schéma réellement livré (finding DOC-4).

### Division Qualité (Gordon Ramsay)

- **High** Zéro test dans tout le projet (finding QUAL-1, détaillé sous Test Quality Auditor).
- **Medium (Confirmé)** `rss.py:44` : logique `bozo`/`entries` incorrecte, reproduite (finding QUAL-2).
- **Low** `models.py:48` : contrainte CHECK générée par f-string sur un `repr()` de tuple Python — fonctionne aujourd'hui car `PLATEFORMES` est une constante statique, mais fragile en cas d'évolution (finding QUAL-3).

### Division Architecture (Steve Jobs)

- **High** `rss.py:43,50` : absence de timeout réseau, violation directe du principe "dégrader, jamais bloquer" déclaré par le projet lui-même (finding ARCH-1).
- **Medium** `.env.example:2` : format de connexion incohérent avec la topologie serverless retenue (finding ARCH-2, `[RISQUE]`).
- **Low** `supabase/migrations/` créé sans `supabase/config.toml` : la structure suit la convention CLI Supabase mais le scaffold `supabase init` n'a jamais été exécuté (finding ARCH-3).

### Division Cybersécurité Offensive (Sherlock Holmes)

- **Medium** Absence de `.gitignore` alors que GitHub est la prochaine étape documentée (finding SEC-1).
- **Medium** `requirements.txt` non plafonné/non verrouillé pour un pipeline non supervisé (finding SEC-2).
- **Low `[RISQUE]`** Contenu RSS stocké brut sans stratégie de sanitization documentée — vecteur XSS stocké prospectif pour la Phase 4 (finding SEC-3), aucune des 7 user stories ne couvre ce point.
- **Testé et écarté** : XXE via `feedparser` — payload de test local avec entité externe (`file:///etc/hostname`) ; l'entité revient littérale (`'&xxe;'`), non résolue. Pas de vulnérabilité.

---

## Details Par Sous-Audit

### Business Logic Auditor
- **Verdict** : AUDIT_FAIL (Medium)
- **Findings** : QUAL-2 (logique bozo/entries), et par ricochet l'observabilité du drop silencieux d'entrées sans date (recoupe Fail-Loud Auditor).
- **Points conformes** : le repli Reuters→Guardian fonctionne exactement comme spécifié (`doc/userstories_scraper.md:16`), testé en direct. La déduplication par URL canonique fonctionne et est défendue au niveau base (contrainte `uq_articles_url_canonique`, testée par insertion directe rejetée).

### Requirements Compliance Auditor
- **Verdict** : AUDIT_PASS pour les exigences dans le périmètre livré (voir Matrice De Couverture ci-dessus) ; les exigences hors périmètre (US-02, US-03, US-05 complet, US-06) sont explicitement non couvertes et le code le dit lui-même (`rss.py:64`), pas de fausse promesse.
- **Findings** : aucun écart entre code livré et critère d'acceptation revendiqué comme fait.
- **Points conformes** : le docstring de `collecter_rss` (`rss.py:58-64`) énonce honnêtement son propre périmètre plutôt que de laisser deviner ce qui est fait.

### Doc-Sync Auditor
- **Verdict** : AUDIT_FAIL (Medium)
- **Findings** : DOC-1, DOC-2, DOC-3, DOC-4 (détails ci-dessus et dans Top Findings).
- **Points conformes** : `doc/architecture.md` et les `userstories_*.md` restent globalement synchronisés entre eux (vérifié lors d'un audit précédent dans cette même session, non ré-audité ligne à ligne ici car hors du delta code de cette session — cf. Limites).

### A11y/UX Checker
- **Verdict** : Non applicable — aucun front-end/UI livré dans le périmètre de cet audit.

### Clean Code Auditor
- **Verdict** : AUDIT_PASS (mineur)
- **Findings** : QUAL-3 (f-string CHECK constraint). `rss.py:99` utilise le littéral `"rss"` directement plutôt que de référencer `PLATEFORMES[0]` ou un enum partagé — aucun bug aujourd'hui, mais deux sources de vérité (le tuple `PLATEFORMES` et le littéral) pour la même notion.
- **Points conformes** : fonctions courtes et à responsabilité unique (`canonicaliser_url`, `hacher_contenu`, `_extraire_date_publication`, `_extraire_contenu`), pas de duplication de logique, noms honnêtes vis-à-vis du comportement.

### Fail-Loud Auditor
- **Verdict** : AUDIT_FAIL (High)
- **Findings** : entrées sans date ignorées en `logger.debug` uniquement (`rss.py:78`), invisibles avec la config `INFO` de `run_rss.py:6`. Confirmé en direct : NaturalNews aujourd'hui, 31 entrées sur 31 silencieusement perdues, `articles_ajoutes: 0` sans distinction possible entre "rien de nouveau" et "tout est illisible".
- **Points conformes** : les échecs de flux complet (Reuters, ou tout flux à `bozo`+0 entrées) sont eux correctement journalisés en `warning`, visibles par défaut.

### Test Quality Auditor
- **Verdict** : AUDIT_FAIL (High)
- **Findings** : QUAL-1 — zéro fichier de test dans le projet, aucun framework de test dans `requirements.txt`. Vérification faite manuellement pendant l'implémentation (curl, runs en direct, requêtes SQL) mais aucune de ces vérifications n'est rejouable automatiquement ; rien ne protège contre une régression future.
- **Points conformes** : sans objet, aucun test à évaluer qualitativement.

### Mutation/Saboteur Auditor
- **Verdict** : sans objet, dérive directement de Test Quality Auditor.
- **Findings** : toute mutation de `rss.py` (inverser `flux.bozo or not flux.entries` en `and`, retirer le `continue` de dédup à la ligne 86, retirer `session.commit()`, inverser la contrainte `ck_scores_non_evaluable_coherent`) passerait inaperçue indéfiniment faute de tout test.

### Layer Enforcer
- **Verdict** : AUDIT_PASS
- **Points conformes** : séparation nette `db.py` (connexion) / `models.py` (schéma) / `scraper/sources_rss.py` (config) / `scraper/rss.py` (logique métier) / `scraper/run_rss.py` (point d'entrée). Aucune dépendance dans le mauvais sens observée.

### YAGNI Auditor
- **Verdict** : AUDIT_PASS
- **Points conformes** : pas d'abstraction spéculative, pas d'option de config jamais peuplée, pas d'API publique morte. `hash_contenu` est calculé mais pas encore consommé pour la dédup — ce n'est pas une sur-ingénierie spéculative mais une conséquence directe d'une contrainte `NOT NULL` déjà actée en Phase 0 pour une US-05 déjà planifiée (`plan_implementation.md:46`), pas un ajout gratuit de cette session.

### SRE/Performance Auditor
- **Verdict** : AUDIT_FAIL (High)
- **Findings** : ARCH-1 (absence de timeout réseau, High), N+1 sur la vérification de doublon (`rss.py:82-86`, Medium), risque de connexion non poolée en environnement serverless (ARCH-2, Medium, `[RISQUE]`).
- **Points conformes** : `run_rss.py:10` utilise `with SessionLocal() as session:` — pas de fuite de session/connexion.

### Architecture Consistency Auditor
- **Verdict** : AUDIT_FAIL (Medium)
- **Findings** : ARCH-1, ARCH-2, ARCH-3 (`supabase/config.toml` absent).
- **Points conformes** : le schéma réellement livré (migration + modèles) est structurellement identique à l'interface `evaluer(article)` documentée dans `architecture.md:79-101` (vérifié en Phase 0 par compilation du DDL généré par SQLAlchemy contre le SQL écrit à la main — résultats identiques). La contrainte "GDELT n'est pas une plateforme" décidée dans la doc est correctement reflétée dans le schéma (`plateforme in ('rss','reddit')`).

### Contextual Threat Analyst
- **Verdict** : AUDIT_FAIL (Low, prospectif)
- **Findings** : SEC-3 — scénario d'abus : un contenu RSS malveillant (HTML actif dans `content:encoded`) stocké tel quel aujourd'hui, sans sanitization documentée, deviendrait un XSS stocké classique le jour où la Phase 4 (frontend) l'affiche sans échappement. Le scraper collecte délibérément des sources à faible crédibilité (naturalnews.com, beforeitsnews.com), c'est-à-dire précisément le type de source la plus susceptible d'héberger du contenu adversarial.
- **Points conformes** : aucune URL n'est contrôlable par un utilisateur externe aujourd'hui (toutes les sources sont des constantes développeur dans `sources_rss.py`) — pas de surface SSRF actuelle.

### SAST Scanner
- **Verdict** : AUDIT_FAIL (Low)
- **Findings** : QUAL-3 (f-string dans une contrainte CHECK — non exploitable aujourd'hui, cf. Clean Code Auditor).
- **Points conformes** : toutes les requêtes applicatives passent par l'ORM SQLAlchemy avec liaison de paramètres (`select(Article.id).where(Article.url_canonique == url_canonique)`, `rss.py:83`) — pas d'injection SQL trouvée. XXE testé et écarté (voir Cybersécurité ci-dessus).

### Supply Chain & Artifact Auditor
- **Verdict** : AUDIT_FAIL (Medium)
- **Findings** : SEC-1 (`.gitignore` absent), SEC-2 (dépendances non plafonnées/non verrouillées).
- **Points conformes** : `.env.example` utilise un placeholder (`[YOUR-PASSWORD]`), pas de secret réel commité.

### Privacy/Exfiltration Auditor
- **Verdict** : AUDIT_PASS (limite déjà assumée par le projet)
- **Findings** : aucun nouveau — la rétention indéfinie de contenu (potentiellement des bylines identifiables via `auteur`) est déjà documentée comme limite acceptée en phase prototype (`doc/architecture.md:140`), pas un angle mort silencieux découvert par cet audit.
- **Points conformes** : aucune télémétrie, aucun appel réseau en dehors des flux RSS explicitement configurés.

---

## Points Conformes

- Repli Reuters → Guardian fonctionnel, testé en direct sur les flux réels.
- Déduplication par URL canonique défendue à deux niveaux (application + contrainte DB), contrainte vérifiée par test d'insertion directe rejeté.
- Contraintes `ck_scores_non_evaluable_coherent` et `ck_scores_score_final_range` (issues de l'audit précédent de cette session) vérifiées comme réellement actives en base, pas seulement décrites en commentaire.
- Contrainte `ck_articles_plateforme` vérifiée comme réellement active (insertion `'gdelt'` rejetée).
- Pas d'injection SQL (ORM paramétré partout).
- Pas de résolution d'entité XXE par `feedparser` (testé).
- Pas de secret réel commité.
- Séparation des responsabilités propre entre les modules du scraper.
- Docstrings honnêtes sur le périmètre réellement couvert vs différé.

## Limites De Verification

- Aucune instance Supabase réelle n'existe (compte cloud non créable par l'agent) — tout le code a été testé contre un Postgres local (Homebrew, v14), pas contre Supabase lui-même. Le finding ARCH-2 (pooler de connexion) est donc `[RISQUE]`, pas confirmé en conditions réelles.
- Le comportement "timeout réseau absent" (finding ARCH-1) est confirmé par lecture de code (aucun paramètre de timeout passé à `feedparser.parse`), pas reproduit avec un serveur qui traîne réellement — simuler un hang réseau de façon sûre et non destructive dépasse le périmètre de cet audit.
- La cohérence interne de `doc/architecture.md` et des `userstories_*.md` entre eux (hors delta introduit par le code de cette session) a déjà fait l'objet d'un audit dédié plus tôt dans cette même session (agent `architecture-critic`) — non refait ligne à ligne ici pour éviter la redondance ; seuls les écarts *entre doc et code livré* ont été ré-audités.
- US-02 (Reddit), US-03 (GDELT), US-05 complet (dédup par hash), US-06 (journalisation par run), et les 4 blocs Évaluateur/Contextualiseur/Frontend n'existent pas encore — non audités car rien à auditer.
- Commandes exécutées : `curl` (statut HTTP des flux), `psql` (création base locale, application migration, tests de contraintes par insertion directe), lancement réel du collecteur contre les 8 flux RSS en production (réseau sortant réel, aucune donnée sensible impliquée), test XXE local avec payload inoffensif (lecture simulée de `/etc/hostname`, aucun appel réseau externe). Aucune commande destructive exécutée ; aucune donnée n'a persisté au-delà des lignes déjà présentes dans la base de test locale (les insertions de test de contrainte ont toutes été rejetées par la base).
