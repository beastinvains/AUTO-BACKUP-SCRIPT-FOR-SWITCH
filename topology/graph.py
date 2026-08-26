"""Evidence-based topology graph construction.

Pure functions over :mod:`topology.normalization` facts: no database, no HTTP, no
vendor syntax, so the whole LLDP-to-graph behavior is unit-testable with fixtures.

Rules that keep the graph honest (blueprint 14.3 / 15 "Incorrect topology"):

* an edge requires a local interface **and** a remote identity — nothing is invented;
* a neighbor that cannot be matched to inventory unambiguously becomes an explicit
  ``external`` node instead of being merged into a lookalike device;
* confidence rises only through corroboration, never through repetition.
"""

from __future__ import annotations

from topology.normalization import (
    DeviceFacts, DeviceIndex, NeighborFacts, external_node_key, normalize_chassis_id,
)

#: The only relationship Phase 3 has evidence for. Later phases add HOSTS, RUNS,
#: DEPENDS_ON, ROUTES_TO and BALANCES_TO; the payload shape already carries the type.
CONNECTED_TO = "CONNECTED_TO"

CONFIDENCE_CORROBORATED = 0.95  # both endpoints managed and each reported the other
CONFIDENCE_SINGLE_SIDED = 0.7   # both endpoints managed, only one reported the link
CONFIDENCE_UNRESOLVED = 0.4     # far endpoint is not in inventory

Endpoint = tuple[str, str | None]


def _endpoint(device_id: str, interface: str | None) -> Endpoint:
    return device_id, (str(interface).strip() or None) if interface else None


def _canonical(first: Endpoint, second: Endpoint) -> tuple[Endpoint, Endpoint]:
    """Order endpoints so A->B and B->A produce one identical key."""
    return tuple(sorted((first, second), key=lambda item: (item[0], item[1] or "")))  # type: ignore[return-value]


def _device_node(device: DeviceFacts) -> dict:
    return {
        "id": device.id, "kind": "device", "managed": True, "hostname": device.name,
        "type": device.type, "vendor": device.vendor, "model": device.model,
        "platform": device.platform, "os_version": device.os_version,
        "management_ip": device.management_ip, "serial_number": device.serial_number,
        "status": device.status, "site": device.site, "discovery_state": device.discovery_state,
        "confidence": device.confidence, "last_seen_at": device.last_seen_at,
        "last_backup_at": device.last_backup_at, "interface_count": device.interface_count,
        "neighbor_count": device.neighbor_count, "degree": 0,
    }


def _external_node(node_id: str, neighbor: NeighborFacts) -> dict:
    """A neighbor observed over LLDP that inventory does not (yet) contain."""
    return {
        "id": node_id, "kind": "external", "managed": False,
        "hostname": neighbor.remote_system_name or normalize_chassis_id(neighbor.remote_chassis_id) or "unknown",
        "type": "other", "vendor": None, "model": None, "platform": None, "os_version": None,
        "management_ip": None, "serial_number": None, "status": "unknown", "site": None,
        "discovery_state": "unrecognized", "confidence": 0.0, "last_seen_at": None,
        "last_backup_at": None, "interface_count": 0, "neighbor_count": 0, "degree": 0,
        "chassis_id": normalize_chassis_id(neighbor.remote_chassis_id), "observed_by": [],
    }


def _observation(neighbor: NeighborFacts, reporter: str) -> dict:
    return {
        "reported_by": reporter, "reported_by_id": neighbor.device_id,
        "local_interface": neighbor.local_interface, "remote_interface": neighbor.remote_interface,
        "remote_system_name": neighbor.remote_system_name, "remote_chassis_id": neighbor.remote_chassis_id,
        "source": "lldp",
    }


def _confidence(both_managed: bool, observation_count: int) -> float:
    if not both_managed:
        return CONFIDENCE_UNRESOLVED
    return CONFIDENCE_CORROBORATED if observation_count > 1 else CONFIDENCE_SINGLE_SIDED


def _wanted(value: object, wanted: str | None) -> bool:
    """Case-insensitive filter match; ``None``/``all``/empty means "do not filter"."""
    if not wanted or wanted.casefold() == "all":
        return True
    return str(value or "").casefold() == wanted.casefold()


