"""Phase 3 API tests.

Everything here runs against an in-memory database and a fake adapter — no network
device is required.  The suite covers the device API, the topology API, add-device
validation, schedules (including that a scheduled run goes through the Phase 2
BackupService), log filtering, and regression coverage for the Phase 1 discovery and
Phase 2 backup/configuration-history endpoints.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.app as api
from adapters.base import AdapterError, BaseDeviceAdapter
from adapters.juniper.adapter import parse_device_info, parse_health, parse_interfaces, parse_neighbors
from configuration.service import ConfigurationService
from core.models import DiscoveryResult, DiscoveryTarget
from credentials import get_credentials
from database.models import AuditLogRecord, Base, BackupJobRecord, DeviceRecord, ScheduleRecord
from storage.local import LocalArtifactStorage
from tests.asgi_client import AsgiClient
from tests.fixtures.juniper import SHOW_DESCRIPTIONS, SHOW_HEALTH, SHOW_INTERFACES, SHOW_LLDP, SHOW_VERSION

CONFIG_V1 = "set system host-name lab-ex4300\nset system root-authentication encrypted-password $6$topsecret\nset vlans HR vlan-id 40\n"
CONFIG_V2 = CONFIG_V1.replace("vlan-id 40", "vlan-id 50")

ADMIN = {"x-role": "admin", "x-actor": "admin-user"}
OPERATOR = {"x-role": "operator", "x-actor": "operator-user"}
VIEWER = {"x-role": "viewer", "x-actor": "read-only-user"}

#: Keys that must never appear in an API payload, in any nesting.
SECRET_MARKERS = ("password", "secret", "passphrase", "private_key", "community")


class FakeAdapter(BaseDeviceAdapter):
    """Offline device: fixture discovery output and a canned configuration."""

    def __init__(self):
        self.configuration = CONFIG_V1
        self.failing: set[str] = set()

    def discover(self, target: DiscoveryTarget) -> DiscoveryResult:
        if target.name in self.failing:
            raise AdapterError("connection_error")
        return DiscoveryResult(
            device=parse_device_info(SHOW_VERSION, target),
            interfaces=parse_interfaces(SHOW_INTERFACES, SHOW_DESCRIPTIONS),
            neighbors=parse_neighbors(SHOW_LLDP), health=parse_health(SHOW_HEALTH))

    def get_configuration(self, target: DiscoveryTarget) -> str:
        if target.name in self.failing:
            raise AdapterError("NetmikoAuthenticationException")
        return self.configuration

    get_device_info = get_health = get_interfaces = get_neighbors = lambda self, target: None


def contains_secret(payload: object) -> bool:
    """True if any key anywhere in the structure looks like a secret."""
    if isinstance(payload, dict):
        return any(any(marker in str(key).lower() for marker in SECRET_MARKERS) for key in payload) \
            or any(contains_secret(value) for value in payload.values())
    if isinstance(payload, list):
        return any(contains_secret(item) for item in payload)
    return False


class ApiTestCase(unittest.TestCase):
    """Points the API's services at a throwaway database and a fake adapter."""

    def setUp(self):
        artifacts = tempfile.TemporaryDirectory()
        self.addCleanup(artifacts.cleanup)
        # A single shared connection: FastAPI runs sync endpoints on worker threads.
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.addCleanup(self.engine.dispose)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.adapter = FakeAdapter()

        original = {
            "topology": api.topology_service.sessions, "inventory": api.inventory_service.sessions,
            "schedules": api.schedule_service.sessions, "backup_sessions": api.backup_service.sessions,
            "backup_adapter": api.backup_service.adapter, "configurations": api.backup_service.configurations,
            "discovery_sessions": api.service.repository_factory, "discovery_adapter": api.service.adapter,
        }

        def restore():
            api.topology_service.sessions = original["topology"]
            api.inventory_service.sessions = original["inventory"]
            api.schedule_service.sessions = original["schedules"]
            api.backup_service.sessions = original["backup_sessions"]
            api.backup_service.adapter = original["backup_adapter"]
            api.backup_service.configurations = original["configurations"]
            api.service.repository_factory = original["discovery_sessions"]
            api.service.adapter = original["discovery_adapter"]
            api.service.jobs.clear()
            api.app.dependency_overrides.clear()

        self.addCleanup(restore)
        api.topology_service.sessions = self.sessions
        api.inventory_service.sessions = self.sessions
        api.schedule_service.sessions = self.sessions
        api.backup_service.sessions = self.sessions
        api.backup_service.adapter = self.adapter
        api.backup_service.configurations = ConfigurationService(LocalArtifactStorage(Path(artifacts.name)))
        api.service.repository_factory = self.sessions
        api.service.adapter = self.adapter
        api.service.jobs.clear()
        api.app.dependency_overrides[api.get_session] = self._session_dependency
        self.client = AsgiClient(api.app, headers=ADMIN)
        self.anonymous = AsgiClient(api.app)  # no X-Role at all

    def _session_dependency(self):
        with self.sessions() as session:
            yield session

    # -- fixtures -----------------------------------------------------------------
    def add_device(self, name: str, ip: str, **overrides) -> str:
        payload = {"name": name, "management_ip": ip, "credentials_reference_id": "lab-profile", **overrides}
        response = self.client.post("/api/devices", json_body=payload, headers=ADMIN)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["id"]

    def link(self, device_id: str, local: str, remote_name: str, remote_interface: str,
             chassis: str | None = None) -> None:
        """Write one LLDP observation exactly as Phase 1 discovery would."""
        from database.models import NeighborRecord
        with self.sessions() as session:
            session.add(NeighborRecord(
                device_id=device_id, local_interface=local, remote_system_name=remote_name,
                remote_interface=remote_interface, remote_chassis_id=chassis))
            session.commit()


