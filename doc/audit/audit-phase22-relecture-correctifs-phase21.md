# Audit phase 22 — Relecture des correctifs de la phase 21

Date : 2026-09-13 · Scope : les six correctifs livrés après l'audit phase 21 —
retrait de la copie parasite dans `templates/detail.html`, ancre sur
`_avec_erreur`, lecture paresseuse dans `_message`, décisions explicitées sur le
quota et l'article non évalué, cinq tests neufs dont deux de structure.
Base d'exigences : `doc/audit/audit-phase21-commentaires.md`,
`doc/V3/userstories_crowdsourcing.md` (US-08).
État audité : arbre de travail non commité.

---

## Résumé De L'Audit

| Division | Statut | Synthèse |
| --- | --- | --- |
| Métier (Anton Ego) | 🟢 OK | La section est à sa place, une seule fois, sous l'analyse. Les deux décisions laissées en suspens sont tranchées et écrites. |
| Qualité (Gordon Ramsay) | 🟡 Avertissement | On peut retirer le filtre par article et faire apparaître **tous** les commentaires du site sur **chaque** page : 427 tests ne bronchent pas. |
| Architecture (Steve Jobs) | 🟢 OK | L'ancre est passée par le helper commun plutôt que recopiée dans trois routes. La lecture d'environnement quitte le chemin nominal. |
| Cybersécurité offensive (Sherlock Holmes) | 🟢 OK | Rien de neuf : la surface n'a pas bougé, et les gardes tiennent. |

**Verdict global : AUDIT_PASS avec réserves.** 0 Critique, 0 High, 1 Medium,
2 Low.

Les six findings de la phase 21 sont corrigés, y compris le plus gênant — la page
n'a plus qu'une seule section de commentaires, et elle est dans le corps du
document. La réserve porte sur ce que la suite ne regarde toujours pas.

---

## Index Des Sous-Audits

| Sous-audit | Scope | Crit | High | Medium | Low | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Business Logic Auditor | cycle de vie d'un commentaire | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Requirements Compliance Auditor | US-08 après correctifs | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Doc-Sync Auditor | rapport phase 21, plan V3 | 0 | 0 | 0 | 0 | AUDIT_PASS |
| A11y/UX Checker | `detail.html` rendu | 0 | 0 | 0 | 1 | AUDIT_PASS (réserves) |
| Clean Code Auditor | `_avec_erreur`, `_message` | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Fail-Loud Auditor | chemins de refus | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Test Quality Auditor | 25 tests du module | 0 | 0 | 1 | 1 | AUDIT_FAIL |
| Mutation/Saboteur Auditor | filtre par article, ancre, gabarit | 0 | 0 | 1 | 0 | AUDIT_FAIL |
| Layer Enforcer | inchangé | 0 | 0 | 0 | 0 | AUDIT_PASS |
| YAGNI Auditor | paramètre `ancre` | 0 | 0 | 0 | 0 | AUDIT_PASS |
| SRE/Performance Auditor | `_message`, requêtes | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Architecture Consistency Auditor | plan V3 vs code | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Contextual Threat Analyst | surface inchangée | 0 | 0 | 0 | 0 | AUDIT_PASS |
| SAST Scanner | inchangé | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Supply Chain & Artifact Auditor | inchangé | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Privacy/Exfiltration Auditor | isolation entre articles | 0 | 0 | 1 | 0 | AUDIT_FAIL |

Décompte dédupliqué : **3 findings**.

---

## Matrice De Couverture

| Ce que la phase 21 devait obtenir | Preuve | Statut |
| --- | --- | --- |
| F21-01 — une seule section, dans le corps | `<title>` sans balise, `id="texte"` unique, test de structure | ✅ |
| F21-01 — commentaires SOUS l'analyse | assertion de position, mutation tuée | ✅ |
| F21-02 — un refus ramène à la section | `Location` finit par `#commentaires`, mutation tuée | ✅ |
| F21-03 — article non évalué commentable, décidé | commentaire + code + test | ✅ |
| F21-04 — un retiré occupe le quota, décidé | commentaire + code + test | ✅ |
| F21-06 — pas de lecture d'environnement inutile | deux `if` avant la table | ✅ |
| **Les commentaires d'un article restent sur cet article** | filtre présent… **mutation survit à 427 tests** | ❌ **F22-01** |
| Ordre d'affichage stable | `order_by(date_creation)` **sans clé de départage** | ❌ F22-02 |

---

## Top Findings

