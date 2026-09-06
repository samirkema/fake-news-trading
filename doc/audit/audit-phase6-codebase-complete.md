# Audit complet de la codebase — et correctifs appliqués

Audit en lecture seule de l'état de `main` au commit `a620c27`, suivi de la
correction des 33 findings. Méthode : 4 divisions, 16 sous-audits spécialisés,
preuves `fichier:ligne`, séparation stricte entre défaut confirmé et risque.

**Verdict initial** : Critique 1 · High 6 · Medium 12 · Low 14.
**Après correctifs** : 33/33 traités. Suite de tests 171 passés, 0 skip, contre
un vrai Postgres avec les trois migrations appliquées.

---

## Ce qui a changé, par finding

### Critique

**C1 — Faux vert : 43 % de la suite ne s'exécutait jamais.**
`pytest` affichait `73 passed, 55 skipped` faute de `TEST_DATABASE_URL`, et aucun
des quatre workflows ne lançait la suite. Les 55 skips couvraient *l'intégralité*
de l'authentification (`test_comptes.py` 9/9), du frontend (`test_frontend.py`
25/25), de la persistance et des orchestrateurs.
→ `.github/workflows/ci.yml` : service Postgres 16, migrations appliquées, suite
lancée sur chaque push et chaque PR, et **échec du job si un seul test est
skippé** (budget `SKIPS_MAX=0`, vérifié en parsant le rapport JUnit). Garde-fou
testé dans les deux sens : 0 skip avec base → passe ; 72 skips sans base → bloque.

### High

**H1 — La vérification en source primaire pénalisait tout le monde.**
Le code passait le **titre de presse entier** en `q` à SEC EDGAR. EDGAR conjugue
les termes de `q` : un titre de journaliste n'apparaît jamais verbatim dans un
8-K. Mesuré contre l'API réelle : `q=<vrai titre Tesla>` → 0 hit ; `q=Tesla` sur
la même fenêtre → 2 hits. Toute absence de résultat était lue comme « absence de
confirmation » et facturée `VALEUR_NON_CONFIRME = 85.0` au poids le plus lourd
(1.5). De plus, US-04 conditionne cette pénalité à « une claim présentée comme un
fait précis et vérifiable (annonce, chiffre, décision) » — condition non
implémentée : un commentaire d'humeur citant Apple récoltait 85/100.

Le signal a été restructuré autour d'une **requête de contrôle**, parce que le
seul choix de meilleurs mots-clés ne suffisait pas — mesuré : même avec 4 termes
issus du titre, 0 hit sur un dépôt qui existe.

| Situation | Avant | Après |
| --- | --- | --- |
| Pas de claim factuelle | 85.0 | `None` — non applicable, aucun appel réseau |
| Aucun terme exploitable | 85.0 | `None` — non applicable, aucun appel réseau |
| Dépôt trouvé | 5.0 | 5.0 (inchangé) |
| L'entreprise a déposé, mais nos termes ne matchent pas | **85.0** | `None` — non concluant |
| L'entreprise n'a **rien** déposé dans la fenêtre | 85.0 | 85.0 — la seule pénalité fondée |

Vérifié contre l'API réelle sur trois cas : dépôt existant → 5.0 ; claim inventée
→ non concluant ; simple mention → non applicable. Les verbes d'annonce
(`announces`, `annonce`…) sont exclus de la recherche : excellents marqueurs de
claim, très mauvais termes de recherche (`q="announces fourth quarter"` → 0 hit
sur un 8-K existant, `q="production deliveries"` → 1 hit).

**H2 — La clé API Google recopiée en base puis affichée dans le frontend.**
`httpx` met l'URL complète — `?key=…` compris — dans le message de
`HTTPStatusError`. Ce message était interpolé dans `raison`, persisté dans
`scores.sous_scores`, puis rendu par `templates/detail.html` à tout visiteur
connecté. Prouvé par exécution pendant l'audit.
→ `raison` ne porte plus que `type(exc).__name__` (les trois intégrations :
fact-checking, LLM, SEC). Le détail reste dans le log, où GitHub masque les
secrets. Test dédié qui vérifie l'absence de la clé et de l'hôte.

