# User Stories — Crowdsourcing (V3)

> **Statut : intention, non implémenté.** Ce document décrit ce qu'on veut
> apporter. Le séquencement, le schéma et les fichiers touchés sont dans
> `doc/V3/plan_implementation_crowdsourcing.md`.
>
> Numérotation : la verticale finance occupe la « V2 » et ses incréments 2.1/2.2+
> (cf. `doc/V1/2.1-liste-actifs-et-annotation.md`). Le crowdsourcing est un axe
> orthogonal — il ne dépend d'aucun incrément finance et n'en conditionne aucun —
> d'où une « V3 » distincte plutôt qu'un 2.x. À corriger si tu préfères un autre
> schéma.

Demandé par l'utilisateur le 2026-09-10. Concrétise trois points laissés ouverts
par `doc/V1/roadmap.md` : « soumission d'articles par les utilisateurs » (axe 1),
« commenter un article évalué » (axe 2), et l'accueil de ces fonctionnalités dans
le frontend (axe 4). C'est aussi le moment où la fondation « comptes à 3 rôles »
(`doc/V1/comptes-3-roles.md`) cesse d'être décorative : le rôle
`contributeur` reçoit enfin une capacité que `spectateur` n'a pas.

Périmètre : la participation humaine au pipeline — proposer un article à
analyser, décider ce qui entre, commenter une analyse rendue. **Le pipeline
d'analyse lui-même (scraper, évaluateur, contextualiseur) n'est pas modifié** :
une proposition acceptée devient un article ordinaire, qui suit exactement le
parcours des articles collectés automatiquement.

---

## Ce que cette version change dans les contrats existants

Trois règles écrites en V0/V1 ne survivent pas telles quelles. Les acter ici
plutôt que les laisser se contredire en silence :

| Règle | Où elle est écrite | Ce qu'elle devient |
|---|---|---|
| « Le frontend ne fait **aucune écriture** sur le stockage partagé » | `doc/V0/architecture.md`, `userstories_frontend.md` US-04 | Le frontend écrit désormais trois tables : `propositions`, `commentaires`, `comptes`. Il n'écrit **jamais** `articles`, `scores` ni `mise_en_contexte` — le verdict reste produit par le pipeline seul. Décision détaillée dans `architecture.md`. |
| « L'utilisateur ne voit jamais son statut » | `doc/V1/comptes-3-roles.md` | Un contributeur voit un accès que le spectateur n'a pas. Le rôle devient visible **par ses capacités**, ce qui est le but ; il n'est toujours pas affiché comme une étiquette. |
| « Le mot de passe partagé suffit pour spectateur et contributeur » | `doc/V1/comptes-3-roles.md` | Un contributeur a désormais un **code personnel obligatoire**, imposé par contrainte SQL. `comptes-3-roles.md` prévenait déjà que ce serait le préalable à toute capacité réservée. |

---

## US-01 — Proposer un article à analyser

**En tant que** compte connecté (spectateur inclus),
**je veux** soumettre l'URL d'un article que je juge suspect,
**afin qu'**il soit analysé par le pipeline sans dépendre de ce que les flux RSS
et Reddit ont ramené d'eux-mêmes.

**Critères d'acceptation :**
- Le formulaire demande une **URL** (obligatoire) et une **note libre**
  facultative : pourquoi le proposant le trouve suspect.
- L'URL est validée avant enregistrement : schéma `http`/`https` uniquement,
  longueur bornée, canonicalisation par la fonction existante
  (`scraper.normalisation.canonicaliser_url`) — la même que la collecte
  automatique, pour que les déduplications parlent le même langage.
- Si l'URL canonique correspond à un **article déjà en base**, la proposition
  n'est pas créée : le proposant est renvoyé vers la fiche existante. Proposer un
  article déjà analysé ne doit pas produire un doublon silencieux.
- Si l'URL canonique correspond à une **proposition déjà en attente**, idem : on
  le dit, on n'empile pas.
- La proposition est enregistrée avec le pseudo du proposant, la date, et le
  statut initial `en_attente`.
- Le nombre de propositions par compte et par fenêtre de temps est **plafonné**
  (valeur configurable) : sans cela, un seul compte remplit la file d'attente et
  rend le travail des contributeurs impraticable.
- Le proposant peut consulter l'état de ses propres propositions (cf. US-05).

