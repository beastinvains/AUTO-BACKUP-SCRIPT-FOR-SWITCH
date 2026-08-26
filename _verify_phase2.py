"""End-to-end Phase 2 verification against the running mock switch (127.0.0.1:2222).

httpx is unavailable in this sandbox, so instead of an HTTP client this drives the
SAME objects the API uses: backend.app.backup_service (adapter -> BackupService ->
ConfigurationService -> storage) and the real FastAPI route functions
(list_configurations / get_configuration / diff_configurations). Everything below
the ASGI transport is exercised for real, including the live SSH backup.
"""
import os, tempfile

tmp = tempfile.mkdtemp(prefix="phase2_verify_")
os.environ["DATABASE_URL"] = f"sqlite:///{tmp}/verify.db"
os.environ["BACKUP_ROOT"] = f"{tmp}/artifacts"
# credentials_reference_id="mock" -> get_credentials reads MOCK_USERNAME/MOCK_PASSWORD.
# .env only defines LAB_JUNIPER_*, so load_dotenv(override=True) can't clobber these.
os.environ["MOCK_USERNAME"] = "admin"
os.environ["MOCK_PASSWORD"] = "admin"

from backend.app import backup_service, list_configurations, get_configuration, diff_configurations
from database.session import SessionLocal, engine
from database.models import Base, DeviceRecord

Base.metadata.create_all(engine)
with SessionLocal() as s:
    s.add(DeviceRecord(
        id="dev-mock", name="lab-ex4300", type="switch", vendor="juniper", platform="junos",
        management_ip="127.0.0.1", management_port=2222, credentials_reference_id="mock",
        capabilities=[], status="online", site="lab", discovery_state="discovered",
        evidence={}, confidence=0.95,
    ))
    s.commit()

print("== [4] management_port=2222: real SSH backup via BackupService.run ==")
job_id = backup_service.create_job(["dev-mock"], requested_by="verify")
job = backup_service.run(job_id)
res = job["results"][0]
print("job:", job["status"], "| success:", job["success_count"], "| fail:", job["failure_count"])
print("device result:", {k: res.get(k) for k in ("status", "change_status", "sha256", "error_category")})
assert job["status"] == "SUCCESS", f"backup did not succeed: {res}"
assert res["change_status"] == "CONFIGURATION_CHANGED"

print("\n== [5a] versioning + redaction via the real route functions ==")
with SessionLocal() as s:
    versions = list_configurations("dev-mock", session=s, _actor="verify")
    v1 = versions[0]["version_id"]
    content = get_configuration("dev-mock", v1, session=s, _actor="verify")["content"]
print("versions:", len(versions), "| size:", versions[0]["size_bytes"],
      "| redacted:", "<redacted>" in content, "| invalid_command:", "% Invalid" in content)
assert "% Invalid" not in content, "mock did not serve a real configuration"
assert "<redacted>" in content, "secret redaction did not run"
print("--- stored config (first 8 lines) ---")
print("\n".join(content.splitlines()[:8]))

print("\n== [5b] identical re-backup detected as NO_CHANGE (no new version) ==")
job2 = backup_service.run(backup_service.create_job(["dev-mock"], requested_by="verify"))
with SessionLocal() as s:
    count_after = len(list_configurations("dev-mock", session=s, _actor="verify"))
print("change_status:", job2["results"][0]["change_status"], "| version count still:", count_after)
assert job2["results"][0]["change_status"] == "NO_CHANGE" and count_after == 1

print("\n== [5c] diff of a changed version via the route (the '? ' KeyError case) ==")
with SessionLocal() as s:
    v2 = backup_service.configurations.store(
        s, device_id="dev-mock", device_name="lab-ex4300",
        raw=content.replace("vlan-id 40", "vlan-id 50")).version.id
    diff = diff_configurations("dev-mock", v1, v2, session=s, _actor="verify")
print("summary:", diff["summary"])
print("added:", diff["added"], "| removed:", diff["removed"])
assert diff["summary"]["added"] == 1 and diff["summary"]["removed"] == 1
assert diff["added"] == ["set vlans HR vlan-id 50"]

print("\nALL PHASE 2 END-TO-END CHECKS PASSED")
