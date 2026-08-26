# Fiche résumé — Projet Fake News & Trading Algorithmique

## Objectif du projet
Bibliothèque IA détectant les fake news et quantifiant leur impact sur le monde(notament les marchés financiers), puis stratégies de trading algorithmique utilisant ces signaux d'impact pour automatiser l'analyse de marché et l'exécution.

## Décisions prises

- **Démarrage simple** : un outil hebdomadaire qui scanne des articles et attribue un score de suspicion (0 = fiable, 100 = très suspect), avant d'ajouter du machine learning.
- **Pas de Twitter/X** : coût trop élevé (API officielle en pay-per-use depuis fév. 2026, ~0,005$/lecture, plafond 2M lectures/mois ≈ 10 000$). On se contente de **Reddit** (API officielle, tier gratuit correct) comme source réseau social.
- **Modèle propriétaire, pas seulement des LLM en ligne** : approche hybride retenue —
  1. Utiliser un LLM en ligne au début pour labelliser rapidement un premier corpus.
  2. Fine-tuner un modèle léger (BERT/RoBERTa/DistilBERT) sur ces labels + datasets publics (LIAR, FakeNewsNet, ISOT).
  3. Le modèle "maison" tourne ensuite en production sans coût récurrent par appel ; le LLM externe ne sert que ponctuellement (labellisation, cas ambigus).
- **Scoring et trading = deux phases distinctes** : la phase actuelle produit un score de suspicion hebdomadaire (bibliothèque de détection), sans aucun mécanisme d'exécution de trading. Automatiser l'analyse de marché et l'exécution nécessitera une architecture temps réel séparée, à concevoir seulement une fois le scoring validé — ce n'est pas une extension du pipeline hebdomadaire actuel (cf. `doc/architecture.md`).

## État actuel du code

on part de zéro

## Sources de données retenues

| Source | Statut | Coût |
|---|---|---|
| Flux RSS (Reuters, BBC, Le Monde, etc.) | Intégré | Gratuit |
| GDELT Project | À intégrer | Gratuit |
| Reddit API | À intégrer | Gratuit (tier de base) |
| Alpha Vantage (news sentiment + données marché) | Optionnel, non câblé à un bloc du pipeline actuel (cf. `doc/architecture.md`) | Gratuit en tier de base |
| yfinance (données marché pour scoring d'impact) | Non-objectif actuel du pipeline détection (incompatible avec le batch hebdomadaire, cf. `doc/architecture.md`) — reste dans la feuille de route long terme du projet, pas de ce pipeline | Gratuit |
| Datasets ML : LIAR, FakeNewsNet, ISOT | À utiliser pour entraînement | Gratuit |

## Budget indicatif estimé

- Phase prototype actuelle : 0 à 20€/mois
- Phase avec Reddit + fine-tuning ML (Colab) : 50 à 150€/mois
- Pas de poste Twitter/X à budgétiser (abandonné)
- Le volume collecté n'étant pas plafonné (cf. `doc/userstories_scraper.md`), le poste de coût variable (appels LLM, US-07 évaluateur) est maîtrisé via un plafond d'appels par run hebdomadaire, pas via une limite de collecte (cf. `doc/userstories_évaluateur.md`).

## Prochaines étapes identifiées

1. Ajouter un module Reddit au script (r/wallstreetbets, r/stocks, r/investing pour la finance ; r/worldnews, r/news pour l'actualité générale) en parallèle du RSS
2. Construire un premier dataset labellisé (LLM en ligne pour bootstrap + datasets publics)
3. Fine-tuner un modèle léger (BERT/RoBERTa) sur ce dataset
4. Concevoir, séparément du pipeline détection actuel, le module de scoring d'impact marché (corrélation news/mouvement de prix via yfinance) — nécessite sa propre architecture temps réel, pas une extension du pipeline batch hebdomadaire (cf. `doc/architecture.md`)
5. Backtesting des stratégies de trading (backtrader/vectorbt) avant toute exécution réelle
6. Automatiser le rapport hebdomadaire via GitHub Actions (workflow planifié, cf. `doc/architecture.md` et `doc/plan_implementation.md`)
