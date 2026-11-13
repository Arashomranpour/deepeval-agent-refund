"""Glass UI layer for the Streamlit app: gradient backdrop + frosted cards."""

import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --glass-bg: rgba(255, 255, 255, 0.055);
  --glass-bg-strong: rgba(255, 255, 255, 0.085);
  --glass-border: rgba(255, 255, 255, 0.12);
  --glass-shadow: 0 8px 32px rgba(3, 6, 20, 0.45);
  --accent: #7c9cff;
  --accent-2: #5eead4;
  --text-muted: #a3acc7;
}

html, body, [class*="css"], .stMarkdown, .stText, button, input, textarea {
  font-family: 'Inter', system-ui, sans-serif !important;
}
code, pre, .stCode { font-family: 'JetBrains Mono', ui-monospace, monospace !important; }

/* Backdrop: deep navy with slow-drifting colour glows. */
[data-testid="stAppViewContainer"] {
  background:
    radial-gradient(900px 600px at 10% -10%, rgba(124, 156, 255, 0.28), transparent 60%),
    radial-gradient(800px 500px at 100% 10%, rgba(94, 234, 212, 0.16), transparent 60%),
    radial-gradient(700px 600px at 50% 120%, rgba(168, 85, 247, 0.18), transparent 60%),
    #0b1020;
  background-attachment: fixed;
}
[data-testid="stHeader"] { background: transparent; }

/* Sidebar as a frosted panel. */
[data-testid="stSidebar"] {
  background: rgba(14, 20, 40, 0.55) !important;
  backdrop-filter: blur(18px) saturate(140%);
  -webkit-backdrop-filter: blur(18px) saturate(140%);
  border-right: 1px solid var(--glass-border);
}

/* Cards: bordered containers, metrics, expanders, chat bubbles, forms, tables. */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) ,
[data-testid="stMetric"],
[data-testid="stExpander"] details,
[data-testid="stChatMessage"],
[data-testid="stForm"],
[data-testid="stDataFrame"],
[data-testid="stVegaLiteChart"] {
  background: var(--glass-bg);
  border: 1px solid var(--glass-border) !important;
  border-radius: 16px;
  box-shadow: var(--glass-shadow);
  backdrop-filter: blur(14px) saturate(130%);
  -webkit-backdrop-filter: blur(14px) saturate(130%);
}
[data-testid="stMetric"] { padding: 18px 20px; transition: transform .2s ease, border-color .2s ease; }
[data-testid="stMetric"]:hover { transform: translateY(-2px); border-color: rgba(124, 156, 255, 0.45) !important; }
[data-testid="stMetricLabel"] { color: var(--text-muted); text-transform: uppercase; letter-spacing: .06em; font-size: .75rem; }
[data-testid="stMetricValue"] { font-weight: 700; }
[data-testid="stChatMessage"] { padding: 14px 18px; margin-bottom: 10px; }
[data-testid="stVegaLiteChart"] { padding: 12px; }
[data-testid="stExpander"] details summary:hover { color: var(--accent); }

/* Buttons: glass with a gradient edge on hover; primary gets the accent gradient. */
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {
  background: var(--glass-bg-strong);
  border: 1px solid var(--glass-border);
  border-radius: 12px;
  color: #e8ecf8;
  backdrop-filter: blur(10px);
  transition: all .2s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px rgba(124, 156, 255, .35), 0 6px 20px rgba(124, 156, 255, .18);
  transform: translateY(-1px);
}
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {
  background: linear-gradient(135deg, #7c9cff, #a78bfa) !important;
  border: none !important;
  color: #0b1020 !important;
  font-weight: 600;
}

/* Inputs. */
[data-testid="stChatInput"], .stTextInput input, [data-baseweb="select"] > div {
  background: rgba(255, 255, 255, 0.06) !important;
  border-radius: 12px !important;
  backdrop-filter: blur(10px);
}

/* Hero header. */
.hero { padding: 6px 0 18px 0; }
.hero .eyebrow {
  display: inline-block; padding: 4px 12px; border-radius: 999px;
  background: rgba(124, 156, 255, .14); border: 1px solid rgba(124, 156, 255, .35);
  color: #c7d2ff; font-size: .75rem; letter-spacing: .08em; text-transform: uppercase; font-weight: 600;
}
.hero h1 {
  margin: 10px 0 6px 0; font-size: 2.3rem; font-weight: 700; line-height: 1.15;
  background: linear-gradient(90deg, #ffffff 0%, #c7d2ff 45%, #5eead4 100%);
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.hero p { color: var(--text-muted); margin: 0; font-size: 1rem; }
.chips { margin-top: 12px; display: flex; flex-wrap: wrap; gap: 8px; }
.chip {
  padding: 4px 10px; border-radius: 999px; font-size: .78rem; color: #dbe2ff;
  background: rgba(255, 255, 255, .06); border: 1px solid var(--glass-border);
}
</style>
"""


def apply_glass_theme() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def hero(eyebrow: str, title: str, subtitle: str, chips: list[str] | None = None) -> None:
    chip_html = "".join(f'<span class="chip">{c}</span>' for c in chips or [])
    st.markdown(
        f'<div class="hero"><span class="eyebrow">{eyebrow}</span><h1>{title}</h1>'
        f'<p>{subtitle}</p><div class="chips">{chip_html}</div></div>',
        unsafe_allow_html=True,
    )