- **[Medium] F22-01 · `src/fakenews/frontend/app.py`, `detail_article`** — le
  filtre `Commentaire.article_id == article_id` n'est couvert par **aucun test**.
  **Mesuré :** en le retirant, les **427 tests passent toujours**. Le code est
  juste ; la suite ne le sait pas.
  **Impact d'une régression :** tous les commentaires du site s'afficheraient sur
  toutes les pages d'article. Ce n'est pas une fuite de confidentialité — un
  commentaire est déjà visible de tout compte connecté — mais c'est une
  confusion totale entre les fils, et le genre de défaut qu'un relecteur ne voit
  pas sur une base de test à un seul article.
  La cause est la même qu'en phase 21 : les tests vérifient qu'un texte **est**
  dans la page, jamais qu'un autre **n'y est pas**.
  **Correction attendue :** un test à deux articles, qui vérifie que le
  commentaire de l'un n'apparaît pas sur l'autre. Trois lignes.
- **[Low] F22-02 · `src/fakenews/frontend/app.py`, `detail_article`** —
  `order_by(Commentaire.date_creation)` sans clé de départage. Deux commentaires
  créés dans la même seconde peuvent changer d'ordre d'un affichage à l'autre.
  Le projet connaît ce défaut : c'est le finding M1 de l'audit d'origine, corrigé
  sur la pagination des articles par un `order_by(score, Article.id)`.
  **Correction attendue :** `order_by(Commentaire.date_creation, Commentaire.id)`.
- **[Low] F22-03 · `src/fakenews/frontend/templates/detail.html`** — un
  commentaire multiligne est **aplati** à l'affichage. Le texte est stocké avec
  ses sauts de ligne (vérifié : `Premier paragraphe.\n\nSecond paragraphe…` est
  bien dans le HTML), mais rendu dans un `<p>` sans `white-space`, donc les
  navigateurs les réduisent à une espace. Un commentaire structuré en paragraphes
  arrive en un seul bloc.
  **Correction attendue :** `white-space: pre-line` sur le texte du commentaire —
  une ligne de CSS, sans toucher à l'échappement.

---

## Rectification — une de mes sondes était fausse

La sonde de rendu multiligne concluait « sauts de ligne préservés : True » en
cherchant `white-space` **dans toute la page**. Or `base.html` contient déjà
`white-space: nowrap` dans la règle `.visuellement-cache`, sans rapport. La sonde
répondait donc oui à une question qu'elle ne posait pas.

Le constat correct est l'inverse — les sauts de ligne ne sont pas préservés — et
c'est la lecture du HTML rendu, pas la sonde, qui l'établit. Une recherche de
sous-chaîne sur une page entière est exactement le procédé que cet audit reproche
aux tests de la phase 21 ; il n'était pas meilleur ici.

---

## Thèmes Transverses

1. **Vérifier ce qui est là ne dit rien de ce qui ne devrait pas y être.** F22-01
   et le défaut de la phase 21 ont la même racine : aucune assertion négative,
   aucune assertion d'unicité, aucune assertion de position — jusqu'aux deux
   tests ajoutés hier, qui sont les premiers du genre dans ce module.
2. **Les correctifs de la phase 21 tiennent tous.** Les trois mutations rejouées
   (section remise dans le titre, ancre retirée, filtre des retirés supprimé)
   tombent. Le seul trou est celui qu'aucun test n'a jamais couvert.
3. **Un défaut déjà corrigé ailleurs revient ailleurs.** F22-02 est le tri sans
   départage que la pagination des articles avait déjà subi. Corriger un motif à
   un endroit ne le corrige pas dans le suivant.

---

## Détails Par Division

### Division Métier (Anton Ego)

La salle est enfin dans la salle. Une seule fois, à sa place, sous l'analyse —
et les deux hésitations que je signalais sont devenues des décisions, écrites
dans le code et gardées par un test. C'est ainsi qu'on répond à une critique.

- **Points conformes :** une seule section et un seul formulaire ; l'ordre
  analyse → mise en contexte → commentaires est vérifié par assertion de
  position ; un refus ramène à l'endroit où le message s'affiche ; le quota et
  l'article non évalué sont tranchés explicitement.

### Division Qualité (Gordon Ramsay)

Vous avez ajouté deux assertions de structure, très bien. Maintenant supprimez le
filtre par article et regardez vos quatre cent vingt-sept tests vous applaudir
pendant que chaque page affiche les commentaires de toutes les autres.

- **[Medium] F22-01** — cf. Top Findings. **Type : Confirmé (mesuré).**
- **[Low] F22-04** — aucun test ne couvre l'ORDRE d'affichage des commentaires,
  ce qui rend F22-02 invisible à la suite en plus d'être invisible à l'œil.
