from __future__ import annotations

import difflib
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import ConfigurationVersionRecord
from storage.base import ArtifactStorage


SECRET_VALUE = re.compile(r"(?im)^(.*(?:encrypted-password|authentication-key|secret|private-key|community)\s+)(?:\"[^\"]*\"|\S+)(.*)$")


def normalize_configuration(raw: str) -> str:
    """Make line-oriented Junos snapshots deterministic and redact secret values."""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    lines = [SECRET_VALUE.sub(r"\1<redacted>\2", line) for line in lines]
    return "\n".join(lines).strip() + "\n"


def configuration_hash(normalized: str) -> str:
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def configuration_diff(before: str, after: str) -> dict:
    # ndiff also emits "? " hint lines marking intra-line change columns; they are
    # presentation guides, not configuration content, so drop them before mapping.
    lines = [line for line in difflib.ndiff(before.splitlines(), after.splitlines()) if not line.startswith("? ")]
    added = [line[2:] for line in lines if line.startswith("+ ")]
    removed = [line[2:] for line in lines if line.startswith("- ")]
    unchanged = [line[2:] for line in lines if line.startswith("  ")]
    return {"lines": [{"kind": {"+ ": "added", "- ": "removed", "  ": "unchanged"}[line[:2]], "text": line[2:]} for line in lines],
            "summary": {"added": len(added), "removed": len(removed), "unchanged": len(unchanged)},
            "added": added, "removed": removed}


@dataclass
class StoreResult:
    version: ConfigurationVersionRecord
    changed: bool
    created: bool


class ConfigurationService:
    def __init__(self, storage: ArtifactStorage):
        self.storage = storage

    def store(self, session: Session, *, device_id: str, device_name: str, raw: str,
              source_adapter: str = "juniper", platform: str = "junos") -> StoreResult:
        normalized = normalize_configuration(raw)
        digest = configuration_hash(normalized)
        previous = session.scalar(select(ConfigurationVersionRecord).where(
            ConfigurationVersionRecord.device_id == device_id
        ).order_by(ConfigurationVersionRecord.collected_at.desc()))
        if previous and previous.sha256 == digest:
            return StoreResult(previous, changed=False, created=False)
        now = datetime.now(timezone.utc)
        version = ConfigurationVersionRecord(
            id=str(uuid4()), device_id=device_id, parent_version_id=previous.id if previous else None,
            sha256=digest, source_adapter=source_adapter, platform=platform,
            collected_at=now, size_bytes=len(normalized.encode("utf-8")), status="success",
            retention_state="active", parser_version="junos-display-set-v1",
        )
        version.storage_uri = self.storage.put_configuration(
            device_name=device_name, version_id=version.id, content=normalized.encode("utf-8"), collected_at=now)
        session.add(version)
        session.commit()
        session.refresh(version)
        return StoreResult(version, changed=True, created=True)

    def content(self, version: ConfigurationVersionRecord) -> str:
        return self.storage.get(version.storage_uri).decode("utf-8")

    def apply_retention(self, session: Session, *, older_than_days: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        records = session.scalars(select(ConfigurationVersionRecord).where(
            ConfigurationVersionRecord.collected_at < cutoff,
            ConfigurationVersionRecord.retention_state == "active",
        )).all()
        for record in records:
            self.storage.delete(record.storage_uri)
            record.retention_state = "expired"
        session.commit()
        return len(records)
