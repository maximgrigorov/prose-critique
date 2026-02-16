#!/usr/bin/env python3
"""CLI entry point for prose-critique."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from modules.config import PipelineConfig
from modules.orchestrator import Orchestrator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="prose-critique",
        description="Analyze and critique prose text using LLM-powered pipeline.",
    )
    parser.add_argument(
        "-s", "--source",
        default="source.txt",
        help="Path to source text file (default: source.txt)",
    )
    parser.add_argument(
        "-r", "--requirements",
        default="",
        help="Path to requirements file (optional)",
    )
    parser.add_argument(
        "-o", "--output",
        default="result.md",
        help="Path for Markdown output (default: result.md)",
    )
    parser.add_argument(
        "-j", "--json-output",
        default="result.json",
        help="Path for JSON output (default: result.json)",
    )
    parser.add_argument(
        "-c", "--config",
        default="config.json",
        help="Path to config file (default: config.json)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=None,
        help="Increase verbosity (-v for INFO, -vv for DEBUG)",
    )
    parser.add_argument(
        "--no-audit",
        action="store_true",
        help="Disable the audit step",
    )
    return parser.parse_args()


async def main() -> int:
    args = parse_args()

    source_path = Path(args.source)
    if not source_path.exists():
        print(f"Error: source file not found: {source_path}", file=sys.stderr)
        return 1

    text = source_path.read_text(encoding="utf-8")
    if not text.strip():
        print("Error: source file is empty.", file=sys.stderr)
        return 1

    requirements = ""
    if args.requirements:
        req_path = Path(args.requirements)
        if req_path.exists():
            requirements = req_path.read_text(encoding="utf-8")

    overrides = {}
    if args.verbose is not None:
        overrides["verbosity"] = args.verbose + 1

    config = PipelineConfig.load(config_path=args.config, overrides=overrides)

    if args.no_audit:
        config.enable_audit = False

    if not config.openai_api_key and config.provider == "openai":
        print(
            "Error: OPENAI_API_KEY not set. "
            "Set it in .env or config.json, or use --provider litellm.",
            file=sys.stderr,
        )
        return 1

    orchestrator = Orchestrator(config=config)

    try:
        md_report, json_report, report = await orchestrator.run(text, requirements)
    except ValueError as e:
        print(f"Input error: {e}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"Runtime error: {e}", file=sys.stderr)
        return 1

    output_path = Path(args.output)
    output_path.write_text(md_report, encoding="utf-8")
    print(f"Markdown report written to: {output_path}")

    json_path = Path(args.json_output)
    json_path.write_text(json_report, encoding="utf-8")
    print(f"JSON report written to: {json_path}")

    qs = report.primary_analysis.quality_scores
    print(f"\nOverall score: {qs.overall:.1f}/10")
    if report.audit:
        print(f"Audit verdict: {report.audit.audit_verdict.value} "
              f"(confidence: {report.audit.confidence_score:.2f})")

    print(f"Run ID: {orchestrator.run_id}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
