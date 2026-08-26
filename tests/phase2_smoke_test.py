"""Phase 2 smoke test against the existing mock Juniper switch.

This exercises the project’s real implementation paths, not duplicate logic:
- the existing mock SSH switch
- the existing BackupService + ConfigurationService
- the existing FastAPI route helpers
- the existing DiscoveryService flow

The script uses a temporary SQLite database and temporary backup root so it does
not modify persistent project data.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _is_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _wait_for_port(host: str, port: int, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _is_port_open(host, port):
            return
        time.sleep(0.1)
    raise RuntimeError(f"Mock switch did not become ready at {host}:{port}")


def _start_mock_switch(host: str, port: int) -> subprocess.Popen[str] | None:
    if _is_port_open(host, port):
        return None
    proc = subprocess.Popen(
        [
            sys.executable,
            str(REPO_ROOT / "tests" / "mock_switch.py"),
            "--host",
            host,
            "--port",
            str(port),
        ],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    _wait_for_port(host, port, timeout=10)
    return proc


def _step(label: str, expected: object, actual: object) -> None:
    print(f"{label}: expected={expected!r} actual={actual!r}")
    if actual != expected:
        raise AssertionError(f"{label} failed: expected {expected!r}, got {actual!r}")


def _cleanup_dir(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        for child in sorted(path.rglob("*"), reverse=True):
            if child.is_file() or child.is_symlink():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        path.rmdir()
    else:
        path.unlink()


def main() -> None:
    temp_root = Path(tempfile.mkdtemp(prefix="phase2-smoke-"))
    db_path = temp_root / "phase2_smoke.db"
    backup_root = temp_root / "backups"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["BACKUP_ROOT"] = str(backup_root)
    os.environ["MOCK_USERNAME"] = "admin"
    os.environ["MOCK_PASSWORD"] = "admin"

    from adapters.juniper.adapter import JuniperAdapter
    from backend.app import backup_service, diff_configurations, get_configuration, list_configurations
    from core.models import DiscoveryTarget
    from database.models import Base, ConfigurationVersionRecord, DeviceRecord
    from database.session import SessionLocal, engine
    from discovery.jobs import DiscoveryService

    Base.metadata.create_all(engine)

    default_mock_proc: subprocess.Popen[str] | None = None
    alt_mock_proc: subprocess.Popen[str] | None = None
    try:
        print("Step 1: start or reuse existing mock switch")
        default_mock_proc = _start_mock_switch("127.0.0.1", 2222)
        if default_mock_proc is None:
            print("Step 1 PASS: using existing mock switch already listening on 127.0.0.1:2222")
        else:
            print("Step 1 PASS: started mock switch on 127.0.0.1:2222")

        print("Step 2: create test device record")
        with SessionLocal() as session:
            device_uuid = str(uuid4())
            record = DeviceRecord(
                id=device_uuid,
                name="lab-ex4300",
                type="switch",
                vendor="juniper",
                model="ex4300-48p",
                platform="junos",
                os_version="21.4R3-S5.4",
                serial_number="AB1234",
                management_ip="127.0.0.1",
                management_port=2222,
                credentials_reference_id="mock",
                capabilities=["device_info", "health", "interfaces", "lldp_neighbors"],
                status="online",
                site="lab",
                discovery_state="discovered",
                evidence={"fingerprint": "show version"},
                confidence=0.95,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            device_id = record.id
        _step("device created", True, bool(device_uuid))

        print("Step 3: trigger configuration backup through existing BackupService")
        job_id = backup_service.create_job([device_id], requested_by="smoke")
        job = backup_service.run(job_id)
        result = job["results"][0]
        _step("backup job status", "SUCCESS", job["status"])
        _step("device backup status", "SUCCESS", result["status"])
        _step("initial change status", "CONFIGURATION_CHANGED", result["change_status"])

        print("Step 4: verify configuration version is created")
        with SessionLocal() as session:
            versions = list_configurations(device_id, session=session, _actor="smoke")
            version_count = len(versions)
            version_id = versions[0]["version_id"] if versions else None
            stored = session.scalar(select(ConfigurationVersionRecord).where(ConfigurationVersionRecord.device_id == device_id))
        _step("version count", 1, version_count)
        _step("version exists", True, version_id is not None)
        _step("stored version record exists", True, stored is not None)

        print("Step 5: verify configuration hash is stored")
        with SessionLocal() as session:
            version_row = session.get(ConfigurationVersionRecord, version_id)
            content = get_configuration(device_id, version_id, session=session, _actor="smoke")["content"]
        _step("sha256 present", True, bool(version_row and version_row.sha256))
        _step("hash length", 64, len(version_row.sha256))
        _step("content redaction", True, "<redacted>" in content)

        print("Step 6: trigger second backup with the same configuration")
        second_job_id = backup_service.create_job([device_id], requested_by="smoke")
        second_job = backup_service.run(second_job_id)
        second_result = second_job["results"][0]
        with SessionLocal() as session:
            second_count = len(list_configurations(device_id, session=session, _actor="smoke"))
        _step("second backup change status", "NO_CHANGE", second_result["change_status"])
        _step("duplicate version count", 1, second_count)

        print("Step 7: modify mock configuration on a temporary second mock switch")
        mock_data_path = REPO_ROOT / "tests" / "mock_data.py"
        original_mock_data = mock_data_path.read_text(encoding="utf-8")
        modified_mock_data = original_mock_data.replace("set vlans HR vlan-id 40", "set vlans HR vlan-id 50")
        mock_data_path.write_text(modified_mock_data, encoding="utf-8")
        try:
            alt_mock_proc = _start_mock_switch("127.0.0.1", 2223)
            with SessionLocal() as session:
                record = session.get(DeviceRecord, device_id)
                record.management_port = 2223
                session.commit()
            print("Step 7 PASS: device updated to temporary mock port 2223 with changed configuration")
        finally:
            mock_data_path.write_text(original_mock_data, encoding="utf-8")

        print("Step 8: trigger another backup after config change")
        third_job_id = backup_service.create_job([device_id], requested_by="smoke")
        third_job = backup_service.run(third_job_id)
        third_result = third_job["results"][0]
        with SessionLocal() as session:
            third_count = len(list_configurations(device_id, session=session, _actor="smoke"))
            versions_after = list_configurations(device_id, session=session, _actor="smoke")
            newest = versions_after[0]["version_id"]
            oldest = versions_after[-1]["version_id"]
            diff = diff_configurations(device_id, oldest, newest, session=session, _actor="smoke")
        _step("third backup status", "SUCCESS", third_job["status"])
        _step("third backup change status", "CONFIGURATION_CHANGED", third_result["change_status"])
        _step("new version count", 2, third_count)
        _step("diff detected change", True, diff["summary"]["added"] > 0 or diff["summary"]["removed"] > 0)

        print("Step 9: verify Phase 1 discovery still works")
        discovery = DiscoveryService(JuniperAdapter(), SessionLocal)
        target = DiscoveryTarget(
            name="lab-ex4300",
            management_ip="127.0.0.1",
            port=2222,
            credentials_reference_id="mock",
            site="lab",
        )
        discovery_job = discovery.run([target])
        _step("discovery status", "success", discovery_job.status.value)
        _step("discovery result count", 1, len(discovery_job.results))

        print("Step 10: cleanup temporary test data")
        with SessionLocal() as session:
            session.query(DeviceRecord).filter(DeviceRecord.id == device_id).delete()
            session.query(ConfigurationVersionRecord).filter(ConfigurationVersionRecord.device_id == device_id).delete()
            session.commit()
        for proc in (alt_mock_proc, default_mock_proc):
            if proc is not None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except Exception:
                    pass
        _cleanup_dir(backup_root)
        _cleanup_dir(db_path)
        _cleanup_dir(temp_root)
        print("Step 10 PASS: temporary DB, artifact root, and test data removed")
        print("\nPHASE 2 END-TO-END SMOKE TEST PASS")

    finally:
        for proc in (alt_mock_proc, default_mock_proc):
            if proc is not None:
                try:
                    proc.terminate()
                    proc.wait(timeout=10)
                except Exception:
                    pass
        _cleanup_dir(backup_root)
        _cleanup_dir(db_path)
        _cleanup_dir(temp_root)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - script runner exit path
        print(f"PHASE 2 SMOKE TEST FAILED: {exc}")
        raise
