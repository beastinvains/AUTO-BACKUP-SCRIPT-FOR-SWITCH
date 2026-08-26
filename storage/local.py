from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

from storage.base import ArtifactStorage


class LocalArtifactStorage(ArtifactStorage):
    """Filesystem development store with containment and immutable writes."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    @staticmethod
    def _safe_name(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9._-]", "_", value).strip("._") or "device"

    def put_configuration(self, *, device_name: str, version_id: str, content: bytes, collected_at: datetime) -> str:
        stamp = collected_at.astimezone()
        relative = Path(
            str(stamp.year), stamp.strftime("%m-%B"), stamp.strftime("%d"),
            self._safe_name(device_name), "configuration", f"{version_id}.cfg",
        )
        path = self._resolve(relative.as_posix())
        path.parent.mkdir(parents=True, exist_ok=True)
        # A version id is unique. Refusing replacement protects immutable history.
        if path.exists():
            raise FileExistsError("configuration artifact already exists")
        path.write_bytes(content)
        return relative.as_posix()

    def get(self, uri: str) -> bytes:
        return self._resolve(uri).read_bytes()

    def delete(self, uri: str) -> None:
        self._resolve(uri).unlink(missing_ok=True)

    def _resolve(self, uri: str) -> Path:
        candidate = (self.root / uri).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError("invalid artifact URI")
        return candidate
