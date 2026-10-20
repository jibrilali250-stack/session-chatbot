"""
llm_client.py: one function to call any LLM, plus the numbers you care about.

    from llm_client import ask_llm, MODEL

    result = ask_llm("What is a token?", model=MODEL)
    print(result["text"])
"""
import os
import time

from anthropic import Anthropic
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()  # copies the keys from your .env file into the environment

# The model all the labs use. Change it in your .env file, e.g. LAB_MODEL=gemini:gemini-2.5-flash
MODEL = os.getenv("LAB_MODEL", "groq:llama-3.3-70b-versatile")

# Every provider except Anthropic understands the same "OpenAI-compatible" format,
# so for each one we only need its web address and the name of its key in .env.
PROVIDERS = {
    "openai":      {"url": "https://api.openai.com/v1", "key": "OPENAI_API_KEY"},
    "gemini":      {"url": "https://generativelanguage.googleapis.com/v1beta/openai/", "key": "GEMINI_API_KEY"},
    "groq":        {"url": "https://api.groq.com/openai/v1", "key": "GROQ_API_KEY"},
    "mistral":     {"url": "https://api.mistral.ai/v1", "key": "MISTRAL_API_KEY"},
    "openrouter":  {"url": "https://openrouter.ai/api/v1", "key": "OPENROUTER_API_KEY"},
    # "huggingface": {"url": "https://router.huggingface.co/v1", "key": "HUGGINGFACE_API_KEY"},
    # "local":       {"url": "http://localhost:11434/v1", "key": None},  # Ollama on your own laptop
}

# Prices in US dollars per 1 million tokens. Copy them from each provider's pricing page.
# If a model is not listed here, the cost comes back as None.
PRICES = {
    # "groq:llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
}


def ask_llm(prompt, model, system="You are a helpful assistant.", cache=False):
    """Send a prompt to any model and return the answer with its metrics."""
    provider, model_name = model.split(":", 1)  # "groq:llama-3.3-70b" → "groq", "llama-3.3-70b"

    if provider == "anthropic":
        client = Anthropic()  # reads ANTHROPIC_API_KEY from .env
        if cache:  # Anthropic only caches the parts you mark
            system = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        start = time.time()
        response = client.messages.create(
            model=model_name,
            max_tokens=4000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        seconds = time.time() - start
        text = ""
        for block in response.content:  # keep the answer, skip any "thinking" blocks
            if block.type == "text":
                text += block.text
        usage = response.usage
        cached_tokens = usage.cache_read_input_tokens or 0
        # Anthropic counts new, cached and newly-cached input separately, so add them up
        input_tokens = usage.input_tokens + cached_tokens + (usage.cache_creation_input_tokens or 0)
        output_tokens = usage.output_tokens

    else:
        settings = PROVIDERS[provider]
        if settings["key"] is None:
            api_key = "not-needed"
        else:
            api_key = os.getenv(settings["key"])
            if not api_key:
                raise ValueError(f"Add {settings['key']} to your .env file")
        client = OpenAI(base_url=settings["url"], api_key=api_key)
        start = time.time()
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        seconds = time.time() - start
        text = response.choices[0].message.content or ""
        input_tokens = response.usage.prompt_tokens  # this already includes cached tokens
        output_tokens = response.usage.completion_tokens
        details = response.usage.prompt_tokens_details  # not every provider sends this
        cached_tokens = 0
        if details and details.cached_tokens:
            cached_tokens = details.cached_tokens

    cost = None
    if model in PRICES:
        price = PRICES[model]
        cost = (input_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000

    return {
        "text": text,
        "input_tokens": input_tokens,
        "cached_tokens": cached_tokens,
        "output_tokens": output_tokens,
        "seconds": round(seconds, 2),
        "tokens_per_second": round(output_tokens / seconds, 1),
        "cost": cost,
    }


def print_step(title, text=""):
    """Print a heading (and some text) so you can follow each step of a lab."""
    print()
    print("─" * 70)
    print(title)
    print("─" * 70)
    if text:
        print(text)


def print_metrics(result):
    """Print the numbers for one call on a single line."""
    print(f"   [{result['input_tokens']} tokens in · {result['output_tokens']} tokens out · "
          f"{result['seconds']} s · cost {result['cost']}]")
