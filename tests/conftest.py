import os
import sys
from pathlib import Path

# Tests never touch the real ticket store (SQLite file or Azure Table).
os.environ["TICKETS_BACKEND"] = "memory"
os.environ.pop("AZURE_TABLES_ENDPOINT", None)

# Never read the developer's real .streamlit/secrets.toml (Clerk, admin, database) in tests;
# tests that need secrets set them on AppTest.secrets explicitly.
from streamlit import config as _st_config  # noqa: E402

_st_config.set_option("secrets.files", [str(Path(__file__).resolve().parent / "no-secrets.toml")])

ROOT = Path(__file__).resolve().parents[1]
for folder in ("agent", "evaluations", "app_pages"):
    path = str(ROOT / folder)
    if path not in sys.path:
        sys.path.insert(0, path)
