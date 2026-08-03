import os
from pathlib import Path
from typing import Dict

from dotenv import load_dotenv


class CredentialError(Exception):
    """Raised when credentials are missing from the environment."""


def load_environment(env_file: Path | str | None = None) -> None:
    dotenv_path = Path(env_file or Path(__file__).resolve().parent / ".env")
    if dotenv_path.exists():
        load_dotenv(dotenv_path, override=True)


def get_credentials(profile: str, env_file: Path | str | None = None) -> Dict[str, str]:
    load_environment(env_file)
    username = os.environ.get(f"{profile.upper()}_USERNAME")
    password = os.environ.get(f"{profile.upper()}_PASSWORD")
    if not username or not password:
        raise CredentialError(f"Missing credentials for profile '{profile}'")
    return {"username": username, "password": password}
