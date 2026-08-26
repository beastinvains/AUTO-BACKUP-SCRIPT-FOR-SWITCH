/** Topology page. All nodes and links come from discovered inventory/LLDP API data. */

import { useEffect, useState } from "react";
import { api } from "../api";
import { useAsync } from "../hooks";
import type { Graph, TopologyNode } from "../types";
import { TopologyMap } from "../components/TopologyMap";

const ALL = "All";

export function TopologyPage({ navigate }: { navigate: (page: string, param?: string, tab?: string) => void }) {
  const [site, setSite] = useState(ALL); const [vendor, setVendor] = useState(ALL);
  const [type, setType] = useState(ALL); const [status, setStatus] = useState(ALL);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showLabels, setShowLabels] = useState(true); const [showLinks, setShowLinks] = useState(true);
  const filters = { site: site === ALL ? undefined : site, vendor: vendor === ALL ? undefined : vendor, device_type: type === ALL ? undefined : type, status: status === ALL ? undefined : status };
  const result = useAsync<Graph>(() => api.topology(filters), [site, vendor, type, status]);
  const graph = result.data;
  useEffect(() => { if (!graph?.nodes.some((node) => node.id === selectedId)) setSelectedId(graph?.nodes[0]?.id ?? null); }, [graph, selectedId]);
  const selected: TopologyNode | null = graph?.nodes.find((node) => node.id === selectedId) ?? null;
  if (result.loading && !graph) return <div className="page"><p>Loading discovered topology…</p></div>;
  if (result.error) return <div className="page"><p className="error-banner">Unable to load topology: {result.error}</p><button className="btn btn-primary" onClick={result.reload}>Retry</button></div>;
  if (!graph) return null;
  const selectValue = (value: string) => value || ALL;
  return <div className="page" style={{ gap: 16 }}>
    <div className="filter-toolbar" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
      <select className="filter-select" value={site} onChange={(event) => setSite(selectValue(event.target.value))}><option>{ALL}</option>{graph.filters.sites.map((value) => <option key={value}>{value}</option>)}</select>
      <select className="filter-select" value={vendor} onChange={(event) => setVendor(selectValue(event.target.value))}><option>{ALL}</option>{graph.filters.vendors.map((value) => <option key={value}>{value}</option>)}</select>
      <select className="filter-select" value={type} onChange={(event) => setType(selectValue(event.target.value))}><option>{ALL}</option>{graph.filters.types.map((value) => <option key={value}>{value}</option>)}</select>
      <select className="filter-select" value={status} onChange={(event) => setStatus(selectValue(event.target.value))}><option>{ALL}</option>{graph.filters.statuses.map((value) => <option key={value}>{value}</option>)}</select>
      <label className="inline"><input type="checkbox" checked={showLabels} onChange={(event) => setShowLabels(event.target.checked)} /> IP labels</label>
      <label className="inline"><input type="checkbox" checked={showLinks} onChange={(event) => setShowLinks(event.target.checked)} /> LLDP links</label>
    </div>
    <div className="topology-main-view"><TopologyMap nodes={graph.nodes} edges={graph.edges} selectedNodeId={selectedId} onSelectNode={setSelectedId} showLabels={showLabels} showLinks={showLinks} />
      <aside className="topology-right-sidebar"><div className="netra-panel" style={{ padding: 16 }}><h3>Discovered topology</h3><p>{graph.stats.device_count} managed devices, {graph.stats.external_count} observed external neighbors</p><p>{graph.stats.edge_count} LLDP links · {graph.stats.corroborated_edges} corroborated</p><p>{graph.stats.unresolved_neighbors} unresolved observations</p>{graph.stats.ambiguous_identities.length > 0 && <p>Ambiguous: {graph.stats.ambiguous_identities.join(", ")}</p>}</div>
        {selected && <div className="netra-panel" style={{ padding: 16 }}><h3>{selected.hostname}</h3><p>{selected.vendor ?? "Unknown vendor"} {selected.model ?? ""}</p><p>Address: {selected.management_ip ?? "unmanaged"}</p><p>Site: {selected.site ?? "—"}</p><p>Status: {selected.status} · confidence {selected.confidence}</p><p>{selected.interface_count} interfaces · {selected.neighbor_count} LLDP neighbors</p>{selected.kind === "device" && <button className="btn btn-primary" onClick={() => navigate("devices", selected.id)}>Open device</button>}</div>}</aside>
    </div>
  </div>;
}
