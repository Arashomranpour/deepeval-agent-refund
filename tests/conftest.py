import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for folder in ("agent", "evaluations", "app_pages"):
    path = str(ROOT / folder)
    if path not in sys.path:
        sys.path.insert(0, path)
