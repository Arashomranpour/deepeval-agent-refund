import os
import sys
from pathlib import Path

# Tests never touch the real ticket store (SQLite file or Azure Table).
os.environ["TICKETS_BACKEND"] = "memory"
os.environ.pop("AZURE_TABLES_ENDPOINT", None)

ROOT = Path(__file__).resolve().parents[1]
for folder in ("agent", "evaluations", "app_pages"):
    path = str(ROOT / folder)
    if path not in sys.path:
        sys.path.insert(0, path)
