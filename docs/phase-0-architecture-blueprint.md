# Phase 0 Architecture Blueprint

## 1. High-level architecture

The platform is a modular control plane: it gathers and normalizes infrastructure facts, provides role-aware views, makes bounded recommendations, and executes only human-approved action plans. AI never gets an unrestricted device shell.

    React dashboard -> FastAPI API / identity / RBAC -> core domain services
                                                       |-> discovery workers -> vendor adapters -> devices/APIs
                                                       |-> PostgreSQL + encrypted object backup storage
                                                       |-> controlled AI service using read-only structured tools

Begin as a modular monolith with isolated workers: practical for SIH, yet service boundaries can later be extracted. The existing SSH backup application becomes a Phase 2 source: migrate device access and backup behavior behind adapter/configuration boundaries rather than expanding backup.py.

## 2. Module responsibilities

| Module | Responsible for | Must not be responsible for |
|---|---|---|
| Frontend/dashboard | Role-aware views, input, topology graph and approvals | Device access, secrets or browser-only policy |
| Backend API | Validation, auth boundary and domain orchestration | Vendor commands or long-running device jobs |
| Discovery | Scheduled probes, evidence collection, normalization | Credentials, UI, configuration changes |
| Vendor adapters | Protocols, parsing and vendor action templates | Approvals, database/UI logic, LLM prompting |
| Inventory/topology | Assets, capabilities and graph reconciliation | Treating unverified neighbor reports as truth |
| Monitoring | Collection, metrics and threshold events | Changes or unsupported root-cause claims |
| Configuration/backup | Immutable snapshots, hashes, versions, diffs and retention | Unapproved restore execution |
| Drift/risk/recommendations | Policies and explainable recommendations | Approval or execution |
| AI/ML | Read-only analysis, explanation and bounded suggestions | Direct device connectivity or arbitrary commands |
| Automation | Typed-plan validation, execution, verification, rollback | Inventing commands or bypassing approval |
| Approval/audit | Decision history and immutable evidence | Credentials or authorization replacement |
| Identity | Authentication and RBAC/ABAC | Device secret storage |
| Database/object storage | Metadata / encrypted artifacts | Vendor-specific logic |

## 3. Device abstraction design

Canonical Device fields: id, name, type, vendor, model, platform, os_version, management_ip, credentials_reference_id, capabilities, status, site, discovery_state, last_seen_at, evidence and confidence. Controlled types include switch, router, firewall, load balancer, server, hypervisor, virtual machine and other. Services are separate nodes, allowing a host to run multiple services.

BaseDeviceAdapter receives a just-in-time credential handle and returns typed normalized results plus raw evidence. JuniperAdapter owns Junos details; CiscoAdapter owns IOS/IOS-XE details. Core code contains neither vendor command syntax nor parser specifics.

| Common operation | Constraint |
|---|---|
| discover | Safe fingerprint/protocol evidence |
| get_device_info; get_health | Normalized facts and timestamps |
| get_interfaces; get_neighbors | Interfaces and evidenced neighbor observations |
| get_configuration; backup_configuration | Snapshot and parser/version metadata |
| validate_configuration | Syntax, policy and precondition assessment only |
| execute_action | Only an approved, prevalidated typed action-plan step |

Capability discovery determines eligible operations. Unsupported operations return explicit unsupported results, never guessed commands.

## 4. Discovery architecture

Jobs progress through seed inventory/ranges, reachability, safe fingerprint, adapter selection, collection, normalization, reconciliation and event publication. Allowlists, per-site concurrency and rate limits prevent disruptive scanning.

| Asset | Sources | Normalized outcome |
|---|---|---|
| Network devices | SSH, SNMP, LLDP/CDP, approved vendor APIs | Physical device, interfaces, capabilities and topology evidence |
| Virtual infrastructure | Hypervisor APIs | Hypervisor, VM and host/VM edges |
| Servers | Agent, OS API or constrained SSH | Server and hosted-service facts |
| Applications/services | Agent, registry or approved probes | Service, endpoint and dependencies |

Normalization uses a versioned schema, retains source/timestamp/raw evidence, and resolves identity by stable serial/UUID before controlled fingerprints. It distinguishes Physical Device, Virtual Device and Software/Service. Conflicting observations remain reviewable; weak discovery cannot overwrite trusted manual facts.

## 5. Topology model

Store an evidenced property graph transactionally in PostgreSQL. Each topology relationship has source_node_id, target_node_id, relationship_type, source_interface_id, target_interface_id, status, confidence, evidence_source, observed_at and a validity interval. Types include connected_to, hosted_on, runs, depends_on, routes_to, balances_to and protects.

Physical links are interface-aware; logical dependency links are directed. Reconciliation deduplicates observations and increases confidence only through corroboration. The API returns graph slices by site, device, depth and time for interactive rendering with React Flow or Cytoscape.js.

