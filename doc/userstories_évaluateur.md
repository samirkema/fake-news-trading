# User Stories — Évaluateur de fiabilité (détection fake news)

Périmètre : les 7 signaux identifiés pour scorer la fiabilité d'un article avant tout ML, et leur agrégation en un score composite final 0-100 (0 = fiable, 100 = très suspect).

Chaque signal (US-01 à US-07) exprime sa `valeur` sur cette même échelle 0-100 (0 = fiable, 100 = très suspect) — condition nécessaire pour que la moyenne pondérée de US-08 soit interprétable. Un signal neutre/non applicable a `valeur: null` (exclu du calcul, cf. US-08), pas une valeur numérique arbitraire comme 50.

---

## US-01 — Réputation de la source

**En tant qu'** évaluateur automatique,
**je veux** vérifier si le domaine source de l'article figure sur une liste de domaines fiables ou douteux,
**afin de** pondérer le score de suspicion en fonction de la réputation connue de l'émetteur.

**Critères d'acceptation :**
- Une liste de référence (domaines fiables / douteux) est constituée à partir de sources publiques (ex. dataset OpenSources, listes utilisées par FakeNewsNet).
- Chaque article collecté est associé à son domaine source.
- Si le domaine est absent des deux listes, l'article est marqué "réputation inconnue" (score neutre, pas de pénalité ni bonus).
- Le sous-score de réputation est traçable (raison de la note) dans la sortie.

---

## US-02 — Corroboration croisée

**En tant qu'** évaluateur automatique,
**je veux** savoir si le même événement est rapporté par plusieurs sources indépendantes et réputées,
**afin de** détecter les informations isolées, non recoupées, plus susceptibles d'être fausses.

**Critères d'acceptation :**
- Les articles de la semaine sont regroupés par événement/claim (via GDELT ou similarité de titres/contenu à défaut, cosinus sur embeddings de titre, seuil 0.8).
- Avant comptage, les articles quasi-identiques (même dépêche wire republiée telle quelle) sont fusionnés en un seul émetteur : deux articles sont considérés comme la même source si leur similarité de contenu (cosinus sur embeddings de titre+texte) dépasse 0.85, quel que soit le nombre de domaines qui les republient. "Indépendant" signifie : ne provenant pas du même texte source à ce seuil.
- Le nombre de sources indépendantes (après fusion) corroborant chaque cluster est compté.
- Un événement rapporté par une seule source indépendante (ou uniquement des sources à faible réputation) augmente le score de suspicion.
- Le nombre de sources corroborantes est visible dans la sortie pour chaque article.

---

## US-03 — Vérification via fact-checking existant

**En tant qu'** évaluateur automatique,
**je veux** interroger une base de fact-checking existante avec les claims extraites de l'article,
**afin de** détecter si l'information a déjà été vérifiée ou débunkée par un fact-checker reconnu.

**Critères d'acceptation :**
- Intégration de l'API Google Fact Check Tools (gratuite) sur les claims/mots-clés principaux de l'article.
- Si une correspondance ClaimReview existe et que le verdict est "faux"/"trompeur", le score de suspicion est fortement augmenté ; l'URL de la ClaimReview est tracée comme `preuve_id` (cf. interface `evaluer(article)` dans `architecture.md`), pour être citable par le contextualiseur (US-02 contextualiseur).
- Si une correspondance existe avec un verdict "vrai", le score de suspicion est fortement diminué (même traçabilité `preuve_id`).
- Absence de correspondance = pas d'effet sur le score (signal neutre, pas un signal d'absence de preuve).
- En cas d'indisponibilité, de rate-limit ou de réponse malformée de l'API, l'échec est journalisé et le signal est marqué non disponible pour cet article (exclu du calcul, cf. `architecture.md`).

---

## US-04 — Vérification contre la source primaire (finance)

**En tant qu'** évaluateur automatique,
**je veux** vérifier si une annonce concernant une entreprise cotée apparaît dans ses sources primaires officielles,
**afin de** repérer les "scoops" non confirmés sur des sujets à fort impact marché.

