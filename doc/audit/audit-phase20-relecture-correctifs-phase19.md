# Audit phase 20 — Relecture des correctifs de la phase 19

Date : 2026-09-13 · Scope : les huit correctifs livrés après l'audit phase 19 —
`_collecter_une` et le commit inconditionnel, `_extraire_auteur` et le helper
`_meta`, la migration `0006_index_date_collecte.sql`, le motif du repli
d'exception, les quantificateurs bornés, la reformulation de l'attente,
`tests/test_collecte_propositions.py` — ainsi que la restauration de
`scraper/rss.py` après l'incident `git checkout`.
Base d'exigences : `doc/audit/audit-phase19-collecte-propositions.md`,
`doc/V3/userstories_crowdsourcing.md` (US-04, US-05 évaluateur).
État audité : arbre de travail non commité.

---

## Résumé De L'Audit

| Division | Statut | Synthèse |
| --- | --- | --- |
| Métier (Anton Ego) | 🟢 OK | Le cycle de vie d'une proposition est désormais complet et persistant. L'auteur extrait retire réellement la pénalité qu'il devait retirer — vérifié bout en bout, 35 → 15. |
| Qualité (Gordon Ramsay) | 🟡 Avertissement | Deux comportements vérifiés par sonde ne le sont par aucun test : l'échec de commit, et l'effet de l'auteur sur le score. Ce que la sonde prouve aujourd'hui, rien ne le gardera demain. |
| Architecture (Steve Jobs) | 🟢 OK | Le défaut a été fermé par suppression du motif, pas par ajout de rustines. L'index manquant est posé. |
| Cybersécurité offensive (Sherlock Holmes) | 🟡 Avertissement | La borne anti-backtracking fait ce qu'on lui demande — et rogne au passage l'extraction qu'elle protège. Un correctif en limite un autre, sans que rien ne le dise. |

**Verdict global : AUDIT_PASS avec réserves.** 0 Critique, 0 High, 0 Medium,
4 Low.

**C'est le premier audit de la série qui ne remonte ni High ni Medium.** Les huit
findings de la phase 19 sont corrigés, et deux d'entre eux l'ont été en
supprimant la possibilité du défaut plutôt qu'en le rattrapant. Les quatre
réserves portent sur des angles morts de la couverture de tests et sur une
interaction entre deux correctifs, pas sur un comportement fautif.

---

## Index Des Sous-Audits

| Sous-audit | Scope | Crit | High | Medium | Low | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Business Logic Auditor | cycle de vie d'une proposition | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Requirements Compliance Auditor | US-04 après correctifs | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Doc-Sync Auditor | README, plan V3, rapport phase 19 | 0 | 0 | 0 | 0 | AUDIT_PASS |
| A11y/UX Checker | statut affiché au proposant | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Clean Code Auditor | `_collecter_une`, `_meta` | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Fail-Loud Auditor | échec de commit, repli d'exception | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Test Quality Auditor | 20 tests du collecteur | 0 | 0 | 0 | 2 | AUDIT_PASS (réserves) |
| Mutation/Saboteur Auditor | les 3 correctifs testables | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Layer Enforcer | `rss.py` restauré | 0 | 0 | 0 | 0 | AUDIT_PASS |
| YAGNI Auditor | `_meta`, `_collecter_une` | 0 | 0 | 0 | 0 | AUDIT_PASS |
| SRE/Performance Auditor | migration `0006` | 0 | 0 | 0 | 1 | AUDIT_PASS (réserves) |
| Architecture Consistency Auditor | plan V3 vs code | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Contextual Threat Analyst | pages adverses | 0 | 0 | 0 | 0 | AUDIT_PASS |
| SAST Scanner | motifs d'extraction bornés | 0 | 0 | 0 | 1 | AUDIT_PASS (réserves) |
| Supply Chain & Artifact Auditor | aucune dépendance ajoutée | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Privacy/Exfiltration Auditor | inchangé | 0 | 0 | 0 | 0 | AUDIT_PASS |

Décompte dédupliqué : **4 findings**, tous Low.

---

## Matrice De Couverture

