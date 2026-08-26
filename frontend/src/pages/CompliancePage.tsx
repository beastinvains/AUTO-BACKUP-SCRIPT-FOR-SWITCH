/**
 * Compliance Posture & Benchmark Auditor Page for NETRA.
 */

import { useState } from "react";
import { ComplianceIcon, ShieldAlertIcon, CheckCircleIcon, RefreshIcon } from "../components/icons";
import { StatCard, NetraBadge, Panel } from "../components/ui";

interface Rule {
  id: string;
  name: string;
  category: string;
  severity: "critical" | "warning" | "info";
  standard: "CIS Benchmark" | "NIST 800-53" | "PCI-DSS" | "Internal Baseline";
  passingCount: number;
  totalCount: number;
  score: number;
  remediation: string;
}

const RULES: Rule[] = [
  {
    id: "RULE-101",
    name: "Telnet service disabled (Insecure protocol)",
    category: "Access Control",
    severity: "critical",
    standard: "CIS Benchmark",
    passingCount: 38,
    totalCount: 43,
    score: 88,
    remediation: "Disable plaintext telnet server daemon on all management interfaces.",
  },
  {
    id: "RULE-102",
    name: "SSH v2 with strong cipher suites enforced",
    category: "Cryptography",
    severity: "warning",
    standard: "CIS Benchmark",
    passingCount: 35,
    totalCount: 43,
    score: 81,
    remediation: "Configure `set system services ssh protocol-version v2` and disable weak ciphers.",
  },
  {
    id: "RULE-103",
    name: "SNMPv3 configured with SHA/AES encryption",
    category: "Management",
    severity: "warning",
    standard: "NIST 800-53",
    passingCount: 32,
    totalCount: 43,
    score: 74,
    remediation: "Remove public/private community strings and require authPriv authentication.",
  },
  {
    id: "RULE-104",
    name: "Centralized Syslog forwarding configured",
    category: "Audit & Logging",
    severity: "info",
    standard: "PCI-DSS",
    passingCount: 41,
    totalCount: 43,
    score: 95,
    remediation: "Verify remote syslog server endpoint is reachable on UDP/TCP 514.",
  },
  {
    id: "RULE-105",
    name: "NTP server synchronization verified",
    category: "System Integrity",
    severity: "info",
    standard: "CIS Benchmark",
    passingCount: 43,
    totalCount: 43,
    score: 100,
    remediation: "Ensure minimum two authoritative stratum NTP servers are synchronized.",
  },
  {
    id: "RULE-106",
    name: "Default passwords and factory credentials removed",
    category: "Authentication",
    severity: "critical",
    standard: "NIST 800-53",
    passingCount: 40,
    totalCount: 43,
    score: 93,
    remediation: "Rotate factory default administrative credentials immediately.",
  },
];

