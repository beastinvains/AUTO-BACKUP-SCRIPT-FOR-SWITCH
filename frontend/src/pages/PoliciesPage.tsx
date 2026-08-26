/**
 * Security Policies Definition & Enforcement Page for NETRA.
 */

import { useState } from "react";
import { PoliciesIcon, ShieldAlertIcon, CheckCircleIcon, PlusIcon } from "../components/icons";
import { StatCard, NetraBadge, Modal } from "../components/ui";

interface Policy {
  id: string;
  name: string;
  enforcement: "Enforced" | "Audit Only" | "Disabled";
  scope: string;
  violations: number;
  lastAudited: string;
  description: string;
}

const POLICIES: Policy[] = [
  {
    id: "POL-001",
    name: "Zero Plaintext Management Protocol Policy",
    enforcement: "Enforced",
    scope: "All Network Devices",
    violations: 1,
    lastAudited: "10 mins ago",
    description: "Prohibits Telnet, HTTP, and unencrypted SNMP v1/v2c management daemons across all infrastructure.",
  },
  {
    id: "POL-002",
    name: "SSH Access & Key Exchange Baseline",
    enforcement: "Enforced",
    scope: "Core & Distribution Switches",
    violations: 2,
    lastAudited: "25 mins ago",
    description: "Enforces SSHv2, Diffie-Hellman Group 14+ key exchange, AES-256-GCM cipher suites, and 5-min idle timeout.",
  },
  {
    id: "POL-003",
    name: "Outbound Egress Traffic Restriction",
    enforcement: "Enforced",
    scope: "Edge Firewalls",
    violations: 1,
    lastAudited: "Just now",
    description: "Blocks direct outbound egress to suspicious external IP addresses and unauthorized DNS resolvers.",
  },
  {
    id: "POL-004",
    name: "Administrative Privilege & AAA Policy",
    enforcement: "Audit Only",
    scope: "All Devices",
    violations: 0,
    lastAudited: "1 hour ago",
    description: "Mandates TACACS+ or RADIUS authentication with fallback to local break-glass admin accounts.",
  },
  {
    id: "POL-005",
    name: "Automated Configuration Backup Schedule",
    enforcement: "Enforced",
    scope: "All Managed Devices",
    violations: 0,
    lastAudited: "2 hours ago",
    description: "Mandates continuous SHA-256 versioned snapshot creation every 24 hours.",
  },
];

export function PoliciesPage({ navigate }: { navigate: (page: string, param?: string) => void }) {
  const [addingPolicy, setAddingPolicy] = useState(false);
  const [selectedPolicy, setSelectedPolicy] = useState<Policy | null>(null);

  return (
    <div className="page-content">
      <div className="kpi-grid-4">
        <StatCard
          label="Active Policies"
          value="18"
          icon={<PoliciesIcon size={20} />}
          iconTone="green"
          indicators={[{ text: "● 15 Enforced", tone: "green", dot: true }, { text: "● 3 Audit Only", tone: "blue", dot: true }]}
        />
        <StatCard
          label="Policy Violations"
          value="4"
          icon={<ShieldAlertIcon size={20} />}
          iconTone="red"
          indicators={[{ text: "● 2 Critical", tone: "red", dot: true }, { text: "● 2 Warning", tone: "amber", dot: true }]}
        />
        <StatCard
          label="Protected Devices"
          value="43"
          icon={<CheckCircleIcon size={20} />}
          iconTone="purple"
          indicators={[{ text: "100% estate coverage", tone: "green" }]}
        />
        <StatCard
          label="Auto-Remediation Rate"
          value="94%"
          icon={<CheckCircleIcon size={20} />}
          iconTone="blue"
          indicators={[{ text: "↑ 4% this month", tone: "green" }]}
        />
      </div>

      <div className="table-card">
        <div style={{ padding: "18px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--line)" }}>
          <div>
            <h2 style={{ fontSize: "1.05rem", fontWeight: "600", color: "#ffffff" }}>Network Security Policies</h2>
            <span style={{ fontSize: "0.75rem", color: "var(--ink-3)" }}>Defined rules continuously audited across running configurations</span>
          </div>
          <button className="btn btn-primary" onClick={() => setAddingPolicy(true)}>
            <PlusIcon size={14} />
            <span>Add Policy</span>
          </button>
        </div>

        <div className="table-responsive">
          <table className="netra-table">
            <thead>
              <tr>
                <th>Policy ID</th>
                <th>Policy Name</th>
                <th>Enforcement State</th>
                <th>Scope</th>
                <th>Violations</th>
                <th>Last Audited</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {POLICIES.map((p) => (
                <tr key={p.id}>
                  <td className="table-time">{p.id}</td>
                  <td>
                    <strong style={{ color: "#ffffff" }}>{p.name}</strong>
                    <br />
                    <small style={{ color: "var(--ink-3)" }}>{p.description}</small>
                  </td>
                  <td>
                    <span className={`badge ${p.enforcement === "Enforced" ? "resolved" : "info"}`}>
                      {p.enforcement}
                    </span>
                  </td>
                  <td>{p.scope}</td>
                  <td>
                    {p.violations > 0 ? (
                      <span className="badge critical">{p.violations} active</span>
                    ) : (
                      <span className="badge resolved">0 clean</span>
                    )}
                  </td>
                  <td className="table-time">{p.lastAudited}</td>
                  <td>
                    <button
                      className="btn btn-ghost"
                      style={{ padding: "4px 10px", fontSize: "0.76rem" }}
                      onClick={() => setSelectedPolicy(p)}
                    >
                      View Details
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {selectedPolicy && (
        <Modal title={`Policy: ${selectedPolicy.name}`} onClose={() => setSelectedPolicy(null)}>
          <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            <p style={{ color: "var(--ink-2)", fontSize: "0.84rem" }}>{selectedPolicy.description}</p>
            <div style={{ background: "rgba(255,255,255,0.03)", padding: "12px", borderRadius: "8px", border: "1px solid var(--line)" }}>
              <div style={{ fontSize: "0.75rem", color: "var(--ink-3)" }}>Scope: <strong>{selectedPolicy.scope}</strong></div>
              <div style={{ fontSize: "0.75rem", color: "var(--ink-3)", marginTop: "4px" }}>Status: <strong>{selectedPolicy.enforcement}</strong></div>
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "10px" }}>
              <button className="btn btn-ghost" onClick={() => setSelectedPolicy(null)}>Close</button>
              <button className="btn btn-primary" onClick={() => setSelectedPolicy(null)}>Edit Policy</button>
            </div>
          </div>
        </Modal>
      )}

      {addingPolicy && (
        <Modal title="Create Network Security Policy" onClose={() => setAddingPolicy(false)}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setAddingPolicy(false);
            }}
            style={{ display: "flex", flexDirection: "column", gap: "14px" }}
          >
            <div className="form-group">
              <label>Policy Name</label>
              <input className="form-input" placeholder="e.g. NTP Authentication Requirement" required />
            </div>
            <div className="form-group">
              <label>Enforcement Mode</label>
              <select className="filter-select">
                <option>Enforced (Alert & Block)</option>
                <option>Audit Only (Alert on violation)</option>
              </select>
            </div>
            <div className="form-group">
              <label>Description & Rule Rationale</label>
              <textarea
                className="form-input"
                rows={3}
                placeholder="Explain the security requirement..."
                style={{ resize: "vertical" }}
              />
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "10px" }}>
              <button type="button" className="btn btn-ghost" onClick={() => setAddingPolicy(false)}>Cancel</button>
              <button type="submit" className="btn btn-primary">Save Policy</button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
