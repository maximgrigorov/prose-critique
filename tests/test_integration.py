"""Integration tests (require either a valid OPENAI_API_KEY or LiteLLM proxy)."""

import asyncio
import os
import socket
from pathlib import Path

import pytest

from modules.config import PipelineConfig
from modules.orchestrator import Orchestrator


def _has_valid_openai_key() -> bool:
    """Check if a plausible OpenAI API key is set."""
    key = os.getenv("OPENAI_API_KEY", "")
    return bool(key) and key.startswith("sk-") and len(key) > 20 and "your" not in key.lower()


def _litellm_reachable() -> bool:
    """Check if config.local.json exists and the LiteLLM proxy is reachable."""
    cfg_path = Path("config.local.json")
    if not cfg_path.exists():
        return False
    try:
        cfg = PipelineConfig.load(config_path=str(cfg_path))
        if cfg.provider != "litellm":
            return False
        host = cfg.litellm.base_url.replace("http://", "").replace("https://", "")
        if ":" in host:
            hostname, port = host.split(":", 1)
            port = int(port.split("/")[0])
        else:
            hostname, port = host.split("/")[0], 80
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((hostname, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def _can_run_integration() -> bool:
    return _has_valid_openai_key() or _litellm_reachable()


def _get_config_path() -> str:
    if _litellm_reachable():
        return "config.local.json"
    return "config.json"


pytestmark = pytest.mark.skipif(
    not _can_run_integration(),
    reason="No valid OPENAI_API_KEY and LiteLLM proxy not reachable; skipping integration tests",
)


@pytest.fixture
def config():
    cfg = PipelineConfig.load(config_path=_get_config_path())
    cfg.enable_audit = False
    cfg.primary.max_tokens = 4096
    cfg.verbosity = 2
    return cfg


@pytest.fixture
def sample_text():
    return (
        "The old man sat on the porch, watching the sun set over the hills. "
        "He had seen many sunsets in his long life, but this one felt different.\n\n"
        "His granddaughter came out with two cups of tea. She handed him one "
        "and sat down beside him without saying a word."
    )


class TestIntegration:
    def test_full_pipeline_no_audit(self, config, sample_text):
        orchestrator = Orchestrator(config=config)
        md, js, report = asyncio.run(orchestrator.run(sample_text))

        assert len(md) > 100
        assert len(js) > 100
        assert report.language == "en"
        assert report.primary_analysis.summary != ""
        assert report.primary_analysis.quality_scores.overall > 0
        assert len(report.llm_calls) == 1

    def test_full_pipeline_with_requirements(self, config, sample_text):
        orchestrator = Orchestrator(config=config)
        md, js, report = asyncio.run(
            orchestrator.run(sample_text, requirements="literary fiction, avoid clichés")
        )
        assert report.requirements == "literary fiction, avoid clichés"

    def test_full_pipeline_with_audit(self, sample_text):
        cfg = PipelineConfig.load(config_path=_get_config_path())
        cfg.enable_audit = True
        cfg.primary.max_tokens = 4096
        cfg.audit.max_tokens = 4096
        cfg.verbosity = 2

        orchestrator = Orchestrator(config=cfg)
        md, js, report = asyncio.run(orchestrator.run(sample_text))

        assert report.audit is not None
        assert report.audit.confidence_score >= 0
        assert len(report.llm_calls) == 2

    def test_russian_text(self, config):
        text = (
            "Старик сидел на крыльце и смотрел на закат. "
            "Он видел множество закатов, но этот казался особенным.\n\n"
            "Внучка вышла с двумя чашками чая. Она протянула ему чашку "
            "и села рядом, не говоря ни слова."
        )
        orchestrator = Orchestrator(config=config)
        md, js, report = asyncio.run(orchestrator.run(text))
        assert report.language == "ru"

    def test_input_too_long(self, config):
        text = "x" * 9000
        orchestrator = Orchestrator(config=config)
        with pytest.raises(ValueError, match="exceeds maximum"):
            asyncio.run(orchestrator.run(text))

    def test_empty_input(self, config):
        orchestrator = Orchestrator(config=config)
        with pytest.raises(ValueError, match="empty"):
            asyncio.run(orchestrator.run(""))
