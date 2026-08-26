/**
 * NETRA Alerts & Incident Management Page.
 * Matches Screenshot 2 in the design mockups.
 */

import { useMemo, useState } from "react";
import { api } from "../api";
import { useAsync } from "../hooks";
import { NetraDonut } from "../components/charts";
import {
  AlertTriangleIcon,
  CheckCircleIcon,
  ChevronRightIcon,
  ExportIcon,
  EyeIcon,
  FanIcon,
  FilterIcon,
  MoreVerticalIcon,
  PowerIcon,
  RefreshIcon,
  SearchIcon,
  ShieldAlertIcon,
  SparklesIcon,
  TempIcon,
} from "../components/icons";
import {
  ErrorBanner,
  HardwareTelemetryCard,
  Loading,
  Modal,
  NetraBadge,
  Pager,
  StatCard,
} from "../components/ui";

export interface AlertItem {
  id: string;
  time: string;
  device: string;
  type: string;
  severity: "critical" | "warning" | "info";
  source: "AI" | "System";
  message: string;
  aiScore: number | null;
  status: "New" | "Acknowledged" | "Resolved";
  recommendation?: string;
  rootCause?: string;
}

const ALERTS_DATA: AlertItem[] = [
  {
    id: "ALT-2001",
    time: "May 19, 10:24 AM",
    device: "Firewall-1",
    type: "Policy Violation",
    severity: "critical",
    source: "AI",
    message: "Unusual outbound traffic to multiple risky IPs",
    aiScore: 92,
    status: "New",
    rootCause: "Anomalous egress sessions originating from internal VLAN 20 communicating with known malicious TOR exit node IPs.",
    recommendation: "Apply restrictive egress firewall filter on Firewall-1 interface ge-0/0/0 to block unauthorized outbound TCP 443/8080 traffic.",
  },
  {
    id: "ALT-2002",
    time: "May 19, 09:58 AM",
    device: "Dist-Switch-2",
    type: "Configuration Change",
    severity: "warning",
    source: "AI",
    message: "SSH access policy modified",
    aiScore: 78,
    status: "New",
    rootCause: "Configuration drift committed out-of-band: plaintext password authentication enabled and protocol version lowered.",
    recommendation: "Revert SSH configuration commit to restore CIS compliant baseline configuration.",
  },
  {
    id: "ALT-2003",
    time: "May 19, 09:18 AM",
    device: "Firewall-1",
    type: "Interface Down",
    severity: "critical",
    source: "System",
    message: "Interface ge-0/0/2 is down",
    aiScore: null,
    status: "Acknowledged",
    rootCause: "Physical link loss detected on redundant WAN interface ge-0/0/2. BGP failover engaged to secondary link.",
    recommendation: "Inspect physical fiber connection and SFP transceiver on Firewall-1 port ge-0/0/2.",
  },
  {
    id: "ALT-2004",
    time: "May 19, 08:45 AM",
    device: "Core-Router-1",
    type: "High CPU Usage",
    severity: "warning",
    source: "AI",
    message: "CPU usage is 87% (threshold: 80%)",
    aiScore: 85,
    status: "New",
    rootCause: "Routing engine daemon `rpd` experiencing table recalculation churn following upstream BGP prefix flap.",
    recommendation: "Enable BGP prefix dampening on peer interface and monitor control-plane memory.",
  },
  {
    id: "ALT-2005",
    time: "May 19, 08:12 AM",
    device: "Core-Switch-1",
    type: "Device Up",
    severity: "info",
    source: "System",
    message: "Device came online",
    aiScore: null,
    status: "Resolved",
    rootCause: "Core-Switch-1 finished scheduled reboot and re-established LLDP neighbor adjacencies.",
    recommendation: "Verify all topology links have corroborated status.",
  },
  {
    id: "ALT-2006",
    time: "May 19, 07:30 AM",
    device: "Power-Supply-1",
    type: "Power Supply Failure",
    severity: "critical",
    source: "System",
    message: "PSU-1 failure detected",
    aiScore: null,
    status: "New",
    rootCause: "Hardware sensor reported voltage drop below 10.2V on primary power input line.",
    recommendation: "Dispatch on-site technician to replace hot-swappable Power Supply Unit 1.",
  },
];

