"""The only place Groq chat models are built.

- CLI / evaluations: `make_llm()` reads GROQ_API_KEY from the root .env.
- Streamlit app: `make_llm(api_key)` with the visitor's own key (bring-your-own-key).
"""

from dotenv import load_dotenv
from groq import AuthenticationError, Groq
from langchain_groq import ChatGroq

load_dotenv()

AGENT_MODEL = "openai/gpt-oss-120b"
REQUIRED_MODELS = (AGENT_MODEL,)


def make_llm(api_key: str | None = None) -> ChatGroq:
    # Groq free tier is ~8k tokens/min, so keep every call small:
    # low reasoning effort, a hard cap on output tokens, and retries on 429s.
    kwargs = {"api_key": api_key} if api_key else {}
    return ChatGroq(
        model=AGENT_MODEL,
        temperature=0,
        reasoning_effort="low",
        max_tokens=1024,
        max_retries=6,
        **kwargs,
    )


def validate_api_key(api_key: str) -> str | None:
    """Return an error message, or None if the key works. Lists models: no tokens spent."""
    api_key = api_key.strip()
    if not api_key.startswith("gsk_"):
        return "That doesn't look like a Groq API key (they start with `gsk_`)."
    try:
        available = {m.id for m in Groq(api_key=api_key, max_retries=1).models.list().data}
    except AuthenticationError:
        return "Groq rejected this key. Check it at console.groq.com/keys."
    except Exception:
        return "Couldn't reach Groq to check the key. Please try again."
    missing = [m for m in REQUIRED_MODELS if m not in available]
    return f"This key can't use: {', '.join(missing)}." if missing else None