export function CompliancePage({ navigate }: { navigate: (page: string, param?: string) => void }) {
  const [scanning, setScanning] = useState(false);
  const [scanMessage, setScanMessage] = useState<string | null>(null);
  const [selectedRule, setSelectedRule] = useState<Rule | null>(null);

  const runScan = () => {
    setScanning(true);
    setScanMessage("Running automated compliance audit across 43 network devices…");
    setTimeout(() => {
      setScanning(false);
      setScanMessage("Compliance scan completed: 43 devices evaluated against CIS & NIST baselines.");
      setTimeout(() => setScanMessage(null), 5000);
    }, 1800);
  };

  return (
    <div className="page-content">
      {scanMessage && (
        <div style={{ background: "var(--brand-emerald-wash)", border: "1px solid var(--brand-emerald)", borderRadius: "var(--radius-control)", padding: "12px 18px", color: "var(--brand-emerald-light)", fontSize: "0.85rem", display: "flex", alignItems: "center", gap: "10px" }}>
          <CheckCircleIcon size={18} />
          <span>{scanMessage}</span>
        </div>
      )}

      <div className="kpi-grid-4">
        <StatCard
          label="Overall Compliance"
          value="78%"
          icon={<ComplianceIcon size={20} />}
          iconTone="purple"
          indicators={[{ text: "↑ 8% this week", tone: "green" }]}
        />
        <StatCard
          label="CIS Benchmark Score"
          value="82%"
          icon={<CheckCircleIcon size={20} />}
          iconTone="green"
          indicators={[{ text: "● Passing 34 Rules", tone: "green", dot: true }]}
        />
        <StatCard
          label="NIST 800-53 Baseline"
          value="74%"
          icon={<ShieldAlertIcon size={20} />}
          iconTone="blue"
          indicators={[{ text: "● Passing 28 Rules", tone: "blue", dot: true }]}
        />
        <StatCard
          label="Open Policy Violations"
          value="6"
          icon={<ShieldAlertIcon size={20} />}
          iconTone="red"
          indicators={[{ text: "● Critical 2", tone: "red", dot: true }, { text: "● Warning 4", tone: "amber", dot: true }]}
        />
      </div>

      <div className="table-card">
        <div style={{ padding: "18px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--line)" }}>
          <div>
            <h2 style={{ fontSize: "1.05rem", fontWeight: "600", color: "#ffffff" }}>Security Benchmark Rules</h2>
            <span style={{ fontSize: "0.75rem", color: "var(--ink-3)" }}>Evaluated continuously against live configuration backups</span>
          </div>
          <button
            className="btn btn-primary"
            onClick={runScan}
            disabled={scanning}
          >
            <RefreshIcon size={14} className={scanning ? "spin" : ""} />
            <span>{scanning ? "Scanning…" : "Run Full Scan"}</span>
          </button>
        </div>

        <div className="table-responsive">
          <table className="netra-table">
            <thead>
              <tr>
                <th>Rule ID</th>
                <th>Security Control / Policy</th>
                <th>Standard</th>
                <th>Severity</th>
                <th>Pass Ratio</th>
                <th>Score</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {RULES.map((rule) => (
                <tr key={rule.id}>
                  <td className="table-time">{rule.id}</td>
                  <td>
                    <strong style={{ color: "#ffffff" }}>{rule.name}</strong>
                    <br />
                    <small style={{ color: "var(--ink-3)" }}>{rule.category}</small>
                  </td>
                  <td>
                    <span className="badge info">{rule.standard}</span>
                  </td>
                  <td>
                    <NetraBadge type={rule.severity} />
                  </td>
                  <td>
                    <span style={{ fontFamily: "var(--font-mono)", color: rule.passingCount < rule.totalCount ? "var(--warn-light)" : "var(--brand-emerald-light)" }}>
                      {rule.passingCount} / {rule.totalCount} devices
                    </span>
                  </td>
                  <td>
                    <span className="ai-score-pill">{rule.score}%</span>
                  </td>
                  <td>
                    <button
                      className="btn btn-ghost"
                      style={{ padding: "4px 10px", fontSize: "0.76rem" }}
                      onClick={() => setSelectedRule(rule)}
                    >
                      Remediation
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {selectedRule && (
        <div className="modal-backdrop" onClick={() => setSelectedRule(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Remediation Guidance: {selectedRule.id}</h3>
              <button className="action-icon-btn" onClick={() => setSelectedRule(null)}>✕</button>
            </div>
            <div className="modal-body">
              <div>
                <strong style={{ color: "#ffffff", fontSize: "0.95rem" }}>{selectedRule.name}</strong>
                <p style={{ color: "var(--ink-2)", fontSize: "0.82rem", marginTop: "4px" }}>
                  Standard: <strong>{selectedRule.standard}</strong> • Category: <strong>{selectedRule.category}</strong>
                </p>
              </div>
              <div style={{ background: "rgba(255,255,255,0.03)", border: "1px solid var(--line)", borderRadius: "var(--radius-control)", padding: "14px" }}>
                <span style={{ fontSize: "0.72rem", color: "var(--ink-3)", textTransform: "uppercase", fontWeight: "600" }}>Recommended Action</span>
                <p style={{ color: "var(--brand-emerald-light)", fontSize: "0.85rem", marginTop: "4px" }}>
                  {selectedRule.remediation}
                </p>
              </div>
              <div>
                <span style={{ fontSize: "0.75rem", color: "var(--ink-3)" }}>Affected Devices (Failing):</span>
                <ul style={{ listStyle: "none", marginTop: "6px", display: "flex", flexWrap: "wrap", gap: "6px" }}>
                  {["Core-Router-1", "Dist-Switch-2", "Dist-Router-1", "Power-Supply-1", "Firewall-1"].slice(0, selectedRule.totalCount - selectedRule.passingCount).map((d) => (
                    <li key={d} style={{ background: "var(--crit-wash)", border: "1px solid rgba(239, 68, 68, 0.4)", color: "var(--crit-light)", padding: "2px 8px", borderRadius: "4px", fontSize: "0.75rem" }}>
                      {d}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setSelectedRule(null)}>Close</button>
              <button className="btn btn-primary" onClick={() => { setSelectedRule(null); runScan(); }}>Run Auto-Fix</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
