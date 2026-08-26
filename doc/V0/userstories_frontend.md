# User Stories — Frontend

Périmètre : un site de consultation en lecture seule (local ou hébergé) des articles identifiés comme suspects par l'évaluateur et de leur mise en contexte produite par le contextualiseur, sans écriture sur le stockage partagé.

---

## US-01 — Liste des fake news identifiées

**En tant qu'** utilisateur,
**je veux** consulter la liste des articles dont le score de suspicion dépasse le seuil retenu, triée par score décroissant ou par date,
**afin d'**identifier rapidement les informations les plus suspectes de la semaine.

**Critères d'acceptation :**
- La liste affiche au minimum : titre, domaine source, date de publication, score composite final (US-08 évaluateur).
- La liste est filtrable par plage de dates et par score minimum.
- Seuls les articles au-dessus du seuil de suspicion (les mêmes que ceux traités par le contextualiseur) apparaissent par défaut ; un mode "tous les articles" optionnel permet aussi de voir les articles jugés fiables.

---

## US-02 — Détail d'un article : scores et justifications

**En tant qu'** utilisateur,
**je veux** consulter le détail des sous-scores (US-01 à US-07 évaluateur) et de leurs justifications tracées pour un article donné,
**afin de** comprendre pourquoi le système le considère comme suspect plutôt que de me fier au seul score final.

**Critères d'acceptation :**
- Chaque sous-score affiché est accompagné de sa justification telle que tracée par l'évaluateur.
- Le poids appliqué à chaque signal dans le calcul du score final (US-08 évaluateur) est visible.
- Un signal non applicable/neutre pour cet article est affiché comme tel, pas comme un score à 50 qui serait interprété à tort comme "moyennement suspect".

---

## US-03 — Mise en contexte affichée

**En tant qu'** utilisateur,
**je veux** consulter l'explication produite par le contextualiseur (en quoi l'article est faux, quelle est la réalité connue) directement sur la page de détail de l'article,
**afin d'**avoir une explication lisible plutôt que d'interpréter seul les scores bruts.

**Critères d'acceptation :**
- L'explication, les sources utilisées et l'avertissement sur la nature automatisée (US-04 contextualiseur) sont affichés ensemble, sans que l'un soit omis.
- Si aucune mise en contexte n'a été générée (article sous le seuil de déclenchement du contextualiseur), la page l'indique clairement plutôt que d'afficher une section vide sans explication.

---

## US-04 — Consultation en lecture seule, hébergé (le local sert au dev/test)

**En tant qu'** utilisateur,
**je veux** accéder aux résultats du pipeline via la version hébergée en ligne, qui est la version de référence,
**afin de** consulter les résultats sans dépendre de ma machine locale.

Le mode local n'est pas un second contexte d'usage à maintenir au même niveau : c'est un mode de développement/test pour itérer avant déploiement. Il n'a pas besoin de couvrir tous les critères ci-dessous (authentification, etc.) tant qu'il reste réservé au développeur.

**Critères d'acceptation :**
- Le frontend ne fait aucune écriture sur le stockage partagé (lecture seule stricte, conforme à `architecture.md`).
- Version hébergée : déployée sur Vercel, connectée à l'instance Supabase de production (cf. `architecture.md`, topologie de déploiement). Version locale/dev : même code, connecté soit à une instance Supabase de dev, soit à l'instance de prod en lecture — dans les deux cas la chaîne de connexion Supabase est externalisée (variable d'environnement/config), pas codée en dur.
- En version hébergée (accès public), l'accès est protégé par une authentification minimale (ex. mot de passe partagé) tant que le risque de diffamation lié à la publication de verdicts automatisés nommant des sources n'a pas été traité juridiquement. Ce traitement juridique relève du porteur du projet ; aucune échéance fixée, mais c'est une condition bloquante pour toute ouverture d'accès public non protégée — elle ne peut être levée que par une décision explicite du porteur du projet, pas par défaut.
- Chaque page affichant un score ou une mise en contexte reprend l'avertissement automatisé (US-04 contextualiseur) de façon visible, en version hébergée comme en local.

---

## Hors périmètre (pour rappel)

- L'authentification et le multi-utilisateurs ne sont pas couverts ici — usage mono-utilisateur pour l'instant (cf. `architecture.md`). **MàJ V1 (2026-08-26) :** une fondation « comptes à 3 rôles » (pseudo + mot de passe partagé) a depuis été posée, cf. `doc/V1/comptes-3-roles.md` ; aucune capacité n'y est encore conditionnée.
- Toute action d'écriture (validation manuelle, correction de score par un humain) n'est pas couverte — le frontend reste strictement en lecture seule à ce stade.