**H3 — Le seul compte « vraie frontière » livré sans frontière.**
`0002_comptes.sql` semait `samirkema` en `superadmin` avec `secret_hash` NULL, et
le concédait en commentaire, pendant que `comptes-3-roles.md` affirmait comme
acquis que « le mot de passe partagé ne lui donne pas accès ». Dans l'état livré,
quiconque connaissait le mot de passe partagé obtenait le rôle superadmin.
→ Contrainte `ck_comptes_superadmin_a_un_code` : un `superadmin` **ne peut pas**
avoir `secret_hash` NULL. La migration sème un code aléatoire inconnu de tous —
le compte est inaccessible tant que le vrai code n'est pas posé, ce qui est le bon
défaut. Rattrapage inclus pour les bases déjà déployées avec un NULL. Idempotence
et rejeu vérifiés.

**H4 — L'authentification échouait ouverte.**
`FRONTEND_PASSWORD` absente ⇒ `superadmin` sans cookie ni contrôle. Une variable
d'environnement Vercel supprimée ou mal orthographiée rendait public un site qui
publie des verdicts automatisés nommant des sources — exactement ce que
`userstories_frontend.md` US-04 désigne comme « condition bloquante… qui ne peut
être levée que par une décision explicite du porteur du projet, pas par défaut ».
→ Le mode local demande désormais `FAKENEWS_MODE=local` **explicite**. Hors de ce
mode, une `FRONTEND_PASSWORD` absente refuse tout accès et journalise une erreur.

**H5 — Injection de prompt non traitée.**
Le contenu d'articles Reddit/RSS — contrôlé par un tiers, éventuellement par
l'auteur même de la désinformation notée — était concaténé sans délimitation dans
les prompts de scoring et de génération.
→ `llm.encadrer_contenu_non_fiable()` confine le contenu dans
`<contenu_non_fiable>`, en neutralisant les balises fermantes qu'il contiendrait ;
`CONSIGNE_CONTENU_NON_FIABLE` est ajoutée aux deux `system`.
*(Le contextualiseur disposait déjà de la meilleure défense du dépôt :
`validation.py` revérifie chaque `preuve_id` contre les signaux réellement
calculés, donc le modèle ne peut pas fabriquer de faits tracés. Conservé tel
quel.)*

**H6 — Correspondance de ticker par sous-chaîne.**
`if nom_connu in nom_normalise` promouvait *Oxford Analytica* et *Fordham
University* en Ford, *Intelsat* en Intel, *Amcor plc* en AMC, *Metaverse Studios*
en Meta — chacun héritant ensuite de la pénalité H1.
→ Correspondance sur **séquences de jetons entières**, en deux passages : le nom
tel quel (pour que « General Motors » reste entier), puis débarrassé de son
habillage social (pour que « Ford Motor Company » donne « ford »). Les six faux
positifs sont verrouillés par un test paramétré.

### Medium