def build_graph(
    devices: list[DeviceFacts],
    neighbors: list[NeighborFacts],
    *,
    site: str | None = None,
    vendor: str | None = None,
    device_type: str | None = None,
    status: str | None = None,
) -> dict:
    """Turn inventory devices plus LLDP observations into ``{nodes, edges, stats, filters}``."""
    index = DeviceIndex.build(devices)
    names = {device.id: device.name for device in devices}
    device_nodes = {device.id: _device_node(device) for device in devices}
    external_nodes: dict[str, dict] = {}
    links: dict[tuple[Endpoint, Endpoint], dict] = {}
    unresolved_neighbors = 0
    insufficient_evidence = 0
    ambiguous_hits: set[str] = set()

    resolved: list[tuple[NeighborFacts, str, bool]] = []
    for neighbor in neighbors:
        if not (neighbor.local_interface or "").strip() or neighbor.device_id not in device_nodes:
            insufficient_evidence += 1
            continue
        target = index.resolve_neighbor(neighbor)
        if target == neighbor.device_id:
            continue  # a device advertising itself is not a link between two nodes
        if target is not None:
            resolved.append((neighbor, target, True))
            continue
        # Unresolved: either the neighbor is genuinely outside inventory, or the identity it
        # advertised belongs to several devices. Record the second case so the map can say
        # why a link is missing instead of leaving the operator to wonder.
        ambiguous_hits |= index.ambiguous_matches(neighbor)
        key = external_node_key(neighbor)
        if key is None:
            insufficient_evidence += 1  # no remote name and no chassis id: no identity at all
            continue
        node = external_nodes.setdefault(key, _external_node(key, neighbor))
        reporter = names.get(neighbor.device_id, neighbor.device_id)
        if reporter not in node["observed_by"]:
            node["observed_by"].append(reporter)
        unresolved_neighbors += 1
        resolved.append((neighbor, key, False))

    # Two passes: observations naming both ports define the links, then reports that
    # omit the remote port attach to a matching link rather than duplicating it.
    complete = [item for item in resolved if (item[0].remote_interface or "").strip()]
    partial = [item for item in resolved if not (item[0].remote_interface or "").strip()]

    for neighbor, target_id, both_managed in complete:
        near = _endpoint(neighbor.device_id, neighbor.local_interface)
        far = _endpoint(target_id, neighbor.remote_interface)
        key = _canonical(near, far)
        link = links.setdefault(key, {"endpoints": key, "both_managed": both_managed,
                                      "observations": [], "interface_evidence": "complete"})
        link["observations"].append(_observation(neighbor, names.get(neighbor.device_id, neighbor.device_id)))

    for neighbor, target_id, both_managed in partial:
        near = _endpoint(neighbor.device_id, neighbor.local_interface)
        existing = next((link for key, link in links.items()
                         if near in key and any(endpoint[0] == target_id for endpoint in key)), None)
        if existing is not None:
            existing["observations"].append(_observation(neighbor, names.get(neighbor.device_id, neighbor.device_id)))
            continue
        key = _canonical(near, _endpoint(target_id, None))
        link = links.setdefault(key, {"endpoints": key, "both_managed": both_managed,
                                     "observations": [], "interface_evidence": "partial"})
        link["observations"].append(_observation(neighbor, names.get(neighbor.device_id, neighbor.device_id)))

    edges = []
    for (first, second), link in links.items():
        (source, source_interface), (target, target_interface) = first, second
        edges.append({
            "id": f"{source}:{source_interface or '?'}--{target}:{target_interface or '?'}",
            "source": source, "target": target, "relationship_type": CONNECTED_TO,
            "source_interface": source_interface, "target_interface": target_interface,
            "confidence": _confidence(link["both_managed"], len(link["observations"])),
            "interface_evidence": link["interface_evidence"],
            "corroborated": link["both_managed"] and len(link["observations"]) > 1,
            "evidence": {"source": "lldp", "observations": link["observations"]},
        })

    kept = {node_id: node for node_id, node in device_nodes.items()
            if _wanted(node["site"], site) and _wanted(node["vendor"], vendor)
            and _wanted(node["type"], device_type) and _wanted(node["status"], status)}
    # Keep an edge only when both endpoints survive the filter, where "survives" means a
    # kept device or an external node still anchored to one.
    visible = kept.keys() | external_nodes.keys()
    edges = [edge for edge in edges
             if edge["source"] in visible and edge["target"] in visible
             and (edge["source"] in kept or edge["target"] in kept)]
    # An external node only exists because something points at it; drop it once the
    # device that reported it has been filtered out.
    linked = {endpoint for edge in edges for endpoint in (edge["source"], edge["target"])}
    nodes = list(kept.values()) + [node for node_id, node in external_nodes.items() if node_id in linked]

    degrees: dict[str, int] = {}
    for edge in edges:
        degrees[edge["source"]] = degrees.get(edge["source"], 0) + 1
        degrees[edge["target"]] = degrees.get(edge["target"], 0) + 1
    for node in nodes:
        node["degree"] = degrees.get(node["id"], 0)

    nodes.sort(key=lambda node: (node["kind"] != "device", str(node["hostname"]).casefold()))
    edges.sort(key=lambda edge: edge["id"])
    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "device_count": sum(node["kind"] == "device" for node in nodes),
            "external_count": sum(node["kind"] == "external" for node in nodes),
            "node_count": len(nodes),
            "edge_count": len(edges),
            "corroborated_edges": sum(bool(edge["corroborated"]) for edge in edges),
            "unresolved_neighbors": unresolved_neighbors,
            "insufficient_evidence": insufficient_evidence,
            "ambiguous_identities": sorted(ambiguous_hits),
        },
        "filters": {
            "sites": sorted({node["site"] for node in device_nodes.values() if node["site"]}),
            "vendors": sorted({node["vendor"] for node in device_nodes.values() if node["vendor"]}),
            "types": sorted({node["type"] for node in device_nodes.values() if node["type"]}),
            "statuses": sorted({node["status"] for node in device_nodes.values() if node["status"]}),
        },
    }
