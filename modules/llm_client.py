"""Async LLM client supporting OpenAI and LiteLLM proxy."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Optional

from openai import AsyncOpenAI
from modules.config import PipelineConfig, ModelConfig

logger = logging.getLogger("prose-critique")

_cache_dir = Path(__file__).resolve().parent.parent / "workspace" / "cache"

_ANTHROPIC_PREFIXES = ("claude", "anthropic")


def _cache_key(model: str, messages: list[dict], temperature: float) -> str:
    blob = json.dumps({"model": model, "messages": messages, "t": temperature},
                      sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


def _is_anthropic_model(model: str) -> bool:
    """Check if a model name looks like an Anthropic/Claude model."""
    lower = model.lower()
    return any(lower.startswith(p) for p in _ANTHROPIC_PREFIXES)


def extract_json(text: str) -> str:
    """
    Extract JSON from LLM response that may contain markdown wrapping,
    thinking tags, or preamble/postscript text.
    """
    if not text or not text.strip():
        return text

    # Try direct parse first
    stripped = text.strip()
    try:
        json.loads(stripped)
        return stripped
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code blocks: ```json ... ``` or ``` ... ```
    md_patterns = [
        re.compile(r'```json\s*\n(.*?)\n\s*```', re.DOTALL),
        re.compile(r'```\s*\n(.*?)\n\s*```', re.DOTALL),
    ]
    for pat in md_patterns:
        m = pat.search(text)
        if m:
            candidate = m.group(1).strip()
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                continue

    # Try finding outermost JSON object by brace matching
    start = text.find('{')
    if start >= 0:
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except json.JSONDecodeError:
                        break

    return text


class LLMClient:
    """Unified async client for OpenAI-compatible endpoints."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self._clients: dict[str, AsyncOpenAI] = {}
        self._call_log: list[dict] = []

    def _get_client(self, role: str = "primary") -> tuple[AsyncOpenAI, ModelConfig]:
        """Return (client, model_config) for the given role."""
        if role == "audit":
            mcfg = self.config.audit
        else:
            mcfg = self.config.primary

        key = f"{role}_{self.config.provider}"
        if key not in self._clients:
            if self.config.provider == "litellm":
                self._clients[key] = AsyncOpenAI(
                    base_url=self.config.litellm.base_url,
                    api_key=self.config.litellm.api_key or "sk-placeholder",
                    timeout=mcfg.timeout,
                )
            else:
                self._clients[key] = AsyncOpenAI(
                    api_key=self.config.openai_api_key,
                    timeout=mcfg.timeout,
                )
        return self._clients[key], mcfg

    async def chat(
        self,
        messages: list[dict[str, str]],
        role: str = "primary",
        prompt_id: str = "",
        json_mode: bool = True,
    ) -> tuple[str, dict]:
        """
        Send a chat completion request.

        Returns:
            (response_text, metadata_dict)
        """
        client, mcfg = self._get_client(role)

        if self.config.enable_cache:
            ck = _cache_key(mcfg.model, messages, mcfg.temperature)
            cached = self._read_cache(ck)
            if cached is not None:
                meta = {
                    "call_id": ck[:12],
                    "model": mcfg.model,
                    "prompt_id": prompt_id,
                    "cached": True,
                    "input_tokens": None,
                    "output_tokens": None,
                    "duration_ms": 0,
                }
                self._call_log.append(meta)
                return cached, meta

        kwargs: dict[str, Any] = {
            "model": mcfg.model,
            "messages": messages,
            "temperature": mcfg.temperature,
            "max_tokens": mcfg.max_tokens,
        }
        # Only include top_p if it's not the default (1.0)
        # Anthropic doesn't support both temperature and top_p
        if mcfg.top_p != 1.0:
            kwargs["top_p"] = mcfg.top_p

        # json_object response_format is silently dropped by LiteLLM for Anthropic
        # Only request it for models that support it natively
        if json_mode and not _is_anthropic_model(mcfg.model):
            kwargs["response_format"] = {"type": "json_object"}

        last_err: Optional[Exception] = None
        for attempt in range(mcfg.retries + 1):
            t0 = time.monotonic()
            try:
                resp = await client.chat.completions.create(**kwargs)
                dur = (time.monotonic() - t0) * 1000

                raw_text = resp.choices[0].message.content or ""
                usage = resp.usage

                # Extract JSON from potentially wrapped response
                if json_mode:
                    text = extract_json(raw_text)
                    if text != raw_text:
                        logger.debug(
                            "Extracted JSON from wrapped response (%d -> %d chars)",
                            len(raw_text), len(text),
                        )
                else:
                    text = raw_text

                meta = {
                    "call_id": f"{role}_{prompt_id}_{attempt}",
                    "model": mcfg.model,
                    "prompt_id": prompt_id,
                    "cached": False,
                    "input_tokens": usage.prompt_tokens if usage else None,
                    "output_tokens": usage.completion_tokens if usage else None,
                    "duration_ms": round(dur, 1),
                }
                self._call_log.append(meta)

                if self.config.enable_cache:
                    self._write_cache(ck, text)

                logger.info(
                    "LLM call %s model=%s tokens_in=%s tokens_out=%s dur=%.0fms",
                    meta["call_id"], mcfg.model,
                    meta["input_tokens"], meta["output_tokens"], dur,
                )
                logger.debug("Raw response (first 500 chars): %s", raw_text[:500])
                return text, meta

            except Exception as e:
                last_err = e
                logger.warning(
                    "LLM call attempt %d/%d failed: %s", attempt + 1, mcfg.retries + 1, e
                )
                if attempt < mcfg.retries:
                    await asyncio.sleep(2 ** attempt)

        raise RuntimeError(f"LLM call failed after {mcfg.retries + 1} attempts: {last_err}")

    @property
    def call_log(self) -> list[dict]:
        return list(self._call_log)

    @staticmethod
    def _read_cache(key: str) -> Optional[str]:
        p = _cache_dir / f"{key}.txt"
        if p.exists():
            return p.read_text(encoding="utf-8")
        return None

    @staticmethod
    def _write_cache(key: str, text: str) -> None:
        _cache_dir.mkdir(parents=True, exist_ok=True)
        p = _cache_dir / f"{key}.txt"
        p.write_text(text, encoding="utf-8")
