# Architecture — Projet Fake News & Trading Algorithmique

## Vue d'ensemble

Le système est découpé en 4 blocs, chacun avec une responsabilité et un rythme de vie propre :

```
Scraper  -->  Évaluateur  -->  Contextualiseur  -->  Frontend
   |               |                  |                 |
   +---------------+------------------+-----------------+
                            |
              Stockage partagé (Supabase / PostgreSQL)
```

| Bloc | Rôle | Fréquence |
|---|---|---|
| Scraper | Collecte les articles bruts (RSS, GDELT, Reddit...) | Hebdomadaire |
| Évaluateur | Calcule les signaux US-01 à US-07 et le score composite US-08 | À chaque exécution hebdomadaire, sur les nouveaux articles collectés |
| Contextualiseur | Explique pourquoi un article suspect est faux et quelle est la réalité | Uniquement sur les articles au-dessus du seuil de suspicion |
| Frontend | Consultation des fake news identifiées et de leur mise en contexte | À la demande (lecture seule) |

---

## Décision — Style d'architecture : pipeline batch, pas microservices/événementiel

**Choix retenu :** un pipeline séquentiel classique (4 étapes qui lisent/écrivent dans un stockage partagé), pas une architecture événementielle avec services séparés communiquant en HTTP/queues.

**Pourquoi :**
- Le rythme du projet est un scan hebdomadaire (cf. `fiche-projet-fake-news-trading.md`), pas du temps réel : rien ne justifie l'overhead d'une architecture événementielle.
- Projet solo en phase prototype (budget 0-20€/mois) : la complexité opérationnelle (déploiement, supervision de plusieurs services) n'a pas de contrepartie utile ici.
- Un pipeline batch reste simple à faire tourner, déboguer et faire évoluer seul, tout en gardant les 4 blocs découplés.

---

## Décision — Contrat entre étapes : la base de données, pas des appels directs

Les blocs ne s'appellent pas entre eux directement. Chaque étape lit ce dont elle a besoin dans le stockage partagé et y écrit son résultat :

