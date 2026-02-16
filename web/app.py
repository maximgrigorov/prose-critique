"""Flask web application for prose-critique."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import threading
from pathlib import Path
from typing import Optional

from flask import (
    Flask, render_template, request, jsonify, Blueprint,
    make_response, redirect, url_for, abort,
)
from werkzeug.middleware.proxy_fix import ProxyFix

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from modules.config import PipelineConfig
from modules.orchestrator import Orchestrator
from modules.logger import (
    generate_run_id, list_runs, list_logs, read_log,
    RUNS_DIR,
)

bp = Blueprint(
    "main", __name__,
    static_folder=str(Path(__file__).parent / "static"),
    static_url_path="/static",
)

_active_runs: dict[str, dict] = {}
_active_runs_lock = threading.Lock()

URL_PREFIX = os.getenv("URL_PREFIX", "")


@bp.route("/")
def index():
    return render_template("index.html", url_prefix=URL_PREFIX)


@bp.route("/api/config", methods=["GET"])
def get_config():
    cfg = PipelineConfig.load(config_path="config.json")
    return jsonify(cfg.to_dict(safe=True))


@bp.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.get_json(force=True)
    text = data.get("text", "").strip()
    requirements = data.get("requirements", "").strip()
    config_overrides = data.get("config", {})

    if not text:
        return jsonify({"error": "Text is required."}), 400

    config = PipelineConfig.load(config_path="config.json")

    if config_overrides:
        _apply_web_config(config, config_overrides)

    if not config.openai_api_key and config.provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "")
        if api_key:
            config.openai_api_key = api_key
        else:
            return jsonify({"error": "OPENAI_API_KEY not configured."}), 400

    if len(text) > config.max_input_chars:
        return jsonify({
            "error": f"Text exceeds {config.max_input_chars} character limit (got {len(text)})."
        }), 400

    run_id = generate_run_id()

    with _active_runs_lock:
        _active_runs[run_id] = {
            "status": "running",
            "progress": 0.0,
            "stage": "starting",
            "cancel": False,
        }

    thread = threading.Thread(
        target=_run_pipeline_in_thread,
        args=(run_id, config, text, requirements),
        daemon=True,
    )
    thread.start()

    return jsonify({"run_id": run_id, "status": "started"})


@bp.route("/api/status/<run_id>", methods=["GET"])
def run_status(run_id: str):
    with _active_runs_lock:
        info = _active_runs.get(run_id)

    if not info:
        run_file = RUNS_DIR / f"{run_id}.json"
        if run_file.exists():
            return jsonify({"status": "completed", "run_id": run_id})
        return jsonify({"error": "Run not found."}), 404

    return jsonify({
        "run_id": run_id,
        "status": info["status"],
        "stage": info.get("stage", ""),
        "progress": info.get("progress", 0),
        "error": info.get("error"),
    })


@bp.route("/api/result/<run_id>", methods=["GET"])
def run_result(run_id: str):
    with _active_runs_lock:
        info = _active_runs.get(run_id, {})

    if info.get("status") == "completed":
        return jsonify({
            "run_id": run_id,
            "markdown": info.get("markdown", ""),
            "json_report": info.get("json_report"),
        })

    run_file = RUNS_DIR / f"{run_id}.json"
    if run_file.exists():
        report_data = json.loads(run_file.read_text(encoding="utf-8"))
        from modules.models import CritiqueReport
        from modules.agents.report_builder import build_markdown_report
        report = CritiqueReport(**report_data)
        md = build_markdown_report(report)
        return jsonify({
            "run_id": run_id,
            "markdown": md,
            "json_report": report_data,
        })

    return jsonify({"error": "Result not ready."}), 404


@bp.route("/api/cancel/<run_id>", methods=["POST"])
def cancel_run(run_id: str):
    with _active_runs_lock:
        info = _active_runs.get(run_id)
        if info and info["status"] == "running":
            info["cancel"] = True
            return jsonify({"status": "cancelling"})
    return jsonify({"error": "Run not found or not running."}), 404


@bp.route("/api/runs", methods=["GET"])
def get_runs():
    return jsonify(list_runs())


@bp.route("/api/logs", methods=["GET"])
def get_logs():
    return jsonify(list_logs())


@bp.route("/api/logs/<run_id>", methods=["GET"])
def get_log(run_id: str):
    content = read_log(run_id)
    if content:
        return jsonify({"run_id": run_id, "content": content})
    return jsonify({"error": "Log not found."}), 404


@bp.route("/run/<run_id>/print")
def run_print(run_id: str):
    """Print-optimized view of a run — A4 layout with all sections."""
    report_data = _load_report_data(run_id)
    if not report_data:
        abort(404, "Run not found or no results available")
    return render_template(
        "print_report.html",
        report=report_data,
        run_id=run_id,
        is_ru=report_data.get("language") == "ru",
        is_pdf=False,
    )


@bp.route("/api/run/<run_id>/pdf")
def run_pdf(run_id: str):
    """Download PDF report.

    Uses WeasyPrint if available; otherwise redirects to the print view.
    """
    report_data = _load_report_data(run_id)
    if not report_data:
        return jsonify({"error": "Run not found or no results available"}), 404

    html = render_template(
        "print_report.html",
        report=report_data,
        run_id=run_id,
        is_ru=report_data.get("language") == "ru",
        is_pdf=True,
    )

    try:
        import weasyprint
        pdf_bytes = weasyprint.HTML(string=html).write_pdf()
        response = make_response(pdf_bytes)
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = (
            f'attachment; filename="prose_critique_{run_id}.pdf"'
        )
        return response
    except ImportError:
        return redirect(url_for("main.run_print", run_id=run_id))
    except Exception:
        return redirect(url_for("main.run_print", run_id=run_id))


def _load_report_data(run_id: str) -> dict | None:
    """Load report data from active runs or saved files."""
    with _active_runs_lock:
        info = _active_runs.get(run_id, {})

    if info.get("status") == "completed" and info.get("json_report"):
        return info["json_report"]

    run_file = RUNS_DIR / f"{run_id}.json"
    if run_file.exists():
        return json.loads(run_file.read_text(encoding="utf-8"))

    return None


def _run_pipeline_in_thread(
    run_id: str,
    config: PipelineConfig,
    text: str,
    requirements: str,
) -> None:
    """Run the pipeline in a background thread with its own event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def progress_cb(stage: str, pct: float):
        with _active_runs_lock:
            info = _active_runs.get(run_id)
            if info:
                info["stage"] = stage
                info["progress"] = pct

    def cancel_check() -> bool:
        with _active_runs_lock:
            info = _active_runs.get(run_id)
            return info.get("cancel", False) if info else False

    try:
        orchestrator = Orchestrator(
            config=config,
            run_id=run_id,
            progress_cb=progress_cb,
            cancel_check=cancel_check,
        )

        md_report, json_report, report = loop.run_until_complete(
            orchestrator.run(text, requirements)
        )

        with _active_runs_lock:
            _active_runs[run_id] = {
                "status": "completed",
                "stage": "done",
                "progress": 1.0,
                "markdown": md_report,
                "json_report": report.model_dump(),
            }

    except Exception as e:
        with _active_runs_lock:
            _active_runs[run_id] = {
                "status": "error",
                "stage": "error",
                "progress": 0,
                "error": str(e),
            }
    finally:
        loop.close()


def _apply_web_config(config: PipelineConfig, overrides: dict) -> None:
    """Apply config overrides from web form (safe subset only)."""
    safe_keys = {
        "enable_audit", "enable_cache", "verbosity",
        "max_input_chars", "max_report_chars",
    }
    for k, v in overrides.items():
        if k in safe_keys:
            setattr(config, k, v)

    models = overrides.get("models", {})
    if "primary" in models:
        for mk in ("model", "temperature", "top_p", "max_tokens"):
            if mk in models["primary"]:
                setattr(config.primary, mk, models["primary"][mk])
    if "audit" in models:
        for mk in ("model", "temperature", "top_p", "max_tokens"):
            if mk in models["audit"]:
                setattr(config.audit, mk, models["audit"][mk])

    if "provider" in overrides:
        config.provider = overrides["provider"]


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
        static_folder=str(Path(__file__).parent / "static"),
    )
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    if URL_PREFIX:
        app.register_blueprint(bp, url_prefix=URL_PREFIX)
    else:
        app.register_blueprint(bp)

    return app


def main():
    parser = argparse.ArgumentParser(description="prose-critique web UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8020)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    app = create_app()
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