**Non-objectif :** proposer un contenu (texte collé, capture d'écran) plutôt
qu'une URL. Le pipeline sait analyser une page qu'il peut aller chercher ; il ne
sait rien faire d'un texte sans origine vérifiable, et la réputation de source
(US-01 évaluateur) comme la source primaire (US-04 évaluateur) perdraient leur
ancrage.

---

## US-02 — File d'attente des propositions

**En tant que** contributeur,
**je veux** consulter la liste des articles proposés en attente de décision,
**afin de** filtrer ce qui mérite de consommer une analyse.

**Critères d'acceptation :**
- L'accès est **réservé aux rôles `contributeur` et `superadmin`**. Un spectateur
  qui atteint l'URL directement reçoit un refus, pas seulement un lien masqué
  dans le gabarit : la garde est côté serveur, l'absence de lien n'est qu'un
  confort d'interface.
- La liste affiche : URL proposée, pseudo du proposant, note libre, date, statut.
- Les propositions `en_attente` sont présentées en premier ; les décisions
  passées restent consultables (traçabilité — qui a accepté quoi, et quand).
- La liste est paginée sur le même principe que la liste d'articles (US-01
  frontend), avec un ordre stable départagé par identifiant.

---

## US-03 — Accepter ou refuser une proposition

**En tant que** contributeur,
**je veux** accepter une proposition pour l'envoyer à l'analyse, ou la refuser
avec un motif,
**afin d'**exercer le rôle qui m'est confié : décider ce qui entre dans la base.

**Critères d'acceptation :**
- **Accepter** fait passer la proposition à `acceptee`, avec le pseudo du
  décideur et la date. L'article n'existe pas encore à ce moment : l'acceptation
  est une autorisation d'entrée, pas une collecte (cf. US-04).
- **Refuser** exige un **motif** (texte court, obligatoire), visible par le
  proposant. Un refus sans raison est un mur, pas une décision.
- Une proposition déjà décidée ne peut pas être re-décidée en V3.0. Revenir sur
  une décision se fait en base, comme la gestion des comptes aujourd'hui.
- Un contributeur **peut** décider d'une proposition qu'il a lui-même soumise —
  le superadmin est aussi contributeur et proposera. Le couple
  (proposant, décideur) est tracé, ce qui rend le cas visible sans l'interdire.
- Chaque décision est journalisée côté serveur, au même titre que les décisions
  du pipeline.

---

## US-04 — Entrée d'une proposition acceptée dans le pipeline

**En tant que** pipeline d'analyse,
**je veux** collecter les articles dont l'entrée a été autorisée par un
contributeur,
**afin qu'**ils reçoivent exactement le même traitement que les articles
collectés automatiquement.

**Critères d'acceptation :**
- La collecte est faite **par le pipeline batch, jamais par le frontend**. Aller
  chercher une URL fournie par un utilisateur depuis la fonction serverless qui
  sert le site l'exposerait à servir de relais vers des ressources qu'elle seule
  peut atteindre ; le runner GitHub Actions, lui, n'a rien d'intéressant à
  atteindre. Cette séparation est la mesure de sécurité, pas une préférence
  d'organisation.
- L'article créé porte `plateforme = 'proposition'` (nouvelle valeur autorisée),
  `domaine_source` = hôte de l'URL, et une métadonnée renvoyant à la proposition
  d'origine et à son proposant.
- Le succès fait passer la proposition à `collectee` et l'associe à l'article
  créé. L'article suit ensuite le parcours normal : évaluateur, puis
  contextualiseur s'il dépasse le seuil.
- Un échec de collecte (page inaccessible, contenu vide, format non exploitable)
  fait passer la proposition à `echec_collecte` avec un motif, **sans interrompre
  le traitement des autres** — « dégrader, jamais bloquer » (`architecture.md`)
  s'applique ici comme aux flux RSS.
- Le nombre de propositions collectées par run est plafonné (valeur
  configurable), au même titre que les autres plafonds du pipeline.
- **Tant que le pipeline hebdomadaire reste en pause** (le `schedule` est
  commenté, cf. `README.md`), une proposition acceptée demeure en attente
  d'analyse. L'interface doit l'afficher tel quel — « acceptée, en attente du
  prochain run » — et jamais laisser croire à un traitement immédiat. Une file
  d'attente qui ment sur son délai est pire qu'une file d'attente lente.