## 6. Database/entity model

PostgreSQL contains transactional metadata; encrypted versioned object storage contains configuration artifacts and large raw payloads by hash.

| Entity | Purpose / important fields | Relationships |
|---|---|---|
| users, roles | Identity, external subject, active state and permission bundles | Users-to-roles; approvals/audits |
| devices | Canonical device fields | Credential refs, capabilities, interfaces, configs |
| device_credentials_reference | Vault path/key, allowed scope, rotation state; no secret value | Device |
| device_capabilities, interfaces | Capability evidence; port, MAC, addresses, operational state | Device; topology endpoints |
| topology_relationships | Evidenced time-bound graph edge | Two nodes/interfaces |
| configurations, configuration_versions | Stream; immutable hash, artifact URI, parent/diff, restore eligibility | Device; action/audit |
| metrics | Subject, timestamp, metric/value/unit/labels, source | Device/interface/service |
| services, virtual_machines | Endpoint/owner; VM UUID, guest OS, power state | Host/VM/service dependencies |
| events, alerts, anomalies | Observations; actionable lifecycle; detector/score/evidence | Assets and each other |
| risk_scores, recommendations | Factors/policy/version/expiry; rationale/status | Actions and evidence |
| automation_actions, approvals | Typed plan/results/state; decision/scope/expiry | Configs, approvals, audit |
| audit_logs | Append-only actor/action/resource/correlation/before-after hash | All sensitive resources |

Use UUIDs, UTC timestamps, foreign keys, state constraints, tenant/site scope where applicable and a transactional outbox for worker events.

## 7. AI architecture

AI sees only scoped, read-only structured inventory, topology slices, normalized config diffs, telemetry aggregates, alerts, policies and sanitized audit context. Its service enforces tenant filters, schemas, tool allowlists and citations.

| Capability | Primary approach |
|---|---|
| Configuration drift | Deterministic normalized diff/policy rules; LLM explains impact |
| Anomaly detection | Threshold/seasonality first, then evaluated scikit-learn |
| Risk scoring | Explainable weighted rules initially |
| Root cause | Evidence graph/correlation rules; LLM summarizes hypotheses |
| Natural language | LLM maps requests to approved read-only queries |
| Recommendations/automation | Policy/templates and LLM rationale, never executable free text |

Never send secrets or raw terminal output to prompts. Show provenance and uncertainty, evaluate using fixtures, and retain a deterministic experience if the LLM is unavailable.

## 8. Automation safety workflow

    User request -> intent parsing -> target/scope resolution -> adapter action template
     -> static/device preflight validation -> policy/risk assessment -> human approval
     -> just-in-time credential execution -> post-change verification -> backup -> audit

An action is a typed plan, not a command string: allowed type, targets, pre/postconditions, idempotency key, rollback plan, artifact hashes, expiry and risk. Require dual control for high-risk production work; requesters cannot self-approve. Lock conflicting changes, revalidate at execution, and stop remaining steps on failed verification. Rollback is prevalidated and follows the same approval policy except defined emergency procedures.

## 9. Complete folder structure

    frontend/       React screens, graph components, API client
    backend/        FastAPI composition, routes, workers
    core/           Domain models, ports, policies, errors
    adapters/       Base and Juniper/Cisco/platform adapters
    discovery/      Jobs, probes, normalization, reconciliation
    inventory/      Asset and capability lifecycle
    topology/       Graph services and queries
    monitoring/     Collectors, metrics, alerts
    configuration/  Snapshots, versions, diffs, drift, retention
    backup/         Storage abstraction and backup orchestration
    ai/             Controlled tools, prompts, ML and evaluation
    automation/     Plans, validators, executor, rollback
    identity/       Authentication and authorization
    audit/          Append-only audit/event publishing
    database/       Repositories, ORM and migrations
    storage/        Object-storage and encryption implementations
    config/         Typed settings, policy files, environment templates
    docs/           Architecture, ADRs, runbooks, threat model
    tests/          Unit, contract, integration and security fixtures
    scripts/ infra/ Local scripts; Docker/deployment/CI
    logs/ data/     Ignored local runtime output and fixtures

Root files include README.md, .env.example, .gitignore, dependency manifests and development/container configuration. Production secrets belong in a secret manager; local .env, backups, logs, reports and raw discovered data remain ignored.

## 10. Frontend screen structure

