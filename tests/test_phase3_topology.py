"""Phase 3 topology tests: LLDP evidence in, honest graph out.

Everything here runs on fixtures and in-memory SQLite — no network hardware.
"""

import unittest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from database.models import Base, DeviceRecord, NeighborRecord
from topology.graph import (
    CONFIDENCE_CORROBORATED, CONFIDENCE_SINGLE_SIDED, CONFIDENCE_UNRESOLVED, build_graph,
)
from topology.normalization import (
    DeviceFacts, DeviceIndex, NeighborFacts, normalize_chassis_id, short_hostname,
)
from topology.service import TopologyService

CORE = DeviceFacts(id="d-core", name="core-sw01", type="switch", vendor="juniper", model="ex4300-48p",
                   management_ip="10.10.10.10", serial_number="JN0001", status="online", site="dc-a")
ACCESS = DeviceFacts(id="d-access", name="access-sw02.example.local", type="switch", vendor="juniper",
                     model="ex2300-24t", management_ip="10.10.10.11", serial_number="JN0002",
                     status="online", site="dc-a")
EDGE = DeviceFacts(id="d-edge", name="edge-fw01", type="firewall", vendor="juniper", model="srx300",
                   management_ip="10.10.20.1", serial_number="JN0003", status="degraded", site="dc-b")

SECRETISH = ("password", "secret", "credential", "private_key", "passphrase", "community")


def observed(device_id, local, *, name=None, remote=None, chassis=None) -> NeighborFacts:
    return NeighborFacts(device_id=device_id, local_interface=local, remote_system_name=name,
                         remote_interface=remote, remote_chassis_id=chassis)


class NormalizationTests(unittest.TestCase):
    def test_chassis_id_separators_are_irrelevant(self):
        self.assertEqual(normalize_chassis_id("00:11:22:33:44:55"), normalize_chassis_id("0011.2233.4455"))
        self.assertEqual(normalize_chassis_id("00-11-22-33-44-55"), "001122334455")
        self.assertIsNone(normalize_chassis_id(""))

    def test_fqdn_short_name_and_ip_all_resolve_to_one_device(self):
        index = DeviceIndex.build([CORE, ACCESS])
        self.assertEqual(index.resolve_neighbor(observed("x", "ge-0/0/0", name="access-sw02")), "d-access")
        self.assertEqual(index.resolve_neighbor(observed("x", "ge-0/0/0", name="ACCESS-SW02.example.local")), "d-access")
        self.assertEqual(index.resolve_neighbor(observed("x", "ge-0/0/0", name="10.10.10.11")), "d-access")
        self.assertEqual(index.resolve_neighbor(observed("x", "ge-0/0/0", chassis="jn0002")), "d-access")

    def test_colliding_short_hostname_is_refused_not_guessed(self):
        twin_a = DeviceFacts(id="a", name="core-sw01.site-a.local", management_ip="10.1.1.1")
        twin_b = DeviceFacts(id="b", name="core-sw01.site-b.local", management_ip="10.2.2.2")
        index = DeviceIndex.build([twin_a, twin_b])
        self.assertEqual(short_hostname(twin_a.name), "core-sw01")
        self.assertIn("core-sw01", index.ambiguous)
        self.assertIsNone(index.resolve_neighbor(observed("x", "ge-0/0/0", name="core-sw01")))
        # the unambiguous full name still resolves
        self.assertEqual(index.resolve_neighbor(observed("x", "ge-0/0/0", name="core-sw01.site-b.local")), "b")


