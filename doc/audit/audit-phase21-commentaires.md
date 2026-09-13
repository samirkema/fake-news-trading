# Audit phase 21 — Phase 4 du crowdsourcing : commentaires

Date : 2026-09-13 · Scope : la migration `0007_commentaires.sql`, le modèle
`Commentaire`, les routes `publier_commentaire` et `retirer_commentaire`,
l'affichage dans `templates/detail.html` et `templates/base.html`, le plafond
dans `fakenews.config`, `tests/test_commentaires.py`.
Base d'exigences : `doc/V3/userstories_crowdsourcing.md` (US-08),
`doc/V3/plan_implementation_crowdsourcing.md` (phase 4),
`doc/V0/userstories_frontend.md` US-04 (avertissement sur chaque page).
État audité : arbre de travail non commité.

---

## Résumé De L'Audit

| Division | Statut | Synthèse |
| --- | --- | --- |
| Métier (Anton Ego) | 🔴 Bloquant | La section des commentaires n'est pas sur la page : elle est **dans le titre de l'onglet**. Le formulaire, la liste, les boutons de retrait — tout a été inséré dans `<title>`, donc dans le `<head>`. |
| Qualité (Gordon Ramsay) | 🔴 Bloquant | Dix-neuf tests au vert sur une page dont le HTML est invalide. Ils cherchent des morceaux de texte dans une chaîne ; aucun ne regarde la structure. |
| Architecture (Steve Jobs) | 🟢 OK | Le modèle, les contraintes et la frontière d'écriture sont justes. Le défaut est un accident de gabarit, pas de conception. |
| Cybersécurité offensive (Sherlock Holmes) | 🟢 OK | Autorisation, CSRF, échappement, masquage : tout tient, et la frontière contributeur/superadmin est vérifiée. |

**Verdict global : AUDIT_FAIL.** 1 High, 1 Medium, 4 Low.

La fonctionnalité est correcte **en base et en logique** — publication, plafond,
retrait qui masque sans effacer, non-objectif du score tenu. Elle est fausse **à
l'écran**, et la suite de tests ne pouvait pas le voir.

---

## Index Des Sous-Audits

| Sous-audit | Scope | Crit | High | Medium | Low | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Business Logic Auditor | cycle de vie d'un commentaire | 0 | 0 | 0 | 2 | AUDIT_PASS (réserves) |
| Requirements Compliance Auditor | US-08 vs implémentation | 0 | 1 | 0 | 0 | AUDIT_FAIL |
| Doc-Sync Auditor | README, plan V3, `.env.example` | 0 | 0 | 0 | 0 | AUDIT_PASS |
| A11y/UX Checker | `detail.html`, `base.html` | 0 | 1 | 1 | 0 | AUDIT_FAIL |
| Clean Code Auditor | routes, `_message` | 0 | 0 | 0 | 1 | AUDIT_PASS (réserves) |
| Fail-Loud Auditor | chemins de refus | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Test Quality Auditor | 19 tests neufs | 0 | 1 | 0 | 0 | AUDIT_FAIL |
| Mutation/Saboteur Auditor | retrait, autorisation, CSRF | 0 | 0 | 0 | 1 | AUDIT_PASS (réserves) |
| Layer Enforcer | frontière d'écriture | 0 | 0 | 0 | 0 | AUDIT_PASS |
| YAGNI Auditor | routes et helpers | 0 | 0 | 0 | 0 | AUDIT_PASS |
| SRE/Performance Auditor | requêtes, `_message` | 0 | 0 | 0 | 1 | AUDIT_PASS (réserves) |
| Architecture Consistency Auditor | plan phase 4 vs code | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Contextual Threat Analyst | abus de la parole publique | 0 | 0 | 0 | 0 | AUDIT_PASS |
| SAST Scanner | XSS, authz, CSRF | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Supply Chain & Artifact Auditor | aucune dépendance | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Privacy/Exfiltration Auditor | pseudos et textes conservés | 0 | 0 | 0 | 0 | AUDIT_PASS |

Décompte dédupliqué : **6 findings**.

---

## Matrice De Couverture

