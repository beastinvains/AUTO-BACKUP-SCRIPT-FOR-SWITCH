"""Flask application factory for the local backup dashboard."""

from __future__ import annotations

from flask import Flask

from config import load_config
from scheduler import BackupScheduler
from webui.routes import ui
from webui.services import BackupRunner


def create_app() -> Flask:
    """Create the local reporting interface."""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "local-backup-ui"
    runner = BackupRunner()
    app.extensions["backup_runner"] = runner
    app.extensions["backup_scheduler"] = BackupScheduler(
        callback=lambda: runner.start("scheduled"),
        config=load_config(),
    )
    app.register_blueprint(ui)
    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)