class GraphConstructionTests(unittest.TestCase):
    def test_lldp_observation_becomes_one_interface_aware_edge(self):
        graph = build_graph([CORE, ACCESS], [observed("d-core", "ge-0/0/0", name="access-sw02", remote="ge-0/0/48")])
        (edge,) = graph["edges"]
        self.assertEqual(edge["relationship_type"], "CONNECTED_TO")
        self.assertEqual({edge["source"], edge["target"]}, {"d-core", "d-access"})
        self.assertEqual({edge["source_interface"], edge["target_interface"]}, {"ge-0/0/0", "ge-0/0/48"})
        self.assertEqual(edge["interface_evidence"], "complete")
        self.assertEqual(edge["evidence"]["source"], "lldp")
        self.assertEqual(edge["confidence"], CONFIDENCE_SINGLE_SIDED)
        self.assertEqual(graph["stats"]["node_count"], 2)

    def test_reciprocal_reports_collapse_into_one_corroborated_edge(self):
        graph = build_graph([CORE, ACCESS], [
            observed("d-core", "ge-0/0/0", name="access-sw02.example.local", remote="ge-0/0/48"),
            observed("d-access", "ge-0/0/48", name="core-sw01", remote="ge-0/0/0"),
        ])
        (edge,) = graph["edges"]
        self.assertTrue(edge["corroborated"])
        self.assertEqual(edge["confidence"], CONFIDENCE_CORROBORATED)
        self.assertEqual(len(edge["evidence"]["observations"]), 2)
        self.assertEqual(graph["stats"]["edge_count"], 1)

    def test_report_missing_remote_port_joins_the_known_link(self):
        graph = build_graph([CORE, ACCESS], [
            observed("d-core", "ge-0/0/0", name="access-sw02", remote="ge-0/0/48"),
            observed("d-access", "ge-0/0/48", name="core-sw01"),
        ])
        (edge,) = graph["edges"]
        self.assertEqual(edge["interface_evidence"], "complete")
        self.assertTrue(edge["corroborated"])

    def test_parallel_links_between_two_devices_stay_separate(self):
        graph = build_graph([CORE, ACCESS], [
            observed("d-core", "ge-0/0/0", name="access-sw02", remote="ge-0/0/48"),
            observed("d-core", "ge-0/0/1", name="access-sw02", remote="ge-0/0/47"),
        ])
        self.assertEqual(graph["stats"]["edge_count"], 2)
        # endpoint order is canonicalized by device id, so compare unordered port pairs
        pairs = {frozenset((edge["source_interface"], edge["target_interface"])) for edge in graph["edges"]}
        self.assertEqual(pairs, {frozenset(("ge-0/0/0", "ge-0/0/48")), frozenset(("ge-0/0/1", "ge-0/0/47"))})

    def test_unknown_neighbor_becomes_an_explicit_external_node(self):
        graph = build_graph([CORE], [observed("d-core", "ge-0/0/2", name="rogue-sw", remote="eth0",
                                              chassis="aa:bb:cc:dd:ee:ff")])
        external = [node for node in graph["nodes"] if node["kind"] == "external"]
        self.assertEqual(len(external), 1)
        self.assertFalse(external[0]["managed"])
        self.assertEqual(external[0]["hostname"], "rogue-sw")
        self.assertEqual(external[0]["status"], "unknown")
        self.assertEqual(external[0]["observed_by"], ["core-sw01"])
        self.assertEqual(graph["edges"][0]["confidence"], CONFIDENCE_UNRESOLVED)
        self.assertEqual(graph["stats"]["unresolved_neighbors"], 1)

    def test_one_unmanaged_neighbor_seen_twice_is_a_single_node(self):
        graph = build_graph([CORE, ACCESS], [
            observed("d-core", "ge-0/0/2", name="rogue", remote="eth0", chassis="aa:bb:cc:dd:ee:ff"),
            observed("d-access", "ge-0/0/2", name="rogue.local", remote="eth1", chassis="aabb.ccdd.eeff"),
        ])
        external = [node for node in graph["nodes"] if node["kind"] == "external"]
        self.assertEqual(len(external), 1)
        self.assertEqual(sorted(external[0]["observed_by"]), ["access-sw02.example.local", "core-sw01"])
        self.assertEqual(external[0]["degree"], 2)
        self.assertEqual(graph["stats"]["edge_count"], 2)

    def test_no_edge_without_a_local_port_or_any_remote_identity(self):
        graph = build_graph([CORE], [
            observed("d-core", "", name="access-sw02", remote="ge-0/0/48"),
            observed("d-core", "ge-0/0/5", name=None, remote="ge-0/0/1", chassis=None),
            observed("unknown-device", "ge-0/0/9", name="access-sw02"),
        ])
        self.assertEqual(graph["edges"], [])
        self.assertEqual(graph["stats"]["insufficient_evidence"], 3)

    def test_device_advertising_itself_is_not_a_link(self):
        graph = build_graph([CORE], [observed("d-core", "ge-0/0/0", name="core-sw01", remote="ge-0/0/0")])
        self.assertEqual(graph["edges"], [])
        self.assertEqual(graph["stats"]["unresolved_neighbors"], 0)

    def test_ambiguous_neighbor_is_reported_not_merged(self):
        twin_a = DeviceFacts(id="a", name="core-sw01.site-a.local", management_ip="10.1.1.1")
        twin_b = DeviceFacts(id="b", name="core-sw01.site-b.local", management_ip="10.2.2.2")
        graph = build_graph([twin_a, twin_b, ACCESS],
                            [observed("d-access", "ge-0/0/1", name="core-sw01", remote="ge-0/0/0")])
        # With default show_end_devices=False, twin_a and twin_b (type="other") are filtered out
        self.assertEqual(graph["stats"]["device_count"], 1)
        self.assertEqual(graph["stats"]["external_count"], 1)
        self.assertIn("core-sw01", graph["stats"]["ambiguous_identities"])

    def test_node_carries_the_labels_the_map_must_show(self):
        graph = build_graph([CORE], [])
        (node,) = graph["nodes"]
        for field in ("hostname", "vendor", "model", "status", "type", "management_ip"):
            self.assertIsNotNone(node[field], field)
        self.assertEqual(node["degree"], 0)

    def test_payload_never_carries_credentials(self):
        graph = build_graph([CORE, ACCESS], [observed("d-core", "ge-0/0/0", name="access-sw02", remote="ge-0/0/48")])
        blob = repr(graph).casefold()
        for term in SECRETISH:
            self.assertNotIn(term, blob)

    def test_filters_narrow_devices_and_drop_orphaned_externals(self):
        neighbors = [
            observed("d-core", "ge-0/0/0", name="access-sw02", remote="ge-0/0/48"),
            observed("d-edge", "ge-0/0/3", name="isp-router", remote="Gi0/1", chassis="11:22:33:44:55:66"),
        ]
        everything = build_graph([CORE, ACCESS, EDGE], neighbors)
        self.assertEqual(everything["stats"]["node_count"], 4)
        self.assertEqual(everything["filters"]["sites"], ["dc-a", "dc-b"])
        self.assertEqual(everything["filters"]["types"], ["firewall", "switch"])

        site_a = build_graph([CORE, ACCESS, EDGE], neighbors, site="dc-a")
        self.assertEqual([node["id"] for node in site_a["nodes"]], ["d-access", "d-core"])
        self.assertEqual(site_a["stats"]["external_count"], 0)
        self.assertEqual(site_a["filters"]["sites"], ["dc-a", "dc-b"])  # options stay stable

        firewalls = build_graph([CORE, ACCESS, EDGE], neighbors, device_type="FIREWALL")
        self.assertEqual([node["kind"] for node in firewalls["nodes"]], ["device", "external"])
        self.assertEqual(build_graph([CORE, ACCESS, EDGE], neighbors, status="degraded")["stats"]["device_count"], 1)
        self.assertEqual(build_graph([CORE, ACCESS, EDGE], neighbors, vendor="all")["stats"]["device_count"], 3)

    def test_graph_output_is_deterministic(self):
        neighbors = [observed("d-core", "ge-0/0/0", name="access-sw02", remote="ge-0/0/48")]
        self.assertEqual(build_graph([CORE, ACCESS], neighbors), build_graph([ACCESS, CORE], neighbors))


