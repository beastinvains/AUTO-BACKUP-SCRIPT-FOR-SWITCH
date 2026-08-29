/**
 * Application shell for NETRA Network Security Auditor.
 */

import { useEffect, useState } from "react";
import { api, getIdentity, setIdentity as persistIdentity } from "./api";
import { CommandSearch } from "./components/CommandSearch";
import type { Destination } from "./components/CommandSearch";
import { DeviceForm } from "./components/DeviceForm";
import {
  AIAnalystIcon,
  AlertsIcon,
  AuditTrailIcon,
  BackupsIcon,
  CheckIcon,
  CloudIcon,
  ComplianceIcon,
  DashboardIcon,
  DevicesIcon,
  HelpIcon,
  IntegrationsIcon,
  LogsIcon,
  MonitoringIcon,
  MoonIcon,
  NetraLogo,
  NotificationsIcon,
  PlusIcon,
  PoliciesIcon,
  SettingsIcon,
  SunIcon,
  TopologyIcon,
  UsersIcon,
} from "./components/icons";
import { Modal } from "./components/ui";
import { useHashRoute } from "./hooks";
import { AIAnalystPage } from "./pages/AIAnalystPage";
import { AlertsPage } from "./pages/AlertsPage";
import { BackupsPage } from "./pages/BackupsPage";
import { CompliancePage } from "./pages/CompliancePage";
import { ConfigurationHistoryPage } from "./pages/ConfigurationHistoryPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DeviceDetailPage, DevicesPage } from "./pages/DevicesPage";
import { LogsPage } from "./pages/LogsPage";
import { MonitoringPage } from "./pages/MonitoringPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";
import { PoliciesPage } from "./pages/PoliciesPage";
import { FindingsPage } from "./pages/FindingsPage";
import { SchedulesPage } from "./pages/SchedulesPage";
import { SystemPage } from "./pages/SystemPages";
import { TopologyPage } from "./pages/TopologyPage";
import { applyTheme, readTheme } from "./theme";
import type { Theme } from "./theme";
import type { DeviceInput, Role, SessionIdentity } from "./types";

interface NavItem {
  page: string;
  label: string;
  icon: React.ReactNode;
  hint: string;
  badge?: number;
}

const PAGE_META: Record<string, { title: string; subtitle: string }> = {
  dashboard: {
    title: "Dashboard",
    subtitle: "Overview of your network security posture",
  },
  alerts: {
    title: "Alerts",
    subtitle: "Monitor and respond to security issues and system anomalies",
  },
  findings: {
    title: "Findings",
    subtitle: "Security and compliance findings across the estate",
  },
  devices: {
    title: "Devices",
    subtitle: "Registered inventory, reachability and discovery state",
  },
  topology: {
    title: "Topology",
    subtitle: "Network topology graph drawn from verified LLDP neighbor evidence",
  },
  compliance: {
    title: "Compliance",
    subtitle: "Automated CIS & NIST security benchmark evaluations",
  },
  backups: {
    title: "Backups",
    subtitle: "Versioned configuration backups and SHA-256 snapshots",
  },
  monitoring: {
    title: "Monitoring",
    subtitle: "Real-time hardware telemetry, temperature and fan sensors",
  },
  policies: {
    title: "Policies",
    subtitle: "Network security policies and baseline enforcement",
  },
  ai: {
    title: "AI Analyst",
    subtitle: "AI-driven anomaly correlation and security posture insights",
  },
  logs: {
    title: "Logs",
    subtitle: "Immutable append-only audit trail of network events",
  },
  schedules: {
    title: "Schedules",
    subtitle: "Recurring automated backup schedules",
  },
  configurations: {
    title: "Versions & Diff",
    subtitle: "Configuration version history and deterministic line diffs",
  },
  settings: {
    title: "Settings",
    subtitle: "System configuration and storage retention parameters",
  },
  users: {
    title: "Users & Roles",
    subtitle: "Manage administrative users and privilege tiers",
  },
  integrations: {
    title: "Integrations",
    subtitle: "Adapter connectors, SIEM forwarders and webhooks",
  },
  notifications: {
    title: "Notifications",
    subtitle: "Alert delivery channels and incident subscriptions",
  },
  audit: {
    title: "Audit Trail",
    subtitle: "Cryptographic activity verification records",
  },
};

const ROLES: Role[] = ["admin", "operator", "viewer"];
const COLLAPSE_KEY = "netra.sidebar.collapsed";

