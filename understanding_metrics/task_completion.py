from langchain.agents import create_agent
from deepeval.integrations.langchain import CallbackHandler
from deepeval.dataset import EvaluationDataset, Golden
from deepeval.metrics import TaskCompletionMetric, StepEfficiencyMetric, PlanAdherenceMetric
from dotenv import load_dotenv

load_dotenv()

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evaluations"))
from model import eval_model  # Groq-backed DeepEval judge

def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b

agent = create_agent(
    model="groq:openai/gpt-oss-120b",
    tools=[multiply],
    system_prompt="Be concise.",
)

# Goldens are the inputs you want to evaluate.
dataset = EvaluationDataset(goldens=[
    Golden(input="What is 8 multiplied by 6?"),
    Golden(input="What is 7 multiplied by 9?"),
])

metrics = [TaskCompletionMetric(model=eval_model)]


# The `TaskCompletionMetric` is passed into the `evals_iterator`.
for golden in dataset.evals_iterator(metrics=metrics):
    agent.invoke(
        {"messages": [{"role": "user", "content": golden.input}]},
        config={"callbacks": [CallbackHandler()]},
    )