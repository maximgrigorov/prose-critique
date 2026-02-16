"""Configuration management for prose-critique."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional


_SECRET_KEYS = {"api_key", "openai_api_key", "litellm_api_key"}


def redact(value: str, keep: int = 4) -> str:
    """Mask a secret string, keeping only last *keep* chars."""
    if not value or len(value) <= keep:
        return "***"
    return "*" * (len(value) - keep) + value[-keep:]


def redact_dict(d: dict, keys: set[str] | None = None) -> dict:
    """Return a shallow copy of *d* with secret fields masked."""
    keys = keys or _SECRET_KEYS
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out[k] = redact_dict(v, keys)
        elif k in keys and isinstance(v, str) and v:
            out[k] = redact(v)
        else:
            out[k] = v
    return out


@dataclass
class ModelConfig:
    model: str = "gpt-4o"
    temperature: float = 0.3
    top_p: float = 1.0
    max_tokens: int = 16384
    timeout: int = 120
    retries: int = 2


@dataclass
class LiteLLMConfig:
    base_url: str = "http://localhost:4000"
    api_key: str = ""


@dataclass
class PipelineConfig:
    max_input_chars: int = 8192
    max_report_chars: int = 65536

    primary: ModelConfig = field(default_factory=lambda: ModelConfig())
    audit: ModelConfig = field(default_factory=lambda: ModelConfig(
        model="gpt-4o-mini",
        temperature=0.2,
        max_tokens=8192,
        timeout=90,
    ))

    provider: str = "openai"  # "openai" | "litellm"
    litellm: LiteLLMConfig = field(default_factory=LiteLLMConfig)
    openai_api_key: str = ""

    enable_audit: bool = True
    enable_cache: bool = False
    verbosity: int = 1
    store_prompts: bool = False
    redact_secrets: bool = True

    @classmethod
    def load(
        cls,
        config_path: str | Path | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> "PipelineConfig":
        """Load config from JSON file, env vars, and optional overrides."""
        raw: dict[str, Any] = {}

        if config_path:
            p = Path(config_path)
            if p.exists():
                raw = json.loads(p.read_text(encoding="utf-8"))

        cfg = cls._from_dict(raw)

        env_key = os.getenv("OPENAI_API_KEY", "")
        if env_key and not cfg.openai_api_key:
            cfg.openai_api_key = env_key

        litellm_key = os.getenv("LITELLM_API_KEY", "")
        if litellm_key and not cfg.litellm.api_key:
            cfg.litellm.api_key = litellm_key

        litellm_url = os.getenv("LITELLM_BASE_URL", "")
        if litellm_url and not cfg.litellm.base_url:
            cfg.litellm.base_url = litellm_url

        if overrides:
            cfg._apply_overrides(overrides)

        return cfg

    @classmethod
    def _from_dict(cls, d: dict[str, Any]) -> "PipelineConfig":
        cfg = cls()
        simple = {
            "max_input_chars", "max_report_chars", "provider",
            "enable_audit", "enable_cache", "verbosity",
            "store_prompts", "redact_secrets", "openai_api_key",
        }
        for k in simple:
            if k in d:
                setattr(cfg, k, d[k])

        models = d.get("models", {})
        if "primary" in models:
            cfg.primary = cls._model_cfg(models["primary"])
        if "audit" in models:
            cfg.audit = cls._model_cfg(models["audit"])

        ll = d.get("litellm", {})
        if ll:
            cfg.litellm = LiteLLMConfig(
                base_url=ll.get("base_url", cfg.litellm.base_url),
                api_key=ll.get("api_key", cfg.litellm.api_key),
            )
        return cfg

    @staticmethod
    def _model_cfg(d: dict) -> ModelConfig:
        return ModelConfig(
            model=d.get("model", "gpt-4o"),
            temperature=d.get("temperature", 0.3),
            top_p=d.get("top_p", 1.0),
            max_tokens=d.get("max_tokens", 16384),
            timeout=d.get("timeout", 120),
            retries=d.get("retries", 2),
        )

    def _apply_overrides(self, ov: dict[str, Any]) -> None:
        for k, v in ov.items():
            if hasattr(self, k) and not isinstance(v, dict):
                setattr(self, k, v)

    def to_dict(self, safe: bool = True) -> dict:
        d = {
            "max_input_chars": self.max_input_chars,
            "max_report_chars": self.max_report_chars,
            "models": {
                "primary": asdict(self.primary),
                "audit": asdict(self.audit),
            },
            "provider": self.provider,
            "litellm": asdict(self.litellm),
            "openai_api_key": self.openai_api_key,
            "enable_audit": self.enable_audit,
            "enable_cache": self.enable_cache,
            "verbosity": self.verbosity,
            "store_prompts": self.store_prompts,
            "redact_secrets": self.redact_secrets,
        }
        if safe and self.redact_secrets:
            d = redact_dict(d)
        return d

    def to_json(self, safe: bool = True) -> str:
        return json.dumps(self.to_dict(safe=safe), indent=2, ensure_ascii=False)
