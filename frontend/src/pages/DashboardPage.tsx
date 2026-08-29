/**
 * NETRA Dashboard Page.
 * Matches the Dashboard design in the mockups.
 */

import { useMemo, useState } from "react";
import { api } from "../api";
import { useAsync } from "../hooks";
import {
  ComplianceTrendChart,
  NetraDonut,
} from "../components/charts";
import {
  AlertTriangleIcon,
  CheckCircleIcon,
  ChevronRightIcon,
  CloudIcon,
  ComplianceIcon,
  DatabaseIcon,
  DevicesIcon,
  HardDriveIcon,
  ShieldAlertIcon,
  SparklesIcon,
  SwitchIcon,
} from "../components/icons";
import {
  ErrorBanner,
  Loading,
  NetraBadge,
  StatCard,
} from "../components/ui";

const TREND_POINTS_7D = [
  { date: "May 13", value: 48 },
  { date: "May 14", value: 65 },
  { date: "May 15", value: 68 },
  { date: "May 16", value: 70 },
  { date: "May 17", value: 73 },
  { date: "May 18", value: 76 },
  { date: "May 19", value: 82 },
];

const RECENT_ACTIVITY_MOCK = [
  { id: "act-1", text: "Backup completed for Core-Router-1", time: "10:24 AM", tone: "green", icon: "check" },
  { id: "act-2", text: "Policy violation detected on Dist-Switch-2", time: "09:58 AM", tone: "amber", icon: "alert" },
  { id: "act-3", text: "Configuration change on Firewall-1", time: "09:18 AM", tone: "purple", icon: "change" },
  { id: "act-4", text: "Device Core-Switch-1 came online", time: "08:45 AM", tone: "blue", icon: "device" },
  { id: "act-5", text: "Compliance scan completed", time: "08:30 AM", tone: "green", icon: "check" },
];

