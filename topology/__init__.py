"""Evidence-based topology: identity correlation, graph construction, and queries."""

from topology.graph import CONNECTED_TO, build_graph
from topology.normalization import DeviceFacts, DeviceIndex, NeighborFacts
from topology.service import TopologyService, load_facts

__all__ = [
    "CONNECTED_TO", "DeviceFacts", "DeviceIndex", "NeighborFacts",
    "TopologyService", "build_graph", "load_facts",
]
