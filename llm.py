import os
from groq import Groq

MODEL = "openai/gpt-oss-120b"


def _load_env(path=".env"):
    """Read KEY=value lines from .env into the environment."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


_load_env()


def call_llm(system_prompt: str, user_prompt: str) -> dict:
    """Send a prompt to the LLM. Return the reply and token counts.

    This is the ONLY place the provider is named. Everything else in the
    project calls this function, so swapping providers is a one-file change.
    """
    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_completion_tokens=4000,
    )

    return {
        "text": response.choices[0].message.content,
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "model": MODEL,
    }


if __name__ == "__main__":
    result = call_llm(
        "You are a helpful assistant. Answer in one short sentence.",
        "What is a TOML file?",
    )
    print(result["text"])
    print(f"\ntokens in: {result['prompt_tokens']}  out: {result['completion_tokens']}")