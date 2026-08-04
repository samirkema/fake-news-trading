# User Stories — Contextualiseur

Périmètre : la génération d'une explication factuelle pour les articles identifiés comme suspects par l'évaluateur (score composite US-08 au-dessus d'un seuil de suspicion), en s'appuyant sur les preuves déjà rassemblées par l'évaluateur, sans re-vérification complète depuis zéro.

---

## US-01 — Déclenchement conditionnel sur seuil de suspicion

**En tant que** contextualiseur automatique,
**je veux** ne traiter que les articles dont le score composite final (US-08 évaluateur) atteint ou dépasse un seuil de suspicion configurable,
**afin de** limiter les appels LLM coûteux aux cas réellement suspects plutôt qu'à l'ensemble du corpus collecté.

**Critères d'acceptation :**
- Le seuil est configurable sans modification du code.
- Le seuil par défaut est fixé à 60/100, un point de départ arbitraire à recalibrer une fois qu'un corpus labellisé est disponible (LIAR/FakeNewsNet/ISOT, cf. `fiche-projet-fake-news-trading.md`) — la méthode de calibration future consiste à choisir la valeur qui maximise le F1 du score composite (US-08 évaluateur) sur un jeu de validation retenu.
- Les articles sous le seuil ne génèrent aucun appel au contextualiseur. Un article `non_évaluable` (cf. US-08 évaluateur, tous signaux exclus) est traité comme sous le seuil.
- Le nombre d'appels LLM du contextualiseur par run hebdomadaire est plafonné (valeur configurable, distincte du plafond US-07 évaluateur — un appel d'explication coûte plus cher qu'un appel de scoring court, cf. `architecture.md`). Si le nombre d'articles au-dessus du seuil dépasse le plafond, priorisation par score de suspicion décroissant.
- Chaque run journalise le nombre d'articles traités vs. le nombre total scoré par l'évaluateur — donne une mesure réelle du taux de suspicion, sur le même principe que le comptage par source du scraper (US-06 scraper).

---

## US-02 — Génération de l'explication ancrée sur les preuves de l'évaluateur

**En tant que** contextualiseur automatique,
**je veux** générer une explication de ce qui rend l'article suspect et de quelle est la réalité connue, en m'appuyant en priorité sur les preuves déjà rassemblées par l'évaluateur (verdict Fact Check US-03, résultat de recherche en source primaire US-04, corroboration ou absence de corroboration US-02),
**afin d'**éviter de relancer une recherche complète et de garder l'explication ancrée sur des éléments déjà vérifiés plutôt que sur la seule connaissance générale du LLM.

**Critères d'acceptation :**
- Le prompt envoyé au LLM inclut explicitement les sous-scores et justifications déjà produits par l'évaluateur pour cet article.
- La sortie du LLM est structurée en deux champs distincts plutôt qu'en texte libre : `faits_traces` (chaque item référence le `preuve_id` d'un signal produit par l'évaluateur — cf. interface `evaluer(article)` dans `architecture.md`, ex. `fact_checking:<url_claimreview>`, `source_primaire:<accession_sec>`, `corroboration:<cluster_id>`) et `deductions_llm` (le reste, sans `preuve_id`). Un post-traitement rejette ou déplace vers `deductions_llm` tout item de `faits_traces` dont le `preuve_id` cité ne correspond à aucun `preuve_id` réellement présent dans la sortie de l'évaluateur pour cet article — la distinction n'est pas laissée à la seule discipline du prompt.
- Si aucune preuve externe n'est disponible pour établir "quelle est la réalité" (aucun hit Fact Check, aucune source primaire trouvée), le contextualiseur n'invente pas de contre-récit : il produit une explication limitée aux signaux disponibles (absence de corroboration, style putaclic, etc.) et indique explicitement qu'aucune vérité factuelle n'a pu être établie, plutôt que de fabriquer une réalité alternative.

---

## US-03 — Persistance et traçabilité de la mise en contexte

**En tant que** contextualiseur automatique,
**je veux** enregistrer l'explication générée, les sources utilisées et un niveau de confiance dans le stockage partagé,
**afin que** le frontend puisse l'afficher avec la même traçabilité que les scores de l'évaluateur.

**Critères d'acceptation :**
- Le format de sortie inclut : explication textuelle, liste des preuves/sources utilisées (avec leur origine — Fact Check, source primaire, corroboration), niveau de confiance, date de génération.
- La mise en contexte est associée à l'article de la même manière que les scores (même clé, même logique de stockage — conforme au contrat défini dans `architecture.md`).

---

## US-04 — Avertissement sur la nature automatisée du verdict

**En tant que** contextualiseur automatique,
**je veux** accompagner chaque explication d'un avertissement indiquant qu'il s'agit d'une évaluation automatisée et non d'une accusation éditoriale définitive,
**afin de** limiter le risque de diffamation ou de sur-confiance dans un verdict produit par un LLM.

**Critères d'acceptation :**
- Chaque mise en contexte inclut une mention explicite de son caractère algorithmique/provisoire et du niveau de confiance associé.
- Cette mention est portée par la donnée elle-même (persistée en base), pas uniquement ajoutée a posteriori par le frontend.
- La formulation évite systématiquement toute affirmation catégorique nommant une source comme mensongère ("signaux de suspicion détectés" plutôt qu'un verdict affirmatif) — pas seulement en mode hébergé : la mise en contexte est générée une seule fois et persistée (US-03), donc lue à l'identique par le frontend local et le frontend hébergé (cf. `architecture.md`, contrat lecture seule). Conforme au traitement du risque de diffamation défini dans `userstories_frontend.md`.

---

## Hors périmètre (pour rappel)

- La vérification factuelle primaire (interrogation des fact-checkers, recherche en source primaire) est déjà faite par l'évaluateur (US-03, US-04 évaluateur) — le contextualiseur ne la refait pas, il la réutilise.
- Le fine-tuning ou le choix du LLM utilisé pour la génération n'est pas couvert ici.