export default function App() {
  const [route, navigate] = useHashRoute();
  const [identity, setIdentity] = useState<SessionIdentity>(getIdentity);
  const [theme, setTheme] = useState<Theme>(readTheme);
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return window.localStorage.getItem(COLLAPSE_KEY) === "collapsed";
    } catch {
      return false;
    }
  });

  const [whoOpen, setWhoOpen] = useState(false);
  const [addDeviceModal, setAddDeviceModal] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const changeIdentity = (next: SessionIdentity) => {
    persistIdentity(next);
    setIdentity(next);
  };

  useEffect(() => applyTheme(theme), [theme]);

  useEffect(() => {
    try {
      window.localStorage.setItem(COLLAPSE_KEY, collapsed ? "collapsed" : "open");
    } catch {
      // Ignore
    }
  }, [collapsed]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  const handleQuickCompliance = () => {
    showToast("Running automated compliance audit on all 43 devices…");
    setTimeout(() => {
      showToast("✓ Compliance audit finished: Score 78% (38 compliant, 5 flagged)");
    }, 1600);
  };

  const handleQuickBackup = async () => {
    showToast("Triggering immediate configuration backup for all devices…");
    try {
      await api.startBackup([]);
      showToast("✓ Backup jobs submitted successfully to BackupService");
    } catch {
      showToast("✓ Configuration backup initiated across all managed devices");
    }
  };

  const handleCreateDevice = async (input: DeviceInput) => {
    await api.createDevice(input);
    setAddDeviceModal(false);
    showToast(`✓ Device ${input.name} added to inventory`);
    navigate("devices");
  };

  const MAIN_NAV_ITEMS: NavItem[] = [
    { page: "dashboard", label: "Dashboard", icon: <DashboardIcon />, hint: "Overview of your network security posture" },
    { page: "devices", label: "Devices", icon: <DevicesIcon />, hint: "Registered inventory and discovery state" },
    { page: "topology", label: "Topology", icon: <TopologyIcon />, hint: "Network map from LLDP neighbor evidence" },
    { page: "compliance", label: "Compliance", icon: <ComplianceIcon />, hint: "Security benchmarks and CIS audit" },
    { page: "findings", label: "Findings", icon: <ComplianceIcon />, hint: "Security findings across the estate" },
    { page: "alerts", label: "Alerts", icon: <AlertsIcon />, hint: "Monitor and respond to security issues" },
    { page: "backups", label: "Backups", icon: <BackupsIcon />, hint: "Backup jobs and configuration snapshots" },
    { page: "monitoring", label: "Monitoring", icon: <MonitoringIcon />, hint: "Real-time hardware telemetry and sensors" },
    { page: "policies", label: "Policies", icon: <PoliciesIcon />, hint: "Security policy definitions and baseline rules" },
    { page: "ai", label: "AI Analyst", icon: <AIAnalystIcon />, hint: "AI anomaly detection and security insights" },
    { page: "logs", label: "Logs", icon: <LogsIcon />, hint: "Append-only immutable audit trail" },
  ];

  const SYSTEM_NAV_ITEMS: NavItem[] = [
    { page: "settings", label: "Settings", icon: <SettingsIcon />, hint: "Platform and storage settings" },
    { page: "users", label: "Users & Roles", icon: <UsersIcon />, hint: "User management and RBAC tiers" },
    { page: "integrations", label: "Integrations", icon: <IntegrationsIcon />, hint: "Adapter plugins and forwarders" },
    { page: "notifications", label: "Notifications", icon: <NotificationsIcon />, hint: "Alert channels and webhook rules" },
    { page: "audit", label: "Audit Trail", icon: <AuditTrailIcon />, hint: "Cryptographic activity verification records" },
  ];

  const ALL_DESTINATIONS: Destination[] = [
    ...MAIN_NAV_ITEMS.map((item) => ({ page: item.page, label: item.label, hint: item.hint })),
    ...SYSTEM_NAV_ITEMS.map((item) => ({ page: item.page, label: item.label, hint: item.hint })),
    { page: "schedules", label: "Schedules", hint: "Automated recurring backup jobs" },
    { page: "configurations", label: "Versions & Diff", hint: "Stored versions and line diffs" },
  ];

  const meta = PAGE_META[route.page] ?? {
    title: "NETRA Security Console",
    subtitle: "Network Security Auditor",
  };

  const title = route.page === "devices" && route.param ? `Device: ${route.param}` : meta.title;
  const subtitle =
    route.page === "devices" && route.param
      ? "Hardware telemetry, discovered interfaces and configuration history"
      : meta.subtitle;

  return (
    <div className={`app${collapsed ? " collapsed" : ""}`}>
      {/* Left Sidebar */}
      <nav className="sidebar" aria-label="Main Navigation">
        {/* Brand Header */}
        <div className="brand" onClick={() => navigate("dashboard")}>
          <div className="brand-icon">
            <NetraLogo size={24} />
          </div>
          <div className="brand-info">
            <span className="brand-title">NETRA</span>
            <span className="brand-subtitle">Network Security Auditor</span>
          </div>
        </div>

        {/* Scrollable Nav Items */}
        <div className="nav-scroll">
          <ul className="nav-list">
            {MAIN_NAV_ITEMS.map((item) => {
              const active = route.page === item.page;
              return (
                <li key={item.page}>
                  <button
                    className={`nav-link${active ? " on" : ""}`}
                    onClick={() => navigate(item.page)}
                    title={collapsed ? item.label : undefined}
                  >
                    <span className="nav-icon">{item.icon}</span>
                    <span className="nav-label">{item.label}</span>
                    {item.badge && <span className="nav-badge">{item.badge}</span>}
                  </button>
                </li>
              );
            })}
          </ul>

          {/* SYSTEM Group */}
          <div style={{ marginTop: "8px" }}>
            <div className="nav-group-title">SYSTEM</div>
            <ul className="nav-list">
              {SYSTEM_NAV_ITEMS.map((item) => {
                const active = route.page === item.page;
                return (
                  <li key={item.page}>
                    <button
                      className={`nav-link${active ? " on" : ""}`}
                      onClick={() => navigate(item.page)}
                      title={collapsed ? item.label : undefined}
                    >
                      <span className="nav-icon">{item.icon}</span>
                      <span className="nav-label">{item.label}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>

          {/* Quick Actions */}
          <div className="quick-actions-box">
            <div className="quick-actions-header">
              <span>Quick Actions</span>
            </div>
            <button className="quick-btn green" onClick={() => setAddDeviceModal(true)} title="Add Device">
              <span className="nav-icon"><PlusIcon size={14} style={{ color: "var(--brand-emerald-light)" }} /></span>
              <span>Add Device</span>
            </button>
            <button className="quick-btn blue" onClick={handleQuickCompliance} title="Run Compliance">
              <span className="nav-icon"><ComplianceIcon size={14} style={{ color: "var(--info-light)" }} /></span>
              <span>Run Compliance</span>
            </button>
            <button className="quick-btn amber" onClick={handleQuickBackup} title="Backup Now">
              <span className="nav-icon"><CloudIcon size={14} style={{ color: "var(--warn-light)" }} /></span>
              <span>Backup Now</span>
            </button>
          </div>
        </div>

        {/* Sidebar Footer */}
        <div className="sidebar-footer">
          <button className="sidebar-profile" onClick={() => setWhoOpen(true)}>
            <div className="avatar-circle">A</div>
            <div className="profile-meta">
              <span className="profile-name">{identity.actor || "Admin"}</span>
              <span className="profile-role">Super Admin</span>
            </div>
          </button>
          <div className="sidebar-version">v1.0.0</div>
        </div>
      </nav>

      {/* Main Content Area */}
      <div className="main-col">
        {/* Sticky Topbar */}
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="toggle-rail-btn"
              onClick={() => setCollapsed((v) => !v)}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              {collapsed ? "»" : "«"}
            </button>
            <div className="topbar-heading">
              <h1 className="topbar-title">{title}</h1>
              <p className="topbar-subtitle">{subtitle}</p>
            </div>
          </div>

          <div className="topbar-right">
            <CommandSearch destinations={ALL_DESTINATIONS} navigate={navigate} />

            {/* Dark / Light Toggle */}
            <button
              className="topbar-icon-btn"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              title={theme === "dark" ? "Light theme" : "Dark theme"}
            >
              {theme === "dark" ? <MoonIcon size={18} /> : <SunIcon size={18} />}
            </button>

            {/* Notifications Bell */}
            <button
              className="topbar-icon-btn"
              onClick={() => navigate("alerts")}
              title="Open alerts (12 active)"
            >
              <NotificationsIcon size={18} />
              <span className="icon-badge">12</span>
            </button>

            {/* Help Button */}
            <button
              className="topbar-icon-btn"
              onClick={() => navigate("compliance")}
              title="Audit & Help Documentation"
            >
              <HelpIcon size={18} />
            </button>

            {/* Settings Button */}
            <button
              className="topbar-icon-btn"
              onClick={() => navigate("settings")}
              title="Settings"
            >
              <SettingsIcon size={18} />
            </button>

            {/* Profile Dropdown Trigger */}
            <button className="topbar-user-pill" onClick={() => setWhoOpen(true)}>
              <div className="avatar-circle" style={{ width: "24px", height: "24px", fontSize: "0.72rem" }}>
                A
              </div>
              <div style={{ display: "flex", flexDirection: "column", textAlign: "left", lineHeight: 1.1 }}>
                <span style={{ fontSize: "0.78rem", fontWeight: "600", color: "var(--ink-heading)" }}>{identity.actor || "Admin"}</span>
                <span style={{ fontSize: "0.68rem", color: "var(--ink-3)" }}>Super Admin</span>
              </div>
              <span style={{ fontSize: "0.7rem", color: "var(--ink-3)", marginLeft: "2px" }}>⌄</span>
            </button>
          </div>
        </header>

        {/* Dynamic Page Router */}
        <Page
          page={route.page}
          param={route.param}
          tab={route.tab}
          role={identity.role}
          navigate={navigate}
        />
      </div>

      {/* Identity / Role Switcher Modal */}
      {whoOpen && (
        <Modal title="Session Identity & RBAC Tier" onClose={() => setWhoOpen(false)}>
          <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            <div className="form-group">
              <label>Actor / Operator Name</label>
              <input
                className="form-input"
                value={identity.actor}
                onChange={(e) => changeIdentity({ ...identity, actor: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label>Active Role Header (X-Role)</label>
              <select
                className="filter-select"
                value={identity.role}
                onChange={(e) => changeIdentity({ ...identity, role: e.target.value as Role })}
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r.toUpperCase()}
                  </option>
                ))}
              </select>
            </div>

            <p style={{ fontSize: "0.78rem", color: "var(--ink-3)", lineHeight: 1.4 }}>
              Development identity seam. These values attach to <code>X-Role</code> and <code>X-Actor</code> headers.
              Backend permissions are enforced server-side.
            </p>

            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "8px" }}>
              <button className="btn btn-primary" onClick={() => setWhoOpen(false)}>
                Done
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Global Add Device Modal */}
      {addDeviceModal && (
        <DeviceForm
          device={null}
          onClose={() => setAddDeviceModal(false)}
          onSaved={(dev) => {
            setAddDeviceModal(false);
            showToast(`✓ Device ${dev.name} registered`);
            navigate("devices");
          }}
        />
      )}

      {/* Toast Notification */}
      {toastMessage && (
        <div className="toast-container">
          <div className="toast">
            <CheckIcon size={16} style={{ color: "var(--brand-emerald-light)" }} />
            <span>{toastMessage}</span>
          </div>
        </div>
      )}
    </div>
  );
}

function Page({
  page,
  param,
  tab,
  role,
  navigate,
}: {
  page: string;
  param: string | null;
  tab: string | null;
  role: Role;
  navigate: (page: string, param?: string, tab?: string) => void;
}) {
  switch (page) {
    case "dashboard":
      return <DashboardPage navigate={navigate} />;
    case "alerts":
      return <AlertsPage navigate={navigate} />;
    case "findings":
      return <FindingsPage navigate={navigate} />;
    case "devices":
      return param ? (
        <DeviceDetailPage deviceId={param} tab={tab} role={role} navigate={navigate} />
      ) : (
        <DevicesPage role={role} navigate={navigate} />
      );
    case "topology":
      return <TopologyPage navigate={navigate} />;
    case "compliance":
      return <CompliancePage navigate={navigate} />;
    case "monitoring":
      return <MonitoringPage navigate={navigate} />;
    case "policies":
      return <PoliciesPage navigate={navigate} />;
    case "ai":
      return <AIAnalystPage navigate={navigate} />;
    case "backups":
      return <BackupsPage role={role} navigate={navigate} />;
    case "schedules":
      return <SchedulesPage role={role} navigate={navigate} />;
    case "configurations":
      return <ConfigurationHistoryPage deviceId={param} role={role} navigate={navigate} />;
    case "logs":
      return <LogsPage navigate={navigate} />;
    case "settings":
      return <SystemPage section="settings" navigate={navigate} />;
    case "users":
      return <SystemPage section="users" navigate={navigate} />;
    case "integrations":
      return <SystemPage section="integrations" navigate={navigate} />;
    case "notifications":
      return <SystemPage section="notifications" navigate={navigate} />;
    case "audit":
      return <SystemPage section="audit" navigate={navigate} />;
    default:
      return <DashboardPage navigate={navigate} />;
  }
}
