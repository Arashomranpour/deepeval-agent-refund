"""Chat page: talk to the refund agent with your own Groq API key."""

import logging
from uuid import uuid4

import streamlit as st
from groq import AuthenticationError, RateLimitError
from langchain_core.messages import AIMessage, ToolMessage

from agent import build_agent
from data import users_data
from glass import hero
from models import AGENT_MODEL, make_llm, validate_api_key
from tools import STORE_TODAY

log = logging.getLogger(__name__)

EXAMPLES = [
    "I am user123, I would like a refund for the book and the pen",
    "I am user126, I would like a refund for the backpack and water_bottle",
    "I am user999, I would like a refund for the book",
    "I would like to request a refund",
]


def forget_key() -> None:
    for key in ("agent", "thread_id", "history"):
        st.session_state.pop(key, None)


def new_conversation() -> None:
    st.session_state.thread_id = str(uuid4())
    st.session_state.history = []


# --- Gate: nothing below runs until the visitor connects their own key. -------
HERO = ("LangChain agent · Groq", "Refund support agent",
        "A tool-using LangChain agent that checks purchase history and the 30-day policy "
        "before issuing a refund. Every answer shows the tools it called.",
        [f"🧠 {AGENT_MODEL}", f"📅 store date {STORE_TODAY}", "🔧 4 tools", "🔑 bring your own key"])

if "agent" not in st.session_state:
    hero(*HERO)
    with st.sidebar:
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
                    new_conversation()
                    st.rerun()
    st.info("👈 Connect a Groq API key to start chatting. "
            "The **Evaluation results** page works without a key.")
    st.stop()

# --- Sidebar -------------------------------------------------------------------
with st.sidebar:
    st.caption(f"Model: `{AGENT_MODEL}` on Groq")
    st.caption(f"Store date: **{STORE_TODAY}** (refunds allowed within 30 days)")
    st.button("New conversation", on_click=new_conversation, use_container_width=True)
    st.button("Forget key", on_click=forget_key, use_container_width=True)
    with st.expander("Demo customers"):
        for user, items in users_data.items():
            st.markdown(f"**{user}**: " + ", ".join(
                f"{name} (${item['price']}, {item['date']})" for name, item in items.items()))

hero(*HERO)


def render_tools(tools: list[dict]) -> None:
    if not tools:
        return
    with st.expander(f"🔧 {len(tools)} tool call{'s' if len(tools) != 1 else ''}"):
        for t in tools:
            st.markdown(f"**`{t['name']}`**")
            st.json(t["args"], expanded=False)
            if t.get("output") is not None:
                st.code(str(t["output"]), language=None)


for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        render_tools(msg.get("tools", []))

prompt = st.chat_input("Ask about a refund…")
if not st.session_state.history and not prompt:
    st.markdown("**Try one of these:**")
    cols = st.columns(2)
    for i, example in enumerate(EXAMPLES):
        if cols[i % 2].button(example, key=f"example_{i}", use_container_width=True):
            prompt = example

if prompt:
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            with st.spinner("Thinking…"):
                config = {"configurable": {"thread_id": st.session_state.thread_id}}
                before = len(st.session_state.agent.get_state(config).values.get("messages", []))
                response = st.session_state.agent.invoke(
                    {"messages": [{"role": "user", "content": prompt}]}, config=config)
        except RateLimitError:
            st.session_state.history.pop()
            st.warning("Your Groq key has hit its rate limit. Please wait a minute and try again.")
            st.stop()
        except AuthenticationError:
            forget_key()
            st.error("Groq rejected the API key. Please connect a key again.")
            st.stop()
        except Exception:
            log.exception("agent call failed")
            st.session_state.history.pop()
            st.error("The agent couldn't answer that. Please try again.")
            st.stop()

        new_messages = response["messages"][before:]
        outputs = {m.tool_call_id: m.content for m in new_messages if isinstance(m, ToolMessage)}
        tools = [
            {"name": c["name"], "args": c["args"], "output": outputs.get(c["id"])}
            for m in new_messages if isinstance(m, AIMessage)
            for c in m.tool_calls
        ]
        answer = response["messages"][-1].content
        st.markdown(answer)
        render_tools(tools)
    st.session_state.history.append({"role": "assistant", "content": answer, "tools": tools})
