from uuid import uuid4

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.messages import HumanMessage
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import InMemorySaver

from models import make_llm
from prompts import agent_system_prompt
from tools import calculate_right_refund, get_today_date, get_user_purchase_history, issue_refund_ticket

load_dotenv()

TOOLS = [calculate_right_refund, get_user_purchase_history, issue_refund_ticket, get_today_date]


def build_agent(llm: BaseChatModel):
    # No structured output: on Groq it needs a forced tool call that gpt-oss sometimes
    # skips (HTTP 400). The agent's last message is the answer; see final_answer().
    return create_agent(
        model=llm,
        system_prompt=agent_system_prompt,
        tools=TOOLS,
        checkpointer=InMemorySaver(),
    )


def final_answer(response: dict) -> str:
    """The text of the agent's last message."""
    return response["messages"][-1].content


def stream_reply(agent, text: str, config: dict):
    """Run one turn and yield events as they happen:
    ("tool_call", {"id", "name", "args"}), ("tool_result", {"id", "output"}),
    ("token", str) for answer text, and ("reset", None) when text that preceded a tool
    call should be discarded (the real answer comes after the tools)."""
    for mode, data in agent.stream(
        {"messages": [HumanMessage(content=text)]},
        config=config,
        stream_mode=["messages", "updates"],
    ):
        if mode == "messages":
            chunk, meta = data
            if meta.get("langgraph_node") == "model" and isinstance(chunk.content, str) and chunk.content:
                yield "token", chunk.content
        elif mode == "updates":
            for node, update in data.items():
                for msg in (update or {}).get("messages", []):
                    if node == "model" and getattr(msg, "tool_calls", None):
                        yield "reset", None
                        for call in msg.tool_calls:
                            yield "tool_call", {"id": call["id"], "name": call["name"], "args": call["args"]}
                    elif node == "tools":
                        yield "tool_result", {"id": msg.tool_call_id, "output": msg.content}


_default_agent = None


def __getattr__(name):
    # `from agent import agent` (used by the evaluation scripts) builds the agent
    # lazily from GROQ_API_KEY in .env, so importing this module needs no key.
    global _default_agent
    if name == "agent":
        if _default_agent is None:
            _default_agent = build_agent(make_llm())
        return _default_agent
    raise AttributeError(name)


def run_conversation():
    """Chat with the agent in the terminal. Type 'quit' to stop."""
    agent = build_agent(make_llm())
    config = {"configurable": {"thread_id": str(uuid4())}}
    text = "I would like to request a refund"
    while text.strip().lower() not in {"quit", "exit", ""}:
        print(f"you: {text}")
        response = agent.invoke({"messages": [HumanMessage(content=text)]}, config=config)
        print(f"agent: {final_answer(response)}")
        text = input("reply (or 'quit'): ")
    print("the job is done!")


if __name__ == "__main__":
    run_conversation()