| Exigence (US-08) | Preuve | Statut |
| --- | --- | --- |
| Tout compte connecté peut commenter | test dédié, publication immédiate | ✅ |
| Pseudo, date, texte affichés | rendus… **dans `<title>`** | ❌ **F21-01** |
| Longueur bornée | 2000 caractères, test dédié | ✅ |
| Texte échappé à l'affichage | `&lt;script&gt;`, test dédié | ✅ |
| **Affichés SOUS l'analyse, jamais mêlés à elle** | section insérée **avant** le contenu, dans le `<head>` | ❌ **F21-01** |
| L'avertissement automatisé reste affiché | présent, test dédié | ✅ |
| Le superadmin peut retirer | test + mutation | ✅ |
| Le retrait masque sans effacer | contenu conservé, `retire_par`/`retire_le` posés | ✅ |
| Un retiré reste consultable par le superadmin | sonde : contributeur **ne le voit pas**, superadmin oui | ✅ |
| Plafond par compte et par fenêtre | compté en base, test dédié | ✅ |
| **Les commentaires n'influencent pas le score** | `score_final` et `sous_scores` inchangés, test dédié | ✅ |
| Écriture protégée par CSRF | deux routes, deux tests, mutations tuées | ✅ |

---

## Top Findings

- **[High] F21-01** — ✅ **corrigé le 2026-09-13**, cf. « Suivi des correctifs ».
  `src/fakenews/frontend/templates/detail.html:4` — toute la
  section des commentaires a été insérée **dans le bloc `title`**, pas dans le
  bloc `content`. Le gabarit commence désormais par :
  ```jinja
  {% block title %}{{ article.titre | truncate(70) }} — Fake News Détection
  <hr>
  <section id="commentaires" class="commentaires">
  ```
  **Mesuré** sur la page rendue : `<section id="commentaires">` apparaît au
  **183ᵉ caractère**, à l'intérieur de `<title>`, donc dans le `<head>`. Le
  formulaire de publication, la liste des commentaires et les boutons de retrait
  s'y trouvent tous.
  **Impact :** le HTML est invalide ; ce que le navigateur en fait n'est pas
  spécifié et varie. Dans le meilleur des cas l'onglet porte un titre absurde et
  la section est ignorée — c'est-à-dire que **la fonctionnalité livrée n'est pas
  visible**. Le 3ᵉ critère d'US-08 — « affichés SOUS l'analyse et la mise en
  contexte, jamais mêlés à elles » — est violé de la manière la plus littérale
  qui soit : ils sont au-dessus de tout, dans l'en-tête du document.
  **Cause :** la section a été ajoutée par un remplacement de la **première**
  occurrence de `{% endblock %}` dans le fichier. La première est celle du bloc
  `title` (ligne 4), pas celle du bloc `content` (ligne 157).
  **Correction attendue :** déplacer la section avant le `{% endblock %}` final,
  et ajouter un test qui vérifie la STRUCTURE — par exemple que
  `id="commentaires"` apparaît après `Score composite` dans le document, ou que
  `<title>` ne contient aucune balise.
- **[Medium] F21-02 · `src/fakenews/frontend/app.py`, `publier_commentaire`** —
  asymétrie entre succès et échec. Le succès renvoie vers
  `/articles/{id}#commentaires` ; l'échec vers `/articles/{id}?erreur=…`, **sans
  ancre**. Un commentaire refusé (vide, trop long, plafond atteint) ramène donc
  l'utilisateur en haut de la page, où rien n'a changé.
  L'ancre a été écrite sur le chemin nominal et oubliée sur le chemin d'échec :
  le message existe, il est juste hors du champ de vision.
  **Correction attendue :** `_avec_erreur` doit accepter une ancre, ou la route
  construire `?erreur=…#commentaires`.

---

## Thèmes Transverses

1. **Un test de sous-chaîne ne teste pas une page.** Les dix-neuf tests
   cherchent `"Un apport de contexte utile."` dans `reponse.text` — et le
   trouvent, puisque le texte EST dans la chaîne. Qu'il soit dans `<title>` leur
   est parfaitement égal. La suite prouve que les données circulent, pas que la
   page existe.
2. **Le chemin nominal a son ancre, le chemin d'échec ne l'a pas.** Même motif
   qu'aux phases 19 et 20 : le soin porté au cas qui marche, moins au cas qui
   échoue.
