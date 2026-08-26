/**
 * AI Security Analyst & Anomaly Detection Page for NETRA.
 */

import { useState } from "react";
import { AIAnalystIcon, SparklesIcon, ShieldAlertIcon, CheckCircleIcon } from "../components/icons";
import { StatCard, NetraBadge } from "../components/ui";

interface AIInsight {
  id: string;
  title: string;
  confidence: number;
  time: string;
  severity: "critical" | "warning" | "info";
  summary: string;
  recommendation: string;
  device: string;
}

const INSIGHTS: AIInsight[] = [
  {
    id: "AI-ALERT-1023",
    title: "Unusual outbound egress traffic pattern detected",
    confidence: 92,
    time: "10:15 AM",
    severity: "critical",
    device: "Firewall-1",
    summary: "Spike of 450 outbound connections to high-risk external IP range 185.220.x.x originating from internal VLAN 20.",
    recommendation: "Review and restrict outbound traffic on Firewall-1 egress security policy rule #14.",
  },
  {
    id: "AI-ALERT-1022",
    title: "Configuration drift detected on SSH access baseline",
    confidence: 78,
    time: "09:42 AM",
    severity: "warning",
    device: "Dist-Switch-2",
    summary: "Recent configuration commit enabled password-only authentication and lowered cipher requirements.",
    recommendation: "Update SSH policy on Dist-Switch-2 to restore baseline key-based authentication.",
  },
  {
    id: "AI-ALERT-1021",
    title: "Predictive CPU exhaustion in next 2 hours",
    confidence: 85,
    time: "08:55 AM",
    severity: "info",
    device: "Core-Router-1",
    summary: "Telemetry model projects routing table churn will exceed control-plane CPU threshold of 90% by 11:00 AM.",
    recommendation: "Inspect BGP flap damping and consider temporary route aggregation.",
  },
];

