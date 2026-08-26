"""The mock lab estate must produce real evidence, not just plausible-looking text.

Every assertion here runs the fixtures through the *same* parsers and the *same* graph
builder the platform uses over SSH, so the lab guide's claims about what can be
demonstrated are checked instead of asserted.  No sockets and no hardware: the fixture
text goes through ``mock_switch.command_response`` exactly as a session would return it.
"""

from __future__ import annotations

import unittest

from adapters.juniper.adapter import (
    COMMANDS, parse_device_info, parse_health, parse_interfaces, parse_neighbors,
)
from core.models import DeviceStatus, DeviceType, DiscoveryState, DiscoveryTarget
from tests.lab_estate import (
    BASE_PORT, CONFIGURATION_COMMAND, UNREACHABLE_DEVICE, build_estate,
)
from tests.mock_switch import command_response
from topology.graph import build_graph
from topology.normalization import DeviceFacts, NeighborFacts

LAB_HOST = "192.168.50.20"  # any address; the lab reaches every persona on one host


def _session_output(persona, command: str) -> str:
    """What netmiko would hand the adapter: the echoed command plus the device output."""
    response = command_response(command, persona.responses)
    return response.split("\n", 1)[1] if "\n" in response else ""


def _discover(persona):
    """Run one persona through the discovery parsers, without a network."""
    target = DiscoveryTarget(
        name=persona.hostname, management_ip=LAB_HOST, port=persona.port(),
        credentials_reference_id="mock_lab", type=DeviceType(persona.device_type),
        vendor="juniper", site=persona.site,
    )
    device = parse_device_info(_session_output(persona, COMMANDS["facts"]), target)
    interfaces = parse_interfaces(_session_output(persona, COMMANDS["interfaces"]),
                                 _session_output(persona, COMMANDS["descriptions"]))
    neighbors = parse_neighbors(_session_output(persona, COMMANDS["neighbors"]))
    health = parse_health(_session_output(persona, COMMANDS["health"]), device.evidence.get("uptime"))
    return device, interfaces, neighbors, health


def _graph(personas=None) -> dict:
    """Build the topology the platform would build after discovering the whole estate."""
    personas = personas or build_estate()
    devices, observations = [], []
    for persona in personas:
        device, interfaces, neighbors, _ = _discover(persona)
        devices.append(DeviceFacts(
            id=device.name, name=device.name, type=device.type.value, vendor=device.vendor,
            model=device.model, platform=device.platform, os_version=device.os_version,
            management_ip=str(device.management_ip), serial_number=device.serial_number,
            status=device.status.value, site=device.site,
            discovery_state=device.discovery_state.value, confidence=device.confidence,
            interface_count=len(interfaces), neighbor_count=len(neighbors),
        ))
        observations += [NeighborFacts(
            device_id=device.name, local_interface=item.local_interface,
            remote_system_name=item.remote_system_name, remote_interface=item.remote_interface,
            remote_chassis_id=item.remote_chassis_id,
        ) for item in neighbors]
    return build_graph(devices, observations)