def _device_row(facts: DeviceFacts) -> DeviceRecord:
    return DeviceRecord(id=facts.id, name=facts.name, type=facts.type, vendor=facts.vendor, model=facts.model,
                        platform="junos", os_version="21.4R3", serial_number=facts.serial_number,
                        management_ip=facts.management_ip, management_port=22, credentials_reference_id="lab",
                        capabilities=["get_configuration"], status=facts.status, site=facts.site,
                        discovery_state="discovered", evidence={}, confidence=0.95)


class TopologyServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.statements = []
        event.listen(self.engine, "before_cursor_execute", self._count)
        with self.sessions() as session:
            session.add_all([_device_row(CORE), _device_row(ACCESS), _device_row(EDGE)])
            session.add_all([
                NeighborRecord(device_id="d-core", local_interface="ge-0/0/0", remote_system_name="access-sw02",
                               remote_interface="ge-0/0/48", remote_chassis_id="00:11:22:33:44:55"),
                NeighborRecord(device_id="d-access", local_interface="ge-0/0/48", remote_system_name="10.10.10.10",
                               remote_interface="ge-0/0/0", remote_chassis_id="00:11:22:33:44:66"),
                NeighborRecord(device_id="d-edge", local_interface="ge-0/0/3", remote_system_name="isp-router",
                               remote_interface="Gi0/1", remote_chassis_id="11:22:33:44:55:66"),
            ])
            session.commit()
        self.service = TopologyService(self.sessions)

    def tearDown(self):
        event.remove(self.engine, "before_cursor_execute", self._count)
        self.engine.dispose()

    def _count(self, conn, cursor, statement, *_args):
        if statement.lstrip().upper().startswith("SELECT"):
            self.statements.append(statement)

    def test_graph_reads_inventory_as_the_single_source_of_truth(self):
        graph = self.service.graph()
        self.assertEqual(graph["stats"]["device_count"], 3)
        self.assertEqual(graph["stats"]["external_count"], 1)
        self.assertEqual(graph["stats"]["edge_count"], 2)
        core = next(node for node in graph["nodes"] if node["id"] == "d-core")
        self.assertEqual(core["neighbor_count"], 1)
        self.assertIsNone(core["last_backup_at"])
        link = next(edge for edge in graph["edges"] if edge["target"] == "d-core" or edge["source"] == "d-core")
        self.assertTrue(link["corroborated"])  # management IP on one side, hostname on the other

    def test_graph_query_count_does_not_grow_with_inventory(self):
        self.statements.clear()
        self.service.graph()
        baseline = len(self.statements)
        with self.sessions() as session:
            for index in range(25):
                session.add(DeviceRecord(id=f"bulk-{index}", name=f"bulk-sw{index:02d}", type="switch",
                                         vendor="juniper", model="ex2300", platform="junos", os_version="21.4R3",
                                         serial_number=f"BULK{index:04d}", management_ip=f"10.99.0.{index + 1}",
                                         management_port=22, credentials_reference_id="lab", capabilities=[],
                                         status="online", site="dc-c", discovery_state="discovered",
                                         evidence={}, confidence=0.5))
                session.add(NeighborRecord(device_id=f"bulk-{index}", local_interface="ge-0/0/0",
                                           remote_system_name="core-sw01", remote_interface=f"ge-0/0/{index}"))
            session.commit()
        self.statements.clear()
        graph = self.service.graph()
        self.assertEqual(len(self.statements), baseline)
        self.assertEqual(graph["stats"]["device_count"], 28)
        self.assertEqual(graph["stats"]["edge_count"], 27)

    def test_nodes_and_edges_slices_agree_with_the_full_graph(self):
        graph, nodes, edges = self.service.graph(), self.service.nodes(), self.service.edges()
        self.assertEqual(nodes["nodes"], graph["nodes"])
        self.assertEqual(edges["edges"], graph["edges"])

    def test_device_slice_returns_only_the_local_neighborhood(self):
        slice_ = self.service.device_slice("d-edge")
        self.assertEqual(sorted(node["id"] for node in slice_["nodes"]),
                         ["d-edge", "external:chassis:112233445566"])
        self.assertEqual(slice_["stats"]["edge_count"], 1)
        with self.assertRaises(KeyError):
            self.service.device_slice("does-not-exist")

    def test_neighbor_view_says_whether_the_neighbor_is_managed(self):
        resolved = self.service.neighbors("d-core")
        self.assertEqual(resolved[0]["resolved_device_name"], ACCESS.name)
        self.assertTrue(resolved[0]["managed"])
        unresolved = self.service.neighbors("d-edge")
        self.assertFalse(unresolved[0]["managed"])
        self.assertIsNone(unresolved[0]["resolved_device_id"])


if __name__ == "__main__":
    unittest.main()