class DeviceApiTests(ApiTestCase):
    def test_compliance_trend_endpoint_returns_points(self):
        response = self.client.get("/api/compliance/trend", params={"days": 7})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("points", response.json())

    def test_credential_loader_accepts_user_or_username_env_names(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text("LAB_JUNIPER_USER=legacy-user\nLAB_JUNIPER_PASSWORD=legacy-pass\n", encoding="utf-8")
            self.assertEqual(
                get_credentials("lab_juniper", env_file=env_path),
                {"username": "legacy-user", "password": "legacy-pass"},
            )

            env_path.write_text("LAB_JUNIPER_USERNAME=canonical-user\nLAB_JUNIPER_PASSWORD=canonical-pass\n", encoding="utf-8")
            self.assertEqual(
                get_credentials("lab_juniper", env_file=env_path),
                {"username": "canonical-user", "password": "canonical-pass"},
            )

    def test_list_and_read_a_device(self):
        device_id = self.add_device("core-sw01", "10.10.10.10", vendor="Juniper", site="dc-a")
        listing = self.client.get("/api/devices")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual([item["name"] for item in listing.json()], ["core-sw01"])
        detail = self.client.get(f"/api/devices/{device_id}")
        self.assertEqual(detail.json()["management_ip"], "10.10.10.10")
        self.assertEqual(detail.json()["vendor"], "juniper")  # normalized on the way in
        self.assertEqual(self.client.get("/api/devices/does-not-exist").status_code, 404)

    def test_device_summary_reports_counts_without_reading_artifacts(self):
        device_id = self.add_device("core-sw01", "10.10.10.10")
        self.link(device_id, "ge-0/0/0", "access-sw02", "ge-0/0/48")
        summary = self.client.get(f"/api/devices/{device_id}/summary").json()
        self.assertEqual(summary["neighbor_count"], 1)
        self.assertEqual(summary["interface_count"], 0)
        self.assertEqual(summary["configuration_version_count"], 0)
        self.assertIsNone(summary["last_backup_at"])
        self.assertFalse(contains_secret(summary))

    def test_device_payloads_never_contain_secret_fields(self):
        self.add_device("core-sw01", "10.10.10.10")
        for path in ("/api/devices", "/api/topology", "/api/dashboard"):
            self.assertFalse(contains_secret(self.client.get(path).json()), path)


class AddDeviceValidationTests(ApiTestCase):
    def test_creating_a_device_requires_an_administrator(self):
        payload = {"name": "core-sw01", "management_ip": "10.10.10.10", "credentials_reference_id": "lab"}
        self.assertEqual(self.client.post("/api/devices", json_body=payload, headers=OPERATOR).status_code, 403)
        self.assertEqual(self.client.post("/api/devices", json_body=payload, headers=VIEWER).status_code, 403)
        self.assertEqual(self.anonymous.post("/api/devices", json_body=payload).status_code, 403)

    def test_edit_and_delete_require_an_administrator(self):
        device_id = self.add_device("core-sw01", "10.10.10.10")
        payload = {"name": "renamed", "management_ip": "10.10.10.10", "credentials_reference_id": "lab"}
        self.assertEqual(self.client.put(f"/api/devices/{device_id}", json_body=payload, headers=OPERATOR).status_code, 403)
        self.assertEqual(self.client.delete(f"/api/devices/{device_id}", headers=VIEWER).status_code, 403)
        # a read-only user can still read
        self.assertEqual(self.client.get("/api/devices", headers=VIEWER).status_code, 200)

    def test_invalid_input_is_rejected(self):
        bad = [
            {"name": "", "management_ip": "10.0.0.1", "credentials_reference_id": "lab"},
            {"name": "sw", "management_ip": "not-an-ip", "credentials_reference_id": "lab"},
            {"name": "sw", "management_ip": "10.0.0.1", "credentials_reference_id": "lab", "management_port": 0},
            {"name": "sw", "management_ip": "10.0.0.1", "credentials_reference_id": "lab", "type": "toaster"},
            {"name": "sw", "management_ip": "10.0.0.1"},  # missing credential reference
        ]
        for payload in bad:
            self.assertEqual(self.client.post("/api/devices", json_body=payload, headers=ADMIN).status_code, 422, payload)

    def test_plaintext_passwords_are_refused_rather_than_ignored(self):
        response = self.client.post("/api/devices", headers=ADMIN, json_body={
            "name": "sw", "management_ip": "10.0.0.1", "credentials_reference_id": "lab",
            "password": "hunter2"})
        self.assertEqual(response.status_code, 422)
        self.assertIn("extra", response.text.lower())
        response = self.client.post("/api/devices", headers=ADMIN, json_body={
            "name": "sw", "management_ip": "10.0.0.1", "credentials_reference_id": "admin_password_1"})
        self.assertEqual(response.status_code, 422)
        with self.sessions() as session:
            self.assertEqual(session.scalar(select(DeviceRecord)), None)

    def test_duplicate_name_or_endpoint_is_a_conflict(self):
        self.add_device("core-sw01", "10.10.10.10")
        duplicate_endpoint = {"name": "other", "management_ip": "10.10.10.10", "credentials_reference_id": "lab"}
        duplicate_name = {"name": "core-sw01", "management_ip": "10.10.10.99", "credentials_reference_id": "lab"}
        self.assertEqual(self.client.post("/api/devices", json_body=duplicate_endpoint, headers=ADMIN).status_code, 409)
        self.assertEqual(self.client.post("/api/devices", json_body=duplicate_name, headers=ADMIN).status_code, 409)

    def test_same_address_on_another_port_is_a_different_device(self):
        """A device is the endpoint it is reached on, not the address alone.

        Several devices behind one address on different SSH ports is a real arrangement —
        a jump host, a console server, or the mock lab in ``tests/mock_lab.py`` — so the
        pair is what must be unique.
        """
        self.add_device("lab-core", "10.10.10.10", management_port=2201)
        second = self.add_device("lab-dist", "10.10.10.10", management_port=2202)
        self.assertEqual(self.client.post("/api/devices", headers=ADMIN, json_body={
            "name": "lab-dist-again", "management_ip": "10.10.10.10", "management_port": 2202,
            "credentials_reference_id": "lab"}).status_code, 409)
        moved = self.client.put(f"/api/devices/{second}", headers=ADMIN, json_body={
            "name": "lab-dist", "management_ip": "10.10.10.10", "management_port": 2201,
            "credentials_reference_id": "lab"})
        self.assertEqual(moved.status_code, 409)  # would collide with lab-core's endpoint

    def test_manual_device_is_unverified_and_audited(self):
        device_id = self.add_device("core-sw01", "10.10.10.10")
        with self.sessions() as session:
            record = session.get(DeviceRecord, device_id)
            self.assertEqual((record.status, record.discovery_state, record.confidence), ("unknown", "pending", 0.0))
            self.assertEqual(record.evidence["source"], "manual")
            entry = session.scalar(select(AuditLogRecord).where(AuditLogRecord.action == "DEVICE_CREATED"))
            self.assertEqual((entry.actor, entry.result), ("admin-user", "SUCCESS"))

    def test_update_and_delete_round_trip(self):
        device_id = self.add_device("core-sw01", "10.10.10.10")
        updated = self.client.put(f"/api/devices/{device_id}", headers=ADMIN, json_body={
            "name": "core-sw01", "management_ip": "10.10.10.10", "credentials_reference_id": "lab-profile",
            "site": "dc-b", "management_port": 2222})
        self.assertEqual(updated.status_code, 200)
        self.assertEqual((updated.json()["site"], updated.json()["management_port"]), ("dc-b", 2222))
        removed = self.client.delete(f"/api/devices/{device_id}", headers=ADMIN)
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(removed.json()["configuration_versions_removed"], 0)
        self.assertEqual(self.client.get(f"/api/devices/{device_id}").status_code, 404)


class TopologyApiTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.core = self.add_device("core-sw01", "10.10.10.10", vendor="Juniper", site="dc-a")
        self.access = self.add_device("access-sw02", "10.10.10.11", vendor="Juniper", site="dc-a")
        self.edge = self.add_device("edge-fw01", "10.10.20.1", vendor="Juniper", site="dc-b", type="firewall")
        self.link(self.core, "ge-0/0/0", "access-sw02", "ge-0/0/48")
        self.link(self.access, "ge-0/0/48", "core-sw01", "ge-0/0/0")

    def test_graph_endpoint_returns_nodes_edges_and_stats(self):
        graph = self.client.get("/api/topology").json()
        self.assertEqual({node["hostname"] for node in graph["nodes"]},
                         {"core-sw01", "access-sw02", "edge-fw01"})
        self.assertEqual(len(graph["edges"]), 1)  # both directions collapse into one link
        edge = graph["edges"][0]
        self.assertEqual(edge["relationship_type"], "CONNECTED_TO")
        self.assertEqual({edge["source_interface"], edge["target_interface"]}, {"ge-0/0/0", "ge-0/0/48"})
        self.assertTrue(edge["corroborated"])
        self.assertEqual(edge["evidence"]["source"], "lldp")
        self.assertEqual(graph["stats"]["device_count"], 3)

    def test_nodes_and_edges_endpoints_are_slices_of_the_same_graph(self):
        graph = self.client.get("/api/topology").json()
        self.assertEqual(self.client.get("/api/topology/nodes").json()["nodes"], graph["nodes"])
        self.assertEqual(self.client.get("/api/topology/edges").json()["edges"], graph["edges"])

    def test_filters_narrow_the_graph_without_narrowing_the_filter_options(self):
        filtered = self.client.get("/api/topology", params={"site": "dc-b"}).json()
        self.assertEqual([node["hostname"] for node in filtered["nodes"]], ["edge-fw01"])
        self.assertEqual(filtered["edges"], [])
        self.assertEqual(sorted(filtered["filters"]["sites"]), ["dc-a", "dc-b"])
        by_type = self.client.get("/api/topology", params={"device_type": "firewall"}).json()
        self.assertEqual([node["hostname"] for node in by_type["nodes"]], ["edge-fw01"])

    def test_site_route_matches_the_site_filter(self):
        self.assertEqual(self.client.get("/api/topology/dc-b").json()["nodes"],
                         self.client.get("/api/topology", params={"site": "dc-b"}).json()["nodes"])

    def test_device_slice_is_an_ego_graph(self):
        slice_ = self.client.get(f"/api/topology/devices/{self.core}").json()
        self.assertEqual({node["hostname"] for node in slice_["nodes"]}, {"core-sw01", "access-sw02"})
        self.assertEqual(slice_["stats"]["edge_count"], 1)
        self.assertEqual(self.client.get("/api/topology/devices/missing").status_code, 404)

    def test_unmanaged_neighbor_appears_as_an_external_node(self):
        self.link(self.edge, "ge-0/0/5", "isp-router", "xe-1/1/1")
        graph = self.client.get("/api/topology").json()
        external = [node for node in graph["nodes"] if not node["managed"]]
        self.assertEqual([node["hostname"] for node in external], ["isp-router"])
        self.assertEqual(graph["stats"]["unresolved_neighbors"], 1)

    def test_resolved_neighbors_endpoint_marks_managed_devices(self):
        raw = self.client.get(f"/api/devices/{self.core}/neighbors").json()
        self.assertEqual(raw[0]["remote_system_name"], "access-sw02")
        resolved = self.client.get(f"/api/devices/{self.core}/neighbors", params={"resolved": "true"}).json()
        self.assertEqual(resolved[0]["resolved_device_id"], self.access)
        self.assertTrue(resolved[0]["managed"])

    def test_topology_and_inventory_agree_on_device_ids(self):
        inventory = {item["id"] for item in self.client.get("/api/devices").json()}
        nodes = {node["id"] for node in self.client.get("/api/topology").json()["nodes"] if node["managed"]}
        self.assertEqual(inventory, nodes)


class ScheduleApiTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.device = self.add_device("core-sw01", "10.10.10.10")

    def create(self, **overrides):
        payload = {"name": "nightly", "frequency": "daily", "run_at": "02:00", **overrides}
        return self.client.post("/api/schedules", json_body=payload, headers=ADMIN)

    def test_creating_a_schedule_requires_an_administrator(self):
        self.assertEqual(self.client.post("/api/schedules", json_body={"name": "n"}, headers=OPERATOR).status_code, 403)
        self.assertEqual(self.client.post("/api/schedules", json_body={"name": "n"}, headers=VIEWER).status_code, 403)

    def test_schedule_is_created_with_a_next_run(self):
        response = self.create(device_ids=[self.device])
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual(body["cadence"], "Daily at 02:00 UTC")
        self.assertEqual(body["device_names"], ["core-sw01"])
        self.assertIsNotNone(body["next_run_at"])
        self.assertEqual([item["name"] for item in self.client.get("/api/schedules").json()], ["nightly"])

    def test_invalid_schedules_are_rejected(self):
        self.assertEqual(self.create(frequency="weekly").status_code, 422)  # weekly needs a day
        self.assertEqual(self.create(run_at="99:99").status_code, 422)
        self.assertEqual(self.create(frequency="fortnightly").status_code, 422)
        self.assertEqual(self.create(device_ids=["no-such-device"]).status_code, 409)
        self.create()
        self.assertEqual(self.create().status_code, 409)  # duplicate name

    def test_enable_disable_and_delete(self):
        schedule_id = self.create().json()["id"]
        disabled = self.client.post(f"/api/schedules/{schedule_id}/enabled", params={"enabled": "false"}, headers=ADMIN)
        self.assertFalse(disabled.json()["enabled"])
        self.assertIsNone(disabled.json()["next_run_at"])
        enabled = self.client.post(f"/api/schedules/{schedule_id}/enabled", params={"enabled": "true"}, headers=ADMIN)
        self.assertTrue(enabled.json()["enabled"])
        self.assertEqual(self.client.post(f"/api/schedules/{schedule_id}/enabled", params={"enabled": "false"},
                                          headers=OPERATOR).status_code, 403)
        self.assertEqual(self.client.delete(f"/api/schedules/{schedule_id}", headers=ADMIN).status_code, 204)
        self.assertEqual(self.client.get(f"/api/schedules/{schedule_id}").status_code, 404)

    def test_running_a_schedule_goes_through_the_phase_2_backup_service(self):
        schedule_id = self.create(device_ids=[self.device]).json()["id"]
        response = self.client.post(f"/api/schedules/{schedule_id}/run", headers=OPERATOR)
        self.assertEqual(response.status_code, 202)
        with self.sessions() as session:  # one job table, written by BackupService
            job = session.scalar(select(BackupJobRecord))
            self.assertEqual(job.requested_by, "schedule:nightly")
            self.assertEqual((job.status, job.success_count), ("SUCCESS", 1))
            self.assertEqual(job.results[0]["change_status"], "CONFIGURATION_CHANGED")
            schedule = session.get(ScheduleRecord, schedule_id)
            self.assertEqual((schedule.last_status, schedule.last_job_id), ("SUCCESS", job.id))

    def test_due_schedules_run_on_a_runner_tick(self):
        schedule_id = self.create().json()["id"]
        with self.sessions() as session:  # pull the next run into the past
            session.get(ScheduleRecord, schedule_id).next_run_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            session.commit()
        results = api.schedule_runner.tick()
        self.assertEqual([item["status"] for item in results], ["SUCCESS"])
        with self.sessions() as session:
            schedule = session.get(ScheduleRecord, schedule_id)
            self.assertGreater(schedule.next_run_at.replace(tzinfo=timezone.utc), datetime.now(timezone.utc))
            self.assertEqual(session.scalar(select(BackupJobRecord)).requested_by, "schedule:nightly")

    def test_a_failing_device_still_re_arms_the_schedule(self):
        self.adapter.failing.add("core-sw01")
        schedule_id = self.create(device_ids=[self.device]).json()["id"]
        self.client.post(f"/api/schedules/{schedule_id}/run", headers=ADMIN)
        with self.sessions() as session:
            schedule = session.get(ScheduleRecord, schedule_id)
            self.assertEqual(schedule.last_status, "FAILED")
            self.assertIsNotNone(schedule.next_run_at)


class BackupAndConfigurationRegressionTests(ApiTestCase):
    """Phase 2 behaviour must be unchanged by the Phase 3 additions."""

    def setUp(self):
        super().setUp()
        self.device = self.add_device("core-sw01", "10.10.10.10")

    def run_backup(self, headers=OPERATOR):
        response = self.client.post("/api/backups", json_body={"device_ids": [self.device]}, headers=headers)
        self.assertEqual(response.status_code, 202, response.text)
        return response.json()["job_id"]

    def test_backup_requires_an_operator_and_reports_per_device_results(self):
        self.assertEqual(self.client.post("/api/backups", json_body={"device_ids": []}, headers=VIEWER).status_code, 403)
        job_id = self.run_backup()
        job = self.client.get(f"/api/backups/{job_id}", headers=OPERATOR).json()
        self.assertEqual((job["status"], job["success_count"], job["failure_count"]), ("SUCCESS", 1, 0))
        self.assertEqual(job["results"][0]["device"], "core-sw01")
        self.assertEqual([item["job_id"] for item in self.client.get("/api/backups", headers=OPERATOR).json()], [job_id])

    def test_configuration_history_versions_only_on_change(self):
        self.run_backup()
        self.run_backup()  # identical configuration
        versions = self.client.get(f"/api/devices/{self.device}/configurations", headers=OPERATOR).json()
        self.assertEqual(len(versions), 1)
        self.adapter.configuration = CONFIG_V2
        self.run_backup()
        versions = self.client.get(f"/api/devices/{self.device}/configurations", headers=OPERATOR).json()
        self.assertEqual(len(versions), 2)
        self.assertNotEqual(versions[0]["sha256"], versions[1]["sha256"])

    def test_stored_configuration_is_redacted_and_diffable(self):
        self.run_backup()
        self.adapter.configuration = CONFIG_V2
        self.run_backup()
        versions = self.client.get(f"/api/devices/{self.device}/configurations", headers=OPERATOR).json()
        newest, oldest = versions[0]["version_id"], versions[1]["version_id"]
        content = self.client.get(f"/api/devices/{self.device}/configurations/{newest}", headers=OPERATOR).json()
        self.assertIn("<redacted>", content["content"])
        self.assertNotIn("topsecret", content["content"])
        diff = self.client.get(f"/api/devices/{self.device}/configurations/{oldest}/diff/{newest}",
                               headers=OPERATOR).json()
        self.assertEqual(diff["summary"], {"added": 1, "removed": 1, "unchanged": 2})
        self.assertEqual(diff["added"], ["set vlans HR vlan-id 50"])

    def test_configuration_endpoints_reject_unauthorized_readers(self):
        self.run_backup()
        self.assertEqual(self.client.get(f"/api/devices/{self.device}/configurations", headers=VIEWER).status_code, 403)

    def test_discovery_endpoint_reuses_the_phase_1_service(self):
        job = self.client.post(f"/api/devices/{self.device}/discovery", headers=OPERATOR)
        self.assertEqual(job.status_code, 200, job.text)
        self.assertEqual(job.json()["status"], "success")
        detail = self.client.get(f"/api/devices/{self.device}/summary").json()
        self.assertEqual(detail["interface_count"], 3)  # discovery wrote to the same row
        self.assertEqual(detail["neighbor_count"], 1)
        self.assertEqual(self.client.post(f"/api/devices/{self.device}/discovery", headers=VIEWER).status_code, 403)

    def test_interface_and_health_endpoints_serialize_for_the_ui(self):
        self.client.post(f"/api/devices/{self.device}/discovery", headers=OPERATOR)
        interfaces = self.client.get(f"/api/devices/{self.device}/interfaces").json()
        self.assertEqual([item["name"] for item in interfaces], ["ge-0/0/0", "ge-0/0/1", "irb.10"])
        self.assertEqual(interfaces[0]["description"], "Uplink to core")
        self.assertEqual(interfaces[2]["addresses"], ["10.0.10.2/24"])
        health = self.client.get(f"/api/devices/{self.device}/health").json()
        self.assertEqual((health["cpu_percent"], health["memory_percent"]), (18.0, 43.0))
        self.assertFalse(contains_secret(interfaces))


class LogApiTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.device = self.add_device("core-sw01", "10.10.10.10")
        self.client.post("/api/backups", json_body={"device_ids": [self.device]}, headers=OPERATOR)

    def test_events_cover_device_backup_and_job_activity(self):
        events = self.client.get("/api/logs").json()
        self.assertEqual({event["event"] for event in events},
                         {"DEVICE_CREATED", "BACKUP_CONFIGURATION", "BACKUP_JOB"})
        self.assertTrue(all(event["timestamp"] for event in events))

    def test_filters_narrow_the_feed(self):
        self.assertEqual({event["event"] for event in self.client.get("/api/logs", params={"category": "device"}).json()},
                         {"DEVICE_CREATED"})
        self.assertEqual({event["event"] for event in self.client.get("/api/logs", params={"category": "backup"}).json()},
                         {"BACKUP_CONFIGURATION", "BACKUP_JOB"})
        by_device = self.client.get("/api/logs", params={"device_id": self.device}).json()
        self.assertTrue(all(event["resource_id"] == self.device for event in by_device))
        self.assertEqual(self.client.get("/api/logs", params={"status": "FAILED"}).json(), [])
        self.assertEqual(len(self.client.get("/api/logs", params={"limit": 1}).json()), 1)
        self.assertTrue(self.client.get("/api/logs", params={"search": "core-sw01"}).json())

    def test_time_window_filters(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        self.assertEqual(self.client.get("/api/logs", params={"start": future}).json(), [])
        self.assertTrue(self.client.get("/api/logs", params={"start": past}).json())

    def test_authentication_failures_are_categorized(self):
        self.adapter.failing.add("core-sw01")
        self.client.post("/api/backups", json_body={"device_ids": [self.device]}, headers=OPERATOR)
        events = self.client.get("/api/logs", params={"category": "authentication"}).json()
        self.assertEqual([event["status"] for event in events], ["FAILED"])
        self.assertIn("Authentication failed", events[0]["summary"])

    def test_log_details_never_include_credential_material(self):
        events = self.client.get("/api/logs").json()
        created = next(event for event in events if event["event"] == "DEVICE_CREATED")
        self.assertIn("management_ip", created["details"])
        self.assertNotIn("credentials_reference", created["details"])  # secret-shaped key is dropped
        self.assertFalse(contains_secret(events))

    def test_filter_options_are_offered_to_the_ui(self):
        options = self.client.get("/api/logs/options").json()
        self.assertIn("discovery", options["categories"])
        self.assertIn("FAILED", options["statuses"])
        self.assertEqual([item["name"] for item in options["devices"]], ["core-sw01"])


class DashboardApiTests(ApiTestCase):
    def test_dashboard_counts_match_the_inventory_and_topology(self):
        core = self.add_device("core-sw01", "10.10.10.10", vendor="Juniper")
        access = self.add_device("access-sw02", "10.10.10.11", vendor="Juniper")
        self.link(core, "ge-0/0/0", "access-sw02", "ge-0/0/48")
        self.link(access, "ge-0/0/48", "core-sw01", "ge-0/0/0")
        self.client.post("/api/backups", json_body={"device_ids": [core]}, headers=OPERATOR)

        summary = self.client.get("/api/dashboard").json()
        self.assertEqual(summary["infrastructure"]["total_devices"], 2)
        self.assertEqual(summary["infrastructure"]["unknown"], 2)  # never discovered yet
        self.assertEqual(summary["infrastructure"]["by_vendor"], {"juniper": 2})
        self.assertEqual(summary["topology"]["connections"], 1)
        self.assertEqual(summary["topology"]["devices"], 2)
        self.assertEqual(summary["backup"]["devices_never_backed_up"], 1)
        self.assertEqual(summary["backup"]["total_jobs"], 1)
        self.assertEqual(summary["discovery"]["pending_devices"], 2)
        self.assertEqual(summary["schedules"]["total"], 0)


if __name__ == "__main__":
    unittest.main()