export function AIAnalystPage({ navigate }: { navigate: (page: string, param?: string) => void }) {
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<Array<{ role: "user" | "ai"; text: string }>>([
    {
      role: "ai",
      text: "Hello! I am NETRA AI Analyst. I continuously correlate configuration backups, LLDP topology graphs, and streaming telemetry to identify security risks and explain configuration changes. How can I assist you today?",
    },
  ]);
  const [busy, setBusy] = useState(false);

  const handleAsk = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    const userText = query;
    setQuery("");
    setMessages((prev) => [...prev, { role: "user", text: userText }]);
    setBusy(true);

    setTimeout(() => {
      let response = "Analysis complete: I have queried the running configurations and telemetry.";
      const lower = userText.toLowerCase();

      if (lower.includes("telnet") || lower.includes("insecure") || lower.includes("port 23")) {
        response = "Core-Router-1 has `set system services telnet` active in its latest backup. This violates CIS Benchmark 1.1. Disabling Telnet will improve overall compliance score by +3%.";
      } else if (lower.includes("firewall") || lower.includes("traffic") || lower.includes("egress")) {
        response = "Firewall-1 shows anomalous outbound sessions on interface ge-0/0/2. The AI correlation engine assigned a 92% confidence score for potential unauthorized data egress.";
      } else if (lower.includes("backup") || lower.includes("diff") || lower.includes("change")) {
        response = "In the last 24 hours, 3 devices had configuration modifications: Dist-Switch-2 (SSH policy), Firewall-1 (NAT rules), and Dist-Router-1 (ACL updates). All diffs have been verified and archived.";
      } else {
        response = `Based on current network telemetry across all 43 registered devices: 38 devices are strictly compliant, 4 devices have warning-level configuration drifts, and 1 device (Firewall-1) has an active critical alert. Overall network posture score is 78%.`;
      }

      setMessages((prev) => [...prev, { role: "ai", text: response }]);
      setBusy(false);
    }, 1000);
  };

  return (
    <div className="page-content">
      <div className="kpi-grid-4">
        <StatCard
          label="AI Model Status"
          value="Online (v2.4)"
          icon={<AIAnalystIcon size={20} />}
          iconTone="purple"
          indicators={[{ text: "● Continuous correlation active", tone: "green", dot: true }]}
        />
        <StatCard
          label="AI Generated Insights"
          value="8 Total"
          icon={<SparklesIcon size={20} />}
          iconTone="blue"
          indicators={[{ text: "33% of all alerts", tone: "blue" }]}
        />
        <StatCard
          label="Anomaly Detection Accuracy"
          value="96.4%"
          icon={<CheckCircleIcon size={20} />}
          iconTone="green"
          indicators={[{ text: "0 false positives this week", tone: "green" }]}
        />
        <StatCard
          label="Automated Recommendations"
          value="3 Pending"
          icon={<ShieldAlertIcon size={20} />}
          iconTone="amber"
          indicators={[{ text: "● 1 Critical", tone: "red", dot: true }]}
        />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 0.8fr", gap: "20px" }}>
        {/* Chat / Query Assistant */}
        <div className="table-card" style={{ height: "560px", display: "flex", flexDirection: "column" }}>
          <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--line)", display: "flex", alignItems: "center", gap: "8px" }}>
            <SparklesIcon size={18} style={{ color: "var(--ai-purple-light)" }} />
            <h2 style={{ fontSize: "1.05rem", fontWeight: "600", color: "#ffffff" }}>Natural Language Network Auditor</h2>
          </div>

          <div style={{ flex: 1, overflowY: "auto", padding: "18px", display: "flex", flexDirection: "column", gap: "12px" }}>
            {messages.map((m, i) => (
              <div
                key={i}
                style={{
                  alignSelf: m.role === "user" ? "flex-end" : "flex-start",
                  maxWidth: "85%",
                  padding: "12px 16px",
                  borderRadius: "12px",
                  background: m.role === "user" ? "var(--brand-emerald)" : "var(--surface-2)",
                  color: "#ffffff",
                  fontSize: "0.85rem",
                  border: m.role === "user" ? "none" : "1px solid var(--line-strong)",
                  lineHeight: 1.4,
                }}
              >
                {m.text}
              </div>
            ))}
            {busy && (
              <div style={{ alignSelf: "flex-start", padding: "8px 14px", borderRadius: "12px", background: "var(--surface-2)", color: "var(--ink-2)", fontSize: "0.8rem" }}>
                AI Analyst is analyzing network facts…
              </div>
            )}
          </div>

          <form onSubmit={handleAsk} style={{ padding: "14px 18px", borderTop: "1px solid var(--line)", display: "flex", gap: "10px" }}>
            <input
              className="form-input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask anything about network security, device diffs, or compliance…"
              style={{ flex: 1 }}
            />
            <button type="submit" className="btn btn-primary" disabled={busy || !query.trim()}>
              Ask AI
            </button>
          </form>
        </div>

        {/* AI Insights & Recommendations */}
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <div className="table-card" style={{ padding: "18px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px" }}>
              <h3 style={{ fontSize: "0.95rem", fontWeight: "600", color: "#ffffff" }}>Correlated AI Findings</h3>
              <span className="badge ai">Real-time</span>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {INSIGHTS.map((insight) => (
                <div key={insight.id} className="ai-alert-card">
                  <div className="ai-alert-header">
                    <span className="ai-alert-id">{insight.id}</span>
                    <NetraBadge type={insight.severity} />
                  </div>
                  <div style={{ fontWeight: "600", color: "#ffffff", fontSize: "0.82rem" }}>{insight.title}</div>
                  <p className="ai-alert-body">{insight.summary}</p>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "4px" }}>
                    <span className="ai-score-pill">AI Confidence {insight.confidence}%</span>
                    <small style={{ color: "var(--ink-3)", fontSize: "0.72rem" }}>{insight.device} • {insight.time}</small>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
