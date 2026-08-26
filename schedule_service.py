"""Backup schedules.

A schedule row says *when* and *on which devices*; the run itself is handed to the
Phase 2 :class:`~backup_service.BackupService`, the same object the API and the CLI use.
That is deliberate: there is one backup implementation, one job table, and one audit
trail, so a scheduled backup and a manual backup are indistinguishable afterwards.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select

from database.models import AuditLogRecord, DeviceRecord, ScheduleRecord

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


class ScheduleFrequency(str, Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class ScheduleSpec(BaseModel):
    """Validated schedule input. Times are UTC so runs do not shift with the host."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    frequency: ScheduleFrequency = ScheduleFrequency.DAILY
    run_at: str = Field(default="02:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    device_ids: list[str] = Field(default_factory=list)  # empty means every managed device
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        if not (name := value.strip()):
            raise ValueError("name must not be blank")
        return name

    @model_validator(mode="after")
    def weekly_needs_a_day(self):
        """Checked on the whole model: an *omitted* day_of_week must fail too."""
        if self.frequency == ScheduleFrequency.WEEKLY and self.day_of_week is None:
            raise ValueError("weekly schedules require day_of_week (0=Monday)")
        return self


def _aware(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; treat stored values as the UTC they were."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def next_occurrence(frequency: str, run_at: str, day_of_week: int | None, after: datetime) -> datetime:
    """First UTC moment strictly after ``after`` that matches the cadence."""
    hour, minute = (int(part) for part in run_at.split(":"))
    after = _aware(after)
    if frequency == ScheduleFrequency.HOURLY:
        candidate = after.replace(minute=minute, second=0, microsecond=0)
        return candidate if candidate > after else candidate + timedelta(hours=1)
    candidate = after.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if frequency == ScheduleFrequency.WEEKLY:
        if day_of_week is not None:  # a row without a day repeats on the day it was armed
            candidate += timedelta(days=(day_of_week - candidate.weekday()) % 7)
        return candidate if candidate > after else candidate + timedelta(days=7)
    return candidate if candidate > after else candidate + timedelta(days=1)


def describe(record: ScheduleRecord) -> str:
    """Human-readable cadence for the schedules table."""
    if record.frequency == ScheduleFrequency.HOURLY:
        return f"Hourly at :{record.run_at.split(':')[1]}"
    if record.frequency == ScheduleFrequency.WEEKLY:
        day = WEEKDAYS[record.day_of_week] if record.day_of_week is not None else "unknown day"
        return f"Weekly on {day} at {record.run_at} UTC"
    return f"Daily at {record.run_at} UTC"


class ScheduleService:
    """CRUD plus execution for backup schedules; owns no device access of its own."""

    def __init__(self, sessions, backup_service, logger=None):
        self.sessions, self.backups, self.logger = sessions, backup_service, logger

    def list(self) -> list[dict]:
        with self.sessions() as session:
            records = list(session.scalars(select(ScheduleRecord).order_by(ScheduleRecord.name)))
            names = dict(session.execute(select(DeviceRecord.id, DeviceRecord.name)).all())
            return [self.serialize(record, names) for record in records]

    def get(self, schedule_id: str) -> dict:
        with self.sessions() as session:
            record = session.get(ScheduleRecord, schedule_id)
            if record is None:
                raise KeyError(schedule_id)
            names = dict(session.execute(select(DeviceRecord.id, DeviceRecord.name)).all())
            return self.serialize(record, names)

    def create(self, spec: ScheduleSpec, *, actor: str) -> dict:
        now = datetime.now(timezone.utc)
        with self.sessions() as session:
            self._assert_devices_exist(session, spec.device_ids)
            if session.scalar(select(ScheduleRecord).where(ScheduleRecord.name == spec.name)):
                raise ValueError(f"a schedule named {spec.name!r} already exists")
            record = ScheduleRecord(
                id=str(uuid4()), name=spec.name, device_ids=list(spec.device_ids),
                frequency=spec.frequency.value, run_at=spec.run_at, day_of_week=spec.day_of_week,
                enabled=spec.enabled, created_at=now, created_by=actor,
                next_run_at=next_occurrence(spec.frequency.value, spec.run_at, spec.day_of_week, now) if spec.enabled else None,
            )
            session.add(record)
            self._audit(session, actor, "SCHEDULE_CREATED", record)
            session.commit()
            names = dict(session.execute(select(DeviceRecord.id, DeviceRecord.name)).all())
            return self.serialize(record, names)

    def update(self, schedule_id: str, spec: ScheduleSpec, *, actor: str) -> dict:
        now = datetime.now(timezone.utc)
        with self.sessions() as session:
            record = session.get(ScheduleRecord, schedule_id)
            if record is None:
                raise KeyError(schedule_id)
            self._assert_devices_exist(session, spec.device_ids)
            clash = session.scalar(select(ScheduleRecord).where(
                ScheduleRecord.name == spec.name, ScheduleRecord.id != schedule_id))
            if clash:
                raise ValueError(f"a schedule named {spec.name!r} already exists")
            record.name, record.frequency, record.run_at = spec.name, spec.frequency.value, spec.run_at
            record.day_of_week, record.device_ids = spec.day_of_week, list(spec.device_ids)
            record.enabled, record.updated_at = spec.enabled, now
            record.next_run_at = next_occurrence(record.frequency, record.run_at, record.day_of_week, now) if spec.enabled else None
            self._audit(session, actor, "SCHEDULE_UPDATED", record)
            session.commit()
            names = dict(session.execute(select(DeviceRecord.id, DeviceRecord.name)).all())
            return self.serialize(record, names)

    def set_enabled(self, schedule_id: str, enabled: bool, *, actor: str) -> dict:
        now = datetime.now(timezone.utc)
        with self.sessions() as session:
            record = session.get(ScheduleRecord, schedule_id)
            if record is None:
                raise KeyError(schedule_id)
            record.enabled, record.updated_at = enabled, now
            record.next_run_at = next_occurrence(record.frequency, record.run_at, record.day_of_week, now) if enabled else None
            self._audit(session, actor, "SCHEDULE_ENABLED" if enabled else "SCHEDULE_DISABLED", record)
            session.commit()
            names = dict(session.execute(select(DeviceRecord.id, DeviceRecord.name)).all())
            return self.serialize(record, names)

    def delete(self, schedule_id: str, *, actor: str) -> None:
        with self.sessions() as session:
            record = session.get(ScheduleRecord, schedule_id)
            if record is None:
                raise KeyError(schedule_id)
            self._audit(session, actor, "SCHEDULE_DELETED", record)
            session.delete(record)
            session.commit()

    def due(self, now: datetime | None = None) -> list[str]:
        """Ids of enabled schedules whose next run has arrived."""
        now = _aware(now) or datetime.now(timezone.utc)
        with self.sessions() as session:
            records = session.scalars(select(ScheduleRecord).where(ScheduleRecord.enabled.is_(True)))
            return [record.id for record in records
                    if record.next_run_at is not None and _aware(record.next_run_at) <= now]

    def run_due(self, now: datetime | None = None) -> list[dict]:
        """Execute every due schedule through BackupService and re-arm it."""
        now = _aware(now) or datetime.now(timezone.utc)
        return [self.run(schedule_id, now=now) for schedule_id in self.due(now)]

    def run(self, schedule_id: str, *, now: datetime | None = None) -> dict:
        """Run one schedule immediately. The only backup path is BackupService."""
        now = _aware(now) or datetime.now(timezone.utc)
        with self.sessions() as session:
            record = session.get(ScheduleRecord, schedule_id)
            if record is None:
                raise KeyError(schedule_id)
            name, device_ids = record.name, list(record.device_ids)
        job_id = self.backups.create_job(device_ids or None, requested_by=f"schedule:{name}")
        try:
            job = self.backups.run(job_id)
            status = job["status"]
        except Exception as exc:  # a failed run must still re-arm the schedule
            status, job = "FAILED", {"job_id": job_id, "status": "FAILED", "error": type(exc).__name__}
        with self.sessions() as session:
            record = session.get(ScheduleRecord, schedule_id)
            if record is not None:
                record.last_run_at, record.last_status, record.last_job_id = now, status, job_id
                record.next_run_at = next_occurrence(record.frequency, record.run_at, record.day_of_week, now)
                session.add(AuditLogRecord(
                    id=str(uuid4()), actor=f"schedule:{name}", action="SCHEDULE_RUN",
                    resource_type="schedule", resource_id=schedule_id, correlation_id=job_id,
                    result=status, created_at=now,
                    details={"schedule": name, "device_count": len(record.device_ids) or "all"}))
                session.commit()
        return {"schedule_id": schedule_id, "job_id": job_id, "status": status, "job": job}

    @staticmethod
    def _assert_devices_exist(session, device_ids: list[str]) -> None:
        if not device_ids:
            return
        found = set(session.scalars(select(DeviceRecord.id).where(DeviceRecord.id.in_(device_ids))))
        if missing := sorted(set(device_ids) - found):
            raise ValueError(f"unknown device ids: {', '.join(missing)}")

    @staticmethod
    def _audit(session, actor: str, action: str, record: ScheduleRecord) -> None:
        session.add(AuditLogRecord(
            id=str(uuid4()), actor=actor, action=action, resource_type="schedule",
            resource_id=record.id, correlation_id=record.id, result="SUCCESS",
            created_at=datetime.now(timezone.utc),
            details={"schedule": record.name, "frequency": record.frequency, "run_at": record.run_at,
                     "enabled": record.enabled, "device_count": len(record.device_ids) or "all"}))

    @staticmethod
    def serialize(record: ScheduleRecord, device_names: dict[str, str] | None = None) -> dict:
        names = device_names or {}
        return {
            "id": record.id, "name": record.name, "frequency": record.frequency,
            "run_at": record.run_at, "day_of_week": record.day_of_week,
            "cadence": describe(record), "enabled": record.enabled,
            "device_ids": list(record.device_ids),
            "device_names": [names.get(device_id, device_id) for device_id in record.device_ids],
            "scope": "all devices" if not record.device_ids else f"{len(record.device_ids)} device(s)",
            "next_run_at": _aware(record.next_run_at), "last_run_at": _aware(record.last_run_at),
            "last_status": record.last_status, "last_job_id": record.last_job_id,
            "created_at": _aware(record.created_at), "created_by": record.created_by,
            "updated_at": _aware(record.updated_at),
        }
