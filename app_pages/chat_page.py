"""Chat page: talk to the refund agent with your own Groq API key."""

import logging
import time
from uuid import uuid4

import streamlit as st
from chat_auth import clerk_configured, display_name, sign_in_button, sign_out_button, signed_in
from groq import AuthenticationError, RateLimitError

from agent import build_agent, stream_reply
from data import users_data
from glass import hero
from models import AGENT_MODEL, make_llm, validate_api_key
from telemetry import agent_turn_span, setup_telemetry
from tools import STORE_TODAY

log = logging.getLogger("refund_app")
setup_telemetry()

MAX_MESSAGES = 20  # per browser session: protects visitors' own keys from runaway use
REPO_URL = "https://github.com/Arashomranpour/deepeval-agent-refund"

EXAMPLES = [
    "I am user123, I would like a refund for the book and the pen",
    "I am user126, I would like a refund for the backpack and water_bottle",
    "I am user999, I would like a refund for the book",
    "I would like to request a refund",
]


def forget_key() -> None:
    for key in ("agent", "thread_id", "history", "sent"):
        st.session_state.pop(key, None)


def new_conversation() -> None:
    st.session_state.thread_id = str(uuid4())
    st.session_state.history = []


def render_tools(tools: list[dict]) -> None:
    if not tools:
        return
    with st.expander(f"🔧 {len(tools)} tool call{'s' if len(tools) != 1 else ''}"):
        for t in tools:
            st.markdown(f"**`{t['name']}`**")
            st.json(t["args"], expanded=False)
            if t.get("output") is not None:
                st.code(str(t["output"]), language=None)


HERO = ("LangChain agent · Groq", "Refund support agent",
        "A tool-using LangChain agent that checks purchase history and the 30-day policy "
        "before issuing a refund. Watch each tool call live as it works.",
        [f"🧠 {AGENT_MODEL}", f"📅 store date {STORE_TODAY}", "🔧 4 tools", "🔑 bring your own key"])

USE_CLERK = clerk_configured()
if USE_CLERK:
    HERO[3].append("🔐 Clerk sign-in")

# --- Gate 1: sign in with Clerk (when configured). -----------------------------
if USE_CLERK and not signed_in():
    forget_key()  # a signed-out visitor never keeps an agent built from an earlier key
    hero(*HERO)
    _, middle, _ = st.columns([1, 2, 1])
    with middle:
        st.subheader("Sign in to chat with the agent")
        st.markdown("Sign in with your email, Google or GitHub account through Clerk. "
                    "The **Evaluation results** page is open to everyone.")
        sign_in_button()
    with st.sidebar:
        st.link_button("⭐ Source on GitHub", REPO_URL, use_container_width=True)
    st.stop()


def account_box() -> None:
    if USE_CLERK:
        st.caption(f"Signed in as **{display_name()}**")
        sign_out_button()


# --- Gate 2: nothing below runs until the visitor connects their own key. -----
if "agent" not in st.session_state:
    hero(*HERO)
    with st.sidebar:
        account_box()
        st.subheader("🔑 Connect your Groq API key")
        st.markdown(
            "Get a free key at [console.groq.com/keys](https://console.groq.com/keys). "
            "It stays in this browser session only and is never saved."
        )
        with st.form("api_key_form", clear_on_submit=True):
            key = st.text_input("Groq API key", type="password", placeholder="gsk_…")
            if st.form_submit_button("Connect", type="primary") and key:
                if error := validate_api_key(key):
                    st.error(error)
                else:
                    st.session_state.agent = build_agent(make_llm(key.strip()))
                    st.session_state.sent = 0
                    new_conversation()
                    st.rerun()
        st.link_button("⭐ Source on GitHub", REPO_URL, use_container_width=True)
    st.info("👈 Connect a Groq API key to start chatting. "
            "The **Evaluation results** page works without a key.")
    st.stop()

sent = st.session_state.setdefault("sent", 0)

