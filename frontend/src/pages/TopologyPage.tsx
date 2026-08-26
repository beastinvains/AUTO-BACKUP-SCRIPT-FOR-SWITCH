/**
 * Topology Page for NETRA Network Security Auditor.
 * Complete interactive canvas matching Screenshot 3.
 */

import { useState } from "react";
import { NetraDonut } from "../components/charts";
import {
  AlertTriangleIcon,
  CheckCircleIcon,
  CloudIcon,
  DevicesIcon,
  FanIcon,
  MinusIcon,
  PlayIcon,
  PlusIcon,
  PowerIcon,
  RefreshIcon,
  ShieldAlertIcon,
  SparklesIcon,
  SwitchIcon,
  TempIcon,
} from "../components/icons";
import {
  MOCK_TOPO_NODES,
  MOCK_TOPO_LINKS,
  TopologyMap,
  type TopoNodeVisual,
} from "../components/TopologyMap";
import { NetraBadge, Status } from "../components/ui";

export function TopologyPage({ navigate }: { navigate: (page: string, param?: string, tab?: string) => void }) {
  const [selectedNodeId, setSelectedNodeId] = useState<string>("CORE-JUN-01");
  const [siteFilter, setSiteFilter] = useState("All Sites");
  const [vendorFilter, setVendorFilter] = useState("All Vendors");
  const [typeFilter, setTypeFilter] = useState("All Device Types");
  const [healthFilter, setHealthFilter] = useState("Health: All");
  const [liveMode, setLiveMode] = useState(true);
  const [layoutMode, setLayoutMode] = useState("Auto");

  // Layers checkboxes
  const [layerDevices, setLayerDevices] = useState(true);
  const [layerLinks, setLayerLinks] = useState(true);
  const [layerIpLabels, setLayerIpLabels] = useState(true);
  const [layerAlerts, setLayerAlerts] = useState(true);

  // Inspector tab
  const [inspectorTab, setInspectorTab] = useState("overview");

  const selectedNode: TopoNodeVisual =
    MOCK_TOPO_NODES.find((n) => n.id === selectedNodeId) ?? MOCK_TOPO_NODES[5];

  // Radial semi-circle gauge component
  const renderRadialGauge = (value: number, label: string) => {
    const pct = Math.min(Math.max(value / 100, 0), 1);
    const r = 36;
    const c = Math.PI * r; // circumference of half-circle
    const offset = c * (1 - pct);
    const color = value > 80 ? "#ef4444" : value > 60 ? "#f59e0b" : "#10b981";

    return (
      <div className="metric-gauge-card">
        <span style={{ fontSize: "0.74rem", color: "var(--ink-2)", fontWeight: "500" }}>{label}</span>
        <svg width="84" height="46" viewBox="0 0 84 46">
          <path
            d="M 8 40 A 34 34 0 0 1 76 40"
            fill="none"
            stroke="rgba(255,255,255,0.08)"
            strokeWidth="7"
            strokeLinecap="round"
          />
          <path
            d="M 8 40 A 34 34 0 0 1 76 40"
            fill="none"
            stroke={color}
            strokeWidth="7"
            strokeDasharray={`${c} ${c}`}
            strokeDashoffset={offset}
            strokeLinecap="round"
          />
          <text
            x="42"
            y="36"
            textAnchor="middle"
            fill="var(--ink-heading)"
            style={{ fontSize: "12px", fontWeight: "700", fontFamily: "var(--font-mono)" }}
          >
            {value}%
          </text>
        </svg>
      </div>
    );
  };

  return (
    <div className="page" style={{ gap: "16px" }}>
      {/* Top Filter & Toolbar */}
      <div className="filter-toolbar" style={{ justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
          <select
            className="filter-select"
            value={siteFilter}
            onChange={(e) => setSiteFilter(e.target.value)}
          >
            <option>All Sites</option>
            <option>DataCenter-1</option>
            <option>Branch-Office</option>
          </select>

          <select
            className="filter-select"
            value={vendorFilter}
            onChange={(e) => setVendorFilter(e.target.value)}
          >
            <option>All Vendors</option>
            <option>Juniper</option>
            <option>Cisco</option>
            <option>Linux</option>
          </select>

          <select
            className="filter-select"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
          >
            <option>All Device Types</option>
            <option>Switch</option>
            <option>Router</option>
            <option>Firewall</option>
            <option>Server</option>
          </select>

          <select
            className="filter-select"
            value={healthFilter}
            onChange={(e) => setHealthFilter(e.target.value)}
          >
            <option>Health: All</option>
            <option>Healthy</option>
            <option>Warning</option>
            <option>Critical</option>
          </select>

          <select
            className="filter-select"
            value={layoutMode}
            onChange={(e) => setLayoutMode(e.target.value)}
            style={{ borderLeft: "2px solid var(--brand-emerald)" }}
          >
            <option>Layout: Auto</option>
            <option>Layout: Hierarchical</option>
            <option>Layout: Circular</option>
          </select>

          <label className="inline" style={{ fontSize: "0.8rem", color: "var(--ink)" }}>
            <span style={{ color: "var(--ink-2)" }}>Live</span>
            <input
              type="checkbox"
              checked={liveMode}
              onChange={(e) => setLiveMode(e.target.checked)}
              style={{ width: "16px", height: "16px", accentColor: "var(--brand-emerald)" }}
            />
          </label>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <button className="filter-btn">Expand All</button>
          <button className="filter-btn">Collapse All</button>
          <button className="btn btn-primary" onClick={() => navigate("devices")}>
            <PlusIcon size={14} />
            <span>Add View</span>
          </button>
        </div>
      </div>

      {/* Main Canvas & Right Widgets */}
      <div className="topology-main-view">
        {/* Canvas Area with Overlays */}
        <div style={{ position: "relative" }}>
          <TopologyMap
            selectedNodeId={selectedNodeId}
            onSelectNode={(id) => id && setSelectedNodeId(id)}
            showLabels={layerIpLabels}
            showLinks={layerLinks}
            showAlerts={layerAlerts}
          />

          {/* Left Floating Overlays */}
          <div className="topology-floating-overlays">
            {/* Legend Card */}
            <div className="topology-overlay-card">
              <span className="overlay-card-title">Legend</span>
              <ul className="overlay-legend-list">
                <li><span className="dot-indicator green" /> Healthy</li>
                <li><span className="dot-indicator amber" /> Warning</li>
                <li><span className="dot-indicator red" /> Critical</li>
                <li><span className="dot-indicator" style={{ background: "#64748b" }} /> Offline</li>
                <li><span className="dot-indicator blue" /> Unknown</li>
              </ul>
            </div>

            {/* Layers Card */}
            <div className="topology-overlay-card">
              <span className="overlay-card-title">Layers</span>
              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                <label className="overlay-checkbox-label">
                  <input
                    type="checkbox"
                    checked={layerDevices}
                    onChange={(e) => setLayerDevices(e.target.checked)}
                    style={{ accentColor: "var(--brand-emerald)" }}
                  />
                  <span>Devices</span>
                </label>
                <label className="overlay-checkbox-label">
                  <input
                    type="checkbox"
                    checked={layerLinks}
                    onChange={(e) => setLayerLinks(e.target.checked)}
                    style={{ accentColor: "var(--brand-emerald)" }}
                  />
                  <span>Links</span>
                </label>
                <label className="overlay-checkbox-label">
                  <input
                    type="checkbox"
                    checked={layerIpLabels}
                    onChange={(e) => setLayerIpLabels(e.target.checked)}
                    style={{ accentColor: "var(--brand-emerald)" }}
                  />
                  <span>IP Labels</span>
                </label>
                <label className="overlay-checkbox-label">
                  <input
                    type="checkbox"
                    checked={layerAlerts}
                    onChange={(e) => setLayerAlerts(e.target.checked)}
                    style={{ accentColor: "var(--brand-emerald)" }}
                  />
                  <span>Alerts</span>
                </label>
              </div>
            </div>
          </div>

          {/* Minimap Box in bottom right of canvas */}
          <div className="topology-minimap-box">
            <div className="minimap-tools">
              <button className="minimap-btn" title="Zoom in">+</button>
              <button className="minimap-btn" title="Zoom out">−</button>
              <button className="minimap-btn" title="Fit to view">⊡</button>
              <button className="minimap-btn" title="Lock view">🔒</button>
            </div>
            <svg width="100%" height="100%" viewBox="0 0 960 560" style={{ background: "#090d16" }}>
              {/* Mini nodes overview */}
              {MOCK_TOPO_LINKS.map((l) => {
                const src = MOCK_TOPO_NODES.find((n) => n.id === l.source);
                const tgt = MOCK_TOPO_NODES.find((n) => n.id === l.target);
                if (!src || !tgt) return null;
                return (
                  <line
                    key={l.id}
                    x1={src.x}
                    y1={src.y}
                    x2={tgt.x}
                    y2={tgt.y}
                    stroke="rgba(16,185,129,0.3)"
                    strokeWidth="4"
                  />
                );
              })}
              {MOCK_TOPO_NODES.map((n) => (
                <circle
                  key={n.id}
                  cx={n.x}
                  cy={n.y}
                  r="14"
                  fill={n.status === "critical" ? "#ef4444" : n.status === "warning" ? "#f59e0b" : "#10b981"}
                />
              ))}
              {/* Viewport rect box */}
              <rect x="220" y="100" width="520" height="340" fill="none" stroke="#ffffff" strokeWidth="4" strokeDasharray="12 8" opacity="0.7" />
            </svg>
          </div>
        </div>

        {/* Right Sidebar Widgets */}
        <aside className="topology-right-sidebar">
          {/* Topology Summary Donut */}
          <div className="netra-panel" style={{ padding: "16px" }}>
            <div className="netra-panel-header">
              <h3 style={{ fontSize: "0.92rem", fontWeight: "600", color: "var(--ink-heading)" }}>
                Topology Summary
              </h3>
            </div>
            <NetraDonut
              centerValue={46}
              centerLabel="Total Devices"
              segments={[
                { label: "Healthy", value: 32, color: "#10b981" },
                { label: "Warning", value: 8, color: "#f59e0b" },
                { label: "Critical", value: 3, color: "#ef4444" },
                { label: "Offline", value: 3, color: "#64748b" },
              ]}
            />
          </div>

          {/* Quick Actions Card */}
          <div className="netra-panel" style={{ padding: "16px" }}>
            <div className="netra-panel-header">
              <h3 style={{ fontSize: "0.92rem", fontWeight: "600", color: "var(--ink-heading)" }}>
                Quick Actions
              </h3>
            </div>
            <div className="quick-action-grid">
              <button className="topo-action-btn" onClick={() => navigate("devices")}>
                <RefreshIcon size={14} />
                <span>Run Discovery</span>
              </button>
              <button className="topo-action-btn green">
                <SwitchIcon size={14} />
                <span>Map Topology</span>
              </button>
              <button className="topo-action-btn blue" onClick={() => navigate("monitoring")}>
                <CheckCircleIcon size={14} />
                <span>Health Check</span>
              </button>
              <button className="topo-action-btn purple">
                <CloudIcon size={14} />
                <span>Export Topology</span>
              </button>
            </div>
          </div>

          {/* Selected Path */}
          <div className="selected-path-box">
            <span style={{ fontSize: "0.72rem", fontWeight: "600", textTransform: "uppercase", color: "var(--ink-3)" }}>
              Selected Path
            </span>
            <div className="path-crumbs">
              Internet &gt; FW-JUN-01 &gt; CORE-JUN-01 &gt; DIST-SW-01 &gt; {selectedNode.name} <span className="dot-indicator green" style={{ marginLeft: "4px" }} />
            </div>
            <div className="path-stats">
              <span>Latency: <strong>2 ms</strong></span>
              <span>Hops: <strong>4</strong></span>
              <span>Status: <strong style={{ color: "var(--brand-emerald-light)" }}>Good</strong></span>
            </div>
          </div>

          {/* AI Insights Card */}
          <div className="netra-panel" style={{ padding: "16px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <SparklesIcon size={15} style={{ color: "var(--ai-purple-light)" }} />
              <h3 style={{ fontSize: "0.92rem", fontWeight: "600", color: "var(--ai-purple-light)" }}>
                AI Insights
              </h3>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px", fontSize: "0.78rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--crit-light)" }}>
                <span className="dot-indicator red" />
                <span>NVR-01 has high CPU usage (95%)</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--warn-light)" }}>
                <span className="dot-indicator amber" />
                <span>DMZ-SW-01 has configuration drift</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--ink-2)" }}>
                <span className="dot-indicator amber" />
                <span>2 devices have outdated firmware</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--brand-emerald-light)" }}>
                <span className="dot-indicator green" />
                <span>Topology last verified 15 mins ago</span>
              </div>
            </div>
          </div>
        </aside>
      </div>

      {/* Bottom Inspector Panel for Selected Device */}
      <section className="topology-inspector">
        <div className="inspector-header">
          <div className="inspector-title-group">
            <div className="avatar-circle" style={{ width: "36px", height: "36px" }}>
              <SwitchIcon size={20} style={{ color: "var(--brand-emerald-light)" }} />
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: "700", color: "var(--ink-heading)" }}>
                  {selectedNode.name}
                </h2>
                <NetraBadge type={selectedNode.status === "critical" ? "critical" : selectedNode.status === "warning" ? "warning" : "resolved"} label={selectedNode.status.toUpperCase()} />
              </div>
              <p style={{ fontSize: "0.75rem", color: "var(--ink-3)" }}>
                {selectedNode.vendor} {selectedNode.model} Switch
              </p>
            </div>
          </div>

          <div className="inspector-meta-row">
            <div className="inspector-meta-item">
              <span className="inspector-meta-label">IP Address</span>
              <span className="inspector-meta-val">{selectedNode.ip}</span>
            </div>
            <div className="inspector-meta-item">
              <span className="inspector-meta-label">Uptime</span>
              <span className="inspector-meta-val">{selectedNode.uptime ?? "15d 4h 23m"}</span>
            </div>
            <div className="inspector-meta-item">
              <span className="inspector-meta-label">Model</span>
              <span className="inspector-meta-val">{selectedNode.model}</span>
            </div>
            <div className="inspector-meta-item">
              <span className="inspector-meta-label">Vendor</span>
              <span className="inspector-meta-val">{selectedNode.vendor}</span>
            </div>
          </div>
        </div>

        {/* Inspector Subtabs */}
        <div className="tabs-bar" style={{ padding: "0" }}>
          {[
            { id: "overview", label: "Overview" },
            { id: "interfaces", label: `Interfaces (${selectedNode.interfacesCount ?? 48})` },
            { id: "neighbors", label: `Neighbors (${selectedNode.neighborsCount ?? 12})` },
            { id: "alerts", label: `Alerts (${selectedNode.alertsCount ?? 2})` },
            { id: "config", label: "Config History" },
            { id: "logs", label: "Logs" },
          ].map((t) => (
            <button
              key={t.id}
              className={`tab-btn${inspectorTab === t.id ? " active" : ""}`}
              onClick={() => setInspectorTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Real-time Hardware Telemetry Row */}
        <div className="inspector-metrics-row">
          {renderRadialGauge(selectedNode.cpu ?? 32, "CPU Usage")}
          {renderRadialGauge(selectedNode.mem ?? 45, "Memory Usage")}

          <div className="metric-gauge-card">
            <span style={{ fontSize: "0.74rem", color: "var(--ink-2)", fontWeight: "500" }}>Temperature</span>
            <div style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "6px" }}>
              <TempIcon size={18} style={{ color: "var(--brand-emerald-light)" }} />
              <strong style={{ fontSize: "1.1rem", color: "var(--ink-heading)" }}>{selectedNode.temp ?? "42°C"}</strong>
            </div>
          </div>

          <div className="metric-gauge-card">
            <span style={{ fontSize: "0.74rem", color: "var(--ink-2)", fontWeight: "500" }}>Power Supply</span>
            <div style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "6px" }}>
              <PowerIcon size={18} style={{ color: "var(--brand-emerald-light)" }} />
              <strong style={{ fontSize: "1rem", color: "var(--brand-emerald-light)" }}>{selectedNode.power ?? "OK 2/2"}</strong>
            </div>
          </div>

          <div className="metric-gauge-card">
            <span style={{ fontSize: "0.74rem", color: "var(--ink-2)", fontWeight: "500" }}>Fan Speed</span>
            <div style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "6px" }}>
              <FanIcon size={18} style={{ color: "var(--brand-emerald-light)" }} />
              <strong style={{ fontSize: "0.95rem", color: "var(--ink-heading)" }}>{selectedNode.fan ?? "4200 RPM"}</strong>
            </div>
          </div>

          <div className="metric-gauge-card">
            <span style={{ fontSize: "0.74rem", color: "var(--ink-2)", fontWeight: "500" }}>Status</span>
            <div style={{ display: "flex", alignItems: "center", gap: "6px", marginTop: "6px" }}>
              <CheckCircleIcon size={18} style={{ color: "var(--brand-emerald-light)" }} />
              <strong style={{ fontSize: "1rem", color: "var(--brand-emerald-light)" }}>Online</strong>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