| Ce que la phase 19 devait obtenir | Preuve | Statut |
| --- | --- | --- |
| F19-01 — un échec est réellement écrit en base | sonde, relecture en session neuve : **`echec_collecte`** | ✅ |
| F19-01 — aucune issue ne saute le commit | 3 formes d'issue testées, mutation tuée | ✅ |
| **Un commit qui ÉCHOUE laisse un état cohérent** | sonde : statut `echec_collecte`, motif posé, **aucun article orphelin** | ✅ (non testé, F20-02) |
| F19-02 — l'auteur déclaré est repris | 5 formes réelles sur 7 extraites | ✅ |
| **F19-02 — la pénalité d'US-05 disparaît réellement** | sonde : style **35 → 15** sur la même page signée | ✅ (non testé, F20-03) |
| F19-02 — une page non signée reste sans auteur | contre-épreuve présente | ✅ |
| F19-03 — index sur `date_collecte` | `pg_indexes` : `idx_articles_date_collecte` | ✅ |
| F19-06 — le repli d'exception pose un motif | sonde : « erreur inattendue (RuntimeError) » | ✅ |
| F19-07 — la borne de lecture est exercée | test sur la vraie `_telecharger` : `read(1000)` → 1000 | ✅ |
| F19-08 — quantificateurs bornés | `[^>]{0,300}` dans tous les motifs | ✅ |
| **La borne ne dégrade pas l'extraction** | balise à attributs longs : **auteur ET date perdus** | ❌ **F20-01** |
| `rss.py` restauré après l'incident `git checkout` | suite verte, test phase 11 compris | ✅ |

---

## Top Findings

- **[Low] F20-01 · `src/fakenews/scraper/propositions.py`, `_ATTRS`** — la borne
  `[^>]{0,300}`, posée pour fermer le backtracking de F19-08, fait **échouer
  silencieusement** l'extraction quand la balise `<meta>` porte plus de 300
  caractères d'attributs AVANT celui qu'on cherche. **Mesuré** sur une balise
  précédée d'un `data-*` de 320 caractères : auteur → `None`, date → `None`, sans
  la moindre trace.
  Les deux correctifs de la phase 19 se limitent donc l'un l'autre : F19-08
  protège, F19-02 perd en couverture, et rien ne dit que l'un paie l'autre.
  L'impact réel dépend de la forme des pages collectées — **[RISQUE]**, la forme
  testée est contrivée, mais des balises `<meta>` chargées d'attributs `data-*`
  existent dans la nature.
  **Correction attendue :** restreindre la recherche au `<head>` (borné, connu)
  et relever la limite en conséquence ; ou extraire les attributs d'une balise
  plutôt que de les balayer d'un bloc. À défaut, l'écrire : une borne qui coupe
  de l'information doit le dire.
- **[Low] F20-02 · `tests/test_collecte_propositions.py`** — le comportement en
  cas d'**échec du commit** n'est couvert par aucun test. Il est pourtant correct,
  et c'est le chemin le plus délicat du module : la sonde montre un statut
  `echec_collecte`, un motif posé, et **aucun article orphelin**. Ce qu'une sonde
  prouve un jour, rien ne le garde le lendemain.
  **Correction attendue :** un test qui fait échouer le premier `commit` et
  vérifie les trois propriétés — statut, motif, absence d'article.
- **[Low] F20-03 · `tests/test_collecte_propositions.py`** — l'extraction
  d'auteur est testée ; son **effet** ne l'est pas. Or la raison d'être de F19-02
  n'était pas d'extraire une chaîne, c'était de cesser de pénaliser
  systématiquement les articles proposés. Vérifié par sonde : la même page passe
  de **35 à 15** en score stylistique selon qu'elle est signée ou non.
  **Correction attendue :** un test qui relie `_extraire_auteur` à
  `evaluer_style` — la valeur du correctif, pas son mécanisme.

---

## Thèmes Transverses

