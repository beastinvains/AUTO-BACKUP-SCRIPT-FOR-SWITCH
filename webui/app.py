"""Flask application factory for the local backup dashboard."""

from __future__ import annotations

from flask import Flask

from webui.routes import ui
from webui.services import BackupRunner


def create_app() -> Flask:
    """Create the local reporting interface."""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "local-backup-ui"
    app.extensions["backup_runner"] = BackupRunner()
    app.register_blueprint(ui)
    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)
