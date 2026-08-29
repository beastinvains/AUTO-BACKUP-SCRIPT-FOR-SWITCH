import { useMemo, useState } from "react";
import { api } from "../api";
import { useAsync } from "../hooks";
import { ComplianceIcon, ShieldAlertIcon } from "../components/icons";
import { Loading, NetraBadge, StatCard, ErrorBanner } from "../components/ui";

export function FindingsPage({ navigate }: { navigate: (page: string, param?: string) => void }) {
  const [filter, setFilter] = useState("");
  
  const state = useAsync(async () => {
    return await api.findings();
  }, []);
  
  const handleAcknowledge = async (id: string) => {
    await api.acknowledgeFinding(id);
    state.reload();
  };

  const handleResolve = async (id: string) => {
    await api.resolveFinding(id, "Resolved via UI");
    state.reload();
  };

  const handleSuppress = async (id: string) => {
    await api.suppressFinding(id);
    state.reload();
  };

  const allFindings = state.data ?? [];
  const findings = useMemo(() => allFindings.filter((item) => !filter || item.severity === filter), [allFindings, filter]);
  
  const critical = allFindings.filter((item) => item.severity === "critical" && item.status === "open").length;
  const high = allFindings.filter((item) => item.severity === "high" && item.status === "open").length;
  const openCount = allFindings.filter(a => a.status === "open").length;

  return (
    <div className="page-content">
      {state.error && <ErrorBanner message={state.error} />}
      {state.loading && <Loading what="findings" />}

      {!state.loading && (
        <>
          <div className="kpi-grid-4">
            <StatCard 
              label="Total Findings" 
              value={allFindings.length} 
              icon={<ComplianceIcon size={20} />} 
              iconTone="purple" 
            />
            <StatCard 
              label="Open Findings" 
              value={openCount} 
              icon={<ShieldAlertIcon size={20} />} 
              iconTone={openCount > 0 ? "amber" : "green"} 
            />
            <StatCard 
              label="Critical (Open)" 
              value={critical} 
              icon={<ShieldAlertIcon size={20} />} 
              iconTone={critical > 0 ? "red" : "green"} 
            />
            <StatCard 
              label="High (Open)" 
              value={high} 
              icon={<ShieldAlertIcon size={20} />} 
              iconTone={high > 0 ? "amber" : "green"} 
            />
          </div>
          
          <div className="filter-toolbar">
            <select className="filter-select" value={filter} onChange={(event) => setFilter(event.target.value)}>
              <option value="">All severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
              <option value="info">Info</option>
            </select>
          </div>
          
          <div className="table-card">
            <div style={{ padding: "16px 20px" }}>
              <h2 style={{ color: "var(--ink)" }}>Security & Compliance Findings ({findings.length})</h2>
            </div>
            <div className="table-responsive">
              <table className="netra-table">
                <thead>
                  <tr>
                    <th>First / Last Seen</th>
                    <th>Device</th>
                    <th>Category</th>
                    <th>Severity</th>
                    <th>Status</th>
                    <th>Title</th>
                    <th>Count</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {findings.map((item) => (
                    <tr key={item.id} style={{ opacity: (item.status === 'resolved' || item.status === 'suppressed') ? 0.6 : 1 }}>
                      <td className="table-time" style={{ whiteSpace: "nowrap" }}>
                        <div>{new Date(item.first_seen_at).toLocaleDateString()}</div>
                        <div style={{ fontSize: "0.75rem", color: "var(--ink-3)" }}>{new Date(item.last_seen_at).toLocaleTimeString()}</div>
                      </td>
                      <td>
                        <button className="table-device-link" onClick={() => navigate("devices", item.device_id)}>
                          {item.device_id.split("-")[0]}...
                        </button>
                      </td>
                      <td>{item.category.replace(/_/g, " ")}</td>
                      <td><NetraBadge type={item.severity === "critical" ? "critical" : item.severity === "high" || item.severity === "medium" ? "warning" : "info"} /></td>
                      <td><NetraBadge type={item.status === "open" ? "new" : item.status === "resolved" ? "resolved" : "acknowledged"} /></td>
                      <td>
                        <div style={{ fontWeight: 500, color: "var(--ink)" }}>{item.title}</div>
                      </td>
                      <td>{item.occurrence_count}</td>
                      <td>
                        <div style={{ display: "flex", gap: "8px" }}>
                          {item.status === "open" && (
                            <button className="filter-btn" onClick={() => handleAcknowledge(item.id)}>
                              Ack
                            </button>
                          )}
                          {(item.status === "open" || item.status === "acknowledged") && (
                            <>
                              <button className="filter-btn" onClick={() => handleResolve(item.id)}>
                                Resolve
                              </button>
                              <button className="filter-btn" onClick={() => handleSuppress(item.id)}>
                                Suppress
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                  {findings.length === 0 && (
                    <tr>
                      <td colSpan={8} style={{ textAlign: "center", padding: "32px", color: "var(--ink-3)" }}>
                        No findings match criteria
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
