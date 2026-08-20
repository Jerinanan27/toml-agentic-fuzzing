import sys
import os
import re


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm import call_llm

IMPORT_LINE = (
    "from hypothesis import strategies as st\n"
    "from metrics import DottedKey, RawValue, QuotedKey, Document, \\\n"
    "    TableHeader, ArrayTableHeader, Comment, KeyValue\n"
)

def strip_fences(text: str) -> str:
    """Remove reasoning tags and markdown fences some models add."""
    # Remove closed <think>...</think> blocks
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Remove an unclosed <think> and everything after it up to code
    # (Qwen sometimes runs out of tokens mid-reasoning)
    if "<think>" in text:
        # take everything AFTER the last </think>, or if none,
        # look for the code start
        if "</think>" in text:
            text = text.split("</think>")[-1]
        else:
            # no close tag - the reasoning ate the whole response
            text = ""
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
    """Check the strategy produces examples that actually serialise.

    Generating is not sufficient. A strategy can emit a node the
    serialiser does not recognise - e.g. a tuple of statements where a
    statement belongs - which .example() accepts happily and which only
    fails later, part-way through a recorded run. Round-tripping to TOML
    here converts that into a rejection at the gate, which is where the
    loop can still respond to it.
    """
    import warnings
    from hypothesis.errors import HypothesisDeprecationWarning
    from metrics import to_toml

    # Promote Hypothesis's deprecation warnings to errors. The one that
    # matters is use of the `random` module inside a strategy: it bypasses
    # Hypothesis's own entropy, so runs are not replayable and the shrinker
    # cannot reduce the values it produced. A strategy that does this still
    # runs and still finds crashes, so nothing else here would catch it.
    with warnings.catch_warnings():
        warnings.simplefilter("error", HypothesisDeprecationWarning)

        for _ in range(n):
            example = strategy.example()
            text = to_toml(example)      # raises on unknown node types
            if "\x00" in text:
                raise ValueError(
                    "strategy emitted a NUL byte; tomlc99 takes a "
                    "NUL-terminated char* so such inputs cannot be tested"
                )

        
def ask_for_improvement(task_prompt: str, current_code: str, feedback: str) -> dict:
    """Send the task, the current code and the feedback. Get new code back."""
    user_prompt = (
        "You are refining a Hypothesis strategy that generates TOML documents\n"
        "to fuzz tomlc99. Node classes available: Document, KeyValue,\n"
        "TableHeader, ArrayTableHeader, Comment, QuotedKey, DottedKey,\n"
        "RawValue. Every element of Document.statements must be exactly one\n"
        "of Comment, KeyValue, TableHeader, ArrayTableHeader. Never emit NUL\n"
                "bytes. Keep st.recursive/@composite for recursive productions and\n"
        "build deep nesting with a loop, not Python recursion. Use only\n"
        "Hypothesis strategies for randomness - never the `random` module,\n"
        "which breaks reproducibility and shrinking.\n"
        "\n=== YOUR CURRENT STRATEGY ===\n"
        + current_code
        + "\n\n=== " + feedback
        + "\n\nRewrite the strategy to fix the problems above, keeping the "
          "grammar production coverage you already have. Return ONLY Python "
          "code, no explanation, no markdown fences. Do NOT include <think> "
          "blocks. Define a variable named `strategy`."
    )

    response = call_llm(
        "You are an expert Python developer writing Hypothesis strategies.",
        user_prompt,
    )
    response["code"] = strip_fences(response["text"])
    return response