- **Scraper** écrit les articles bruts (contenu, domaine source, date, métadonnées).
- **Évaluateur** lit les articles non encore scorés, écrit les sous-scores (US-01 à US-07), leurs justifications tracées, et le score composite final (US-08).
- **Contextualiseur** lit les articles dont le score final dépasse le seuil de suspicion, écrit son explication (en quoi l'info est fausse + quelle est la réalité).
- **Frontend** lit l'ensemble en lecture seule (articles + scores + mise en contexte).

**Pas de rescoring en v1 :** un article n'est scoré qu'une seule fois, jamais recalculé ensuite. C'est une limite acceptée pour cette première version simple, pas un oubli : plusieurs signaux (corroboration, fact-checking, décalage Reddit/presse) sont des instantanés temporels qui pourraient en théorie être invalidés par une preuve arrivant plus tard, mais rejouer le scoring périodiquement est un chantier à part (versioning des scores, détection des articles à revoir) qui n'est pas nécessaire pour une v1. Mitigation retenue à la place : l'avertissement automatisé systématique sur chaque verdict (US-04 contextualiseur, US-04 frontend) rappelle son caractère provisoire et automatisé plutôt que définitif.

**Pourquoi :**
- Découplage total : chaque étape peut tourner indépendamment, être relancée sans rejouer les précédentes, ou changer de technologie sans impacter les autres.
- Traçabilité et historique obtenus "gratuitement" — cohérent avec l'exigence de traçabilité déjà posée dans chaque user story de l'évaluateur.
- Pas de couplage temporel : pas besoin que les 4 blocs tournent en même temps.

**Stockage retenu :** Supabase (PostgreSQL managé, tier gratuit). Remplace le choix initial SQLite : un fichier SQLite local n'est accessible que depuis la machine qui l'héberge, ce qui bloquait tout accès distant pour un frontend hébergé (cf. décision de topologie de déploiement ci-dessous). Supabase donne un Postgres accessible en réseau sans serveur à administrer soi-même, pour un coût nul en phase prototype — cohérent avec le budget serré et avec l'usage mono-utilisateur/pas d'écriture concurrente qui justifiait SQLite au départ.

---

## Décision — Topologie de déploiement : Vercel + GitHub + Supabase

**Choix retenu :**
- **Supabase** héberge le stockage partagé (PostgreSQL, cf. décision ci-dessus) — accessible aussi bien depuis un job de collecte que depuis le frontend hébergé.
- **Vercel** héberge le frontend (déploiement à chaque push sur `main`), qui lit Supabase directement (accès réseau natif, plus de distinction "chemin local vs. distant" à gérer côté frontend).
- **GitHub** héberge le code et sert de déclencheur : le pipeline batch hebdomadaire (scraper → évaluateur → contextualiseur) tourne via un workflow GitHub Actions planifié (`schedule: cron`), qui écrit dans Supabase. Pas de serveur à faire tourner en permanence pour un job qui ne s'exécute qu'une fois par semaine.
- **Render : repli uniquement**, à éviter par défaut à cause du temps de démarrage (cold start) de ses instances gratuites. À n'envisager que si GitHub Actions s'avère insuffisant pour le pipeline batch (ex. dépassement de la durée max d'un job, besoin d'un processus persistant) — pas un choix par défaut.

**Pourquoi :** cette topologie répond directement à la question laissée ouverte par le choix initial "SQLite + frontend hébergé" (comment un frontend public accède-t-il au fichier produit par un job tournant on ne sait où) : le stockage est désormais nativement accessible en réseau, le frontend et le batch sont hébergés séparément mais parlent au même Supabase, et rien ne tourne en continu — cohérent avec le style pipeline batch retenu plus haut et avec le budget 0-20€/mois de la phase prototype.

---

## Décision — Gestion des erreurs des intégrations externes : dégrader, jamais bloquer

**Choix retenu :** toute intégration externe (RSS, Reddit, GDELT, Google Fact Check Tools, SEC EDGAR, LLM) applique le même pattern en cas d'échec (indisponibilité, rate-limit, timeout, réponse malformée) : l'échec est journalisé, le signal ou la source concernée est marqué non disponible/exclu, et le pipeline continue avec les autres sources et signaux plutôt que de s'interrompre.

**Pourquoi :** le pipeline tourne en autonomie hebdomadaire sans supervision humaine immédiate ; une intégration externe indisponible ne doit jamais empêcher la production d'un score partiel. C'est déjà le comportement défini pour le repli Reuters (US-01 scraper) — ce principe est généralisé à toutes les intégrations plutôt que traité au cas par cas dans chaque user story.

---

## Décision — Évaluateur : geler l'interface, pas l'implémentation

L'évaluateur expose une interface stable, indépendante du moteur utilisé pour chaque signal :

```
evaluer(article) -> {
  score_final,           # US-08
  sous_scores: {
    reputation,          # US-01
    corroboration,       # US-02
    fact_checking,       # US-03
    source_primaire,     # US-04
    style,               # US-05
    decalage_viral,      # US-06
    llm_bootstrap,       # US-07
  },
  justifications: {       # traçabilité par signal
    reputation:      {valeur, raison, preuve_id: "reputation"},
    corroboration:   {valeur, raison, preuve_id: "corroboration:<cluster_id>"},
    fact_checking:   {valeur, raison, preuve_id: "fact_checking:<url_claimreview>" | "fact_checking"},
    source_primaire: {valeur, raison, preuve_id: "source_primaire:<accession_sec_edgar>" | "source_primaire"},
    style:           {valeur, raison, preuve_id: "style"},
    decalage_viral:  {valeur, raison, preuve_id: "decalage_viral:<cluster_id>"},
    llm_bootstrap:   {valeur, raison, preuve_id: "llm_bootstrap"},
  }
}
```

Chaque signal (US-01 à US-06) et l'agrégateur (US-08) sont des modules indépendants derrière cette interface. US-07 (scoring LLM en ligne) est un module de scoring parmi d'autres, pas un cas particulier architectural.

`preuve_id` est une chaîne stable par signal : le nom du signal seul quand la "preuve" est le jugement propre de l'évaluateur (réputation, style, LLM bootstrap), complétée par une référence externe vérifiable quand elle existe (URL ClaimReview pour le fact-checking, numéro d'accession SEC EDGAR pour la source primaire, identifiant de cluster GDELT/similarité pour la corroboration et le décalage viral). C'est ce `preuve_id` que le contextualiseur (US-02) doit citer pour qu'un item de `faits_traces` soit accepté — cf. `userstories_contextualiseur.md`.