- **Points conformes :** les deux tests de structure ajoutés hier sont les
  premiers du dépôt à vérifier une POSITION plutôt qu'une présence, et ils tuent
  la mutation qui avait produit le défaut ; le test de refus est paramétré sur une
  clé lisible plutôt que sur sa charge utile.

### Division Architecture (Steve Jobs)

L'ancre passe par le helper commun, pas par trois recopies. La lecture
d'environnement quitte le chemin nominal. Rien à retirer.

- **Points conformes :** `_avec_erreur(chemin, code, ancre="")` garde un seul
  point de construction d'URL d'erreur ; `_message` ne lit la configuration que
  pour les deux messages qui en dépendent ; aucune abstraction ajoutée.

### Division Cybersécurité Offensive (Sherlock Holmes)

Élémentaire, et pourtant : rien. La surface n'a pas bougé, les gardes tiennent, et
le seul défaut de la journée est une omission de test, pas une ouverture.

- **Observation :** F22-01 n'est pas une faille — un commentaire est déjà visible
  de tout compte connecté, et le filtre des retirés reste indépendant. La
  confusion entre fils serait un défaut d'usage, pas d'autorisation.
- **Points conformes :** CSRF, `exige_role`, échappement, masquage des retirés :
  inchangés et toujours vérifiés par leurs mutations.

---

## Détails Par Sous-Audit

### Business Logic Auditor
- **Verdict :** AUDIT_PASS. Les deux décisions ouvertes sont fermées et testées.

### Requirements Compliance Auditor
- **Verdict :** AUDIT_PASS. Les douze critères d'US-08 sont tenus, le 3ᵉ
  (« sous l'analyse ») désormais par une assertion de position.

### Doc-Sync Auditor
- **Verdict :** AUDIT_PASS. Le suivi de la phase 21 rectifie explicitement le
  constat initial (duplication, pas simple mauvais placement) plutôt que de le
  laisser tel quel.

### A11y/UX Checker
- **Verdict :** AUDIT_PASS avec réserves. **Findings :** F22-03 (multiligne
  aplati). Les identifiants dupliqués ont disparu, donc l'association
  `label`/`for` est de nouveau univoque.

### Clean Code / Fail-Loud / Layer Enforcer / YAGNI / SRE / Architecture Consistency
- **Verdict :** AUDIT_PASS. Aucun finding.

### Test Quality Auditor
- **Verdict :** AUDIT_FAIL. **Findings :** F22-01, F22-04.

### Mutation/Saboteur Auditor
- **Verdict :** AUDIT_FAIL. **Mutation qui survit :** retirer le filtre par
  article (427 tests verts). **Mutations tuées :** section remise dans le bloc
  `title`, ancre retirée des refus, filtre des retirés supprimé, retrait ouvert
  aux contributeurs, CSRF retirée.

### Contextual Threat Analyst / SAST / Supply Chain / Privacy
- **Verdict :** AUDIT_PASS, sauf Privacy qui porte F22-01 sous l'angle du
  cloisonnement des fils.

---

## Points Conformes (Synthèse)

- **Les six findings de la phase 21 sont corrigés**, et les trois mutations
  correspondantes tombent.
- Les deux premiers tests de **structure** du dépôt existent : position et
  unicité, pas seulement présence.
- Les deux décisions de comportement (quota d'un commentaire retiré, article non
  évalué commentable) sont dans le code, dans un test et dans le rapport.
- Le suivi de la phase 21 **rectifie son propre diagnostic** au lieu de le
  maintenir.
- **427 tests, 0 skip** contre un vrai Postgres avec les sept migrations.

---

## Limites De Vérification

- **F22-03 :** le rendu réel n'a pas été observé dans un navigateur ; la
  conclusion repose sur la règle de réduction des espaces du HTML, qui ne souffre
  pas d'exception en l'absence de `white-space`.
- **F22-02 :** la permutation d'ordre n'a pas été reproduite ; deux insertions
  dans la même seconde sont nécessaires, et le défaut est établi par lecture.
- **Une de mes sondes a produit un faux positif** (cf. rectification ci-dessus) ;
  le constat retenu vient de la lecture du HTML rendu.
- Aucun code de production modifié pendant cet audit — les mutations ont été
  restaurées depuis une copie, pas depuis `git` (leçon de la phase 19).

### Commandes Exécutées

| Commande | Résultat |
| --- | --- |
| `TEST_DATABASE_URL=… pytest -q` | **427 passed, 0 skipped** |
| Mutation : filtre `article_id` retiré | **427 passed** — la suite ne voit rien |
| Sonde : commentaire multiligne rendu | `\n\n` présent dans le HTML, aucun `white-space` sur le texte |
| Lecture de `detail.html` | une seule section, dans le bloc `content` |