class LabEstateFixtureTests(unittest.TestCase):
    """The personas answer what the adapter asks, and answer it as Junos would."""

    def setUp(self) -> None:
        self.personas = build_estate()

    def test_every_command_the_adapter_issues_is_answered(self):
        for persona in self.personas:
            for key, command in COMMANDS.items():
                response = command_response(command, persona.responses)
                self.assertNotIn("% Invalid command", response, f"{persona.hostname}/{key}")
                self.assertTrue(response.startswith(f"{command}\n"), f"{persona.hostname}/{key} echo")

    def test_netmiko_session_setup_is_answered(self):
        """Netmiko's Junos driver sends these three before any show command."""
        for persona in self.personas:
            for command in ("set cli screen-width 511", "set cli complete-on-space off",
                            "set cli screen-length 0"):
                self.assertNotIn("% Invalid command", command_response(command, persona.responses),
                                 f"{persona.hostname}: {command}")

    def test_ports_are_distinct_and_start_at_the_base(self):
        ports = [persona.port() for persona in self.personas]
        self.assertEqual(ports, list(range(BASE_PORT, BASE_PORT + len(ports))))
        self.assertNotIn(BASE_PORT + int(UNREACHABLE_DEVICE["port_offset"]), ports)

    def test_each_persona_is_recognized_as_a_junos_device(self):
        for persona in self.personas:
            device, interfaces, neighbors, health = _discover(persona)
            with self.subTest(device=persona.hostname):
                self.assertEqual(device.name, persona.hostname)
                self.assertEqual((device.vendor, device.platform), ("juniper", "junos"))
                self.assertEqual(device.model, persona.model)
                self.assertEqual(device.os_version, persona.os_version)
                self.assertEqual(device.serial_number, persona.serial_number)
                self.assertEqual(device.status, DeviceStatus.ONLINE)
                self.assertEqual(device.discovery_state, DiscoveryState.DISCOVERED)
                self.assertEqual(device.management_port, persona.port())
                self.assertTrue(interfaces, "no interfaces parsed")
                self.assertEqual(health.cpu_percent, float(persona.cpu_percent))
                self.assertEqual(health.memory_percent, float(persona.memory_percent))
                self.assertEqual(device.evidence["uptime"], persona.uptime)

    def test_interface_descriptions_are_correlated(self):
        core = next(p for p in self.personas if p.hostname == "core-rtr01")
        _, interfaces, _, _ = _discover(core)
        by_name = {item.name: item for item in interfaces}
        self.assertEqual(by_name["ge-0/0/0"].description, "Transit to dist-sw01.dc-a")
        self.assertEqual(by_name["ge-0/0/0.0"].addresses, ["10.10.0.1/30"])
        self.assertEqual(by_name["ge-0/0/4"].operational_state, "down")

    def test_configurations_are_per_device_and_carry_secrets_to_redact(self):
        seen = set()
        for persona in self.personas:
            configuration = _session_output(persona, COMMANDS["configuration"])
            with self.subTest(device=persona.hostname):
                self.assertIn(f"set system host-name {persona.hostname}", configuration)
                self.assertIn("encrypted-password", configuration)  # redaction has something to do
                self.assertIn("snmp community" if persona.device_type != "firewall"
                              else "security policies", configuration)
                self.assertNotIn(configuration, seen, "two devices share a configuration")
                seen.add(configuration)


