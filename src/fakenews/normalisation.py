"""Canonicalisation d'URL et hachage de contenu — infrastructure neutre, au même
titre que `fakenews.config`, `fakenews.db` et `fakenews.llm`.

Vivait dans `fakenews.scraper` tant que la collecte automatique était le seul
producteur d'articles. La V3 en ajoute un second : le frontend, qui canonicalise
l'URL d'une proposition pour la dédupliquer contre les articles déjà collectés
(cf. doc/V3/userstories_crowdsourcing.md US-01).

Les deux DOIVENT canonicaliser à l'identique — sinon la déduplication ne compare
plus rien, et un article déjà analysé peut être reproposé indéfiniment. Or
`doc/V0/architecture.md` pose que « les blocs ne s'appellent pas entre eux
directement » : le frontend ne peut pas importer le scraper. Même dilemme que le
seuil de suspicion, même issue (cf. `fakenews.config`) — un module
d'infrastructure partagé, qui n'appartient à aucun bloc. La duplication, elle,
était impossible ici : deux implémentations qui divergent d'un caractère font
diverger toute la déduplication.
"""

import hashlib
from urllib.parse import urlsplit, urlunsplit


def canonicaliser_url(url: str) -> str:
    """Normalise une URL pour la déduplication : retire query string et fragment,
    scheme/host en minuscules (US-05 scraper)."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, "", ""))


def hacher_contenu(titre: str, contenu: str) -> str:
    return hashlib.sha256(f"{titre}\n{contenu}".encode("utf-8")).hexdigest()
