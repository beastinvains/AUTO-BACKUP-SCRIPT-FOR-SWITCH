import os
from pathlib import Path
from typing import Dict

from dotenv import load_dotenv


class CredentialError(Exception):
    """Raised when credentials are missing from the environment."""


def _profile_env_prefix(profile: str) -> str:
    return profile.upper().replace("-", "_")


def load_environment(env_file: Path | str | None = None) -> None:
    dotenv_path = Path(env_file or Path(__file__).resolve().parent / ".env")
    if dotenv_path.exists():
        load_dotenv(dotenv_path, override=True)


def get_credentials(profile: str, env_file: Path | str | None = None) -> Dict[str, str]:
    load_environment(env_file)
    prefix = _profile_env_prefix(profile)
    username = (
        os.environ.get(f"{prefix}_USERNAME")
        or os.environ.get(f"{prefix}_USER")
    )
    password = os.environ.get(f"{prefix}_PASSWORD")
    if not username or not password:
        raise CredentialError(f"Missing credentials for profile '{profile}'")
    return {"username": username, "password": password}
