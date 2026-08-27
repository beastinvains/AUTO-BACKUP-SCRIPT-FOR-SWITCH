import io
import json
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from adapters.base import AdapterError, BaseDeviceAdapter
from adapters.juniper.adapter import JuniperAdapter, parse_device_info, parse_health, parse_interfaces, parse_neighbors
from audit.logging import log_discovery
from core.models import DiscoveryResult, DiscoveryTarget
from database.models import Base, HealthRecord
from database.session import SessionLocal
from discovery.jobs import DiscoveryService, JobStatus
from inventory.repository import InventoryRepository
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from tests.fixtures.juniper import SHOW_DESCRIPTIONS, SHOW_HEALTH, SHOW_INTERFACES, SHOW_LLDP, SHOW_VERSION
from tests.mock_switch import command_response


class FakeConnection:
    def __init__(self):
        self.commands = []

    def send_command(self, command, **_kwargs):
        self.commands.append(command)
        return {
            "show version | no-more": SHOW_VERSION,
            "show interfaces terse | no-more": SHOW_INTERFACES,
            "show interfaces descriptions | no-more": SHOW_DESCRIPTIONS,
            "show lldp neighbors | no-more": SHOW_LLDP,
            "show system processes extensive | no-more": SHOW_HEALTH,
        }[command]

    def disconnect(self):
        pass


class JuniperParserTests(unittest.TestCase):
    def setUp(self):
        self.target = DiscoveryTarget(name="seed", management_ip="192.0.2.10", credentials_reference_id="lab")

    def test_device_identification_and_validation(self):
        device = parse_device_info(SHOW_VERSION, self.target)
        self.assertEqual(device.vendor, "juniper")
        self.assertEqual(device.platform, "junos")
        self.assertEqual(device.model, "ex4300-48p")
        self.assertEqual(device.confidence, 0.95)

    def test_interface_lldp_and_health_parsing(self):
        interfaces = parse_interfaces(SHOW_INTERFACES, SHOW_DESCRIPTIONS)
        self.assertEqual(interfaces[0].description, "Uplink to core")
        self.assertEqual(interfaces[2].addresses, ["10.0.10.2/24"])
        neighbors = parse_neighbors(SHOW_LLDP)
        self.assertEqual(neighbors[0].local_interface, "ge-0/0/0")
        self.assertEqual(neighbors[0].remote_system_name, "core-sw")
        health = parse_health(SHOW_HEALTH)
        self.assertEqual((health.cpu_percent, health.memory_percent), (18.0, 43.0))

    def test_adapter_only_runs_allowlisted_discovery_commands(self):
        connection = FakeConnection()
        adapter = JuniperAdapter(credentials_provider=lambda _: {"username": "user", "password": "not-logged"},
                                 connection_factory=lambda **_: connection)
        result = adapter.discover(self.target)
        self.assertEqual(result.device.vendor, "juniper")
        self.assertEqual(len(result.interfaces), 3)
        self.assertEqual(len(result.neighbors), 1)
        self.assertEqual(len(connection.commands), 5)

    def test_mock_switch_supports_phase1_juniper_commands(self):
        self.assertIn("Hostname: lab-ex4300", command_response("show version | no-more"))
        self.assertIn("ge-0/0/0", command_response("show interfaces terse | no-more"))
        self.assertIn("Uplink to core", command_response("show interfaces descriptions | no-more"))
        self.assertIn("core-sw", command_response("show lldp neighbors | no-more"))
        self.assertIn("CPU utilization: 18", command_response("show system processes extensive | no-more"))
        self.assertIn("Screen width set to", command_response("set cli screen-width 511"))
        self.assertIn("Disabling complete-on-space", command_response("set cli complete-on-space off"))
        self.assertIn("Screen length set to", command_response("set cli screen-length 0"))


class SuccessfulAdapter(BaseDeviceAdapter):
    def discover(self, target):
        return DiscoveryResult(device=parse_device_info(SHOW_VERSION, target),
                               interfaces=parse_interfaces(SHOW_INTERFACES, SHOW_DESCRIPTIONS),
                               neighbors=parse_neighbors(SHOW_LLDP), health=parse_health(SHOW_HEALTH))
    get_device_info = get_health = get_interfaces = get_neighbors = lambda self, target: None


class FailingAdapter(SuccessfulAdapter):
    def discover(self, target):
        if target.name == "bad":
            raise AdapterError("connection_error")
        return super().discover(target)


class DiscoveryAndPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.targets = [
            DiscoveryTarget(name="good", management_ip="192.0.2.10", credentials_reference_id="lab"),
            DiscoveryTarget(name="bad", management_ip="192.0.2.11", credentials_reference_id="lab"),
        ]

    def test_failed_device_does_not_stop_partial_job_and_persists_success(self):
        job = DiscoveryService(FailingAdapter(), self.sessions).run(self.targets)
        self.assertEqual(job.status, JobStatus.PARTIAL)
        self.assertEqual([item.status for item in job.results], [JobStatus.SUCCESS, JobStatus.FAILED])
        with self.sessions() as session:
            records = InventoryRepository(session).list()
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].vendor, "juniper")
            self.assertEqual(len(records[0].interfaces), 3)

    def test_repeated_discovery_updates_existing_health_row(self):
        connection = FakeConnection()
        adapter = JuniperAdapter(
            credentials_provider=lambda _: {"username": "user", "password": "not-logged"},
            connection_factory=lambda **_: connection,
        )
        target = DiscoveryTarget(name="good", management_ip="192.0.2.10", credentials_reference_id="lab")
        service = DiscoveryService(adapter, self.sessions)
        service.run([target])
        service.run([target])
        with self.sessions() as session:
            self.assertEqual(session.query(HealthRecord).count(), 1)

    def test_secret_fields_are_not_logged(self):
        stream = io.StringIO()
        logger = logging.getLogger("phase1.secret-test")
        logger.handlers[:] = [logging.StreamHandler(stream)]
        logger.setLevel(logging.INFO)
        log_discovery(logger, event="test", password="should-not-appear", credentials_reference_id="also-hidden")
        self.assertNotIn("should-not-appear", stream.getvalue())
        self.assertNotIn("credentials_reference_id", stream.getvalue())


if __name__ == "__main__":
    unittest.main()

