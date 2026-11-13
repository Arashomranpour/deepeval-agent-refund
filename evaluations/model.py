"""DeepEval judge model backed by Groq (via langchain-groq) instead of OpenAI."""

from dotenv import load_dotenv
from deepeval.models import DeepEvalBaseLLM
from langchain_groq import ChatGroq

load_dotenv()  # reads GROQ_API_KEY from the root .env

JUDGE_MODEL = "openai/gpt-oss-120b"


class GroqJudge(DeepEvalBaseLLM):
    def __init__(self, model: str = JUDGE_MODEL):
        self.model_name = model
        super().__init__(model)

    def load_model(self):
        # Small, cheap judge calls so a free-tier key can finish a run.
        return ChatGroq(
            model=self.model_name,
            temperature=0,
            reasoning_effort="low",
            max_tokens=1024,
            max_retries=6,
        )

    def generate(self, prompt: str, schema=None):
        if schema is not None:
            return self.model.with_structured_output(schema, method="json_schema").invoke(prompt)
        return self.model.invoke(prompt).content

    async def a_generate(self, prompt: str, schema=None):
        if schema is not None:
            return await self.model.with_structured_output(schema, method="json_schema").ainvoke(prompt)
        return (await self.model.ainvoke(prompt)).content

    def get_model_name(self):
        return f"groq/{self.model_name}"


eval_model = GroqJudge()