**Critères d'acceptation :**
- Extraction des tickers/entreprises citées dans l'article (NER).
- Recherche de la claim dans SEC EDGAR full-text search (gratuit) et/ou les communiqués officiels de l'entreprise, sur une fenêtre de ±5 jours ouvrés autour de la publication (valeur configurable) — un dépôt SEC (8-K notamment) peut légitimement accuser plusieurs jours de retard sur la couverture presse, cette fenêtre évite de pénaliser un journalisme rapide mais exact.
- Absence de confirmation en source primaire, pour une claim présentée comme un fait précis et vérifiable (annonce, chiffre, décision), augmente le score de suspicion.
- Le résultat de la recherche (trouvé / non trouvé / non applicable) est tracé dans la sortie ; en cas de "trouvé", le numéro d'accession du dépôt SEC EDGAR (ou l'URL du communiqué) est tracé comme `preuve_id` (cf. `architecture.md`).
- Ce signal repose sur SEC EDGAR, qui ne couvre que les entreprises cotées aux États-Unis : c'est un biais géographique structurel assumé pour cette phase (comme le biais anglophone de Reddit documenté en US-02 scraper). Pour toute entreprise hors de ce périmètre, le signal est marqué "non applicable" et exclu du calcul (cf. US-08), pas traité comme une absence de confirmation pénalisante.
- En cas d'indisponibilité, de rate-limit ou de réponse malformée de SEC EDGAR, l'échec est journalisé et le signal est marqué non disponible pour cet article (exclu du calcul, cf. `architecture.md`).

---

## US-05 — Signaux stylistiques

**En tant qu'** évaluateur automatique,
**je veux** analyser le style rédactionnel de l'article (auteur, citations, ton),
**afin de** détecter les patterns typiques des contenus peu fiables ou putaclic.

**Critères d'acceptation :**
- Détection de la présence/absence d'un auteur identifiable (byline).
- Détection de la présence/absence de citations ou de sources nommées dans le corps du texte.
- La langue de l'article est détectée en amont ; les marqueurs stylistiques de sensationnalisme (ponctuation excessive, vocabulaire à forte charge émotionnelle, titre putaclic) sont évalués via des lexiques/règles distincts par langue (au minimum anglais et français, cf. US-01 scraper), pas une règle unique appliquée telle quelle à tout le corpus.
- Chaque signal détecté contribue individuellement et de façon traçable au sous-score stylistique.

---

## US-06 — Décalage d'apparition Reddit / presse établie

**En tant qu'** évaluateur automatique,
**je veux** comparer le moment de première détection d'une info sur Reddit à sa reprise par la presse établie,
**afin de** repérer les rumeurs financières qui circulent sur Reddit avant toute confirmation par la presse établie (pattern pump & dump).

**Critères d'acceptation :**
- Pour chaque claim/événement (cf. clustering US-02), le timestamp de première détection sur Reddit et le timestamp de première reprise par un flux RSS de presse établie sont comparés — pas un suivi de volume dans le temps, incompatible avec une collecte hebdomadaire à point unique (cf. `architecture.md`).
- Une première détection sur Reddit sans reprise par la presse établie sur la fenêtre de la semaine augmente le score de suspicion.
- L'ordre observé (Reddit avant presse / presse avant Reddit / pas de correspondance) est visible dans la sortie, pas un délai continu qui supposerait plusieurs points de mesure dans la semaine.

---

## US-07 — Scoring LLM en bootstrap

**En tant qu'** évaluateur automatique,
**je veux** soumettre le texte de l'article à un LLM en ligne avec un prompt de scoring structuré,
**afin de** disposer d'un score de suspicion provisoire et d'un label exploitable pour l'entraînement futur du modèle maison.