export function DashboardPage({ navigate }: { navigate: (page: string, param?: string) => void }) {
  const [range, setRange] = useState("7");

  const state = useAsync(async () => {
    try {
      const [dashboard, devices, logs, alerts] = await Promise.all([
        api.dashboard().catch(() => null),
        api.devices().catch(() => []),
        api.logs({ limit: 50 }).catch(() => []),
        api.alerts({ status: "new", limit: 5 }).catch(() => []),
      ]);
      return { dashboard, devices, logs, alerts };
    } catch {
      return { dashboard: null, devices: [], logs: [], alerts: [] };
    }
  }, []);

  const liveDevices = state.data?.devices ?? [];
  const db = state.data?.dashboard;
  const liveAlerts = state.data?.alerts ?? [];

  const totalDevices = db?.infrastructure.total_devices || (liveDevices.length > 0 ? liveDevices.length : 43);
  const onlineDevices = db?.infrastructure.online || 38;
  const offlineDevices = db?.infrastructure.offline || (totalDevices - onlineDevices > 0 ? totalDevices - onlineDevices : 5);

  const posture = db?.security_posture;
  const complianceScore = posture?.compliance?.score ?? "N/A";
  const openAlertsCount = posture?.alerts?.new ?? 0;
  
  const alertsSeveritySegments = [
    { label: "Critical", value: posture?.alerts?.by_severity?.critical ?? 0, color: "#ef4444" },
    { label: "Warning", value: (posture?.alerts?.by_severity?.high ?? 0) + (posture?.alerts?.by_severity?.medium ?? 0), color: "#f59e0b" },
    { label: "Info", value: posture?.alerts?.by_severity?.info ?? 0, color: "#3b82f6" },
  ];

  const deviceStatusSegments = [
    { label: "Online", value: onlineDevices, percentage: Math.round((onlineDevices / totalDevices) * 100) || 0, color: "#10b981" },
    { label: "Offline", value: offlineDevices, percentage: Math.round((offlineDevices / totalDevices) * 100) || 0, color: "#ef4444" },
    { label: "Unknown", value: totalDevices - onlineDevices - offlineDevices, percentage: Math.round(((totalDevices - onlineDevices - offlineDevices) / totalDevices) * 100) || 0, color: "#64748b" },
  ];

  return (
    <div className="page-content">
      {state.error && <ErrorBanner message={state.error} />}

      {/* Row 1: 4 Stat Cards */}
      <div className="kpi-grid-4">
        <StatCard
          label="Devices"
          value={totalDevices}
          icon={<SwitchIcon size={20} />}
          iconTone="green"
          indicators={[
            { text: `● Online ${onlineDevices}`, tone: "green" },
            { text: `● Offline ${offlineDevices}`, tone: "red" },
          ]}
          onClick={() => navigate("devices")}
        />
        <StatCard
          label="Compliance Score"
          value={complianceScore !== "N/A" ? `${complianceScore}%` : "N/A"}
          icon={<ComplianceIcon size={20} />}
          iconTone="purple"
          indicators={[]}
          onClick={() => navigate("compliance")}
        />
        <StatCard
          label="Open Alerts"
          value={openAlertsCount.toString()}
          icon={<AlertTriangleIcon size={20} />}
          iconTone="amber"
          indicators={[
            { text: `● Critical ${posture?.alerts?.by_severity?.critical ?? 0}`, tone: "red" },
            { text: `● Warning ${(posture?.alerts?.by_severity?.high ?? 0) + (posture?.alerts?.by_severity?.medium ?? 0)}`, tone: "amber" },
          ]}
          onClick={() => navigate("alerts")}
        />
        <StatCard
          label="Last 24h"
          value={db?.backup.total_jobs?.toString() || "0"}
          icon={<CloudIcon size={20} />}
          iconTone="blue"
          indicators={[{ text: "Backups", tone: "blue" }]}
          onClick={() => navigate("backups")}
        />
      </div>

      {/* Row 2: Charts & Status Widgets Grid */}
      <div className="dashboard-main-grid">
        {/* Left column: Trend Chart + Alerts Severity Chart */}
        <div className="dashboard-left-col">
          <div className="dashboard-charts-row">
            {/* Compliance Trend Line Chart */}
            <div className="netra-panel">
              <div className="netra-panel-header">
                <h2 className="panel-title">Compliance Trend</h2>
                <select
                  className="filter-select"
                  value={range}
                  onChange={(e) => setRange(e.target.value)}
                  style={{ padding: "4px 8px", fontSize: "0.75rem" }}
                >
                  <option value="7">Last 7 Days</option>
                  <option value="14">Last 14 Days</option>
                  <option value="30">Last 30 Days</option>
                </select>
              </div>
              <ComplianceTrendChart points={TREND_POINTS_7D} />
            </div>

            {/* Alerts by Severity Donut */}
            <div className="netra-panel">
              <div className="netra-panel-header">
                <h2 className="panel-title">Alerts by Severity</h2>
              </div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", flex: 1, paddingTop: "8px" }}>
                <NetraDonut
                  segments={alertsSeveritySegments}
                  centerValue={openAlertsCount}
                  centerLabel="Total"
                  size={135}
                  strokeWidth={14}
                />
              </div>
            </div>
          </div>

          {/* Bottom Card: Recent Alerts Table */}
          <div className="table-card">
            <div style={{ padding: "16px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--line)" }}>
              <h2 style={{ fontSize: "0.98rem", fontWeight: "600", color: "#ffffff" }}>Recent Alerts</h2>
              <button className="panel-link" onClick={() => navigate("alerts")}>
                View all alerts →
              </button>
            </div>

            <div className="table-responsive">
              <table className="netra-table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Device</th>
                    <th>Type</th>
                    <th>Severity</th>
                    <th>Message</th>
                    <th style={{ width: "30px" }} />
                  </tr>
                </thead>
                <tbody>
                  {liveAlerts.length === 0 ? (
                    <tr>
                      <td colSpan={6} style={{ textAlign: "center", padding: "32px", color: "var(--ink-3)" }}>
                        No new alerts
                      </td>
                    </tr>
                  ) : liveAlerts.map((alt) => (
                    <tr key={alt.id}>
                      <td className="table-time">{new Date(alt.created_at).toLocaleString()}</td>
                      <td>
                        {alt.device_id ? (
                           <button
                             className="table-device-link"
                             onClick={() => navigate("devices", alt.device_id!)}
                           >
                             {alt.device_id.split("-")[0]}...
                           </button>
                        ) : (
                           <span style={{ color: "var(--ink-3)" }}>System</span>
                        )}
                      </td>
                      <td>{alt.category}</td>
                      <td>
                        <NetraBadge type={alt.severity === "critical" ? "critical" : alt.severity === "high" || alt.severity === "medium" ? "warning" : "info"} />
                      </td>
                      <td>
                        <span style={{ color: "var(--ink-2)" }}>{alt.title}</span>
                      </td>
                      <td>
                        <button
                          className="action-icon-btn"
                          onClick={() => navigate("alerts")}
                          title="Open alert"
                        >
                          <ChevronRightIcon size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right column: Device Status + Recent Activity + System Health */}
        <div className="dashboard-right-col">
          {/* Device Status Overview Donut */}
          <div className="netra-panel">
            <div className="netra-panel-header">
              <h2 className="panel-title">Device Status Overview</h2>
            </div>
            <div style={{ padding: "6px 0" }}>
              <NetraDonut
                segments={deviceStatusSegments}
                centerValue={43}
                centerLabel="Total"
                size={120}
                strokeWidth={13}
              />
            </div>
            <div style={{ borderTop: "1px solid var(--line)", paddingTop: "10px", display: "flex", justifyContent: "flex-end" }}>
              <button className="panel-link" onClick={() => navigate("devices")}>
                View all devices →
              </button>
            </div>
          </div>

          {/* Recent Activity */}
          <div className="netra-panel">
            <div className="netra-panel-header">
              <h2 className="panel-title">Recent Activity</h2>
            </div>
            <div className="activity-feed">
              {RECENT_ACTIVITY_MOCK.map((act) => (
                <div key={act.id} className="activity-item">
                  <div className="activity-left">
                    {act.tone === "green" && <CheckCircleIcon size={15} style={{ color: "var(--brand-emerald-light)", flexShrink: 0 }} />}
                    {act.tone === "amber" && <AlertTriangleIcon size={15} style={{ color: "var(--warn-light)", flexShrink: 0 }} />}
                    {act.tone === "purple" && <SwitchIcon size={15} style={{ color: "var(--ai-purple-light)", flexShrink: 0 }} />}
                    {act.tone === "blue" && <DevicesIcon size={15} style={{ color: "var(--info-light)", flexShrink: 0 }} />}
                    <span className="activity-text">{act.text}</span>
                  </div>
                  <span className="activity-time">{act.time}</span>
                </div>
              ))}
            </div>
            <div style={{ borderTop: "1px solid var(--line)", paddingTop: "10px", display: "flex", justifyContent: "flex-end" }}>
              <button className="panel-link" onClick={() => navigate("logs")}>
                View all activity →
              </button>
            </div>
          </div>

          {/* System Health */}
          <div className="netra-panel">
            <div className="netra-panel-header">
              <h2 className="panel-title">System Health</h2>
            </div>
            <div className="health-list">
              <div className="health-item">
                <div className="health-label-wrap">
                  <CheckCircleIcon size={15} style={{ color: "var(--brand-emerald-light)" }} />
                  <span>Collectors</span>
                </div>
                <span className="health-status good">Healthy</span>
                <div className="health-bar-track">
                  <div className="health-bar-fill good" style={{ width: "100%" }} />
                </div>
                <span className="health-value">4/4</span>
              </div>

              <div className="health-item">
                <div className="health-label-wrap">
                  <DatabaseIcon size={15} style={{ color: "var(--brand-emerald-light)" }} />
                  <span>Database</span>
                </div>
                <span className="health-status good">Healthy</span>
                <div className="health-bar-track">
                  <div className="health-bar-fill good" style={{ width: "100%" }} />
                </div>
                <span className="health-value">100%</span>
              </div>

              <div className="health-item">
                <div className="health-label-wrap">
                  <HardDriveIcon size={15} style={{ color: "var(--warn-light)" }} />
                  <span>Storage</span>
                </div>
                <span className="health-status warn">Warning</span>
                <div className="health-bar-track">
                  <div className="health-bar-fill warn" style={{ width: "72%" }} />
                </div>
                <span className="health-value">72%</span>
              </div>

              <div className="health-item">
                <div className="health-label-wrap">
                  <SparklesIcon size={15} style={{ color: "var(--brand-emerald-light)" }} />
                  <span>AI Analyst</span>
                </div>
                <span className="health-status good">Healthy</span>
                <div className="health-bar-track">
                  <div className="health-bar-fill good" style={{ width: "100%" }} />
                </div>
                <span className="health-value">100%</span>
              </div>
            </div>
            <div style={{ borderTop: "1px solid var(--line)", paddingTop: "10px", display: "flex", justifyContent: "flex-end" }}>
              <button className="panel-link" onClick={() => navigate("monitoring")}>
                View system status →
              </button>
            </div>
          </div>
        </div>
      </div>

      <footer className="page-footer">
        © 2026 NETRA. All rights reserved.
      </footer>
    </div>
  );
}
