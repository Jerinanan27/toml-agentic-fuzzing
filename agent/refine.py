import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm import call_llm

IMPORT_LINE = (
    "from hypothesis import strategies as st\n"
    "from metrics import DottedKey\n"
)


def strip_fences(text: str) -> str:
    """Remove markdown code fences if the model added them."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def load_strategy(code: str):
    """Execute the code and pull out the `strategy` variable.
    Raises if the code is broken or `strategy` is missing."""
    namespace = {}
    exec(IMPORT_LINE + code, namespace)
    if "strategy" not in namespace:
        raise ValueError("no variable named 'strategy' was defined")
    return namespace["strategy"]


def validate_strategy(strategy, n=10) -> None:
    """Check the strategy actually produces examples.
    Raises if it does not."""
    samples = [strategy.example() for _ in range(n)]
    if len(samples) < n:
        raise ValueError("strategy did not produce enough examples")


def ask_for_improvement(task_prompt: str, current_code: str, feedback: str) -> dict:
    """Send the task, the current code and the feedback. Get new code back."""
    user_prompt = (
        task_prompt
        + "\n\n=== YOUR CURRENT STRATEGY ===\n"
        + current_code
        + "\n\n=== "
        + feedback
        + "\n\nRewrite the strategy to fix the problems above. "
        + "Return ONLY Python code, no explanation, no markdown fences. "
        + "Define a variable named `strategy`."
    )

    response = call_llm(
        "You are an expert Python developer writing Hypothesis strategies.",
        user_prompt,
    )
    response["code"] = strip_fences(response["text"])
    return response