3. **La logique est saine, la présentation ne l'est pas.** Migration, contraintes,
   autorisation, CSRF, masquage, non-objectif du score : tout est correct et
   vérifié. Le seul défaut sérieux vient d'une manipulation de texte sur un
   gabarit, faite sans relire le résultat.

---

## Détails Par Division

### Division Métier (Anton Ego)

On m'annonce une salle de commentaires ; je la trouve rangée dans l'enseigne du
restaurant. La cuisine est irréprochable — mais personne ne mangera, puisque la
table est accrochée au-dessus de la porte.

- **[High] F21-01** — cf. Top Findings. **Type : Confirmé (mesuré).**
- **[Low] F21-03** — on peut commenter un article **non évalué** : la page
  affiche « Cet article n'a pas encore été évalué » et propose quand même le
  formulaire. **Vérifié.** US-08 parle de « commenter l'analyse d'un article » ;
  commenter en l'absence d'analyse n'est pas interdit, ce n'est simplement pas ce
  que l'exigence décrit. Sans danger ; à trancher explicitement plutôt qu'à
  laisser au hasard du routage.
- **[Low] F21-04** — un commentaire **retiré continue d'occuper le quota** de son
  auteur. **Vérifié :** avec un plafond à 1 et un commentaire retiré, l'auteur ne
  peut plus publier. C'est probablement le bon choix — sinon se faire retirer
  libérerait du quota, ce qui récompense l'abus — mais rien ne le dit, ni dans le
  code ni dans la documentation.

### Division Qualité (Gordon Ramsay)

Dix-neuf tests. Dix-neuf. Et pas un seul ne s'est demandé OÙ, dans la page, le
texte qu'il venait de trouver se trouvait. Vous avez goûté la sauce et déclaré
le plat réussi sans regarder l'assiette.

- **[High] F21-01, sous l'angle test** — aucun test ne vérifie la structure du
  document. `assert "Un apport de contexte utile." in page` passe que la section
  soit dans `<body>`, dans `<title>` ou dans un commentaire HTML.
  **Correction attendue :** au moins une assertion de position
  (`page.index("Score composite") < page.index('id="commentaires"')`) ou de
  bonne formation du `<head>`.
- **[Low] F21-05** — la mutation « déplacer la section hors du bloc content »
  survivrait à toute la suite : c'est précisément ce qui s'est produit.
- **Points conformes :** les quatre mutations testées sont tuées (retrait
  transformé en suppression, filtre du public retiré, retrait ouvert aux
  contributeurs, CSRF supprimée) ; le test du non-objectif compare `score_final`
  ET `sous_scores` avant/après ; le test d'échappement vérifie l'absence de
  `<script>` **et** la présence de `&lt;script&gt;`, donc il ne passerait pas sur
  une page vide.

### Division Architecture (Steve Jobs)

Le modèle est juste. Les contraintes disent en base ce que les routes appliquent.
Le défaut n'est pas là.

- **[Low] F21-06** `app.py`, `_message` — deux lectures d'environnement à chaque
  appel (**mesuré : 2**), donc à chaque rendu de page portant un message. Sans
  conséquence mesurable ; la table grandit à chaque phase, et ce sera une raison
  de plus de la sortir de `app.py`.
- **Points conformes :** `ck_commentaires_retrait_trace` rend impossible un
  retrait qui ne dirait pas qui ni quand — même principe que
  `ck_propositions_decision_tracee` ; le filtre des retirés est côté serveur, pas
  dans le gabarit ; la condition « pas déjà retiré » est dans l'`update`, donc
  deux retraits simultanés ne réécrivent pas l'horodatage du premier ; aucune
  dépendance ajoutée.

### Division Cybersécurité Offensive (Sherlock Holmes)

Élémentaire, et pourtant : rien à signaler. La parole des visiteurs entre par une
route protégée, sort échappée, et ne s'efface jamais tout à fait.

- **Points conformes :** CSRF exigée sur les deux routes d'écriture, vérifiée
  avant tout effet de bord, et les deux mutations correspondantes tombent ;
  `exige_role("superadmin")` sur le retrait, avec refus en 404 — un
  **contributeur** ne voit pas non plus les commentaires retirés, vérifié par
  sonde ; échappement Jinja actif et testé ; le texte est borné avant insertion ;
  le plafond est compté en base, donc insensible au nombre d'instances ; aucune
  donnée personnelle nouvelle hors le pseudo, déjà visible ailleurs.