---

## US-05 — Espace compte

**En tant que** compte connecté,
**je veux** un espace personnel où retrouver mes propositions et, si j'ai un code
personnel, le changer moi-même,
**afin de** ne pas dépendre d'une intervention en base pour gérer mon accès.

**Critères d'acceptation :**
- L'espace affiche **mes propositions** et leur statut, motif de refus compris.
- Un compte doté d'un code personnel (contributeur, superadmin) peut le
  **changer** : le formulaire exige le **code actuel**, puis le nouveau code
  saisi deux fois.
- Le nouveau code est soumis à des bornes explicites (longueur minimale, longueur
  maximale) et **doit accepter tout caractère saisissable**, accents compris.
  Cette exigence n'est pas cosmétique : la comparaison de mots de passe actuelle
  lève une erreur serveur sur une chaîne non-ASCII (cf. `doc/audit/`, phase 14,
  F2). Ouvrir un écran où l'utilisateur choisit son mot de passe **avant** d'avoir
  corrigé ce point revient à lui offrir un moyen de verrouiller son compte.
- Le changement de code **invalide les sessions existantes** de ce pseudo — c'est
  déjà le comportement mécanique (la clé de signature du cookie dérive de
  `secret_hash`, cf. `comptes-3-roles.md`), il est ici érigé en propriété voulue
  et testée.
- Un spectateur, qui utilise le mot de passe partagé, ne se voit pas proposer de
  changement de code : il n'en a pas. Son espace se limite à ses propositions.

---

## US-06 — Nommer un contributeur

**En tant que** superadmin,
**je veux** promouvoir un compte existant au rôle de contributeur, et le
rétrograder,
**afin de** choisir qui décide de ce qui entre dans la base.

**Critères d'acceptation :**
- L'accès est réservé au `superadmin`. Le superadmin possède **toutes** les
  capacités du contributeur : les gardes raisonnent en « au moins ce niveau »,
  jamais en égalité stricte de rôle.
- La promotion pose un **code provisoire**, affiché **une seule fois** au
  superadmin pour transmission hors ligne. Le contributeur est invité à le
  changer dans son espace (US-05).
- Une **contrainte de schéma** garantit qu'un `contributeur` ne peut pas exister
  sans code personnel — extension exacte de `ck_comptes_superadmin_a_un_code`,
  qui protège déjà le superadmin. Sans elle, le mot de passe partagé suffirait à
  obtenir le rôle, et la capacité d'accepter des articles serait ouverte à
  quiconque connaît ce mot de passe. La règle doit vivre dans la base, pas dans
  la discipline de celui qui écrit l'`UPDATE`.
- La rétrogradation ramène le compte à `spectateur` et efface son code personnel
  (il retombe sur le mot de passe partagé), ce qui invalide ses sessions.
- La gestion en SQL direct reste possible et documentée — l'écran ne la remplace
  pas, il évite d'y recourir pour l'opération courante.

---

## US-07 — Existence des comptes

**En tant que** superadmin,
**je veux** que les comptes qui se connectent existent en base,
**afin de** pouvoir choisir un contributeur *parmi les comptes* plutôt que de
deviner des pseudos.

**Critères d'acceptation :**
- À la **première connexion réussie**, un pseudo inconnu est enregistré avec le
  rôle `spectateur`. C'est le seul cas où le frontend crée une ligne de compte.
- La table reste la source de vérité du rôle : un pseudo enregistré sans rôle
  particulier se comporte exactement comme aujourd'hui.
- **Limite connue, à documenter dans l'interface du superadmin :** tant qu'un
  compte n'a pas de code personnel, son pseudo n'est **pas une identité
  vérifiée** — toute personne connaissant le mot de passe partagé peut occuper un
  pseudo libre. La promotion referme cette porte pour le compte promu (le mot de
  passe partagé cesse de lui donner accès), mais elle ne dit rien de ce que le
  pseudo a fait avant. Un superadmin qui promeut le fait sur la foi d'un échange
  hors ligne, pas sur la foi de la table.

---

## US-08 — Commenter l'analyse d'un article

**En tant que** compte connecté,
**je veux** ajouter un commentaire sur la page d'un article analysé,
**afin d'**apporter un contexte, une correction ou un désaccord que le pipeline
automatique n'a pas vu.