1. **Deux correctifs peuvent se marcher dessus.** F19-08 (borner le
   backtracking) et F19-02 (extraire l'auteur) ont été posés dans le même geste,
   et le premier rogne le second. Ce n'est pas une faute — c'est le genre
   d'interaction qu'un correctif groupé produit, et qu'il faut aller chercher.
2. **La sonde n'est pas un test.** Trois comportements ont été vérifiés à la main
   pendant cette relecture ; deux ne sont gardés par rien. La série d'audits a
   montré plusieurs fois ce que devient une propriété que personne ne garde.
3. **Le défaut fermé par suppression ne revient pas.** F19-01 a été traité en
   supprimant les sorties anticipées, pas en ajoutant des `commit()`. La mutation
   correspondante meurt sur les trois formes d'issue, et il n'existe plus de
   chemin à oublier. Même leçon que `_secrets_egaux` et
   `_mot_de_passe_partage()` : la règle, pas la ligne.

---

## Détails Par Division

### Division Métier (Anton Ego)

Le cycle de vie d'une proposition est enfin complet : acceptée, collectée ou
refusée, et dans tous les cas **inscrite**. J'ajoute, ce qui est rare, une
satisfaction : l'auteur extrait ne sert pas à décorer une colonne — il retire
vraiment les vingt points que la maison infligeait à tout article proposé.

- **Points conformes :** les trois issues (`collectee`, `echec_collecte`,
  rattachement à un article existant) sont persistées ; un commit qui échoue
  laisse un état cohérent, motif compris, et ne dépose aucun article orphelin ;
  l'interface ne promet plus d'échéance que la file ne garantit pas.

### Division Qualité (Gordon Ramsay)

Vingt tests, et les deux propriétés les plus intéressantes ne sont vérifiées que
par un script que personne ne relancera. Vous avez prouvé que ça marche
aujourd'hui. Personne ne saura le jour où ça cessera.

- **[Low] F20-02**, **[Low] F20-03** — cf. Top Findings.
- **Points conformes :** le test paramétré couvre les trois formes d'issue et
  compte les commits — la propriété qui manquait, pas sa conséquence ; sa
  docstring dit explicitement ce que la fixture partagée **ne peut pas** prouver,
  au lieu de laisser croire l'inverse ; la contre-épreuve « page non signée reste
  sans auteur » empêche de retourner une valeur bidon ; le plafond de lecture est
  désormais exercé sur la vraie fonction.

### Division Architecture (Steve Jobs)

Correct. Le défaut a été retiré, pas contourné. L'index manquant est posé, avec la
raison écrite dans la migration.

- **[Low] F20-04** `supabase/migrations/0006_index_date_collecte.sql` — `create
  index` sans `concurrently` prend un verrou qui bloque les écritures sur
  `articles` le temps de la construction. Négligeable au volume actuel ;
  `psql -f` s'exécutant en autocommit, `concurrently` serait possible si la table
  grossit. **Type : [RISQUE]**, durée non mesurée.
- **Points conformes :** `_collecter_une` rend la classe de défaut inatteignable
  plutôt que de la rattraper ; `_meta(noms)` a deux appelants et supprime huit
  lignes dupliquées ; aucune dépendance ajoutée ; `rss.py` restauré à l'identique,
  correctif de la phase 11 compris — vérifié par son test dédié.

### Division Cybersécurité Offensive (Sherlock Holmes)

Élémentaire, et pourtant : la borne que vous avez posée contre une page adverse
vous prive d'information sur une page ordinaire. La défense fonctionne ; elle
coûte quelque chose, et ce quelque chose n'est écrit nulle part.

- **[Low] F20-01** — cf. Top Findings. **Type : Confirmé (mesuré)** pour le
  mécanisme ; **[RISQUE]** pour la fréquence en conditions réelles.
- **Point de vigilance, non retenu comme finding :** `_extraire_auteur` balaie
  tout le document, pas seulement le `<head>`. Une balise `<meta name="author">`
  placée dans le corps — par un widget embarqué, par exemple — l'emporterait sur
  l'absence de déclaration en tête. Sans conséquence de sécurité : l'auteur ne
  sert qu'à un signal stylistique, et un auteur faux ou absent y produit le même
  effet qu'aujourd'hui.
- **Points conformes :** les quatre motifs d'extraction sont bornés ; la lecture
  est plafonnée à 2 Mo, vérifié sur la vraie fonction ; le schéma est revalidé au
  point de connexion ; la collecte reste hors de Vercel.

---

## Détails Par Sous-Audit

### Business Logic Auditor
- **Verdict :** AUDIT_PASS. Les quatre issues d'une proposition sont persistées,
  y compris sur échec de commit.

### Requirements Compliance Auditor
- **Verdict :** AUDIT_PASS. Le 4ᵉ critère d'US-04 — « échec ⇒ `echec_collecte`
  avec un motif, sans interrompre » — est désormais tenu **en base**, pas
  seulement dans le bilan.

### Doc-Sync Auditor
- **Verdict :** AUDIT_PASS. README (migration `0006` incluse), plan V3, état
  d'avancement et rapport phase 19 décrivent ce qui est livré. L'incident
  `git checkout` est consigné dans le suivi de la phase 19 plutôt que passé sous
  silence.

### A11y/UX Checker
- **Verdict :** AUDIT_PASS. Le statut affiché au proposant ne promet plus
  d'échéance ; les motifs d'échec lui sont visibles.

### Clean Code Auditor
- **Verdict :** AUDIT_PASS. Deux fonctions courtes à la place d'une longue ; le
  helper `_meta` est justifié par deux appelants.

### Fail-Loud Auditor
- **Verdict :** AUDIT_PASS. Le repli d'exception pose un motif nommant le type
  d'erreur, comme toutes les autres branches.

### Test Quality Auditor
- **Verdict :** AUDIT_PASS avec réserves. **Findings :** F20-02, F20-03.

### Mutation/Saboteur Auditor
- **Verdict :** AUDIT_PASS. Trois mutations tuées : commit rendu conditionnel
  (3 cas sur 3), auteur remis à `None`, lecture rendue non bornée.
  **Mutation qui survivrait :** relever `_ATTRS` à `[^>]*` — aucun test ne
  tomberait, puisque aucun ne couvre le backtracking (F19-08 n'a jamais eu de
  test, seulement une borne).

### Layer Enforcer / YAGNI / Architecture Consistency
- **Verdict :** AUDIT_PASS. `rss.py` restauré dans son état attendu ; aucun
  franchissement de frontière ; le plan décrit exactement le code.

### SRE/Performance Auditor
- **Verdict :** AUDIT_PASS avec réserves. **Findings :** F20-04.

### Contextual Threat Analyst
- **Verdict :** AUDIT_PASS. Aucun scénario d'abus nouveau : la surface n'a pas
  bougé, et les bornes posées la réduisent.

### SAST Scanner
- **Verdict :** AUDIT_PASS avec réserves. **Findings :** F20-01 (effet de bord
  d'une mesure défensive).

### Supply Chain & Artifact Auditor / Privacy
- **Verdict :** AUDIT_PASS. Aucune dépendance, aucune donnée nouvelle.

---

## Points Conformes (Synthèse)

- **Les huit findings de la phase 19 sont corrigés**, et deux l'ont été en
  supprimant la possibilité du défaut : plus de sortie anticipée qui saute un
  commit, plus d'auteur câblé à `None`.
- Le chemin le plus délicat — **un commit qui échoue** — laisse un état cohérent :
  statut, motif, et aucun article orphelin.
- Le correctif F19-02 produit l'effet qu'on attendait de lui, mesuré de bout en
  bout : 35 → 15 en score stylistique sur la même page selon qu'elle est signée.
- `rss.py` a été restauré à l'identique après l'incident `git checkout`, correctif
  de l'audit phase 11 compris, et la suite le confirme.
- **402 tests, 0 skip** contre un vrai Postgres avec les six migrations.

---

## Limites De Vérification

- **F20-01 :** la forme testée (320 caractères d'attributs avant la cible) est
  construite pour le test ; sa fréquence sur des pages réelles n'est pas mesurée.
- **F20-04 :** durée du verrou de `create index` non mesurée ; la table de test
  est vide.
- **Aucun téléchargement réel** : redirections, certificats invalides et serveurs
  lents restent hors couverture, pour le collecteur comme pour les flux RSS.
- **F19-08 n'a toujours pas de test** — une borne, pas une preuve. L'audit
  phase 19 ne l'exigeait pas, et le coût d'un test de backtracking dépasse
  probablement le risque.
- Aucun code de production modifié pendant cet audit.

### Commandes Exécutées

| Commande | Résultat |
| --- | --- |
| `TEST_DATABASE_URL=… pytest -q` | **402 passed, 0 skipped** |
| Sonde auteur, 7 formes de balise `<meta>` | 5 extraites, 1 absente (attendu), **1 perdue sur borne** |
| Sonde commit en échec, relecture en session neuve | `echec_collecte`, motif posé, **0 article orphelin** |
| Sonde effet sur `evaluer_style` | signée **15**, non signée **35** |
| Sonde date sur balise à attributs longs | **None** — même limite que l'auteur |
| `select indexname from pg_indexes …` | `idx_articles_date_collecte` présent |