# --- Sidebar -------------------------------------------------------------------
with st.sidebar:
    account_box()
    st.caption(f"Model: `{AGENT_MODEL}` on Groq")
    st.caption(f"Store date: **{STORE_TODAY}** (refunds allowed within 30 days)")
    st.progress(min(sent / MAX_MESSAGES, 1.0), text=f"{sent} / {MAX_MESSAGES} messages this session")
    st.button("New conversation", on_click=new_conversation, use_container_width=True)
    st.button("Forget key", on_click=forget_key, use_container_width=True)
    with st.expander("Demo customers"):
        for user, items in users_data.items():
            st.markdown(f"**{user}**: " + ", ".join(
                f"{name} (${item['price']}, {item['date']})" for name, item in items.items()))
    st.link_button("⭐ Source on GitHub", REPO_URL, use_container_width=True)

hero(*HERO)

for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        render_tools(msg.get("tools", []))

limit_reached = sent >= MAX_MESSAGES
if limit_reached:
    st.info(f"This session has used its {MAX_MESSAGES} messages. Reload the page to start a new session.")
prompt = st.chat_input("Ask about a refund…", disabled=limit_reached)
if not st.session_state.history and not prompt and not limit_reached:
    st.markdown("**Try one of these:**")
    cols = st.columns(2)
    for i, example in enumerate(EXAMPLES):
        if cols[i % 2].button(example, key=f"example_{i}", use_container_width=True):
            prompt = example

if prompt and not limit_reached:
    st.session_state.sent = sent + 1
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        status = st.status("Working on it…", expanded=True)
        answer_box = st.empty()
        answer, tools, by_id = "", [], {}
        started = time.perf_counter()
        config = {"configurable": {"thread_id": st.session_state.thread_id}}
        with agent_turn_span(st.session_state.thread_id, st.session_state.sent) as span:
            try:
                for kind, data in stream_reply(st.session_state.agent, prompt, config):
                    if kind == "token":
                        answer += data
                        answer_box.markdown(answer + "▌")
                    elif kind == "reset":
                        answer = ""
                        answer_box.empty()
                    elif kind == "tool_call":
                        by_id[data["id"]] = {"name": data["name"], "args": data["args"], "output": None}
                        tools.append(by_id[data["id"]])
                        status.write(f"🔧 Calling `{data['name']}`")
                    elif kind == "tool_result" and data["id"] in by_id:
                        by_id[data["id"]]["output"] = data["output"]
                        status.write(f"✅ `{by_id[data['id']]['name']}` returned")
            except RateLimitError:
                span.set_attribute("app.outcome", "rate_limited")
                status.update(label="Rate limited", state="error")
                st.session_state.history.pop()
                st.warning("Your Groq key has hit its rate limit. Please wait a minute and try again.")
                st.stop()
            except AuthenticationError:
                span.set_attribute("app.outcome", "auth_error")
                forget_key()
                st.error("Groq rejected the API key. Please connect a key again.")
                st.stop()
            except Exception:
                span.set_attribute("app.outcome", "error")
                log.exception("agent turn failed")
                status.update(label="Something went wrong", state="error")
                st.session_state.history.pop()
                st.error("The agent couldn't answer that. Please try again.")
                st.stop()

            elapsed = time.perf_counter() - started
            span.set_attribute("app.outcome", "ok")
            span.set_attribute("app.tool_calls", len(tools))
            span.set_attribute("app.tools", ",".join(t["name"] for t in tools))
            span.set_attribute("app.latency_ms", int(elapsed * 1000))
            log.info("agent turn ok", extra={"tool_calls": len(tools), "latency_ms": int(elapsed * 1000)})

        status.update(label=f"Done in {elapsed:.1f}s · {len(tools)} tool call{'s' if len(tools) != 1 else ''}",
                      state="complete", expanded=False)
        answer_box.markdown(answer or "_(no answer)_")
        render_tools(tools)
    st.session_state.history.append({"role": "assistant", "content": answer, "tools": tools})
