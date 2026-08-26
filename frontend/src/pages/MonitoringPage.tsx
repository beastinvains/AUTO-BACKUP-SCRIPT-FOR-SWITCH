/**
 * Hardware Telemetry & Real-Time Monitoring Page for NETRA.
 */

import { useState } from "react";
import { MonitoringIcon, TempIcon, FanIcon, PowerIcon, RefreshIcon } from "../components/icons";
import { StatCard, HardwareTelemetryCard, Panel } from "../components/ui";

const TELEMETRY_DEVICES = [
  {
    name: "Core-Router-1",
    type: "Router",
    vendor: "Juniper",
    status: "online" as const,
    temp: "42°C",
    power: "OK",
    fan: "4200 RPM",
    alertsCount: 0,
    cpu: 34,
    mem: 45,
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
    cpu: 68,
    mem: 72,
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
    cpu: 89,
    mem: 84,
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
    cpu: 28,
    mem: 40,
  },
  {
    name: "AP-Office-1",
    type: "Access Point",
    vendor: "Cisco",
    status: "online" as const,
    temp: "39°C",
    power: "OK",
    fan: "Passive",
    alertsCount: 0,
    cpu: 18,
    mem: 32,
  },
  {
    name: "Dist-Router-1",
    type: "Router",
    vendor: "Juniper",
    status: "warning" as const,
    temp: "54°C",
    power: "OK",
    fan: "3400 RPM",
    alertsCount: 1,
    cpu: 82,
    mem: 65,
  },
];

export function MonitoringPage({ navigate }: { navigate: (page: string, param?: string) => void }) {
  const [filter, setFilter] = useState("all");

  const filtered = TELEMETRY_DEVICES.filter((d) => {
    if (filter === "warning") return d.status === "warning";
    if (filter === "critical") return d.status === "critical";
    if (filter === "online") return d.status === "online";
    return true;
  });

  return (
    <div className="page-content">
      <div className="kpi-grid-4">
        <StatCard
          label="Telemetry Collectors"
          value="4 / 4 Active"
          icon={<MonitoringIcon size={20} />}
          iconTone="green"
          indicators={[{ text: "● 100% collectors healthy", tone: "green", dot: true }]}
        />
        <StatCard
          label="Thermal Status"
          value="48°C Avg"
          icon={<TempIcon size={20} />}
          iconTone="amber"
          indicators={[{ text: "● 1 Over-temp warning (72°C)", tone: "red", dot: true }]}
        />
        <StatCard
          label="Fan Speed Health"
          value="96%"
          icon={<FanIcon size={20} />}
          iconTone="blue"
          indicators={[{ text: "● 1 Fan degradation detected", tone: "amber", dot: true }]}
        />
        <StatCard
          label="Power Supply Redundancy"
          value="42 / 43 OK"
          icon={<PowerIcon size={20} />}
          iconTone="red"
          indicators={[{ text: "● 1 PSU Failure (Firewall-1)", tone: "red", dot: true }]}
        />
      </div>

      <div className="netra-panel">
        <div className="netra-panel-header">
          <div>
            <h2 className="panel-title">Live Hardware Telemetry</h2>
            <span className="panel-subtitle">Streaming sensor readings collected via SNMP & SSH telemetry probes</span>
          </div>
          <div style={{ display: "flex", gap: "8px" }}>
            {["all", "online", "warning", "critical"].map((tab) => (
              <button
                key={tab}
                className={`filter-btn ${filter === tab ? "export" : ""}`}
                onClick={() => setFilter(tab)}
              >
                {tab.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "16px" }}>
          {filtered.map((d) => (
            <div key={d.name} style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              <HardwareTelemetryCard
                name={d.name}
                type={d.type}
                vendor={d.vendor}
                status={d.status}
                temp={d.temp}
                power={d.power}
                powerFail={d.powerFail}
                fan={d.fan}
                fanFail={d.fanFail}
                alertsCount={d.alertsCount}
                onClick={() => navigate("devices", d.name)}
              />
              <div style={{ background: "var(--surface-2)", border: "1px solid var(--line-subtle)", borderRadius: "8px", padding: "10px 14px", display: "flex", flexDirection: "column", gap: "8px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem" }}>
                  <span style={{ color: "var(--ink-3)" }}>CPU Load</span>
                  <span style={{ fontFamily: "var(--font-mono)", color: d.cpu > 80 ? "var(--crit-light)" : "var(--brand-emerald-light)" }}>{d.cpu}%</span>
                </div>
                <div style={{ height: "4px", background: "rgba(255,255,255,0.06)", borderRadius: "2px", overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${d.cpu}%`, background: d.cpu > 80 ? "var(--crit)" : "var(--brand-emerald)" }} />
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem" }}>
                  <span style={{ color: "var(--ink-3)" }}>Memory</span>
                  <span style={{ fontFamily: "var(--font-mono)", color: "var(--ink-2)" }}>{d.mem}%</span>
                </div>
                <div style={{ height: "4px", background: "rgba(255,255,255,0.06)", borderRadius: "2px", overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${d.mem}%`, background: "var(--info)" }} />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
