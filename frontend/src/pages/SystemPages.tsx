/**
 * System Configuration & Management Pages for NETRA.
 */

import { useState } from "react";
import { api, getIdentity } from "../api";
import { useAsync } from "../hooks";
import type { AppSettings } from "../types";
import { SettingsIcon, UsersIcon, IntegrationsIcon, NotificationsIcon, AuditTrailIcon, CheckCircleIcon, PlusIcon } from "../components/icons";
import { StatCard, NetraBadge, Modal } from "../components/ui";

export function SystemPage({
  section,
  navigate,
}: {
  section: "settings" | "users" | "integrations" | "notifications" | "audit";
  navigate: (page: string, param?: string) => void;
}) {
  switch (section) {
    case "users":
      return <UsersSection />;
    case "integrations":
      return <IntegrationsSection />;
    case "notifications":
      return <NotificationsSection />;
    case "audit":
      return <AuditTrailSection navigate={navigate} />;
    default:
      return <SettingsSection navigate={navigate} />;
  }
}

function SettingsSection({ navigate }: { navigate: (page: string, param?: string) => void }) {
  const loaded = useAsync(() => api.settings(), []);
  const [form, setForm] = useState<AppSettings | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const values = form ?? loaded.data;
  const isAdmin = getIdentity().role === "admin";
  const save = async () => {
    if (!values || !isAdmin) return;
    try {
      setError(null); setMessage(null);
      const saved = await api.updateSettings(values);
      setForm(saved); setMessage("Settings saved. New scheduled runs will use these values.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to save settings"); }
  };
  return (
    <div className="page-content">
      {error && <p className="error-banner">{error}</p>}
      {message && <p className="notice">{message}</p>}
      <div className="netra-panel">
        <div className="netra-panel-header">
          <h2 className="panel-title">System & Security Settings</h2>
          <span className="badge resolved">Configured</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "16px", maxWidth: "680px" }}>
          <div className="form-group">
            <label>Default Backup Time (UTC)</label>
            <input className="form-input" value={values?.backup_time ?? ""} type="time" onChange={(e) => values && setForm({ ...values, backup_time: e.target.value })} disabled={!isAdmin} />
            <small>For named device schedules, use the Schedules page.</small>
          </div>
          <div className="form-group">
            <label>Backup Artifact Retention (Days)</label>
            <input className="form-input" value={values?.retention_days ?? ""} type="number" min="1" max="3650" onChange={(e) => values && setForm({ ...values, retention_days: Number(e.target.value) })} disabled={!isAdmin} />
          </div>
          <div className="form-group">
            <label>Backup Storage Directory</label>
            <input className="form-input" value={values?.backup_directory ?? ""} onChange={(e) => values && setForm({ ...values, backup_directory: e.target.value })} disabled={!isAdmin} />
            <small>Configuration backup files are written here by the backend.</small>
          </div>
          <div className="form-group">
            <label>Backup Worker Threads</label>
            <input className="form-input" value={values?.max_workers ?? ""} type="number" min="1" max="64" onChange={(e) => values && setForm({ ...values, max_workers: Number(e.target.value) })} disabled={!isAdmin} />
          </div>
          <div className="notice">Named schedules are managed separately and can target all devices or a selected device/cluster.</div>
          <div style={{ marginTop: "10px" }}>
            <button className="btn btn-primary" onClick={() => void save()} disabled={!isAdmin || !values}>{isAdmin ? "Save Settings" : "Admin role required"}</button>
            <button className="btn btn-ghost" style={{ marginLeft: "8px" }} onClick={() => navigate("schedules")}>Manage Backup Schedules</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function UsersSection() {
  const [users, setUsers] = useState([
    { name: "Admin", email: "admin@netra.internal", role: "Super Admin", status: "Active", lastLogin: "Just now" },
    { name: "Network Ops", email: "ops@netra.internal", role: "Operator", status: "Active", lastLogin: "2 hours ago" },
    { name: "Security Auditor", email: "auditor@netra.internal", role: "Viewer", status: "Active", lastLogin: "Yesterday" },
  ]);

  return (
    <div className="page-content">
      <div className="table-card">
        <div style={{ padding: "18px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--line)" }}>
          <div>
            <h2 style={{ fontSize: "1.05rem", fontWeight: "600", color: "#ffffff" }}>Users & Role-Based Access Control</h2>
            <span style={{ fontSize: "0.75rem", color: "var(--ink-3)" }}>Manage administrative users, API service keys, and privilege tiers</span>
          </div>
          <button className="btn btn-primary">
            <PlusIcon size={14} />
            <span>Invite User</span>
          </button>
        </div>
        <div className="table-responsive">
          <table className="netra-table">
            <thead>
              <tr>
                <th>User / Name</th>
                <th>Email</th>
                <th>Role Tier</th>
                <th>Status</th>
                <th>Last Active</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.email}>
                  <td><strong style={{ color: "#ffffff" }}>{u.name}</strong></td>
                  <td>{u.email}</td>
                  <td><span className="badge info">{u.role}</span></td>
                  <td><span className="badge resolved">{u.status}</span></td>
                  <td className="table-time">{u.lastLogin}</td>
                  <td><button className="btn btn-ghost" style={{ padding: "4px 8px", fontSize: "0.74rem" }}>Edit</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function IntegrationsSection() {
  return (
    <div className="page-content">
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "16px" }}>
        {[
          { name: "Junos & Cisco Adapters", status: "Connected", desc: "Native SSH & NETCONF adapters for hardware discovery" },
          { name: "Splunk / Syslog SIEM", status: "Connected", desc: "Real-time RFC 5424 structured event streaming" },
          { name: "Slack & Teams Webhooks", status: "Connected", desc: "Critical incident alerts and remediation notifications" },
          { name: "Vault Credential Store", status: "Connected", desc: "Just-in-time credential resolution without plain secrets" },
        ].map((item) => (
          <div key={item.name} className="netra-panel">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ fontSize: "0.95rem", fontWeight: "600", color: "#ffffff" }}>{item.name}</h3>
              <span className="badge resolved">{item.status}</span>
            </div>
            <p style={{ fontSize: "0.82rem", color: "var(--ink-2)" }}>{item.desc}</p>
            <div style={{ marginTop: "auto", paddingTop: "10px" }}>
              <button className="btn btn-ghost" style={{ width: "100%", fontSize: "0.78rem" }}>Configure</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function NotificationsSection() {
  return (
    <div className="page-content">
      <div className="netra-panel">
        <div className="netra-panel-header">
          <h2 className="panel-title">Notification Channels & Alert Rules</h2>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          {[
            { channel: "Critical Security Violations", target: "#netra-sec-alerts (Slack)", freq: "Instant" },
            { channel: "Daily Backup Summary", target: "net-admins@company.com (Email)", freq: "Daily 06:00 UTC" },
            { channel: "Configuration Drift Notifications", target: "Webhook (SIEM Collector)", freq: "Real-time" },
          ].map((n) => (
            <div key={n.channel} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 16px", background: "var(--surface-2)", borderRadius: "8px", border: "1px solid var(--line)" }}>
              <div>
                <strong style={{ color: "#ffffff", fontSize: "0.88rem" }}>{n.channel}</strong>
                <div style={{ fontSize: "0.75rem", color: "var(--ink-3)" }}>Target: {n.target}</div>
              </div>
              <span className="badge info">{n.freq}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function AuditTrailSection({ navigate }: { navigate: (page: string) => void }) {
  return (
    <div className="page-content">
      <div className="netra-panel">
        <div className="netra-panel-header">
          <h2 className="panel-title">Immutable Audit Trail</h2>
          <button className="btn btn-primary" onClick={() => navigate("logs")}>Open Full Log Feed</button>
        </div>
        <p style={{ color: "var(--ink-2)", fontSize: "0.84rem" }}>
          Every configuration commit, discovery trigger, user login, and automated remediation action is cryptographically signed and stored in the append-only audit database.
        </p>
      </div>
    </div>
  );
}