| Screen | User sees |
|---|---|
| Login | SSO/local sign-in, MFA and access notice |
| Overview dashboard | Asset/health totals, alerts, drift, approvals and jobs |
| Infrastructure map | Searchable graph with health/confidence overlays |
| Devices / device details | Inventory; identity, interfaces, health, neighbors, configs and permitted actions |
| Topology | Full/sliced graph, path/dependency and evidence inspector |
| Alerts | Prioritized queue, correlation, acknowledgement and assignment |
| Configuration history / backups | Versions, visual diffs, baselines, retention and artifact status |
| AI assistant | Scoped questions, cited sources and uncertainty; no execution |
| Recommendations | Ranked proposals, factors/evidence and reviewed plan creation |
| Automation / approval | Plan, validation/risk/rollback, decisions and live execution |
| Audit logs | Searchable tamper-evident timeline |
| Settings | Sites, integrations, policies, roles, schedules and retention |

## 11. Security architecture

Use OIDC/OAuth2 and MFA, short-lived tokens, separate service identities, server-side default-deny RBAC/ABAC, validated APIs and rate limits. Store device secrets only in a vault and pass short-lived references to workers. Encrypt database/artifacts at rest, use TLS in transit, rotate secrets/keys, redact logs and enforce least privilege.

Segment worker networks, allowlist discovery targets, validate adapter actions against typed schemas/policy, maintain integrity-protected append-only audit logs, run dependency/secret scanning in CI, test restores and threat-model automation before enabling it.

## 12. Recommended technology stack

| Area | Choice | Why |
|---|---|---|
| Backend | Python + FastAPI | Matches existing project; typed and async-friendly |
| Network automation | Netmiko initially | Mature Juniper/Cisco SSH hidden behind adapters |
| Jobs | Redis-backed queue selected in Phase 1 | Isolates slow device work from API |
| Data | PostgreSQL + SQLAlchemy/Alembic | Strong relations, JSON metadata and migrations |
| Artifacts | S3-compatible encrypted storage | Durable versioned configuration backups |
| Frontend/topology | React + TypeScript; Cytoscape.js or React Flow | Team-friendly dashboard and graph |
| ML/AI | scikit-learn; LLM via controlled service | Explainable baseline plus safe natural language |
| Delivery | Docker Compose locally, Docker images | Repeatable without premature Kubernetes |

## 13. Development roadmap

| Phase | Goal | Inputs | Outputs | Dependencies |
|---|---|---|---|---|
| 0 | Blueprint | Existing backup app | Architecture, ADRs, threat model | None |
| 1 | Inventory + Juniper discovery | Seeds, vault references | Inventory, Juniper adapter, jobs | 0 |
| 2 | Backup/versioning | Adapter, object storage | Snapshots, hashes, diffs/history | 1 |
| 3 | Topology visualization | Interfaces/neighbors | Graph model/map | 1 |
| 4 | Cisco adapter | Cisco lab devices | Contract-tested Cisco support | 1-2 |
| 5 | Server/VM discovery | APIs/agents | Server/VM/service inventory | 1 |
| 6 | Monitoring/telemetry | Managed assets | Metrics/events/alerts | 1, 5 |
| 7 | Drift detection | Versioned configs | Baselines/drift alerts | 2 |
| 8 | ML anomaly detection | Historical metrics | Evaluated detector | 6 |
| 9 | AI assistant/recommendations | Read models/policies/evals | Scoped cited AI UX | 3, 6-8 |
| 10 | Human-approved automation | Typed adapters/policies | Verified rollback-capable actions | 2, 4, 7, 9 |
| 11 | Testing, security, SIH demo | Prototype | Test evidence and reliable demo | Intended scope |

## 14. Important architectural decisions

1. Modular monolith first; workers isolate I/O and preserve service-extraction paths.
2. Vendor details live only in capability-based adapters.
3. Discovery produces confidence-rated evidence, not unquestioned facts.
4. PostgreSQL is metadata authority; artifacts are immutable encrypted objects.
5. Actions are typed, hashed, expiring plans—not AI-generated command strings.
6. Rules precede ML/LLM for control decisions; AI is read-only by default.
7. Approval, verification, snapshot and audit are one workflow.
8. Secrets are references only, never source, logs, UI responses or prompts.
9. Contract tests use captured/simulated vendor responses.
10. Deliver a Juniper vertical slice before Cisco and broader asset types.

## 15. Potential risks and mitigations

| Risk | Avoidance |
|---|---|
| Vendor differences | Capability adapters, fixtures, contract tests and lab validation |
| Incorrect topology | Evidence/confidence, reconciliation and explicit unknown state |
| Automation outage | Allowlisted plans, dry runs, approvals, locks, windows, verification/rollback |
| Credential exposure | Vault, redaction, least privilege, rotation and secret scanning |
| Hallucination/prompt injection | Structured read-only tools, validation, citations and no direct execution |
| Data growth | Retention/downsampling and object storage |
| Student-team scope creep | Vertical slices; defer microservices, advanced ML and orchestration |
| Demo reliability | Mock devices, deterministic fixtures, offline data and rehearsal |
| Migration disruption | Keep current backup app operational; migrate one concern at a time |
