"""
Evidence Service — Phase 4.

Stores immutable evidence artifacts (SHA-256 hashed) separately from
configuration backup artifacts. The file content lives in LocalArtifactStorage;
this module creates the EvidenceRecord row that tracks it.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from database.models import EvidenceRecord


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EvidenceService:
    """
    Manages creation and retrieval of EvidenceRecord rows.

    The storage backend is a simple local filesystem directory (same as
    LocalArtifactStorage) — no vendor commands, no SSH, pure file I/O.
    """

    def __init__(self, session_factory, storage_root: str | Path):
        self._session_factory = session_factory
        self._root = Path(storage_root) / "evidence"
        self._root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    def store(
        self,
        data: bytes | str | dict,
        evidence_type: str,
        device_id: str | None = None,
        collection_job_id: str | None = None,
        config_version_id: str | None = None,
        source_adapter: str | None = None,
        metadata: dict | None = None,
    ) -> EvidenceRecord:
        """
        Serialize *data*, compute SHA-256, write to disk, create EvidenceRecord.

        Returns the persisted EvidenceRecord (already committed).
        """
        if isinstance(data, dict):
            raw = json.dumps(data, sort_keys=True, default=str).encode()
        elif isinstance(data, str):
            raw = data.encode()
        else:
            raw = data

        sha256 = hashlib.sha256(raw).hexdigest()
        record_id = str(uuid4())
        # Namespace by device so old evidence is easy to sweep
        subdir = self._root / (device_id or "estate")
        subdir.mkdir(parents=True, exist_ok=True)
        path = subdir / f"{record_id}.json"
        path.write_bytes(raw)

        record = EvidenceRecord(
            id=record_id,
            device_id=device_id,
            collection_job_id=collection_job_id,
            collected_at=_utcnow(),
            evidence_type=evidence_type,
            source_adapter=source_adapter,
            sha256=sha256,
            size_bytes=len(raw),
            storage_uri=str(path),
            config_version_id=config_version_id,
            metadata_=metadata or {},
        )
        with self._session_factory() as session:
            session.add(record)
            session.commit()
            session.refresh(record)
        return record

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    def get(self, evidence_id: str) -> EvidenceRecord | None:
        with self._session_factory() as session:
            return session.get(EvidenceRecord, evidence_id)

    def content(self, evidence_id: str) -> bytes | None:
        record = self.get(evidence_id)
        if not record:
            return None
        path = Path(record.storage_uri)
        return path.read_bytes() if path.exists() else None

    def list_for_device(
        self,
        device_id: str,
        evidence_type: str | None = None,
        limit: int = 100,
    ) -> list[EvidenceRecord]:
        from sqlalchemy import select

        with self._session_factory() as session:
            q = select(EvidenceRecord).where(EvidenceRecord.device_id == device_id)
            if evidence_type:
                q = q.where(EvidenceRecord.evidence_type == evidence_type)
            q = q.order_by(EvidenceRecord.collected_at.desc()).limit(limit)
            return list(session.scalars(q))

    @staticmethod
    def serialize(record: EvidenceRecord) -> dict:
        return {
            "id": record.id,
            "device_id": record.device_id,
            "collection_job_id": record.collection_job_id,
            "collected_at": record.collected_at,
            "evidence_type": record.evidence_type,
            "source_adapter": record.source_adapter,
            "sha256": record.sha256,
            "size_bytes": record.size_bytes,
            "config_version_id": record.config_version_id,
            "metadata": record.metadata_,
        }
