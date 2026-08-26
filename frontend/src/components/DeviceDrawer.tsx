/**
 * Details drawer for a topology selection.
 *
 * Deliberately a summary, not a second device page (Phase 3 section 11): identity, status,
 * counts and freshness, then links into the pages that own the full detail. The payload
 * comes from `/api/devices/{id}/summary`, which reads metadata only and never opens a
 * stored configuration artifact.
 */

import { api } from "../api";
import { percent, time, titleCase } from "../format";
import { useAsync } from "../hooks";
import type { DeviceSummary, TopologyEdge, TopologyNode } from "../types";
import { Drawer, ErrorBanner, Fact, Loading, Status } from "./ui";

export function NodeDrawer({
  node,
  onClose,
  navigate,
}: {
  node: TopologyNode;
  onClose: () => void;
  navigate: (page: string, param?: string, tab?: string) => void;
}) {
  // Unmanaged endpoints have no inventory row, so there is nothing to summarize for them.
  const summary = useAsync<DeviceSummary | null>(
    () => (node.managed ? api.deviceSummary(node.id) : Promise.resolve(null)),
    [node.id, node.managed],
  );

  return (
    <Drawer
      title={node.hostname}
      subtitle={node.managed ? `${titleCase(node.type)} · ${node.site ?? "no site"}` : "Unmanaged neighbour"}
      onClose={onClose}
    >
      <ErrorBanner message={summary.error} />

      {node.managed ? (
        <ManagedNode node={node} summary={summary.data} loading={summary.loading} navigate={navigate} />
      ) : (
        <ExternalNode node={node} />
      )}
    </Drawer>
  );
}

function ManagedNode({
  node,
  summary,
  loading,
  navigate,
}: {
  node: TopologyNode;
  summary: DeviceSummary | null;
  loading: boolean;
  navigate: (page: string, param?: string, tab?: string) => void;
}) {
  if (loading && !summary) return <Loading what="device summary" />;
  return (
    <>
      <dl className="facts">
        <Fact label="Hostname">{node.hostname}</Fact>
        <Fact label="Vendor">{node.vendor ?? "unknown"}</Fact>
        <Fact label="Model">{node.model ?? "unknown"}</Fact>
        <Fact label="Operating system">
          {[node.platform, node.os_version].filter(Boolean).join(" ") || "unknown"}
        </Fact>
        <Fact label="Management IP">
          <code>{node.management_ip ?? "unknown"}</code>
        </Fact>
        <Fact label="Status">
          <Status value={node.status} />
        </Fact>
        <Fact label="Last discovery">{time(summary?.last_discovery_at ?? node.last_seen_at)}</Fact>
        <Fact label="Last backup">{time(summary?.last_backup_at ?? node.last_backup_at)}</Fact>
        <Fact label="Interfaces">{summary?.interface_count ?? node.interface_count}</Fact>
        <Fact label="Neighbours">{summary?.neighbor_count ?? node.neighbor_count}</Fact>
        <Fact label="Connections drawn">{node.degree}</Fact>
        <Fact label="Identity confidence">{percent(node.confidence)}</Fact>
      </dl>

      <p className="provenance">GET /api/devices/{node.id.slice(0, 8)}…/summary · metadata only, no stored configuration is opened</p>

      <div className="drawer-actions">
        <button className="ghost" onClick={() => navigate("devices", node.id)}>
          View device
        </button>
        <button className="ghost" onClick={() => navigate("devices", node.id, "interfaces")}>
          View interfaces
        </button>
        <button className="ghost" onClick={() => navigate("devices", node.id, "neighbors")}>
          View neighbours
        </button>
        <button className="ghost" onClick={() => navigate("configurations", node.id)}>
          View configuration
        </button>
        <button className="ghost" onClick={() => navigate("devices", node.id, "backups")}>
          View backup history
        </button>
      </div>
    </>
  );
}

function ExternalNode({ node }: { node: TopologyNode }) {
  return (
    <>
      <p className="notice">
        This endpoint was reported by a neighbour but does not match any inventory device, so it is drawn from
        evidence only. Add it as a device to manage and back it up.
      </p>
      <dl className="facts">
        <Fact label="Reported name">{node.hostname}</Fact>
        <Fact label="Chassis ID">
          <code>{node.chassis_id ?? "not reported"}</code>
        </Fact>
        <Fact label="Seen by">{node.observed_by?.join(", ") || "unknown"}</Fact>
        <Fact label="Connections drawn">{node.degree}</Fact>
      </dl>
    </>
  );
}

/** Link details: which interfaces, how the link was established, and how much to trust it. */
export function EdgeDrawer({
  edge,
  nodes,
  onClose,
}: {
  edge: TopologyEdge;
  nodes: TopologyNode[];
  onClose: () => void;
}) {
  const name = (id: string) => nodes.find((node) => node.id === id)?.hostname ?? id;
  return (
    <Drawer title="Connection" subtitle={`${name(edge.source)} ↔ ${name(edge.target)}`} onClose={onClose}>
      <dl className="facts">
        <Fact label="Relationship">{edge.relationship_type}</Fact>
        <Fact label="Source interface">
          <code>{edge.source_interface ?? "not reported"}</code>
        </Fact>
        <Fact label="Target interface">
          <code>{edge.target_interface ?? "not reported"}</code>
        </Fact>
        <Fact label="Interface evidence">{edge.interface_evidence}</Fact>
        <Fact label="Confirmed by both ends">{edge.corroborated ? "yes" : "no — one side only"}</Fact>
        <Fact label="Confidence">{percent(edge.confidence)}</Fact>
        <Fact label="Evidence source">{edge.evidence.source}</Fact>
      </dl>

      <h3>Observations</h3>
      <p className="provenance">Each row is one LLDP report. Two rows mean both ends saw the link.</p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Reported by</th>
              <th scope="col">Local</th>
              <th scope="col">Remote</th>
              <th scope="col">Remote name</th>
            </tr>
          </thead>
          <tbody>
            {edge.evidence.observations.map((observation, index) => (
              <tr key={`${observation.reported_by_id}-${observation.local_interface}-${index}`}>
                <td>{observation.reported_by}</td>
                <td>
                  <code>{observation.local_interface}</code>
                </td>
                <td>
                  <code>{observation.remote_interface ?? "—"}</code>
                </td>
                <td>{observation.remote_system_name ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Drawer>
  );
}