const TELEMETRY_CAROUSEL = [
  {
    name: "Core-Router-1",
    type: "Router",
    vendor: "Juniper",
    status: "online" as const,
    temp: "42°C",
    power: "OK",
    fan: "4200 RPM",
    alertsCount: 0,
  },
  {
    name: "Dist-Switch-2",
    type: "Switch",
    vendor: "Cisco",
    status: "warning" as const,
    temp: "58°C",
    power: "OK",
    fan: "2800 RPM",
    alertsCount: 2,
  },
  {
    name: "Firewall-1",
    type: "Firewall",
    vendor: "FortiGate",
    status: "critical" as const,
    temp: "72°C",
    power: "PSU-1 Fail",
    powerFail: true,
    fan: "1500 RPM",
    fanFail: true,
    alertsCount: 3,
  },
  {
    name: "Core-Switch-1",
    type: "Switch",
    vendor: "Juniper",
    status: "online" as const,
    temp: "41°C",
    power: "OK",
    fan: "4600 RPM",
    alertsCount: 0,
  },
  {
    name: "AP-Office-1",
    type: "Access Point",
    vendor: "Cisco",
    status: "online" as const,
    temp: "39°C",
    power: "OK",
    alertsCount: 0,
  },
];

export function AlertsPage({ navigate }: { navigate: (page: string, param?: string) => void }) {
  const [activeTab, setActiveTab] = useState<"All Alerts" | "Device Status" | "AI Alerts" | "Acknowledged" | "Resolved">("All Alerts");
  const [search, setSearch] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [deviceFilter, setDeviceFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [timeFilter, setTimeFilter] = useState("24h");
  const [selectedAlert, setSelectedAlert] = useState<AlertItem | null>(null);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const [alertsList, setAlertsList] = useState<AlertItem[]>(ALERTS_DATA);

  const filterTabAlerts = useMemo(() => {
    return alertsList.filter((a) => {
      if (activeTab === "Device Status" && !a.type.includes("Interface") && !a.type.includes("Power") && !a.type.includes("CPU")) return false;
      if (activeTab === "AI Alerts" && a.source !== "AI") return false;
      if (activeTab === "Acknowledged" && a.status !== "Acknowledged") return false;
      if (activeTab === "Resolved" && a.status !== "Resolved") return false;

      if (severityFilter && a.severity !== severityFilter.toLowerCase()) return false;
      if (deviceFilter && a.device !== deviceFilter) return false;
      if (typeFilter && a.type !== typeFilter) return false;
      if (sourceFilter && a.source !== sourceFilter) return false;
      if (search.trim()) {
        const needle = search.toLowerCase();
        if (!`${a.device} ${a.type} ${a.message} ${a.severity}`.toLowerCase().includes(needle)) return false;
      }
      return true;
    });
  }, [alertsList, activeTab, severityFilter, deviceFilter, typeFilter, sourceFilter, search]);

  const pagedAlerts = filterTabAlerts.slice(page * pageSize, (page + 1) * pageSize);

  const resetFilters = () => {
    setSearch("");
    setSeverityFilter("");
    setDeviceFilter("");
    setTypeFilter("");
    setSourceFilter("");
    setTimeFilter("24h");
    setPage(0);
  };

  const exportCsv = () => {
    const header = ["Time", "Device", "Type", "Severity", "Source", "Message", "AI Score", "Status"];
    const rows = filterTabAlerts.map((a) => [
      `"${a.time}"`,
      `"${a.device}"`,
      `"${a.type}"`,
      `"${a.severity}"`,
      `"${a.source}"`,
      `"${a.message.replace(/"/g, '""')}"`,
      `"${a.aiScore ? `${a.aiScore}%` : "—"}"`,
      `"${a.status}"`,
    ]);
    const csvContent = [header.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `NETRA-Alerts-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const updateAlertStatus = (id: string, newStatus: "New" | "Acknowledged" | "Resolved") => {
    setAlertsList((prev) =>
      prev.map((item) => (item.id === id ? { ...item, status: newStatus } : item)),
    );
    if (selectedAlert && selectedAlert.id === id) {
      setSelectedAlert((prev) => (prev ? { ...prev, status: newStatus } : null));
    }
  };

  const alertSummaryTypeSegments = [
    { label: "Policy Violation", value: 8, percentage: 33, color: "#ef4444" },
    { label: "Configuration Change", value: 6, percentage: 25, color: "#f97316" },
    { label: "Interface Down", value: 4, percentage: 17, color: "#eab308" },
    { label: "Performance", value: 3, percentage: 13, color: "#10b981" },
    { label: "Others", value: 3, percentage: 12, color: "#8b5cf6" },
  ];

  return (
    <div className="page-content">
      {/* Sub-nav Tabs */}
      <div className="tabs-bar">
        {(["All Alerts", "Device Status", "AI Alerts", "Acknowledged", "Resolved"] as const).map((tab) => (
          <button
            key={tab}
            className={`tab-btn${activeTab === tab ? " active" : ""}`}
            onClick={() => {
              setActiveTab(tab);
              setPage(0);
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Top Row: 5 Metric Cards */}
      <div className="kpi-grid-5">
        <StatCard
          label="Total Alerts"
          value="24"
          icon={<AlertTriangleIcon size={20} />}
          iconTone="red"
          indicators={[{ text: "↑ 20% vs yesterday", tone: "red" }]}
        />
        <StatCard
          label="Critical"
          value="6"
          icon={<ShieldAlertIcon size={20} />}
          iconTone="red"
          indicators={[{ text: "↑ 2 new", tone: "red" }]}
        />
        <StatCard
          label="Warning"
          value="12"
          icon={<AlertTriangleIcon size={20} />}
          iconTone="amber"
          indicators={[{ text: "↑ 3 new", tone: "amber" }]}
        />
        <StatCard
          label="Info"
          value="6"
          icon={<CheckCircleIcon size={20} />}
          iconTone="blue"
          indicators={[{ text: "↓ 1 resolved", tone: "green" }]}
        />
        <StatCard
          label="AI Generated"
          value="8"
          icon={<SparklesIcon size={20} />}
          iconTone="purple"
          indicators={[{ text: "33% of total", tone: "blue" }]}
        />
      </div>

      {/* Filter Toolbar */}
      <div className="filter-toolbar">
        <div className="filter-search-wrap">
          <SearchIcon size={16} style={{ color: "var(--ink-3)" }} />
          <input
            className="search-input"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
            placeholder="Search alerts, devices..."
          />
        </div>

        <select
          className="filter-select"
          value={severityFilter}
          onChange={(e) => {
            setSeverityFilter(e.target.value);
            setPage(0);
          }}
        >
          <option value="">All Severities</option>
          <option value="Critical">Critical</option>
          <option value="Warning">Warning</option>
          <option value="Info">Info</option>
        </select>

        <select
          className="filter-select"
          value={deviceFilter}
          onChange={(e) => {
            setDeviceFilter(e.target.value);
            setPage(0);
          }}
        >
          <option value="">All Devices</option>
          <option value="Firewall-1">Firewall-1</option>
          <option value="Dist-Switch-2">Dist-Switch-2</option>
          <option value="Core-Router-1">Core-Router-1</option>
          <option value="Core-Switch-1">Core-Switch-1</option>
          <option value="Power-Supply-1">Power-Supply-1</option>
        </select>

        <select
          className="filter-select"
          value={typeFilter}
          onChange={(e) => {
            setTypeFilter(e.target.value);
            setPage(0);
          }}
        >
          <option value="">All Types</option>
          <option value="Policy Violation">Policy Violation</option>
          <option value="Configuration Change">Configuration Change</option>
          <option value="Interface Down">Interface Down</option>
          <option value="High CPU Usage">High CPU Usage</option>
          <option value="Power Supply Failure">Power Supply Failure</option>
        </select>

        <select
          className="filter-select"
          value={sourceFilter}
          onChange={(e) => {
            setSourceFilter(e.target.value);
            setPage(0);
          }}
        >
          <option value="">AI / Traditional</option>
          <option value="AI">AI Generated</option>
          <option value="System">Traditional (System)</option>
        </select>

        <select
          className="filter-select"
          value={timeFilter}
          onChange={(e) => setTimeFilter(e.target.value)}
        >
          <option value="24h">Last 24 Hours</option>
          <option value="7d">Last 7 Days</option>
          <option value="30d">Last 30 Days</option>
        </select>

        <button className="filter-btn" onClick={() => {}}>
          <FilterIcon size={14} />
          <span>More Filters</span>
        </button>

        <button className="filter-btn" onClick={resetFilters}>
          <RefreshIcon size={14} />
          <span>Reset</span>
        </button>

        <button className="filter-btn export" onClick={exportCsv}>
          <ExportIcon size={14} />
          <span>Export</span>
        </button>
      </div>

      {/* Device Status Overview (Hardware Carousel) */}
      <div className="telemetry-section">
        <div className="telemetry-header">
          <h2 style={{ fontSize: "0.98rem", fontWeight: "600", color: "#ffffff" }}>Device Status Overview</h2>
          <div className="telemetry-updated">
            <span>Last updated: 2 mins ago</span>
            <button className="action-icon-btn" title="Refresh Telemetry">
              <RefreshIcon size={14} />
            </button>
          </div>
        </div>

        <div className="telemetry-carousel-wrap">
          <div className="telemetry-cards-row">
            {TELEMETRY_CAROUSEL.map((dev) => (
              <HardwareTelemetryCard
                key={dev.name}
                name={dev.name}
                type={dev.type}
                vendor={dev.vendor}
                status={dev.status}
                temp={dev.temp}
                power={dev.power}
                powerFail={dev.powerFail}
                fan={dev.fan}
                fanFail={dev.fanFail}
                alertsCount={dev.alertsCount}
                onClick={() => navigate("devices", dev.name)}
              />
            ))}
          </div>
          <button className="carousel-nav-btn" aria-label="Next Devices">
            <ChevronRightIcon size={18} />
          </button>
        </div>
      </div>

      {/* Main Content Grid: Alerts Table + Right Side Panels */}
      <div className="alerts-grid">
        {/* Alerts List Table */}
        <div className="table-card">
          <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--line)" }}>
            <h2 style={{ fontSize: "0.98rem", fontWeight: "600", color: "#ffffff" }}>
              Alerts List ({filterTabAlerts.length})
            </h2>
          </div>

          <div className="table-responsive">
            <table className="netra-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Device</th>
                  <th>Type</th>
                  <th>Severity</th>
                  <th>Source</th>
                  <th>Message</th>
                  <th>AI Score</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {pagedAlerts.map((item) => (
                  <tr key={item.id}>
                    <td className="table-time">{item.time}</td>
                    <td>
                      <button
                        className="table-device-link"
                        onClick={() => navigate("devices", item.device)}
                      >
                        {item.device}
                      </button>
                    </td>
                    <td>{item.type}</td>
                    <td>
                      <NetraBadge type={item.severity} />
                    </td>
                    <td>
                      <span className={`badge ${item.source === "AI" ? "ai" : "system"}`}>
                        {item.source === "AI" && <SparklesIcon size={11} />}
                        {item.source}
                      </span>
                    </td>
                    <td>
                      <span style={{ color: "var(--ink)" }}>{item.message}</span>
                    </td>
                    <td>
                      {item.aiScore ? (
                        <span className="ai-score-pill">{item.aiScore}%</span>
                      ) : (
                        <span style={{ color: "var(--ink-3)" }}>—</span>
                      )}
                    </td>
                    <td>
                      <span className={`badge ${item.status.toLowerCase()}`}>
                        {item.status}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                        <button
                          className="action-icon-btn"
                          title="Inspect Alert Details"
                          onClick={() => setSelectedAlert(item)}
                        >
                          <EyeIcon size={15} />
                        </button>
                        <button
                          className="action-icon-btn"
                          title="More options"
                          onClick={() => setSelectedAlert(item)}
                        >
                          <MoreVerticalIcon size={15} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <Pager
            total={filterTabAlerts.length}
            page={page}
            pageSize={pageSize}
            onPage={setPage}
            onPageSize={(s) => {
              setPageSize(s);
              setPage(0);
            }}
            noun="alerts"
          />
        </div>

        {/* Right Side Column Widgets */}
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          {/* AI Generated Alerts */}
          <div className="netra-panel">
            <div className="netra-panel-header">
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <SparklesIcon size={16} style={{ color: "var(--ai-purple-light)" }} />
                <h2 className="panel-title">AI Generated Alerts</h2>
              </div>
              <button className="panel-link" onClick={() => navigate("ai")}>
                View all →
              </button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              <div className="ai-alert-card">
                <div className="ai-alert-header">
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <span className="ai-alert-id">AI-ALERT-1023</span>
                    <span className="badge ai">AI</span>
                  </div>
                  <span className="table-time">10:15 AM</span>
                </div>
                <p className="ai-alert-body">
                  Unusual outbound traffic from Firewall-1 to multiple external IPs.
                </p>
                <div style={{ marginTop: "4px" }}>
                  <NetraBadge type="critical" />
                </div>
              </div>

              <div className="ai-alert-card">
                <div className="ai-alert-header">
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <span className="ai-alert-id">AI-ALERT-1022</span>
                    <span className="badge ai">AI</span>
                  </div>
                  <span className="table-time">09:42 AM</span>
                </div>
                <p className="ai-alert-body">
                  Configuration drift detected on Dist-Switch-2 (SSH Access Policy)
                </p>
                <div style={{ marginTop: "4px" }}>
                  <NetraBadge type="warning" />
                </div>
              </div>

              <div className="ai-alert-card">
                <div className="ai-alert-header">
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <span className="ai-alert-id">AI-ALERT-1021</span>
                    <span className="badge ai">AI</span>
                  </div>
                  <span className="table-time">08:55 AM</span>
                </div>
                <p className="ai-alert-body">
                  High CPU usage trend predicted on Core-Router-1 in next 2 hours.
                </p>
                <div style={{ marginTop: "4px" }}>
                  <NetraBadge type="info" />
                </div>
              </div>
            </div>
          </div>

          {/* Top Recommendations */}
          <div className="netra-panel">
            <div className="netra-panel-header">
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <SparklesIcon size={16} style={{ color: "var(--info-light)" }} />
                <h2 className="panel-title">Top Recommendations</h2>
              </div>
              <button className="panel-link" onClick={() => navigate("ai")}>
                View all →
              </button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              <div className="recommendation-card">
                <div className="recommendation-icon critical">
                  <ShieldAlertIcon size={16} />
                </div>
                <div className="recommendation-content">
                  <span className="recommendation-text">
                    Review and restrict outbound traffic on Firewall-1
                  </span>
                  <div>
                    <NetraBadge type="critical" />
                  </div>
                </div>
              </div>

              <div className="recommendation-card">
                <div className="recommendation-icon warning">
                  <AlertTriangleIcon size={16} />
                </div>
                <div className="recommendation-content">
                  <span className="recommendation-text">
                    Update SSH policy on Dist-Switch-2 to comply with baseline
                  </span>
                  <div>
                    <NetraBadge type="warning" />
                  </div>
                </div>
              </div>

              <div className="recommendation-card">
                <div className="recommendation-icon info">
                  <CheckCircleIcon size={16} />
                </div>
                <div className="recommendation-content">
                  <span className="recommendation-text">
                    Monitor CPU trend on Core-Router-1 and consider capacity upgrade
                  </span>
                  <div>
                    <NetraBadge type="info" />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Alert Summary by Type */}
          <div className="netra-panel">
            <div className="netra-panel-header">
              <h2 className="panel-title">Alert Summary by Type</h2>
            </div>
            <div style={{ padding: "6px 0" }}>
              <NetraDonut
                segments={alertSummaryTypeSegments}
                centerValue={24}
                centerLabel="Total"
                size={125}
                strokeWidth={14}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Slide-over / Modal for Alert Details */}
      {selectedAlert && (
        <div className="drawer-backdrop" onClick={() => setSelectedAlert(null)}>
          <div className="drawer-panel" onClick={(e) => e.stopPropagation()}>
            <div className="drawer-header">
              <div>
                <span className="table-time">{selectedAlert.id}</span>
                <h3 style={{ fontSize: "1.1rem", fontWeight: "600", color: "#ffffff", marginTop: "2px" }}>
                  {selectedAlert.type}
                </h3>
              </div>
              <button className="action-icon-btn" onClick={() => setSelectedAlert(null)}>✕</button>
            </div>

            <div className="drawer-body">
              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                <NetraBadge type={selectedAlert.severity} />
                <span className={`badge ${selectedAlert.source.toLowerCase()}`}>{selectedAlert.source}</span>
                <span className={`badge ${selectedAlert.status.toLowerCase()}`}>{selectedAlert.status}</span>
                {selectedAlert.aiScore && <span className="ai-score-pill">AI Confidence {selectedAlert.aiScore}%</span>}
              </div>

              <div style={{ background: "rgba(255,255,255,0.03)", padding: "14px", borderRadius: "8px", border: "1px solid var(--line)" }}>
                <span style={{ fontSize: "0.72rem", color: "var(--ink-3)", textTransform: "uppercase", fontWeight: "600" }}>Device & Time</span>
                <p style={{ color: "#ffffff", fontSize: "0.85rem", marginTop: "2px" }}>
                  <strong>{selectedAlert.device}</strong> • {selectedAlert.time}
                </p>
                <p style={{ color: "var(--ink-2)", fontSize: "0.82rem", marginTop: "6px" }}>
                  {selectedAlert.message}
                </p>
              </div>

              {selectedAlert.rootCause && (
                <div>
                  <span style={{ fontSize: "0.75rem", color: "var(--ink-3)", fontWeight: "600", textTransform: "uppercase" }}>Correlated Root Cause</span>
                  <p style={{ color: "var(--ink)", fontSize: "0.82rem", marginTop: "4px", background: "var(--surface-2)", padding: "12px", borderRadius: "8px", border: "1px solid var(--line-subtle)" }}>
                    {selectedAlert.rootCause}
                  </p>
                </div>
              )}

              {selectedAlert.recommendation && (
                <div>
                  <span style={{ fontSize: "0.75rem", color: "var(--ink-3)", fontWeight: "600", textTransform: "uppercase" }}>Automated Remediation</span>
                  <p style={{ color: "var(--brand-emerald-light)", fontSize: "0.82rem", marginTop: "4px", background: "var(--brand-emerald-wash)", padding: "12px", borderRadius: "8px", border: "1px solid rgba(16, 185, 129, 0.3)" }}>
                    {selectedAlert.recommendation}
                  </p>
                </div>
              )}
            </div>

            <div className="drawer-footer">
              {selectedAlert.status !== "Acknowledged" && (
                <button
                  className="btn btn-ghost"
                  onClick={() => updateAlertStatus(selectedAlert.id, "Acknowledged")}
                >
                  Acknowledge
                </button>
              )}
              {selectedAlert.status !== "Resolved" && (
                <button
                  className="btn btn-primary"
                  onClick={() => updateAlertStatus(selectedAlert.id, "Resolved")}
                >
                  Mark Resolved
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