- **Observation, non retenue comme finding :** le plafond est vérifié puis
  l'insertion faite — deux requêtes distinctes. Deux publications simultanées du
  même compte peuvent donc dépasser le plafond d'une unité. Identique pour les
  propositions. Impact nul (un commentaire de plus), correction disproportionnée
  au risque.

---

## Détails Par Sous-Audit

### Business Logic Auditor
- **Verdict :** AUDIT_PASS avec réserves. **Findings :** F21-03, F21-04.
- **Points conformes :** publication immédiate assumée et documentée ; retrait
  tracé ; plafond opposable.

### Requirements Compliance Auditor
- **Verdict :** AUDIT_FAIL. Le 3ᵉ critère d'US-08 — affichage **sous** l'analyse,
  jamais mêlé à elle — est violé par F21-01. Les dix autres critères sont tenus
  et testés.

### Doc-Sync Auditor
- **Verdict :** AUDIT_PASS. README (migration `0007`, variable
  `COMMENTAIRES_MAX_PAR_JOUR`), `.env.example`, plan V3 et section « reste à
  faire » décrivent l'état réel, y compris le découpage d'`app.py` non fait et
  les deux sujets ouverts (modération a priori, RGPD).

### A11y/UX Checker
- **Verdict :** AUDIT_FAIL. **Findings :** F21-01 (HTML invalide : contenu de flux
  dans `<head>`), F21-02 (message d'erreur hors du champ de vision).
- **Points conformes :** `label for` / `id` appariés sur le champ de commentaire ;
  `role="alert"` sur l'erreur ; `maxlength` cohérent avec la borne serveur ; les
  commentaires retirés portent une classe distincte et une mention explicite.

### Clean Code Auditor
- **Verdict :** AUDIT_PASS avec réserves. **Findings :** F21-06.
- **Points conformes :** les deux routes sont courtes, chaque refus a son code de
  message, aucune duplication avec les propositions au-delà du strict nécessaire.

### Fail-Loud Auditor
- **Verdict :** AUDIT_PASS. Chaque refus produit un code de message traduit ; un
  article inexistant renvoie 404 ; un retrait impossible renvoie un message plutôt
  qu'un silence.

### Test Quality Auditor
- **Verdict :** AUDIT_FAIL. **Findings :** F21-01 (aucun test de structure),
  F21-05.

### Mutation/Saboteur Auditor
- **Verdict :** AUDIT_PASS avec réserves. Quatre mutations tuées ; **la mutation
  de placement du gabarit survivrait** — elle est d'ailleurs la réalité auditée.

### Layer Enforcer / YAGNI / Architecture Consistency
- **Verdict :** AUDIT_PASS. `commentaires` est la troisième table écrite par le
  frontend, conformément à la décision V3 ; `articles`, `scores` et
  `mise_en_contexte` restent hors de sa portée en écriture.

### SRE/Performance Auditor
- **Verdict :** AUDIT_PASS avec réserves. **Findings :** F21-06. Les deux index de
  `0007` couvrent les deux seules lectures (par article, par pseudo).

### Contextual Threat Analyst / SAST / Supply Chain / Privacy
- **Verdict :** AUDIT_PASS. Cf. division Cybersécurité.

---

## Points Conformes (Synthèse)

- **La logique est entièrement correcte** : publication, bornes, plafond compté en
  base, retrait qui masque sans effacer, traçabilité du retrait garantie par le
  schéma.
- **Le non-objectif d'US-08 est tenu et testé** : `score_final` et `sous_scores`
  sont inchangés après trois commentaires contestataires.
- **La frontière d'autorisation est juste et vérifiée** : ni un spectateur ni un
  **contributeur** ne voient les commentaires retirés ; seul le superadmin retire.
- Quatre mutations de sécurité et de comportement sont tuées.
- **421 tests, 0 skip** contre un vrai Postgres avec les sept migrations.

---

## Limites De Vérification

- **F21-01 :** le comportement réel des navigateurs face à du contenu de flux dans
  `<title>` n'a pas été observé (pas de navigateur dans l'environnement). La
  non-conformité du document, elle, est certaine.