class LabEstateTopologyTests(unittest.TestCase):
    """The estate's LLDP evidence produces every graph outcome the lab guide promises."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = _graph()
        cls.stats = cls.graph["stats"]
        cls.edges = cls.graph["edges"]

    def edge_between(self, first: str, second: str) -> dict:
        match = next((edge for edge in self.edges
                      if {edge["source"], edge["target"]} == {first, second}), None)
        self.assertIsNotNone(match, f"no edge between {first} and {second}")
        return match

    def test_shape_of_the_estate(self):
        self.assertEqual(self.stats["device_count"], 6)
        self.assertEqual(self.stats["external_count"], 3)
        self.assertEqual(self.stats["edge_count"], 8)
        self.assertEqual(self.stats["unresolved_neighbors"], 3)

    def test_every_confidence_tier_is_demonstrated(self):
        self.assertEqual({edge["confidence"] for edge in self.edges}, {0.95, 0.7, 0.4})
        self.assertEqual(self.stats["corroborated_edges"], 2)
        corroborated = self.edge_between("core-rtr01", "dist-sw01.dc-a.lab")
        self.assertEqual(corroborated["confidence"], 0.95)
        self.assertEqual(len(corroborated["evidence"]["observations"]), 2)
        single_sided = self.edge_between("core-rtr01", "edge-fw01")
        self.assertEqual((single_sided["confidence"], single_sided["corroborated"]), (0.7, False))
        self.assertEqual(len(single_sided["evidence"]["observations"]), 1)

    def test_partial_interface_evidence_is_kept_partial(self):
        """access-sw01 sees access-sw02 on a neighbour that advertises no port id."""
        edge = self.edge_between("access-sw01", "access-sw02")
        self.assertEqual(edge["interface_evidence"], "partial")
        interfaces = {edge["source_interface"], edge["target_interface"]}
        self.assertEqual(interfaces, {"ge-0/0/1", None})
        self.assertEqual(edge["confidence"], 0.7)

    def test_ambiguous_uplink_is_refused_and_reported(self):
        """Both sites run a dist-sw01, so a short-name report must not pick one."""
        self.assertEqual(self.stats["ambiguous_identities"], ["dist-sw01"])
        self.assertFalse(self.edges_between("access-sw02", "dist-sw01.dc-a.lab"))
        self.assertFalse(self.edges_between("access-sw02", "dist-sw01.dc-b.lab"))
        # The uplink is still on the map, drawn to an explicit unmanaged node.
        uplink = next(edge for edge in self.edges
                      if "access-sw02" in (edge["source"], edge["target"])
                      and "ge-0/0/47" in (edge["source_interface"], edge["target_interface"]))
        externals = {node["id"] for node in self.graph["nodes"] if node["kind"] == "external"}
        far_end = uplink["target"] if uplink["source"] == "access-sw02" else uplink["source"]
        self.assertIn(far_end, externals)
        self.assertEqual(uplink["confidence"], 0.4)

    def edges_between(self, first: str, second: str) -> list[dict]:
        return [edge for edge in self.edges if {edge["source"], edge["target"]} == {first, second}]

    def test_unmanaged_neighbors_become_explicit_nodes(self):
        externals = {node["hostname"]: node for node in self.graph["nodes"] if node["kind"] == "external"}
        self.assertEqual(set(externals), {"isp-edge-rtr", "ap-lobby-01", "dist-sw01"})
        for node in externals.values():
            self.assertFalse(node["managed"])
            self.assertEqual(node["discovery_state"], "unrecognized")
            self.assertTrue(node["observed_by"], "an external node must say who saw it")

    def test_no_identity_less_observation_is_produced(self):
        """Every LLDP row in the estate carries an identity, so this counter stays 0.

        The lab cannot demonstrate ``insufficient_evidence`` — a device would have to report
        a neighbour with neither a name nor a chassis id — and that is documented rather
        than faked here.
        """
        self.assertEqual(self.stats["insufficient_evidence"], 0)

    def test_site_filter_narrows_the_map(self):
        graph = _graph()
        dc_b = build_graph(
            [DeviceFacts(id=node["id"], name=node["hostname"], type=node["type"], vendor=node["vendor"],
                         management_ip=node["management_ip"], serial_number=node["serial_number"],
                         status=node["status"], site=node["site"])
             for node in graph["nodes"] if node["kind"] == "device"],
            [NeighborFacts(device_id=observation["reported_by_id"],
                           local_interface=observation["local_interface"],
                           remote_system_name=observation["remote_system_name"],
                           remote_interface=observation["remote_interface"],
                           remote_chassis_id=observation["remote_chassis_id"])
             for edge in graph["edges"] for observation in edge["evidence"]["observations"]],
            site="dc-b",
        )
        self.assertEqual([node["hostname"] for node in dc_b["nodes"] if node["kind"] == "device"],
                         ["dist-sw01.dc-b.lab"])
        self.assertEqual(dc_b["stats"]["edge_count"], 0)  # its only peer is filtered out
        self.assertEqual(dc_b["filters"]["sites"], ["dc-a", "dc-b"])


class LabDriftTests(unittest.TestCase):
    """``drift`` in the lab console must produce a genuine configuration change."""

    def test_drift_changes_the_configuration_and_reports_what_changed(self):
        persona = next(p for p in build_estate() if p.hostname == "dist-sw01.dc-a.lab")
        before = persona.responses[CONFIGURATION_COMMAND]
        summary = persona.apply_drift()
        after = persona.responses[CONFIGURATION_COMMAND]
        self.assertTrue(summary)
        self.assertNotEqual(before, after)
        self.assertIn("set vlans GUEST vlan-id 30", after)
        self.assertEqual(len(after.splitlines()), len(before.splitlines()) + 1)
        self.assertEqual(persona.drift_applied, 1)

    def test_a_replacement_is_a_replacement_not_an_addition(self):
        persona = next(p for p in build_estate() if p.hostname == "dist-sw01.dc-a.lab")
        persona.apply_drift()
        before = persona.responses[CONFIGURATION_COMMAND].splitlines()
        persona.apply_drift()
        after = persona.responses[CONFIGURATION_COMMAND].splitlines()
        self.assertEqual(len(after), len(before))
        self.assertIn("set vlans VOICE vlan-id 120", after)
        self.assertNotIn("set vlans VOICE vlan-id 20", after)

    def test_drift_keeps_working_after_the_scripted_changes_run_out(self):
        persona = next(p for p in build_estate() if p.hostname == "dist-sw01.dc-b.lab")
        seen = set()
        for _ in range(len(persona.drift_steps) + 3):
            persona.apply_drift()
            configuration = persona.responses[CONFIGURATION_COMMAND]
            self.assertNotIn(configuration, seen, "drift produced no change")
            self.assertIn("set system host-name dist-sw01.dc-b.lab", configuration)
            seen.add(configuration)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
