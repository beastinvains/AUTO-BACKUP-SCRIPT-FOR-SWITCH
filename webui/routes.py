"""HTTP routes for the local backup dashboard."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from markupsafe import Markup, escape

from webui.services import current_settings, filtered_log_lines, latest_report, next_backup_at, recent_reports, report_devices, save_settings

ui = Blueprint("ui", __name__)


def _matches(device: dict[str, Any], query: str) -> bool:
    """Search device fields and all saved command content."""
    if not query:
        return True
    needle = query.casefold()
    fields = (device.get("hostname", ""), device.get("ip", ""), device.get("vendor", ""))
    return any(needle in str(value).casefold() for value in fields) or any(
        needle in str(command.get("command", "")).casefold() or needle in str(command.get("output", "")).casefold()
        for command in device.get("commands", []) if isinstance(command, dict)
    )


def highlight(value: object, query: str) -> Markup:
    """Safely highlight case-insensitive user search matches."""
    text = str(value or "")
    if not query:
        return Markup(escape(text))
    parts: list[str] = []
    position = 0
    for match in re.finditer(re.escape(query), text, re.IGNORECASE):
        parts.extend((str(escape(text[position:match.start()])), f"<mark>{escape(match.group())}</mark>"))
        position = match.end()
    parts.append(str(escape(text[position:])))
    return Markup("".join(parts))


@ui.app_context_processor
def navigation_context() -> dict[str, object]:
    """Expose common helpers to templates."""
    return {"highlight": highlight}


@ui.get("/")
def dashboard() -> str:
    report = latest_report()
    devices, statistics = report_devices(report), report.get("statistics", {})
    settings = current_settings()
    return render_template("dashboard.html", statistics={"total_devices": statistics.get("total_devices", len(devices)), "successful": statistics.get("successful", 0), "failed": statistics.get("failed", 0)}, last_backup=report.get("generated_at"), next_backup=next_backup_at(str(settings["backup_time"])))


@ui.get("/reports")
def reports() -> str:
    """Render raw report data for the client-side health dashboard."""
    query = request.args.get("q", "").strip()
    reports = recent_reports()
    report = reports[0] if reports else latest_report()
    return render_template(
        "reports.html",
        devices=report_devices(report),
        reports=reports,
        query=query,
        detail_url=url_for("ui.device_detail", hostname="__HOSTNAME__"),
    )


@ui.get("/devices/<hostname>")
def device_detail(hostname: str) -> str:
    device = next((item for item in report_devices(latest_report()) if item.get("hostname") == hostname), None)
    if device is None:
        abort(404)
    return render_template("device_detail.html", device=device, query=request.args.get("q", "").strip())


@ui.route("/settings", methods=["GET", "POST"])
def settings() -> str:
    if request.method == "POST":
        values = {key: request.form.get(key, "").strip() for key in ("backup_time", "backup_directory", "max_workers", "retention_days")}
        errors: list[str] = []
        try:
            datetime.strptime(values["backup_time"], "%H:%M")
        except ValueError:
            errors.append("Backup time must use 24-hour HH:MM format.")
        if not values["backup_directory"]:
            errors.append("Backup directory is required.")
        try:
            workers = int(values["max_workers"])
            if not 1 <= workers <= 64: raise ValueError
        except ValueError:
            errors.append("Worker threads must be a number from 1 to 64.")
            workers = 0
        try:
            retention = int(values["retention_days"])
            if not 1 <= retention <= 3650: raise ValueError
        except ValueError:
            errors.append("Retention must be a number from 1 to 3650 days.")
            retention = 0
        if errors:
            for error in errors: flash(error, "danger")
            return render_template("settings.html", settings=values)
        save_settings({"backup_time": values["backup_time"], "backup_directory": values["backup_directory"], "max_workers": workers, "retention_days": retention})
        flash("Settings saved. The scheduler will use them on its next check.", "success")
        return redirect(url_for("ui.settings"))
    return render_template("settings.html", settings=current_settings())


@ui.get("/logs")
def logs() -> str:
    level, query = request.args.get("level", "").upper(), request.args.get("q", "").strip()
    level = level if level in {"", "INFO", "WARNING", "ERROR"} else ""
    return render_template("logs.html", lines=filtered_log_lines(level, query), level=level, query=query)


@ui.post("/backup/run")
def run_backup() -> Any:
    runner = current_app.extensions["backup_runner"]
    started = runner.start()
    return jsonify(runner.status()), 202 if started else 409


@ui.get("/api/backup-status")
def backup_status() -> Any:
    return jsonify(current_app.extensions["backup_runner"].status())
