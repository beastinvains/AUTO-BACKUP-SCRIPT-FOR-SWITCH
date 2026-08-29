import { useState, useMemo } from "react";
import { api } from "../api";
import { useAsync } from "../hooks";
import type { Policy, PolicyInput } from "../types";
import { PoliciesIcon, ShieldAlertIcon, CheckCircleIcon, PlusIcon } from "../components/icons";
import { StatCard, NetraBadge, Modal, Loading, ErrorBanner } from "../components/ui";

export function PoliciesPage({ navigate }: { navigate: (page: string, param?: string) => void }) {
  const [addingPolicy, setAddingPolicy] = useState(false);
  const [selectedPolicy, setSelectedPolicy] = useState<Policy | null>(null);

  const state = useAsync(async () => {
    return await api.policies();
  }, []);

  const handleCreatePolicy = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const ruleDefRaw = formData.get("rule_definition") as string;
    
    let ruleDef = {};
    try {
      ruleDef = JSON.parse(ruleDefRaw);
    } catch {
      alert("Invalid JSON for Rule Definition");
      return;
    }

    const payload: PolicyInput = {
      name: formData.get("name") as string,
      description: formData.get("description") as string,
      category: formData.get("category") as string,
      severity: formData.get("severity") as Policy["severity"],
      vendor_scope: (formData.get("vendor_scope") as string).split(",").map(s => s.trim()).filter(Boolean),
      device_type_scope: (formData.get("device_type_scope") as string).split(",").map(s => s.trim()).filter(Boolean),
      rule_type: formData.get("rule_type") as Policy["rule_type"],
      rule_definition: ruleDef,
      enabled: formData.get("enabled") === "on",
    };

    try {
      await api.createPolicy(payload);
      setAddingPolicy(false);
      state.reload();
    } catch (err: any) {
      alert(`Error creating policy: ${err.message}`);
    }
  };

  const handleEvaluate = async (policyId: string) => {
    try {
      await api.evaluatePolicy(policyId);
      alert("Evaluation triggered in background.");
    } catch (err: any) {
      alert(`Error triggering evaluation: ${err.message}`);
    }
  };

  const handleDelete = async (policyId: string) => {
    if (!window.confirm("Delete this policy?")) return;
    try {
      await api.deletePolicy(policyId);
      setSelectedPolicy(null);
      state.reload();
    } catch (err: any) {
      alert(`Error deleting policy: ${err.message}`);
    }
  };

  const policies = state.data ?? [];
  const enabledCount = policies.filter(p => p.enabled).length;

  return (
    <div className="page-content">
      {state.error && <ErrorBanner message={state.error} />}
      {state.loading && <Loading what="policies" />}

      {!state.loading && (
        <>
          <div className="kpi-grid-4">
            <StatCard
              label="Active Policies"
              value={enabledCount}
              icon={<PoliciesIcon size={20} />}
              iconTone="green"
              indicators={[{ text: `● ${policies.length - enabledCount} Disabled`, tone: "amber", dot: true }]}
            />
            <StatCard
              label="Policy Engine"
              value="Running"
              icon={<CheckCircleIcon size={20} />}
              iconTone="blue"
              indicators={[{ text: "Deterministic rules", tone: "blue" }]}
            />
          </div>

          <div className="table-card">
            <div style={{ padding: "18px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--line)" }}>
              <div>
                <h2 style={{ fontSize: "1.05rem", fontWeight: "600", color: "#ffffff" }}>Security Policies</h2>
                <span style={{ fontSize: "0.75rem", color: "var(--ink-3)" }}>Deterministic rules evaluated against configuration and telemetry</span>
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
                    <th>Name</th>
                    <th>Category</th>
                    <th>Severity</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {policies.map((p) => (
                    <tr key={p.id} style={{ opacity: p.enabled ? 1 : 0.6 }}>
                      <td>
                        <strong style={{ color: "#ffffff" }}>{p.name}</strong>
                        <br />
                        <small style={{ color: "var(--ink-3)", display: "block", maxWidth: 400, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{p.description}</small>
                      </td>
                      <td>{p.category.replace(/_/g, " ")}</td>
                      <td><NetraBadge type={p.severity === "critical" ? "critical" : p.severity === "high" || p.severity === "medium" ? "warning" : "info"} /></td>
                      <td>{p.rule_type}</td>
                      <td>
                        <span className={`badge ${p.enabled ? "resolved" : "info"}`}>
                          {p.enabled ? "Enabled" : "Disabled"}
                        </span>
                      </td>
                      <td>
                        <button
                          className="btn btn-ghost"
                          style={{ padding: "4px 10px", fontSize: "0.76rem" }}
                          onClick={() => setSelectedPolicy(p)}
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                  {policies.length === 0 && (
                    <tr>
                       <td colSpan={6} style={{ textAlign: "center", padding: "32px", color: "var(--ink-3)" }}>
                         No policies defined
                       </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {selectedPolicy && (
        <Modal title={`Policy: ${selectedPolicy.name}`} onClose={() => setSelectedPolicy(null)}>
          <div style={{ display: "flex", flexDirection: "column", gap: "14px", width: "500px", maxWidth: "90vw" }}>
            <p style={{ color: "var(--ink-2)", fontSize: "0.9rem" }}>{selectedPolicy.description}</p>
            
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
              <div style={{ background: "rgba(255,255,255,0.03)", padding: "12px", borderRadius: "8px", border: "1px solid var(--line)" }}>
                <div style={{ fontSize: "0.75rem", color: "var(--ink-3)", marginBottom: 4 }}>Rule Type</div>
                <div style={{ fontSize: "0.9rem", color: "var(--ink)" }}>{selectedPolicy.rule_type}</div>
              </div>
              <div style={{ background: "rgba(255,255,255,0.03)", padding: "12px", borderRadius: "8px", border: "1px solid var(--line)" }}>
                <div style={{ fontSize: "0.75rem", color: "var(--ink-3)", marginBottom: 4 }}>Severity</div>
                <div style={{ fontSize: "0.9rem", color: "var(--ink)", textTransform: "capitalize" }}>{selectedPolicy.severity}</div>
              </div>
            </div>

            <div style={{ background: "rgba(255,255,255,0.03)", padding: "12px", borderRadius: "8px", border: "1px solid var(--line)" }}>
               <div style={{ fontSize: "0.75rem", color: "var(--ink-3)", marginBottom: 8 }}>Rule Definition</div>
               <pre style={{ fontSize: "0.8rem", color: "var(--ink-2)", margin: 0, whiteSpace: "pre-wrap", background: "rgba(0,0,0,0.2)", padding: 8, borderRadius: 4 }}>
                 {JSON.stringify(selectedPolicy.rule_definition, null, 2)}
               </pre>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "10px" }}>
              <div>
                 <button className="btn btn-ghost" style={{ color: "var(--crit)" }} onClick={() => handleDelete(selectedPolicy.id)}>Delete</button>
              </div>
              <div style={{ display: "flex", gap: "10px" }}>
                <button className="btn btn-ghost" onClick={() => setSelectedPolicy(null)}>Close</button>
                <button className="btn btn-primary" onClick={() => handleEvaluate(selectedPolicy.id)}>Run Evaluation</button>
              </div>
            </div>
          </div>
        </Modal>
      )}

      {addingPolicy && (
        <Modal title="Create Security Policy" onClose={() => setAddingPolicy(false)}>
          <form onSubmit={handleCreatePolicy} style={{ display: "flex", flexDirection: "column", gap: "14px", width: "500px", maxWidth: "90vw" }}>
            <div className="form-group">
              <label>Policy Name</label>
              <input name="name" className="form-input" placeholder="e.g. Telnet Disabled" required />
            </div>
            <div className="form-group">
              <label>Description</label>
              <textarea name="description" className="form-input" rows={2} required />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
              <div className="form-group">
                <label>Category</label>
                <input name="category" className="form-input" placeholder="e.g. access_control" defaultValue="access_control" required />
              </div>
              <div className="form-group">
                <label>Severity</label>
                <select name="severity" className="filter-select">
                  <option value="critical">Critical</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                  <option value="info">Info</option>
                </select>
              </div>
            </div>
            <div className="form-group">
              <label>Rule Type</label>
              <select name="rule_type" className="filter-select">
                <option value="config_pattern">Config Pattern</option>
                <option value="telemetry_threshold">Telemetry Threshold</option>
                <option value="service_check">Service Check</option>
                <option value="interface_check">Interface Check</option>
              </select>
            </div>
            <div className="form-group">
              <label>Rule Definition (JSON)</label>
              <textarea name="rule_definition" className="form-input" rows={4} defaultValue='{"pattern": "set system services telnet", "match_means": "fail"}' required style={{ fontFamily: "monospace" }} />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
              <div className="form-group">
                <label>Vendor Scope (comma separated)</label>
                <input name="vendor_scope" className="form-input" placeholder="e.g. Juniper, Cisco (leave blank for all)" />
              </div>
              <div className="form-group">
                <label>Device Type Scope</label>
                <input name="device_type_scope" className="form-input" placeholder="e.g. router, switch (leave blank for all)" />
              </div>
            </div>
            <div className="form-group" style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
               <input type="checkbox" name="enabled" id="enabled-chk" defaultChecked />
               <label htmlFor="enabled-chk" style={{ marginBottom: 0 }}>Enabled</label>
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
