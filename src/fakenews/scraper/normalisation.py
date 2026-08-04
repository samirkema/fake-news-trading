import hashlib
from urllib.parse import urlsplit, urlunsplit


def canonicaliser_url(url: str) -> str:
    """Normalise une URL pour la déduplication : retire query string et fragment,
    scheme/host en minuscules (US-05 scraper)."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, "", ""))


def hacher_contenu(titre: str, contenu: str) -> str:
    return hashlib.sha256(f"{titre}\n{contenu}".encode("utf-8")).hexdigest()
