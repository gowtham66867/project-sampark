from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from sampark.llm.model_manager import ModelManager
from sampark.llm.providers import build_provider_clients
from sampark.llm.reasoning_engine import ReasoningEngine
from sampark.skills.skill_manager import SkillManager

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "models.yaml"
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_dotenv_if_present() -> None:
    """Loads a .env file from the project root into os.environ, without
    overriding variables already set in the real shell environment (so an
    operator's own export still wins over a stale .env value). No-op, not
    an error, if python-dotenv isn't installed or no .env file exists --
    this is a convenience for local/demo runs, not a requirement."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(_PROJECT_ROOT / ".env", override=False)


def build_default_reasoning_engine() -> Optional[ReasoningEngine]:
    """Production wiring: returns None if no provider is configured at all
    (neither ANTHROPIC_API_KEY nor GEMINI_API_KEY set). The caller
    (run_demo.py / console.py) is responsible for treating None as "LLM
    unavailable" -- never silently degrading to rule-based-only behavior on
    the graded API surface. Never constructs a StubProviderClient here;
    that only happens in test wiring.

    Anthropic is the primary provider for every role in models.yaml, but a
    Gemini-only deployment (GEMINI_API_KEY set, ANTHROPIC_API_KEY absent)
    still works: ModelManager skips any hop whose provider client isn't
    registered and falls through to the next one, and every role's
    fallback chain includes a Gemini entry precisely so this degrades
    gracefully instead of raising."""
    _load_dotenv_if_present()
    clients = build_provider_clients()
    if not clients:
        return None

    config_path = os.environ.get("SAMPARK_MODELS_CONFIG", str(_DEFAULT_CONFIG_PATH))
    model_manager = ModelManager.from_yaml(config_path, clients)
    skill_manager = SkillManager()
    return ReasoningEngine(model_manager, skill_manager)