- **F21-03, F21-04 :** comportements constatés, pas jugés — ce sont des décisions
  à prendre, pas des défauts prouvés.
- **Course sur le plafond** : raisonnée, non reproduite (deux requêtes vraiment
  simultanées demandent un banc de test dédié).
- Aucun code de production modifié pendant cet audit.

### Commandes Exécutées

| Commande | Résultat |
| --- | --- |
| `TEST_DATABASE_URL=… pytest -q` | **421 passed, 0 skipped** |
| Sonde : position de `id="commentaires"` dans la page rendue | **caractère 183 / 5487, à l'intérieur de `<title>`** |
| Lecture de `detail.html:4` | la section est dans le bloc `title` |
| Sonde : un contributeur voit-il un commentaire retiré ? | **non** |
| Sonde : commenter un article non évalué | accepté |
| Sonde : un commentaire retiré occupe-t-il le quota ? | **oui** |
| Sonde : `Location` en succès vs en échec | `#commentaires` vs **aucune ancre** |
| Sonde : lectures d'environnement par `_message` | **2** |


---

## Suivi Des Correctifs — 2026-09-13

**Les six findings sont traités.** Suite : **427 tests, 0 skip**.

### Rectification du constat de F21-01

Le rapport décrivait la section comme « insérée dans le bloc `title` ». La cause
exacte est plus bête et le symptôme plus large : `str.replace` sans compteur a
remplacé **les deux** `{% endblock %}` du gabarit. Il y avait donc **deux copies**
de la section — une correcte en fin de contenu, une parasite dans le `<head>`.

Conséquences réelles, au-delà de l'invalidité du document : la page servait
**deux formulaires de publication**, **deux listes de commentaires**, et des
identifiants HTML dupliqués (`id="texte"` deux fois), ce qui casse l'association
`label`/`for` pour les lecteurs d'écran.

Le diagnostic initial était donc incomplet, pas faux — et c'est la sonde de
position, pas la lecture du gabarit, qui a mis l'anomalie en évidence.

### F21-01 · ✅ corrigé

La copie parasite est retirée du bloc `title`, qui retrouve sa ligne unique.
Vérifié : une seule occurrence de `id="commentaires"`, une seule de `id="texte"`,
et aucune balise dans `<title>`.

**Deux tests de STRUCTURE** ont été ajoutés — ce qui manquait :
- `<title>` ne contient aucune balise, et les identifiants ne sont pas dupliqués ;
- `Score composite` et `Mise en contexte` apparaissent **avant**
  `id="commentaires"` dans le document, ce qui est le 3ᵉ critère d'US-08 exprimé
  en assertion plutôt qu'en intention.

**Mutation :** remettre la section dans le bloc `title` fait tomber les deux.

### F21-02 · ✅ corrigé

`_avec_erreur` accepte une ancre ; les trois refus de publication renvoient vers
`#commentaires`. Le chemin d'échec revient là où le message s'affiche, comme le
chemin nominal. Mutation : retirer l'ancre fait tomber le test paramétré.

### F21-03, F21-04 · ✅ tranchés et écrits

Commenter un article **non encore évalué** reste possible — la page l'annonce, le
commentaire attendra l'analyse. Un commentaire **retiré continue d'occuper le
quota** de son auteur : l'exclure rendrait le retrait avantageux pour lui
(publier, se faire retirer, recommencer), alors que le plafond existe pour freiner
ce cycle. Les deux décisions sont désormais dans le code **et** dans un test, au
lieu d'être des effets de bord du routage.

### F21-05 · ✅ fermé par F21-01

La mutation de placement du gabarit, qui survivait à toute la suite, est
maintenant tuée par les deux tests de structure.

### F21-06 · ✅ corrigé

Les deux seuls messages dépendant de la configuration la lisent eux-mêmes.
`_message` ne lit plus l'environnement pour traduire « ce commentaire est vide ».

### Revue ponytail

Le paramétrage du test de refus passait une charge de 3 000 caractères en
identifiant de test — l'identifiant monstrueux déjà relevé en phase 19. Remplacé
par une clé lisible (`"vide"` / `"trop long"`).
