"""Topology graph queries over the inventory tables.

There is no separate topology device store (Phase 3 requirement "one source of truth"):
nodes come from ``devices`` and edges from the ``neighbors`` rows Phase 1 discovery
already writes, so a device id means the same thing on every screen.

Every lookup is a fixed number of aggregate queries — four, whether the inventory holds
10 or 100 devices — and configuration *artifacts* are never read, only their metadata.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.models import AuditLogRecord, DeviceRecord, InterfaceRecord, NeighborRecord
from topology.graph import build_graph
from topology.normalization import DeviceFacts, DeviceIndex, NeighborFacts

BACKUP_ACTION = "BACKUP_CONFIGURATION"


def load_facts(session: Session) -> tuple[list[DeviceFacts], list[NeighborFacts]]:
    """Read inventory into storage-independent facts using four grouped queries."""
    devices = list(session.scalars(select(DeviceRecord).order_by(DeviceRecord.name)))
    interface_counts = dict(session.execute(
        select(InterfaceRecord.device_id, func.count(InterfaceRecord.id)).group_by(InterfaceRecord.device_id)
    ).all())
    neighbor_rows = list(session.scalars(select(NeighborRecord)))
    last_backups = dict(session.execute(
        select(AuditLogRecord.resource_id, func.max(AuditLogRecord.created_at))
        .where(AuditLogRecord.action == BACKUP_ACTION, AuditLogRecord.result == "SUCCESS")
        .group_by(AuditLogRecord.resource_id)
    ).all())

    neighbor_counts: dict[str, int] = {}
    for row in neighbor_rows:
        neighbor_counts[row.device_id] = neighbor_counts.get(row.device_id, 0) + 1

    facts = [
        DeviceFacts(
            id=record.id, name=record.name, type=record.type, vendor=record.vendor,
            model=record.model, platform=record.platform, os_version=record.os_version,
            management_ip=record.management_ip, serial_number=record.serial_number,
            status=record.status, site=record.site, discovery_state=record.discovery_state,
            last_seen_at=record.last_seen_at, confidence=record.confidence,
            interface_count=interface_counts.get(record.id, 0),
            neighbor_count=neighbor_counts.get(record.id, 0),
            last_backup_at=last_backups.get(record.id),
        )
        for record in devices
    ]
    observations = [
        NeighborFacts(
            device_id=row.device_id, local_interface=row.local_interface,
            remote_system_name=row.remote_system_name, remote_interface=row.remote_interface,
            remote_chassis_id=row.remote_chassis_id,
        )
        for row in neighbor_rows
    ]
    return facts, observations


class TopologyService:
    """Builds graph slices for the API; owns no schema of its own."""

    def __init__(self, sessions):
        self.sessions = sessions

    def graph(self, **filters) -> dict:
        with self.sessions() as session:
            devices, neighbors = load_facts(session)
        return build_graph(devices, neighbors, **filters)

    def nodes(self, **filters) -> dict:
        graph = self.graph(**filters)
        return {"nodes": graph["nodes"], "stats": graph["stats"], "filters": graph["filters"]}

    def edges(self, **filters) -> dict:
        graph = self.graph(**filters)
        return {"edges": graph["edges"], "stats": graph["stats"]}

    def device_slice(self, device_id: str) -> dict:
        """Ego graph: one device, its edges, and the nodes on the far end (depth 1)."""
        graph = self.graph()
        edges = [edge for edge in graph["edges"] if device_id in (edge["source"], edge["target"])]
        keep = {device_id} | {endpoint for edge in edges for endpoint in (edge["source"], edge["target"])}
        nodes = [node for node in graph["nodes"] if node["id"] in keep]
        if not any(node["id"] == device_id for node in nodes):
            raise KeyError(device_id)
        return {"nodes": nodes, "edges": edges,
                "stats": {"node_count": len(nodes), "edge_count": len(edges)}}

    def neighbors(self, device_id: str) -> list[dict]:
        """LLDP observations for one device, each annotated with the device it resolves to.

        The Phase 1 endpoint returns the raw rows; this adds the correlation result so the
        UI can offer "open this neighbor" only when the neighbor is actually managed.
        """
        with self.sessions() as session:
            devices, observations = load_facts(session)
        index = DeviceIndex.build(devices)
        names = {device.id: device.name for device in devices}
        return [
            {
                "local_interface": item.local_interface,
                "remote_system_name": item.remote_system_name,
                "remote_interface": item.remote_interface,
                "remote_chassis_id": item.remote_chassis_id,
                "resolved_device_id": (resolved := index.resolve_neighbor(item)),
                "resolved_device_name": names.get(resolved) if resolved else None,
                "managed": resolved is not None,
            }
            for item in observations if item.device_id == device_id
        ]
