# Phase 4 — Continuous Security Monitoring, Policy Engine, and Findings Management

## Delivered Scope

Phase 4 extends the core infrastructure inventory, configuration backup, and network topology services by introducing continuous security monitoring, configuration drift detection, automated policy evaluation, compliance evidence gathering, and security findings lifecycle management.

All frontend components have been updated to transition from static/mock stubs to real, live data fetched via backend API singletons (`api.alerts()`, `api.policies()`, `api.findings()`, `api.evidence()`).

---

## Technical Architecture & Core Modules

1. **Continuous Monitoring Collector (`monitoring/collectors.py`, `monitoring/service.py`)**
   - Periodically samples device security posture, configuration state changes, and hardware metrics.
   - Evaluates collected telemetry against operational threshold baselines.

2. **Policy & Rule Engine (`policy/engine.py`, `policy/service.py`, `policy/seed_policies.py`)**
   - Rules-based engine evaluating running configuration states and system parameters.
   - Triggers automated policy violations when drift or unauthorized configurations occur.

3. **Findings & Compliance Management (`findings/service.py`, `evidence/service.py`)**
   - Aggregates active security findings across discovered devices.
   - Provides lifecycle controls for suppressing, acknowledging, and resolving security findings.
   - Generates compliance audit evidence packages.

4. **Web UI Integration (`frontend/src/pages/`)**
   - `AlertsPage.tsx`: Data-driven alert monitoring connected to backend alert feeds with acknowledge/resolve actions.
   - `PoliciesPage.tsx`: Rule configuration view with on-demand background execution, custom rule creation, and deletion.
   - `FindingsPage.tsx`: Active security finding dashboard supporting suppression, resolution, and compliance audit exports.

---

## API Surface & Endpoints

| Endpoint | Methods | Description |
| --- | --- | --- |
| `/api/alerts` | `GET`, `POST` | List security alerts and perform alert lifecycle status updates |
| `/api/policies` | `GET`, `POST`, `DELETE` | List active policy rules, trigger engine execution, create/delete rules |
| `/api/findings` | `GET`, `POST` | Query active security findings, update finding states (suppress/resolve) |
| `/api/evidence` | `GET`, `POST` | Retrieve generated compliance evidence artifacts |

---

## Verification & Validation Workflow

To execute full end-to-end verification of Phase 4 continuous monitoring and findings integration:

### Execution Checklist

1. **Start Mock Juniper Lab:**
   ```bash
   python tests/mock_lab.py --host 0.0.0.0
   ```
2. **Discover Lab Devices:**
   ```bash
   .venv/bin/python scripts/lab_setup.py --host 127.0.0.1
   ```
3. **Execute Security Monitoring & Policy Evaluation:**
   ```bash
   .venv/bin/python -m unittest discover -s tests -p "test_phase4_*.py"
   ```
4. **Verify Live Database Records:**
   Ensure database tables (`security_findings`, `alerts`, `policy_rules`, `compliance_evidence`) are populated with real monitoring output.
5. **UI Verification:**
   Launch Vite dev server (`npm run dev` in `frontend/`) and verify populated rows across `#/alerts`, `#/policies`, and `#/findings`.
