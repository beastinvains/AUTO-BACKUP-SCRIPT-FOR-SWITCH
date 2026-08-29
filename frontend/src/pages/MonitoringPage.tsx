/**
 * Hardware Telemetry & Real-Time Monitoring Page for NETRA.
 */

import { useState, useMemo } from "react";
import { api } from "../api";
import { useAsync } from "../hooks";
import { MonitoringIcon, TempIcon, FanIcon, PowerIcon, RefreshIcon } from "../components/icons";
import { StatCard, HardwareTelemetryCard, Panel, ErrorBanner, Loading } from "../components/ui";

export function MonitoringPage({ navigate }: { navigate: (page: string, param?: string) => void }) {
  const [filter, setFilter] = useState("all");
  const [running, setRunning] = useState(false);

  const state = useAsync(async () => {
    return await api.monitoringOverview();
  }, []);

  const handleRunCollection = async () => {
    setRunning(true);
    try {
      await api.runMonitoring("all");
      setTimeout(() => state.reload(), 3000);
    } catch (e: any) {
      alert(`Error starting collection: ${e.message}`);
    } finally {
      setTimeout(() => setRunning(false), 3000);
    }
  };

  const overview = state.data;
  
  const filtered = overview?.coverage.filter((d) => {
    if (filter === "online") return d.reachability === "online";
    if (filter === "offline") return d.reachability !== "online" && d.reachability !== "not_collected";
    if (filter === "not_collected") return d.reachability === "not_collected";
    return true;
  }) || [];

  return (
    <div className="page-content">
      {state.error && <ErrorBanner message={state.error.toString()} />}
      {state.loading && <Loading what="monitoring data" />}
      
      {!state.loading && overview && (
        <>
          <div className="kpi-grid-4">
            <StatCard
              label="Telemetry Collection"
              value={`${overview.total_devices} Devices`}
              icon={<MonitoringIcon size={20} />}
              iconTone="blue"
              indicators={[
                { text: `● ${overview.devices_online} Online`, tone: "green", dot: true },
                { text: `● ${overview.devices_offline} Offline`, tone: "red", dot: true },
                { text: `● ${overview.devices_not_collected} Not Collected`, tone: "amber", dot: true },
              ]}
            />
            <StatCard
              label="Thermal Status"
              value={(() => {
                const temps = overview.coverage.map(c => c.temperature_c).filter((t): t is number => t != null);
                if (temps.length === 0) return "N/A";
                const avg = temps.reduce((a, b) => a + b, 0) / temps.length;
                return `${Math.round(avg)}°C Avg`;
              })()}
              icon={<TempIcon size={20} />}
              iconTone="amber"
              indicators={[]}
            />
            <StatCard
              label="Fan Speed Health"
              value={(() => {
                 const withFans = overview.coverage.filter(c => c.fan_speed_rpm != null).length;
                 if (overview.total_devices === 0) return "N/A";
                 return `${Math.round((withFans / overview.total_devices) * 100)}% Reported`;
              })()}
              icon={<FanIcon size={20} />}
              iconTone="blue"
              indicators={[]}
            />
            <StatCard
              label="Power Status"
              value={(() => {
                const ok = overview.coverage.filter(c => c.power_status === "ok").length;
                const totalWithPower = overview.coverage.filter(c => c.power_status != null).length;
                if (totalWithPower === 0) return "N/A";
                return `${ok} / ${totalWithPower} OK`;
              })()}
              icon={<PowerIcon size={20} />}
              iconTone="red"
              indicators={[]}
            />
          </div>

          <div className="netra-panel">
            <div className="netra-panel-header">
              <div>
                <h2 className="panel-title">Live Hardware Telemetry</h2>
                <span className="panel-subtitle">Streaming sensor readings collected via telemetry probes</span>
              </div>
              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                {["all", "online", "offline", "not_collected"].map((tab) => (
                  <button
                    key={tab}
                    className={`filter-btn ${filter === tab ? "export" : ""}`}
                    onClick={() => setFilter(tab)}
                  >
                    {tab.replace("_", " ").toUpperCase()}
                  </button>
                ))}
                <button 
                  className="primary-btn" 
                  onClick={handleRunCollection}
                  disabled={running}
                  style={{ marginLeft: "16px" }}
                >
                  <RefreshIcon size={16} className={running ? "spin" : ""} />
                  {running ? "Running..." : "Run Collection"}
                </button>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "16px" }}>
              {filtered.map((d) => (
                <div key={d.device_id} style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  <HardwareTelemetryCard
                    name={d.device_name}
                    type="Device"
                    vendor="Unknown"
                    status={d.reachability === "online" ? "online" : d.reachability === "not_collected" ? "warning" : "critical"}
                    temp={d.temperature_c != null ? `${d.temperature_c}°C` : "N/A"}
                    power={d.power_status || "Unknown"}
                    powerFail={d.power_status && d.power_status !== "ok" ? true : false}
                    fan={d.fan_speed_rpm != null ? `${d.fan_speed_rpm} RPM` : "Unknown"}
                    fanFail={false}
                    alertsCount={0}
                    onClick={() => navigate("devices", d.device_id)}
                  />
                  <div style={{ background: "var(--surface-2)", border: "1px solid var(--line-subtle)", borderRadius: "8px", padding: "10px 14px", display: "flex", flexDirection: "column", gap: "8px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem" }}>
                      <span style={{ color: "var(--ink-3)" }}>CPU Load</span>
                      <span style={{ fontFamily: "var(--font-mono)", color: d.cpu_percent != null && d.cpu_percent > 80 ? "var(--crit-light)" : "var(--brand-emerald-light)" }}>{d.cpu_percent != null ? `${Math.round(d.cpu_percent)}%` : "N/A"}</span>
                    </div>
                    <div style={{ height: "4px", background: "rgba(255,255,255,0.06)", borderRadius: "2px", overflow: "hidden" }}>
                      <div style={{ height: "100%", width: `${d.cpu_percent || 0}%`, background: d.cpu_percent != null && d.cpu_percent > 80 ? "var(--crit)" : "var(--brand-emerald)" }} />
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem" }}>
                      <span style={{ color: "var(--ink-3)" }}>Memory</span>
                      <span style={{ fontFamily: "var(--font-mono)", color: "var(--ink-2)" }}>{d.memory_percent != null ? `${Math.round(d.memory_percent)}%` : "N/A"}</span>
                    </div>
                    <div style={{ height: "4px", background: "rgba(255,255,255,0.06)", borderRadius: "2px", overflow: "hidden" }}>
                      <div style={{ height: "100%", width: `${d.memory_percent || 0}%`, background: "var(--info)" }} />
                    </div>
                  </div>
                </div>
              ))}
              
              {filtered.length === 0 && (
                 <div style={{ gridColumn: "1 / -1", padding: "40px", textAlign: "center", color: "var(--ink-3)" }}>
                   No devices found for this filter.
                 </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
