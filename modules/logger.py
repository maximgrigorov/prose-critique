"""Logging utilities with per-run file logging and secret redaction."""

from __future__ import annotations

import logging
import re
import sys
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from modules.config import redact

WORKSPACE = Path(__file__).resolve().parent.parent / "workspace"
LOGS_DIR = WORKSPACE / "logs"
RUNS_DIR = WORKSPACE / "runs"


def _ensure_dirs() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)


class RedactingFormatter(logging.Formatter):
    """Formatter that masks anything that looks like an API key."""

    _patterns = [
        re.compile(r'(sk-[A-Za-z0-9_-]{20,})'),
        re.compile(r'(Bearer\s+[A-Za-z0-9_.-]{20,})'),
    ]

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        for pat in self._patterns:
            msg = pat.sub(lambda m: redact(m.group(1)), msg)
        return msg


def setup_logger(
    name: str = "prose-critique",
    verbosity: int = 1,
    run_id: Optional[str] = None,
) -> logging.Logger:
    """Create or retrieve a configured logger."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    level = {0: logging.WARNING, 1: logging.INFO}.get(verbosity, logging.DEBUG)
    logger.setLevel(level)

    fmt = RedactingFormatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    if run_id:
        _ensure_dirs()
        fh = logging.FileHandler(LOGS_DIR / f"{run_id}.log", encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


def generate_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")


def save_run(run_id: str, data: dict) -> Path:
    """Persist run JSON to workspace/runs/."""
    _ensure_dirs()
    p = RUNS_DIR / f"{run_id}.json"
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def list_runs() -> list[dict]:
    """List all run files, newest first."""
    _ensure_dirs()
    runs = []
    for f in sorted(RUNS_DIR.glob("*.json"), reverse=True):
        try:
            meta = json.loads(f.read_text(encoding="utf-8"))
            runs.append({
                "run_id": f.stem,
                "file": str(f),
                "timestamp": meta.get("timestamp", ""),
                "language": meta.get("language", ""),
                "input_chars": meta.get("input_char_count", 0),
            })
        except Exception:
            continue
    return runs


def list_logs() -> list[dict]:
    """List all log files, newest first."""
    _ensure_dirs()
    logs = []
    for f in sorted(LOGS_DIR.glob("*.log"), reverse=True):
        logs.append({
            "run_id": f.stem,
            "file": str(f),
            "size": f.stat().st_size,
        })
    return logs


def read_log(run_id: str) -> str:
    """Read a log file by run ID."""
    p = LOGS_DIR / f"{run_id}.log"
    if p.exists():
        return p.read_text(encoding="utf-8")
    return ""