**Critères d'acceptation :**
- Le prompt envoyé au LLM demande un score de suspicion (0-100) et une justification textuelle courte.
- La réponse est parsée en un format structuré (score + justification) et associée à l'article.
- Chaque appel LLM est journalisé (article, score, justification, date) pour constituer le futur dataset d'entraînement.
- Ce signal est clairement identifié comme provisoire/bootstrap dans la sortie, distinct des signaux 1 à 6.
- Le nombre d'appels LLM par run hebdomadaire est plafonné (valeur configurable, `LLM_PLAFOND_EVALUATEUR`), avec priorisation par cluster d'événement (le plus corroboré/le plus viral d'abord) si le volume collecté dépasse le plafond — condition nécessaire pour que le budget (cf. `fiche-projet-fake-news-trading.md`) reste prévisible malgré une collecte de volume non plafonné (US-01 scraper). La priorisation par cluster n'est pas encore possible (dépend du clustering de US-02 évaluateur, non implémenté) : en attendant, les articles sont traités dans l'ordre rencontré jusqu'au plafond — simplification assumée, pas un oubli.

---

## US-08 — Score composite final

**En tant qu'** évaluateur automatique,
**je veux** agréger les sous-scores des signaux US-01 à US-07 en un score de suspicion unique 0-100,
**afin de** fournir une décision exploitable en sortie (rapport hebdomadaire), plutôt que 7 signaux séparés à interpréter manuellement. Ce score pourra plus tard servir de signal d'entrée à un futur système de trading, mais celui-ci n'est pas conçu ici (cf. non-objectif actuel dans `architecture.md`).

**Critères d'acceptation :**
- Chaque signal (US-01 à US-07) contribue au score final avec un poids fixé manuellement/empiriquement. Poids de départ (arbitraires, à recalibrer une fois qu'un corpus labellisé est disponible — cf. US-01 contextualiseur) : reputation 1, corroboration 1, fact_checking 1.5, source_primaire 1.5, style 0.5, decalage_viral 1, llm_bootstrap 1.5 — le bootstrap et les deux signaux à ancrage factuel externe (fact-check, source primaire) pèsent davantage que les signaux purement stylistiques ou de forme.
- Un signal "neutre" ou "non applicable" pour un article donné (ex. US-04 sur un article non financier, US-01 en cas de réputation inconnue) n'influence pas le score final — il est exclu du calcul plutôt que compté comme neutre à 50, pour ne pas diluer les signaux réellement disponibles.
- Le score final est une moyenne pondérée sur les seuls signaux applicables : `score = Σ(poids_i × valeur_i) / Σ(poids_i)` pour les signaux i non exclus — cette division renormalise automatiquement, pas besoin d'ajuster les poids restants à la main.
- Si tous les signaux sont exclus pour un article (dénominateur nul — cas limite mais possible), aucun score n'est calculé : l'article est marqué `score_final: non_évaluable` plutôt que de produire une division par zéro ou un score par défaut trompeur. Un article `non_évaluable` n'apparaît pas dans les listes triées par score (US-01 frontend) et ne déclenche pas le contextualiseur (sous le seuil par construction).
- Le signal bootstrap (US-07, LLM en ligne) a un poids explicitement paramétrable et distinct des signaux 1 à 6 (cf. valeurs de départ ci-dessus). Le remplacement de US-07 par le modèle maison fine-tuné, et tout ajustement de poids qui l'accompagnerait, est hors périmètre pour l'instant (cf. section "Hors périmètre") — les poids restent fixes tant que ce chantier n'est pas engagé.
- La sortie trace la contribution de chaque signal individuel au score final (poids appliqué + valeur), pas seulement le score agrégé, pour garder l'explicabilité déjà exigée signal par signal.
- Le score final et son détail sont associés à l'article dans le même format de sortie que les signaux individuels (persistance/journalisation), pour être consommés par le rapport hebdomadaire et, plus tard, par un éventuel futur système de trading.

---

## Note — Correspondance labels datasets publics ↔ échelle 0-100 (pour le futur fine-tuning)

Point de départ à ajuster empiriquement, pas une valeur figée — nécessaire avant de fusionner les labels bootstrap (US-07) avec les datasets publics pour le fine-tuning (cf. `fiche-projet-fake-news-trading.md`) :

| Dataset | Label d'origine | Score de suspicion 0-100 (proposé) |
|---|---|---|
| LIAR | pants-fire | 95 |
| LIAR | false | 80 |
| LIAR | barely-true | 60 |
| LIAR | half-true | 40 |
| LIAR | mostly-true | 20 |
| LIAR | true | 5 |
| FakeNewsNet / ISOT | fake | 80 |
| FakeNewsNet / ISOT | real | 10 |

---

## Hors périmètre (pour rappel)

- **Tout le côté IA/modèle maison est exclu du périmètre pour l'instant** : le fine-tuning du modèle maison (BERT/RoBERTa) et son intégration comme module `llm_bootstrap` alternatif, ainsi que tout ajustement automatique des poids US-08 qui en dépendrait, ne sont pas couverts ici. Ces user stories produisent seulement les labels/signaux (US-07) qui alimenteront ce chantier plus tard. Les poids US-08 restent fixes et fixés manuellement (cf. valeurs de départ, US-08) tant que ce chantier n'est pas engagé.
