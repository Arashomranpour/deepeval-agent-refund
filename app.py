"""Streamlit app: chat with the refund agent, and browse saved DeepEval results.

Run with:  uv run streamlit run app.py
"""

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

from glass import apply_glass_theme  # noqa: E402

apply_glass_theme()

pages = st.navigation([
    st.Page("app_pages/chat_page.py", title="Chat with the agent", icon="💬", default=True),
    st.Page("app_pages/results_page.py", title="Evaluation results", icon="📊"),
])
pages.run()