**Critères d'acceptation :**
- Tout compte connecté peut commenter, spectateurs compris. La publication est
  immédiate.
- Un commentaire affiche : pseudo de l'auteur, date, texte. Longueur bornée
  (valeur explicite dans le code), texte échappé à l'affichage.
- Les commentaires apparaissent sur la page de détail de l'article, **sous**
  l'analyse et la mise en contexte, jamais mêlés à elles : ce que dit un visiteur
  et ce que dit le système ne doivent pas se confondre visuellement.
- L'avertissement automatisé (US-04 contextualiseur) reste affiché sans
  changement. Un commentaire n'est pas un verdict du système, et le système ne
  reprend pas un commentaire à son compte.
- Le **superadmin peut retirer** un commentaire. Le retrait le masque au public
  mais **conserve la trace** (contenu, auteur, date, qui a retiré et quand) :
  sur un site qui publie des verdicts nommant des médias, un contenu retiré pour
  raison juridique doit rester consultable par le porteur du projet, pas
  s'évaporer.
- Le nombre de commentaires par compte et par fenêtre de temps est plafonné.

**Non-objectif explicite — les commentaires n'influencent pas le score.**
`doc/V1/roadmap.md` évoquait « influer sur le score (mécanisme à définir) ».
Ce n'est pas fait ici, et pas par oubli : le score composite est une moyenne
pondérée de signaux traçables (US-08 évaluateur), dont chaque contribution est
persistée et explicable. Y injecter un vote humain non authentifié le rendrait
manipulable par quiconque connaît le mot de passe partagé, et retirerait au
`detail_calcul` sa propriété d'être reconstituable. Si un retour humain doit
peser un jour, ce sera un **signal à part entière**, avec sa valeur, sa raison et
son `preuve_id`, décidé dans sa propre user story.

---

## Exigences transverses

Elles ne sont pas des « détails d'implémentation » : chacune conditionne
l'acceptation des US ci-dessus.

- **Autorisation centralisée.** Une garde par capacité (`proposer`, `decider`,
  `administrer`), résolue côté serveur, jamais une comparaison de rôle recopiée
  dans les gabarits. Un test doit vérifier que chaque route d'écriture refuse le
  rôle insuffisant, y compris en accès direct à l'URL.
- **Protection CSRF sur toutes les écritures.** Jusqu'ici le seul formulaire du
  site était la connexion, où un CSRF n'a pas d'intérêt pour l'attaquant. Avec
  des actions qui engagent le compte (accepter un article, publier un
  commentaire, changer un code), un jeton anti-CSRF devient obligatoire.
  `samesite=lax` sur le cookie de session réduit la surface, il ne la ferme pas.
- **Plafonds d'écriture.** Propositions et commentaires par compte et par
  fenêtre ; sans eux, un compte suffit à rendre la file inutilisable.
- **Le mot de passe partagé devient un pouvoir d'écriture.** Il n'ouvrait qu'une
  consultation ; il ouvrira la proposition et le commentaire. Le plafond
  anti-bruteforce de `/login` doit être opposable **avant** cette mise en
  service — aujourd'hui il n'oppose aucune friction (60 essais mesurés en 0,10 s,
  cf. `doc/audit/`, phase 14, F4).
- **RGPD.** Les commentaires sont du texte rédigé par des personnes identifiables
  par leur pseudo, conservé sans durée définie. `architecture.md` classe le sujet
  hors périmètre prototype ; cette version le rapproche nettement, et le
  mécanisme de retrait d'US-08 en est le premier élément concret. À rouvrir avant
  toute ouverture publique.

---

## Hors périmètre (pour rappel)

- **Auto-inscription ouverte** : personne ne crée de compte sans connaître le mot
  de passe partagé. US-07 enregistre un pseudo déjà authentifié, il n'ouvre rien.
- **Notifications** (courriel, alerte) sur décision ou réponse.
- **Édition ou suppression d'un commentaire par son auteur**, fils de discussion,
  réponses, votes.
- **Proposition de contenu** (texte, image) plutôt qu'URL — cf. US-01.
- **Retour humain pesant sur le score** — cf. US-08, non-objectif explicite.
- **Interface de gestion fine des comptes** au-delà de promouvoir/rétrograder :
  le reste continue de se faire en SQL (`comptes-3-roles.md`).
