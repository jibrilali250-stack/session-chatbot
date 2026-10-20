"""Guardrails for /chat: checks before and after the model call, configured from a JSON file."""
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

BASE_DIR = Path(__file__).parent
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)")


class GuardrailConfig(BaseModel):
    enabled: bool = True
    max_input_chars: int = Field(2000, ge=1)
    block_injection: bool = True
    injection_phrases: list[str] = []
    mask_pii: bool = True
    topic_check: bool = False
    allowed_topic: str = "general conversation"
    max_output_words: int = Field(300, ge=1)
    banned_output_words: list[str] = []
    blocked_message: str = "Sorry, I can't help with that request."


def config_path():
    return BASE_DIR / os.getenv("GUARDRAILS_FILE", "guardrails.json")


def load_config():
    return GuardrailConfig(**json.loads(config_path().read_text()))


def save_config(config):
    config_path().write_text(json.dumps(config.model_dump(), indent=2) + "\n")


def _topic_ok(message, config):
    # imported here so tests can patch main.ask_llm / guardrails.ask_llm independently
    from llm_client import MODEL, ask_llm

    prompts = json.loads((BASE_DIR / "prompts.json").read_text())
    system = prompts["topic_judge"].format(topic=config.allowed_topic)
    try:
        answer = ask_llm(message, model=MODEL, system=system)["text"]
    except Exception:
        return True  # judge failed: fail open
    return answer.strip().upper().startswith("YES")


def check_input(message, config):
    """Return (allowed, cleaned_text, reason)."""
    if not config.enabled:
        return True, message, None
    if len(message) > config.max_input_chars:
        return False, message, "blocked: too long"
    if config.block_injection:
        lowered = message.lower()
        if any(p.lower() in lowered for p in config.injection_phrases):
            return False, message, "blocked: injection"
    reason = None
    if config.mask_pii:
        masked = []
        message, n = EMAIL_RE.subn("[EMAIL]", message)
        if n:
            masked.append("email")
        message, n = PHONE_RE.subn("[PHONE]", message)
        if n:
            masked.append("phone")
        if masked:
            reason = "masked: " + ", ".join(masked)
    if config.topic_check and not _topic_ok(message, config):
        return False, message, "blocked: off-topic"
    return True, message, reason


def check_output(reply, config):
    """Return (allowed, cleaned_text, reason)."""
    if not config.enabled:
        return True, reply, None
    if len(reply.split()) > config.max_output_words:
        return False, reply, "blocked: reply too long"
    lowered = reply.lower()
    if any(w.lower() in lowered for w in config.banned_output_words):
        return False, reply, "blocked: banned word"
    return True, reply, None
