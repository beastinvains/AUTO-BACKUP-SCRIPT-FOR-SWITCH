/**
 * System Configuration & Management Pages for NETRA.
 */

import { useState } from "react";
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
      return <SettingsSection />;
  }
}

function SettingsSection() {
  return (
    <div className="page-content">
      <div className="netra-panel">
        <div className="netra-panel-header">
          <h2 className="panel-title">System & Security Settings</h2>
          <span className="badge resolved">Configured</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "16px", maxWidth: "680px" }}>
          <div className="form-group">
            <label>Backup Artifact Retention Policy (Days)</label>
            <input className="form-input" defaultValue="90" type="number" />
          </div>
          <div className="form-group">
            <label>Stale Configuration Alert Threshold (Days)</label>
            <input className="form-input" defaultValue="7" type="number" />
          </div>
          <div className="form-group">
            <label>Local Encrypted Vault Path</label>
            <input className="form-input" defaultValue="/var/lib/netra/backups/encrypted_vault" />
          </div>
          <div className="form-group">
            <label>Session Inactivity Timeout (Minutes)</label>
            <input className="form-input" defaultValue="30" type="number" />
          </div>
          <div style={{ marginTop: "10px" }}>
            <button className="btn btn-primary">Save Settings</button>
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
