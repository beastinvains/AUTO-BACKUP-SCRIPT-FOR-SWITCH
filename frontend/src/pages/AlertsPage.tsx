/** Alerts and hardware status derived from discovered devices and health records. */

import { useMemo, useState } from "react";
import { api } from "../api";
import { useAsync } from "../hooks";
import type { Device, Health } from "../types";
import { AlertTriangleIcon, FanIcon, PowerIcon, TempIcon } from "../components/icons";
import { HardwareTelemetryCard, Loading, NetraBadge, StatCard } from "../components/ui";

type HealthRow = { device: Device; health: Health };
type AlertRow = { id: string; device: Device; type: string; severity: "critical" | "warning" | "info"; message: string };

function statusOf(device: Device, health: Health): "online" | "warning" | "critical" {
  const failedPsu = health.power_supplies.some((item) => item.status.toLowerCase() !== "ok");
  if (device.status === "offline" || failedPsu || health.hardware_status === "warning") return "critical";
  if ((health.cpu_percent ?? 0) >= 80 || (health.temperature_c ?? 0) >= 70) return "warning";
  return "online";
}

function buildAlerts(rows: HealthRow[]): AlertRow[] {
  const alerts: AlertRow[] = [];
  for (const { device, health } of rows) {
    if (device.discovery_state === "failed") alerts.push({ id: `${device.id}-discovery`, device, type: "Discovery Failure", severity: "critical", message: "Device discovery failed" });
    if (health.power_supplies.some((item) => item.status.toLowerCase() !== "ok")) alerts.push({ id: `${device.id}-power`, device, type: "Power Supply", severity: "critical", message: health.power_supplies.map((item) => `${item.name}: ${item.status}`).join(", ") });
    if ((health.fan_speed_rpm ?? 0) === 0) alerts.push({ id: `${device.id}-fan`, device, type: "Fan", severity: "critical", message: "Fan speed is unavailable or stopped" });
    if ((health.temperature_c ?? 0) >= 70) alerts.push({ id: `${device.id}-temperature`, device, type: "Temperature", severity: "critical", message: `Temperature is ${health.temperature_c}°C` });
    else if ((health.temperature_c ?? 0) >= 60) alerts.push({ id: `${device.id}-temperature`, device, type: "Temperature", severity: "warning", message: `High temperature: ${health.temperature_c}°C` });
    if ((health.cpu_percent ?? 0) >= 80) alerts.push({ id: `${device.id}-cpu`, device, type: "CPU", severity: "warning", message: `CPU utilization is ${health.cpu_percent}%` });
  }
  return alerts;
}

export function AlertsPage({ navigate }: { navigate: (page: string, param?: string) => void }) {
  const [filter, setFilter] = useState("");
  const result = useAsync<HealthRow[]>(async () => {
    const devices = await api.devices();
    const rows = await Promise.all(devices.map(async (device) => ({ device, health: await api.health(device.id) })));
    return rows;
  }, []);
  const rows = result.data ?? [];
  const alerts = useMemo(() => buildAlerts(rows).filter((item) => !filter || item.severity === filter), [rows, filter]);
  const critical = alerts.filter((item) => item.severity === "critical").length;
  const warning = alerts.filter((item) => item.severity === "warning").length;
  if (result.loading) return <div className="page-content"><Loading what="health data" /></div>;
  if (result.error) return <div className="page-content"><p className="error-banner">Unable to load discovered health data: {result.error}</p><button className="btn btn-primary" onClick={result.reload}>Retry</button></div>;

  return <div className="page-content">
    <div className="kpi-grid-5"><StatCard label="Devices" value={rows.length} icon={<AlertTriangleIcon size={20} />} iconTone="blue" /><StatCard label="Critical" value={critical} icon={<AlertTriangleIcon size={20} />} iconTone="red" /><StatCard label="Warning" value={warning} icon={<AlertTriangleIcon size={20} />} iconTone="amber" /><StatCard label="Power Supplies" value={rows.reduce((sum, row) => sum + row.health.power_supplies.length, 0)} icon={<PowerIcon size={20} />} iconTone="green" /><StatCard label="Active Alerts" value={alerts.length} icon={<AlertTriangleIcon size={20} />} iconTone="red" /></div>
    <div className="filter-toolbar"><select className="filter-select" value={filter} onChange={(event) => setFilter(event.target.value)}><option value="">All severities</option><option value="critical">Critical</option><option value="warning">Warning</option></select></div>
    <div className="telemetry-section"><div className="telemetry-header"><h2>Discovered hardware telemetry</h2><span>Collected from SSH discovery; no demo values</span></div><div className="telemetry-cards-row">{rows.map(({ device, health }) => <div key={device.id}><HardwareTelemetryCard name={device.name} type={device.type} vendor={device.vendor ?? "unknown"} status={statusOf(device, health)} temp={health.temperature_c == null ? "Not available" : `${health.temperature_c}°C`} power={health.power_supplies.length ? health.power_supplies.map((item) => `PSU ${item.name}: ${item.status}`).join(" · ") : "Not available"} powerFail={health.power_supplies.some((item) => item.status.toLowerCase() !== "ok")} fan={health.fan_speed_rpm == null ? "Not available" : `${health.fan_speed_rpm} RPM`} fanFail={health.fan_speed_rpm === 0} alertsCount={buildAlerts([{ device, health }]).length} onClick={() => navigate("devices", device.id)} /><div className="telemetry-card-foot"><span><TempIcon size={13} /> {health.temperature_c ?? "—"}°C</span><span><FanIcon size={13} /> {health.fan_speed_rpm ?? "—"} RPM</span><span>{health.cluster_members.length > 1 ? `Cluster: ${health.cluster_members.join(", ")}` : "Standalone"}</span></div></div>)}</div></div>
    <div className="table-card"><div style={{ padding: "16px 20px" }}><h2>Alerts ({alerts.length})</h2></div><div className="table-responsive"><table className="netra-table"><thead><tr><th>Device</th><th>Type</th><th>Severity</th><th>Message</th><th>Action</th></tr></thead><tbody>{alerts.map((item) => <tr key={item.id}><td><button className="table-device-link" onClick={() => navigate("devices", item.device.id)}>{item.device.name}</button></td><td>{item.type}</td><td><NetraBadge type={item.severity} /></td><td>{item.message}</td><td><button className="filter-btn" onClick={() => navigate("devices", item.device.id)}>Inspect</button></td></tr>)}</tbody></table></div></div>
  </div>;
}
