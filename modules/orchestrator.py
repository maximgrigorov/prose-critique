"""Main pipeline orchestrator: coordinates all analysis steps."""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Callable

from modules.config import PipelineConfig
from modules.llm_client import LLMClient
from modules.models import CritiqueReport, LLMCallMeta
from modules.agents.deterministic_analyzers import run_deterministic_analysis
from modules.agents.primary_analyzer import run_primary_analysis
from modules.agents.auditor import run_audit
from modules.agents.report_builder import build_markdown_report, build_json_report
from modules.utils.auto_requirements import generate_auto_requirements
from modules.utils.prompts import format_primary_prompt_for_display
from modules.logger import generate_run_id, save_run, setup_logger

logger = logging.getLogger("prose-critique")


class Orchestrator:
    """Coordinates the one-pass analysis pipeline."""

    def __init__(
        self,
        config: PipelineConfig,
        run_id: Optional[str] = None,
        progress_cb: Optional[Callable[[str, float], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ):
        self.config = config
        self.run_id = run_id or generate_run_id()
        self.progress_cb = progress_cb
        self.cancel_check = cancel_check
        self.logger = setup_logger(
            "prose-critique",
            verbosity=config.verbosity,
            run_id=self.run_id,
        )

    def _progress(self, stage: str, pct: float) -> None:
        if self.progress_cb:
            self.progress_cb(stage, pct)

    def _cancelled(self) -> bool:
        if self.cancel_check:
            return self.cancel_check()
        return False

    async def run(
        self,
        text: str,
        requirements: str = "",
    ) -> tuple[str, str, CritiqueReport]:
        """
        Execute the full analysis pipeline.

        Args:
            text: Input prose text.
            requirements: Optional author requirements/constraints.

        Returns:
            (markdown_report, json_report, report_object)

        Raises:
            ValueError: If input exceeds max_input_chars.
            RuntimeError: On LLM failure.
        """
        t0 = time.monotonic()

        # ── Validate input ────────────────────────────────────────────
        if len(text) > self.config.max_input_chars:
            raise ValueError(
                f"Input text exceeds maximum of {self.config.max_input_chars} characters "
                f"(got {len(text)}). Please shorten the text."
            )

        if not text.strip():
            raise ValueError("Input text is empty.")

        self.logger.info("=== Starting prose critique run %s ===", self.run_id)
        self.logger.info("Input: %d chars, requirements: %d chars", len(text), len(requirements))
        self._progress("starting", 0.0)

        # ── Step 1: Deterministic analysis ────────────────────────────
        if self._cancelled():
            raise RuntimeError("Cancelled by user.")

        self._progress("deterministic_analysis", 0.1)
        deterministic = run_deterministic_analysis(text)
        language = deterministic.language
        self.logger.info("Language detected: %s", language)

        # ── Step 1b: Auto-generate requirements if none provided ─────
        effective_requirements = requirements
        if not requirements.strip():
            self.logger.info("No user requirements provided — generating baseline requirements...")
            self._progress("generating_requirements", 0.2)
            effective_requirements = generate_auto_requirements(deterministic, text)
            self.logger.debug("Auto-requirements length: %d chars", len(effective_requirements))

        # ── Step 2: Primary LLM analysis ──────────────────────────────
        if self._cancelled():
            raise RuntimeError("Cancelled by user.")

        self._progress("primary_analysis", 0.3)
        client = LLMClient(self.config)

        primary_analysis, primary_meta = await run_primary_analysis(
            client=client,
            text=text,
            language=language,
            deterministic=deterministic,
            requirements=effective_requirements,
        )

        llm_calls: list[LLMCallMeta] = [primary_meta]

        # ── Step 3: Audit (optional) ──────────────────────────────────
        audit_result = None
        if self.config.enable_audit:
            if self._cancelled():
                raise RuntimeError("Cancelled by user.")

            self._progress("audit_analysis", 0.6)
            audit_result, audit_meta = await run_audit(
                client=client,
                text=text,
                language=language,
                primary_analysis=primary_analysis,
            )
            llm_calls.append(audit_meta)

        # ── Step 4: Build report ──────────────────────────────────────
        self._progress("building_report", 0.85)

        duration = (time.monotonic() - t0) * 1000
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]

        # Format the primary prompt for display in the report
        generated_prompt = format_primary_prompt_for_display(
            text=text,
            language=language,
            deterministic=deterministic,
            requirements=effective_requirements,
        )

        report = CritiqueReport(
            version="1.0.0",
            input_text_hash=text_hash,
            input_char_count=len(text),
            input_text=text,
            requirements=requirements,
            generated_prompt=generated_prompt,
            language=language,
            deterministic=deterministic,
            primary_analysis=primary_analysis,
            audit=audit_result,
            llm_calls=llm_calls,
            timestamp=datetime.now(timezone.utc).isoformat(),
            duration_ms=round(duration, 1),
        )

        md_report = build_markdown_report(report)
        json_report = build_json_report(report)

        # ── Persist run ───────────────────────────────────────────────
        try:
            save_run(self.run_id, report.model_dump())
        except Exception as e:
            self.logger.warning("Failed to save run data: %s", e)

        self._progress("done", 1.0)
        self.logger.info(
            "=== Run %s completed in %.1f ms ===", self.run_id, duration
        )

        return md_report, json_report, report
