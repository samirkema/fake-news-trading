-- Correctif d'audit (finding M4) — traçabilité US-08 évaluateur.
--
-- US-08 exige : « La sortie trace la contribution de chaque signal individuel au
-- score final (poids appliqué + valeur), pas seulement le score agrégé. »
-- `calculer_score_composite` produisait déjà exactement cet objet (`detail`), et
-- run_evaluateur le jetait : la contribution n'était reconstituable qu'en
-- recroisant `sous_scores` et `poids` à la main. Cette colonne lui donne sa place.
--
-- Nullable : les scores calculés avant ce correctif n'ont pas de détail, et le
-- principe « pas de rescoring en v1 » (doc/V0/architecture.md) interdit de le
-- recalculer rétroactivement. NULL = « antérieur à la traçabilité explicite ».

alter table scores add column if not exists detail_calcul jsonb;

comment on column scores.detail_calcul is
    'Contribution de chaque signal au score final : {signal: {valeur, poids, exclu}} '
    '(US-08 évaluateur). NULL pour les scores calculés avant l''ajout de la colonne.';
