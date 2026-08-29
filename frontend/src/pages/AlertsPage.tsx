import { useMemo, useState } from "react";
import { api } from "../api";
import { useAsync } from "../hooks";
import { AlertTriangleIcon, CheckCircleIcon, ShieldAlertIcon } from "../components/icons";
import { Loading, NetraBadge, StatCard, ErrorBanner } from "../components/ui";

export function AlertsPage({ navigate }: { navigate: (page: string, param?: string) => void }) {
  const [filter, setFilter] = useState("");
  
  const state = useAsync(async () => {
    return await api.alerts();
  }, []);
  
  const handleAcknowledge = async (id: string) => {
    await api.acknowledgeAlert(id);
    state.reload();
  };

  const handleResolve = async (id: string) => {
    await api.resolveAlert(id);
    state.reload();
  };

  const allAlerts = state.data ?? [];
  const alerts = useMemo(() => allAlerts.filter((item) => !filter || item.severity === filter), [allAlerts, filter]);
  
  const critical = allAlerts.filter((item) => item.severity === "critical" && item.status === "new").length;
  const warning = allAlerts.filter((item) => (item.severity === "high" || item.severity === "medium") && item.status === "new").length;
  const openCount = allAlerts.filter(a => a.status === "new").length;

  return (
    <div className="page-content">
      {state.error && <ErrorBanner message={state.error} />}
      {state.loading && <Loading what="alerts" />}

      {!state.loading && (
        <>
          <div className="kpi-grid-4">
            <StatCard 
              label="Total Alerts" 
              value={allAlerts.length} 
              icon={<ShieldAlertIcon size={20} />} 
              iconTone="blue" 
            />
            <StatCard 
              label="Open Alerts" 
              value={openCount} 
              icon={<AlertTriangleIcon size={20} />} 
              iconTone={openCount > 0 ? "amber" : "green"} 
            />
            <StatCard 
              label="Critical (New)" 
              value={critical} 
              icon={<AlertTriangleIcon size={20} />} 
              iconTone={critical > 0 ? "red" : "green"} 
            />
            <StatCard 
              label="Warning (New)" 
              value={warning} 
              icon={<AlertTriangleIcon size={20} />} 
              iconTone={warning > 0 ? "amber" : "green"} 
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
              <h2 style={{ color: "var(--ink)" }}>Alerts ({alerts.length})</h2>
            </div>
            <div className="table-responsive">
              <table className="netra-table">
                <thead>
                  <tr>
                    <th>Created</th>
                    <th>Device</th>
                    <th>Category</th>
                    <th>Severity</th>
                    <th>Status</th>
                    <th>Title / Message</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {alerts.map((item) => (
                    <tr key={item.id} style={{ opacity: item.status === 'resolved' ? 0.6 : 1 }}>
                      <td className="table-time" style={{ whiteSpace: "nowrap" }}>
                        {new Date(item.created_at).toLocaleString()}
                      </td>
                      <td>
                        {item.device_id ? (
                          <button className="table-device-link" onClick={() => navigate("devices", item.device_id!)}>
                            {item.device_id.split("-")[0]}...
                          </button>
                        ) : "System"}
                      </td>
                      <td>{item.category.replace(/_/g, " ")}</td>
                      <td><NetraBadge type={item.severity === "critical" ? "critical" : item.severity === "high" || item.severity === "medium" ? "warning" : "info"} /></td>
                      <td><NetraBadge type={item.status === "new" ? "new" : item.status === "resolved" ? "resolved" : "acknowledged"} /></td>
                      <td>
                        <div style={{ fontWeight: 500, color: "var(--ink)" }}>{item.title}</div>
                        {item.message && <div style={{ fontSize: "0.8rem", color: "var(--ink-2)", marginTop: 4 }}>{item.message}</div>}
                      </td>
                      <td>
                        <div style={{ display: "flex", gap: "8px" }}>
                          {item.status === "new" && (
                            <button className="filter-btn" onClick={() => handleAcknowledge(item.id)}>
                              Ack
                            </button>
                          )}
                          {(item.status === "new" || item.status === "acknowledged") && (
                            <button className="filter-btn" onClick={() => handleResolve(item.id)}>
                              Resolve
                            </button>
                          )}
                          {item.finding_id && (
                            <button className="filter-btn" onClick={() => navigate("findings", item.finding_id!)}>
                              Finding
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                  {alerts.length === 0 && (
                    <tr>
                      <td colSpan={7} style={{ textAlign: "center", padding: "32px", color: "var(--ink-3)" }}>
                        No alerts match criteria
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