| # | Finding | Correctif |
| --- | --- | --- |
| M1 | Pagination non déterministe : `ORDER BY score_final DESC` sans départage, sur des `numeric(5,2)` où les ex æquo sont la règle | `order_by(..., Article.id)`. Test qui vérifie que l'union des pages = 55 articles distincts (l'ancien se contentait de compter 50 puis 5, et survivait à la mutation) |
| M2 | `date_max` comparé à un `timestamptz` : la journée indiquée était perdue | Bornes converties en minuit UTC explicite, borne haute `< jour+1`. Deux tests de bornes avec données |
| M3 | `non_evaluable` mathématiquement inatteignable (`style` renvoyait toujours une valeur) : contrainte SQL, filtre frontend et garde du contextualiseur étaient du code mort | `style` s'exclut quand il n'y a rien à analyser, et ne reproche plus l'absence de citation à un corps de moins de 200 caractères (un post Reddit de type lien) |
| M4 | `detail` du calcul produit puis jeté, alors qu'US-08 l'exige | Colonne `scores.detail_calcul` (migration 0003), persistée par l'évaluateur et les deux backfills |
| M5 | Cookie = HMAC déterministe du seul pseudo : valide indéfiniment une fois capté, révocable seulement en déconnectant tout le monde | Expiration **dans la charge signée** (`pseudo:expiration:signature`), 30 jours. Tests : cookie expiré refusé, expiration rallongée refusée |
| M6 | Aucune friction sur `POST /login` avec un secret unique partagé | Fenêtre glissante, 10 tentatives / 5 min / client, 429. Limite documentée : compteur par instance sur Vercel |
| M7 | `requirements.txt` monolithique déployé sur Vercel (spacy, praw, feedparser, anthropic, **pytest**…) | `api/requirements.txt` réduit à FastAPI + Jinja2 + SQLAlchemy + psycopg2 |
| M8 | README auto-contradictoire, 7 liens morts, cron annoncé mais commenté | Liens corrigés (libellés compris), contradictions levées, pause du `schedule` signalée dans le README **et** dans `plan_implementation.md` |
| M9 | Évaluateur non borné : tout le backlog chargé, 2-3 appels réseau synchrones par article, aucun throttle SEC | Plafond de 300 articles par run (les plus récents d'abord, reliquat reporté), throttle SEC à 10 req/s |
| M10 | Backfills : table `scores` entière en mémoire, et `poids` écrasé — effaçant la trace des poids réellement appliqués | Itération par lots de 200, fusion au lieu d'écrasement, scores orphelins ignorés proprement |
| M11 | `_telecharger` n'attrapait que trois exceptions : une `HTTPException`, une URL malformée ou un IDN cassé tuait tout le run RSS | `except Exception`, conformément à « toute intégration externe dégrade » |
| M12 | `creer_client()` hors `try` dans un backfill, alors que `run_evaluateur` protège le même appel | Protégé, comportement aligné |

### Low

`L1` commentaire `upvotes` → `score` (le champ réellement écrit) · `L2` bilan RSS
clé sur la source configurée, avec `source_utilisee` en plus — « Reuters » ne
disparaît plus quand son repli prend le relais · `L3` `ignores_sans_date` →
`ignores_incomplets` · `L4` `.get` au lieu de l'indexation directe du barème ·
`L5` `corroboration`/`decalage_viral` conservés au barème (US-08 les fixe), mais
désormais commentés comme tels · `L6` récupération de l'article **dans** le `try`
du contextualiseur · `L7` docstring de `declenchement` corrigée (le pool est le
backlog complet, et le report a bien lieu) · `L8` déplacement `doc/V2` → `doc/V1`
commité comme un renommage · `L9` `!.env.example` dans `.gitignore` · `L10`
modèle spaCy épinglé en 3.8.0 (CI, pipeline, README) · `L11` accès direct à un
article `non_evaluable` conservé — conforme à la lettre d'US-08, la page de détail
est le bon endroit pour expliquer pourquoi · `L12` `delete_cookie` avec les
attributs de la pose · `L13` télémétrie sortante (titres → Google, SEC)
documentée dans `.env.example` · `L14` `pyproject.toml` : un seul mécanisme de
résolution de `src/` au lieu de trois.

### A11y

Chaque page a maintenant son propre `<title>` — toutes partageaient le même, ce
qui rendait onglets et historique indistinguables.

---

## Tests ajoutés

`tests/test_correctifs_audit.py` (19 tests) verrouille chaque finding de sécurité
et de traçabilité. Les tests existants que l'audit avait identifiés comme
incapables de tuer une mutation ont été renforcés :

- le mock SEC ignorait entièrement `request` — remplacer l'URL, retirer
  `forms=8-K` ou supprimer `entityName` laissait la suite verte. Il capture
  désormais la requête, et un test affirme le formulaire, l'entité, la fenêtre de
  dates et la nature des termes de `q` ;
- le test de pagination comptait des lignes sans jamais vérifier que les deux
  pages forment un ensemble sans doublon ni omission ;
- aucun test ne filtrait sur `date_max` avec des données.

Total : **171 tests, 0 skip, 0 échec** contre un Postgres avec les migrations
0001 à 0003.

---

## Limites de vérification

- **Non vérifiable depuis le dépôt** : si l'instance Supabase de production
  contient déjà `samirkema` avec `secret_hash` NULL, la migration 0002 doit être
  rejouée pour appliquer le rattrapage et la contrainte. À faire avant le prochain
  déploiement.
- **`FRONTEND_PASSWORD` sur Vercel** : le passage en fail-closed rend cette
  variable obligatoire. Si elle n'y est pas définie aujourd'hui, le site
  deviendra inaccessible au lieu d'être ouvert — c'est l'effet recherché, mais il
  faut la poser.
- **`api/requirements.txt`** : le comportement de `@vercel/python` (fichier
  adjacent au point d'entrée prioritaire sur celui de la racine) n'a pas pu être
  vérifié sans déployer.
- Ni clé Google Fact Check ni clé Anthropic disponibles : les chemins nominaux de
  ces deux intégrations restent couverts par des doubles, pas par un appel réel.
  SEC EDGAR, en revanche, a été interrogé pour de vrai (API publique, lecture
  seule) — c'est ce qui a permis d'établir puis de vérifier H1.
- Le plafond anti-bruteforce est en mémoire de process : sur Vercel, le plafond
  effectif est multiplié par le nombre d'instances tièdes. Ralentisseur, pas
  barrière.