**Pourquoi :** le projet vise explicitement à remplacer le LLM bootstrap par un modèle maison fine-tuné (BERT/RoBERTa/DistilBERT, cf. `fiche-projet-fake-news-trading.md`). Geler l'interface permet de faire ce remplacement comme un simple swap d'implémentation du module `llm_bootstrap`, sans toucher au reste de l'évaluateur ni au contrat de sortie consommé par le contextualiseur et le frontend. Ce remplacement (et l'ajustement des poids qui pourrait l'accompagner) reste hors périmètre pour l'instant — cf. `userstories_évaluateur.md`.

---

## Décision — Contextualiseur : déclenchement conditionnel, pas systématique

Le contextualiseur ne tourne que sur les articles dont le score final (US-08) dépasse un seuil de suspicion configurable — pas sur l'ensemble des articles scrapés.

**Pourquoi :**
- Un appel LLM d'explication (génération de texte plus longue) coûte plus cher qu'un appel de scoring court : le déclenchement conditionnel maîtrise le coût.
- Il n'a pas besoin de tout re-vérifier depuis zéro : il réutilise les éléments factuels déjà rassemblés par l'évaluateur (verdict Fact Check de US-03, absence de confirmation en source primaire de US-04) comme base de son explication, plutôt que de relancer une recherche complète.

---

## Décision — Frontend : commencer simple, migrer seulement si besoin

**Choix retenu pour la phase actuelle :** backend léger (FastAPI) servant des pages qui lisent directement la base de données, déployé sur Vercel. Pas de SPA (React/Vue) à ce stade.

**Pourquoi :**
- L'usage cible est de la consultation (lister les fake news identifiées, afficher leur mise en contexte) — pas d'interactivité riche qui justifierait une SPA.
- Une SPA ajoute un build, un état client, une complexité de déploiement sans valeur pour ce besoin.
- Vercel héberge aussi bien un usage de développement/test (URL de preview) que la version de référence hébergée (cf. `userstories_frontend.md` US-04) — le même déploiement sert les deux, sans architecture séparée. Le mode local (poste du développeur) reste possible pour itérer avant déploiement, mais n'a plus besoin de résoudre lui-même l'accès distant au stockage puisque Supabase est accessible en réseau dans les deux cas.

**Migration future :** si un besoin de multi-utilisateurs ou d'interactivité riche apparaît, le frontend peut être remplacé sans toucher au pipeline scraper/évaluateur/contextualiseur, puisqu'il ne fait que lire le stockage partagé.

---

## Ce que cette architecture NE couvre pas (pour rappel)

- Le fine-tuning du modèle maison et son intégration comme module `llm_bootstrap` alternatif — prévu mais pas détaillé ici, ni l'ajustement des poids US-08 qui pourrait en découler (cf. `userstories_évaluateur.md`, explicitement hors périmètre pour l'instant).
- **Non-objectif actuel : le module de scoring d'impact marché (yfinance) et les stratégies de trading.** Ce n'est pas un bloc "pas encore dessiné" dans le même schéma : le pipeline hebdomadaire batch décrit ici est structurellement incompatible avec une exécution de trading réactive (l'impact d'une fake news sur un marché se joue en minutes/heures, pas en semaines). Le score de suspicion produit ici pourra servir de signal d'entrée à un futur système de trading, mais celui-ci nécessitera sa propre architecture temps réel/événementielle, à concevoir séparément une fois le scoring validé — pas une extension de ce pipeline.
- Le passage à une architecture multi-services (au-delà de Vercel + GitHub Actions + Supabase) — à envisager seulement si un besoin de concurrence, de volumétrie ou de scaling dépassant le tier gratuit Supabase apparaît.
- **RGPD et droit de republication du contenu collecté** (articles protégés, bylines identifiables) : non traités en phase prototype. À traiter avant toute ouverture d'accès public non protégée — c'est une des raisons pour lesquelles l'accès hébergé reste derrière une authentification minimale tant que ce point n'est pas clos (cf. `userstories_frontend.md` US-04).
- **Politique de rétention/purge du stockage** : non définie en phase prototype (volumes attendus faibles vu le budget et l'usage mono-utilisateur). À revisiter si le volume hebdomadaire cumulé devient significatif.
