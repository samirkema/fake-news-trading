"""Point d'entrée Vercel (fonction serverless Python) — expose l'app FastAPI du
frontend (cf. doc/architecture.md, topologie de déploiement)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fakenews.frontend.app import app  # noqa: E402
