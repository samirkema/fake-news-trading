-- Correctif d'audit (phase 19, F19-03) — index sur l'ordre de traitement de
-- l'évaluateur.
--
-- Le correctif de F3 (audit phase 14) a déplacé la sélection des articles non
-- scorés d'un tri sur `date_publication` — indexée depuis 0001 — vers un tri sur
-- `date_collecte`, qui ne l'était pas. On a refermé une famine en ouvrant un
-- balayage complet à chaque run.
--
-- « Premier collecté, premier servi » est le bon ordre : il reste à le rendre
-- soutenable.

create index if not exists idx_articles_date_collecte on articles (date_collecte);
