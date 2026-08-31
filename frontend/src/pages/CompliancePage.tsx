/**
 * Compliance Posture & Benchmark Auditor Page for NETRA.
 */

import { useState, useMemo } from "react";
import { api } from "../api";
import { useAsync } from "../hooks";
import { ComplianceIcon, ShieldAlertIcon, CheckCircleIcon, RefreshIcon } from "../components/icons";
import { StatCard, NetraBadge, Panel, Loading, ErrorBanner } from "../components/ui";

interface PolicyWithStats {
  id: string;
  name: string;
  description: string | null;
  category: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  enabled: boolean;
  rule_type: string;
  rule_definition: Record<string, unknown>;
  totalDevices: number;
  passingCount: number;
  failingCount: number;
  unknownCount: number;
  score: number;
}

export function CompliancePage({ navigate }: { navigate: (page: string, param?: string) => void }) {
  const [scanning, setScanning] = useState(false);
  const [scanMessage, setScanMessage] = useState<string | null>(null);
  const [selectedPolicy, setSelectedPolicy] = useState<PolicyWithStats | null>(null);

  const policies = useAsync(() => api.policies(), []);
  const evaluations = useAsync(async () => {
    // Get all evaluations to compute per-policy stats
    const allEvals = await api.logs({ category: "policy_evaluation", limit: 1000 });
    return allEvals;
  }, [policies.data?.length]);

  const posture = useAsync(() => api.securityPosture(), []);

  const policiesWithStats = useMemo(() => {
    if (!policies.data) return [];
    
    // Build a map of policy_id -> evaluations from logs
    const evalMap = new Map<string, { pass: number; fail: number; unknown: number }>();
    if (evaluations.data) {
      for (const log of evaluations.data) {
        const details = log.details as Record<string, unknown> | undefined;
        const policyId = details?.policy_id as string | undefined;
        const result = details?.result as string | undefined;
        if (policyId && result) {
          const entry = evalMap.get(policyId) || { pass: 0, fail: 0, unknown: 0 };
          if (result === "pass") entry.pass++;
          else if (result === "fail") entry.fail++;
          else entry.unknown++;
          evalMap.set(policyId, entry);
        }
      }
    }

    return policies.data.map((policy) => {
      const evals = evalMap.get(policy.id) || { pass: 0, fail: 0, unknown: 0 };
      const total = evals.pass + evals.fail + evals.unknown;
      return {
        ...policy,
        totalDevices: total,
        passingCount: evals.pass,
        failingCount: evals.fail,
        unknownCount: evals.unknown,
        score: total > 0 ? Math.round((evals.pass / total) * 100) : 0,
      } as PolicyWithStats;
    });
  }, [policies.data, evaluations.data]);

  const overallStats = useMemo(() => {
    let totalPass = 0, totalFail = 0, totalUnknown = 0, totalEvals = 0;
    for (const p of policiesWithStats) {
      totalPass += p.passingCount;
      totalFail += p.failingCount;
      totalUnknown += p.unknownCount;
      totalEvals += p.totalDevices;
    }
    return {
      totalPolicies: policiesWithStats.length,
      totalPass,
      totalFail,
      totalUnknown,
      totalEvals,
      overallScore: totalEvals > 0 ? Math.round((totalPass / totalEvals) * 100) : 0,
    };
  }, [policiesWithStats]);

  const runScan = () => {
    setScanning(true);
    setScanMessage("Running automated compliance audit across all devices…");
    // Trigger evaluation for all policies
    Promise.all(policiesWithStats.map(p => api.evaluatePolicy(p.id).catch(() => null)))
      .then(() => {
        setScanning(false);
        setScanMessage("Compliance scan completed. Results are being processed.");
        evaluations.reload();
        policies.reload();
        posture.reload();
        setTimeout(() => setScanMessage(null), 5000);
      })
      .catch(() => {
        setScanning(false);
        setScanMessage("Compliance scan encountered errors.");
        setTimeout(() => setScanMessage(null), 5000);
      });
  };

  return (
    <div className="page-content">
      {policies.error && <ErrorBanner message={policies.error} />}
      {scanMessage && (
        <div style={{ background: "var(--brand-emerald-wash)", border: "1px solid var(--brand-emerald)", borderRadius: "var(--radius-control)", padding: "12px 18px", color: "var(--brand-emerald-light)", fontSize: "0.85rem", display: "flex", alignItems: "center", gap: "10px" }}>
          <CheckCircleIcon size={18} />
          <span>{scanMessage}</span>
        </div>
      )}

      <div className="kpi-grid-4">
        <StatCard
          label="Overall Compliance"
          value={overallStats.overallScore > 0 ? `${overallStats.overallScore}%` : "N/A"}
          icon={<ComplianceIcon size={20} />}
          iconTone="purple"
          indicators={overallStats.totalEvals > 0 ? [
            { text: `● Pass ${overallStats.totalPass}`, tone: "green", dot: true },
            { text: `● Fail ${overallStats.totalFail}`, tone: "red", dot: true },
            { text: `● Unknown ${overallStats.totalUnknown}`, tone: "blue", dot: true },
          ] : []}
        />
        <StatCard
          label="Policies Configured"
          value={overallStats.totalPolicies.toString()}
          icon={<CheckCircleIcon size={20} />}
          iconTone={overallStats.totalPolicies > 0 ? "green" : "amber"}
          indicators={[{ text: overallStats.totalPolicies > 0 ? "Active" : "Configure policies to begin", tone: overallStats.totalPolicies > 0 ? "green" : "amber", dot: true }]}
          onClick={() => navigate("policies")}
        />
        <StatCard
          label="Open Findings"
          value={posture.data?.findings?.open?.toString() ?? "0"}
          icon={<ShieldAlertIcon size={20} />}
          iconTone="red"
          indicators={[
            { text: `● Critical ${posture.data?.findings?.by_severity?.critical ?? 0}`, tone: "red", dot: true },
            { text: `● High ${posture.data?.findings?.by_severity?.high ?? 0}`, tone: "amber", dot: true },
          ]}
          onClick={() => navigate("findings")}
        />
        <StatCard
          label="Open Alerts"
          value={posture.data?.alerts?.new?.toString() ?? "0"}
          icon={<ShieldAlertIcon size={20} />}
          iconTone="amber"
          indicators={[
            { text: `● Critical ${posture.data?.alerts?.by_severity?.critical ?? 0}`, tone: "red", dot: true },
            { text: `● Warning ${(posture.data?.alerts?.by_severity?.high ?? 0) + (posture.data?.alerts?.by_severity?.medium ?? 0)}`, tone: "amber", dot: true },
          ]}
          onClick={() => navigate("alerts")}
        />
      </div>

      <div className="table-card">
        <div style={{ padding: "18px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--line)" }}>
          <div>
            <h2 style={{ fontSize: "1.05rem", fontWeight: "600", color: "#ffffff" }}>Security Policies</h2>
            <span style={{ fontSize: "0.75rem", color: "var(--ink-3)" }}>
              {policiesWithStats.length === 0 ? "No policies configured" : `${policiesWithStats.length} policies · Evaluated against live configuration backups`}
            </span>
          </div>
          <button
            className="btn btn-primary"
            onClick={runScan}
            disabled={scanning || policiesWithStats.length === 0}
          >
            <RefreshIcon size={14} className={scanning ? "spin" : ""} />
            <span>{scanning ? "Scanning…" : "Run Full Scan"}</span>
          </button>
        </div>

        <div className="table-responsive">
          <table className="netra-table">
            <thead>
              <tr>
                <th>Policy</th>
                <th>Category</th>
                <th>Severity</th>
                <th>Type</th>
                <th>Status</th>
                <th>Pass Ratio</th>
                <th>Score</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {policiesWithStats.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ textAlign: "center", padding: "48px", color: "var(--ink-3)" }}>
                    No security policies configured. <button className="link" onClick={() => navigate("policies")}>Create a policy</button> to begin compliance evaluation.
                  </td>
                </tr>
              ) : policiesWithStats.map((policy) => (
                <tr key={policy.id}>
                  <td className="table-time">{policy.name}</td>
                  <td>
                    <strong style={{ color: "#ffffff" }}>{policy.name}</strong>
                    <br />
                    <small style={{ color: "var(--ink-3)" }}>{policy.category}</small>
                  </td>
                  <td>
                    <NetraBadge type={policy.severity === "critical" ? "critical" : policy.severity === "high" || policy.severity === "medium" ? "warning" : "info"} />
                  </td>
                  <td>
                    <span className="badge info">{policy.rule_type.replace(/_/g, " ")}</span>
                  </td>
                  <td>
                    <NetraBadge type={policy.enabled ? "new" : "resolved"} />
                  </td>
                  <td>
                    <span style={{ fontFamily: "var(--font-mono)", color: policy.passingCount < policy.totalDevices && policy.totalDevices > 0 ? "var(--warn-light)" : "var(--brand-emerald-light)" }}>
                      {policy.passingCount} / {policy.totalDevices} devices
                    </span>
                  </td>
                  <td>
                    <span className="ai-score-pill">{policy.score}%</span>
                  </td>
                  <td>
                    <button
                      className="btn btn-ghost"
                      style={{ padding: "4px 10px", fontSize: "0.76rem" }}
                      onClick={() => setSelectedPolicy(policy)}
                    >
                      Details
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {selectedPolicy && (
        <div className="modal-backdrop" onClick={() => setSelectedPolicy(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Policy Details: {selectedPolicy.name}</h3>
              <button className="action-icon-btn" onClick={() => setSelectedPolicy(null)}>✕</button>
            </div>
            <div className="modal-body">
              <div>
                <strong style={{ color: "#ffffff", fontSize: "0.95rem" }}>{selectedPolicy.name}</strong>
                <p style={{ color: "var(--ink-2)", fontSize: "0.82rem", marginTop: "4px" }}>
                  Category: <strong>{selectedPolicy.category}</strong> • Severity: <strong>{selectedPolicy.severity}</strong> • Type: <strong>{selectedPolicy.rule_type.replace(/_/g, " ")}</strong>
                </p>
                {selectedPolicy.description && (
                  <p style={{ color: "var(--ink-2)", fontSize: "0.82rem", marginTop: "8px" }}>
                    {selectedPolicy.description}
                  </p>
                )}
              </div>
              <div style={{ background: "rgba(255,255,255,0.03)", border: "1px solid var(--line)", borderRadius: "var(--radius-control)", padding: "14px", marginTop: "16px" }}>
                <span style={{ fontSize: "0.72rem", color: "var(--ink-3)", textTransform: "uppercase", fontWeight: "600" }}>Evaluation Results</span>
                <div style={{ display: "flex", gap: "24px", marginTop: "8px", flexWrap: "wrap" }}>
                  <div style={{ color: "var(--brand-emerald-light)" }}>
                    <strong>{selectedPolicy.passingCount}</strong> Passing
                  </div>
                  <div style={{ color: "var(--crit-light)" }}>
                    <strong>{selectedPolicy.failingCount}</strong> Failing
                  </div>
                  <div style={{ color: "var(--ink-3)" }}>
                    <strong>{selectedPolicy.unknownCount}</strong> Unknown
                  </div>
                  <div style={{ color: "var(--ai-purple-light)" }}>
                    <strong>{selectedPolicy.score}%</strong> Score
                  </div>
                </div>
              </div>
              <div style={{ marginTop: "16px" }}>
                <span style={{ fontSize: "0.75rem", color: "var(--ink-3)" }}>Rule Definition</span>
                <pre style={{ background: "#0a1018", border: "1px solid var(--line)", borderRadius: "var(--radius-control)", padding: "12px", marginTop: "8px", fontSize: "0.72rem", color: "var(--ink-2)", overflow: "auto", maxHeight: "200px" }}>
                  {JSON.stringify(selectedPolicy.rule_definition, null, 2)}
                </pre>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setSelectedPolicy(null)}>Close</button>
              <button className="btn btn-primary" onClick={() => { setSelectedPolicy(null); runScan(); }}>Re-evaluate</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}