"""Tests for configuration loading and redaction."""

import json
import os
import tempfile

import pytest

from modules.config import PipelineConfig, redact, redact_dict


class TestRedaction:
    def test_redact_short(self):
        assert redact("abc") == "***"

    def test_redact_normal(self):
        result = redact("sk-1234567890abcdef")
        assert result.endswith("cdef")
        assert result.startswith("*")
        assert "1234" not in result

    def test_redact_dict(self):
        d = {"api_key": "sk-secret123", "model": "gpt-4o", "nested": {"api_key": "sk-other"}}
        safe = redact_dict(d)
        assert "secret" not in safe["api_key"]
        assert safe["model"] == "gpt-4o"
        assert "other" not in safe["nested"]["api_key"]


class TestPipelineConfig:
    def test_defaults(self):
        cfg = PipelineConfig()
        assert cfg.max_input_chars == 8192
        assert cfg.max_report_chars == 65536
        assert cfg.primary.model == "gpt-4o"
        assert cfg.audit.model == "gpt-4o-mini"
        assert cfg.provider == "openai"
        assert cfg.enable_audit is True
        assert cfg.enable_cache is False
        assert cfg.redact_secrets is True

    def test_load_from_dict(self):
        d = {
            "max_input_chars": 4096,
            "models": {
                "primary": {"model": "gpt-4-turbo", "temperature": 0.5},
                "audit": {"model": "claude-3-haiku", "max_tokens": 4096},
            },
            "provider": "litellm",
            "enable_audit": False,
        }
        cfg = PipelineConfig._from_dict(d)
        assert cfg.max_input_chars == 4096
        assert cfg.primary.model == "gpt-4-turbo"
        assert cfg.primary.temperature == 0.5
        assert cfg.audit.model == "claude-3-haiku"
        assert cfg.provider == "litellm"
        assert cfg.enable_audit is False

    def test_load_from_file(self):
        d = {
            "max_input_chars": 2000,
            "models": {"primary": {"model": "test-model"}},
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(d, f)
            f.flush()
            cfg = PipelineConfig.load(config_path=f.name)

        os.unlink(f.name)
        assert cfg.max_input_chars == 2000
        assert cfg.primary.model == "test-model"

    def test_load_missing_file(self):
        cfg = PipelineConfig.load(config_path="/nonexistent/path.json")
        assert cfg.max_input_chars == 8192  # defaults

    def test_to_dict_safe(self):
        cfg = PipelineConfig()
        cfg.openai_api_key = "sk-verysecretkey12345"
        d = cfg.to_dict(safe=True)
        assert "verysecret" not in json.dumps(d)

    def test_to_dict_unsafe(self):
        cfg = PipelineConfig()
        cfg.openai_api_key = "sk-verysecretkey12345"
        d = cfg.to_dict(safe=False)
        assert d["openai_api_key"] == "sk-verysecretkey12345"

    def test_overrides(self):
        cfg = PipelineConfig()
        cfg._apply_overrides({"verbosity": 2, "enable_cache": True})
        assert cfg.verbosity == 2
        assert cfg.enable_cache is True

    def test_env_var_fallback(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
        cfg = PipelineConfig.load(config_path=None)
        assert cfg.openai_api_key == "sk-from-env"
