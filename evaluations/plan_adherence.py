import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "agent")
)

from agent import agent
from dataset import dataset
from model import eval_model
from slim_trace import install as install_slim_trace

install_slim_trace()  # keep judge requests under Groq's free-tier limit

from deepeval.integrations.langchain import CallbackHandler
from deepeval.metrics import PlanAdherenceMetric

metrics = [PlanAdherenceMetric(threshold=0.8,model=eval_model,include_reason=True)]


for golden in dataset.evals_iterator(metrics=metrics):
    response = agent.invoke(
        {"messages": [{"role": "user", "content": golden.input}]},
        config={"configurable": {"thread_id": str(uuid4())},
        "callbacks": [CallbackHandler()]}
    )
