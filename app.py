"""Streamlit app: chat with the refund agent, and browse saved DeepEval results.

Run with:  uv run streamlit run app.py
"""

import os
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
# The agent modules import each other as top-level modules (`from tools import ...`).
for folder in ("agent", "evaluations", "app_pages"):
    path = str(ROOT / folder)
    if path not in sys.path:
        sys.path.insert(0, path)

st.set_page_config(page_title="Refund Agent Evaluation", page_icon="🧾", layout="wide")

# Streamlit Community Cloud provides settings as secrets; the app reads them from the
# environment (like on Azure and with a local .env). The Groq key is NOT one of them:
# visitors always bring their own.
SECRET_SETTINGS = ("ADMIN_USERNAME", "ADMIN_PASSWORD", "DATABASE_URL", "AGENT_TODAY")
try:
    for name in SECRET_SETTINGS:
        if name in st.secrets and not os.environ.get(name):
            os.environ[name] = str(st.secrets[name])
except Exception:  # no secrets.toml: running locally with .env, on Azure, or in tests
    pass

from glass import apply_glass_theme  # noqa: E402

apply_glass_theme()

pages = st.navigation([
    st.Page("app_pages/chat_page.py", title="Chat with the agent", icon="💬", default=True),
    st.Page("app_pages/results_page.py", title="Evaluation results", icon="📊"),
    st.Page("app_pages/admin_page.py", title="Admin: refund tickets", icon="🔐"),
])
pages.run()
