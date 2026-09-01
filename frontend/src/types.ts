/** Response shapes returned by the FastAPI backend. Kept in step with backend/app.py. */

export type Role = "admin" | "operator" | "viewer";
export type SessionIdentity = { role: Role; actor: string };

export type Device = {
  id: string;
  name: string;
  type: string;
  vendor: string | null;
  model: string | null;
  platform: string | null;
  os_version: string | null;
  serial_number: string | null;
  management_ip: string;
  management_port: number;
  credentials_reference_id: string;
  capabilities: string[];
  status: string;
  site: string | null;
  discovery_state: string;
  last_seen_at: string | null;
  confidence: number;
};

/** Device row plus the metadata counts the drawer needs. Never includes configuration text. */
export type DeviceSummary = Device & {
  interface_count: number;
  neighbor_count: number;
  configuration_version_count: number;
  last_backup_at: string | null;
  last_discovery_at: string | null;
};

/** Add/Edit Device form payload. The credential reference is a profile name, never a secret. */
export type DeviceInput = {
  name: string;
  management_ip: string;
  management_port: number;
  credentials_reference_id: string;
  type: string;
  vendor: string | null;
  site: string | null;
};

export type Interface = {
  id: number;
  device_id: string;
  name: string;
  admin_state: string;
  operational_state: string;
  addresses: string[];
  description: string | null;
  speed: string | null;
};

export type Neighbor = {
  local_interface: string;
  remote_system_name: string | null;
  remote_interface: string | null;
  remote_chassis_id: string | null;
};

/** A neighbour annotated with the inventory device it was correlated to, if any. */
export type ResolvedNeighbor = Neighbor & {
  resolved_device_id: string | null;
  resolved_device_name: string | null;
  managed: boolean;
};

export type Health = {
  device_id: string;
  cpu_percent: number | null;
  memory_percent: number | null;
  uptime: string | null;
  hardware_status: string;
  temperature_c: number | null;
  fan_speed_rpm: number | null;
  power_supplies: { name: string; status: string }[];
  cluster_members: string[];
};

export type Configuration = {
  version_id: string;
  parent_version_id: string | null;
  timestamp: string;
  sha256: string;
  size_bytes: number;
  status: string;
  retention_state: string;
};

export type ConfigurationContent = { version_id: string; sha256: string; content: string };

export type Diff = {
  lines: { kind: "added" | "removed" | "unchanged"; text: string }[];
  summary: { added: number; removed: number; unchanged: number };
  added: string[];
  removed: string[];
};

export type BackupResult = {
  device_id: string;
  device: string;
  status: "SUCCESS" | "FAILED";
  version_id?: string;
  sha256?: string;
  change_status?: "CONFIGURATION_CHANGED" | "NO_CHANGE";
  error_category?: string;
  duration_seconds: number;
};

export type BackupJob = {
  job_id: string;
  requested_by: string;
  target_scope: string[];
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  status: string;
  success_count: number;
  failure_count: number;
  results: BackupResult[];
};

export type TopologyObservation = {
  reported_by: string;
  reported_by_id: string;
  local_interface: string;
  remote_interface: string | null;
  remote_system_name: string | null;
  remote_chassis_id: string | null;
  source: string;
};

export type TopologyNode = {
  id: string;
  kind: "device" | "external";
  managed: boolean;
  hostname: string;
  type: string;
  vendor: string | null;
  model: string | null;
  platform: string | null;
  os_version: string | null;
  management_ip: string | null;
  serial_number: string | null;
  status: string;
  site: string | null;
  discovery_state: string;
  confidence: number;
  last_seen_at: string | null;
  last_backup_at: string | null;
  interface_count: number;
  neighbor_count: number;
  degree: number;
  chassis_id?: string | null;
  observed_by?: string[];
};

export type TopologyEdge = {
  id: string;
  source: string;
  target: string;
  relationship_type: string;
  source_interface: string | null;
  target_interface: string | null;
  confidence: number;
  interface_evidence: "complete" | "partial";
  corroborated: boolean;
  evidence: { source: string; observations: TopologyObservation[] };
};

export type TopologyStats = {
  device_count: number;
  infrastructure_device_count: number;
  end_device_count: number;
  external_count: number;
  node_count: number;
  edge_count: number;
  corroborated_edges: number;
  unresolved_neighbors: number;
  insufficient_evidence: number;
  ambiguous_identities: string[];
};

export type TopologyFilterOptions = {
  sites: string[];
  vendors: string[];
  types: string[];
  statuses: string[];
};

export type Graph = {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
  stats: TopologyStats;
  filters: TopologyFilterOptions;
};

export type TopologyFilters = {
  site?: string;
  vendor?: string;
  device_type?: string;
  status?: string;
  show_end_devices?: boolean;
};

export type DeviceSlice = {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
  stats: { node_count: number; edge_count: number };
};

export type Schedule = {
  id: string;
  name: string;
  frequency: "hourly" | "daily" | "weekly";
  run_at: string;
  day_of_week: number | null;
  cadence: string;
  enabled: boolean;
  device_ids: string[];
  device_names: string[];
  scope: string;
  next_run_at: string | null;
  last_run_at: string | null;
  last_status: string | null;
  last_job_id: string | null;
  created_at: string;
  created_by: string;
  updated_at: string | null;
};

export type ScheduleInput = {
  name: string;
  frequency: "hourly" | "daily" | "weekly";
  run_at: string;
  day_of_week: number | null;
  device_ids: string[];
  enabled: boolean;
};

export type AppSettings = {
  backup_time: string;
  backup_directory: string;
  max_workers: number;
  retention_days: number;
};

export type LogEvent = {
  id: string;
  timestamp: string | null;
  category: string;
  event: string;
  actor: string;
  status: string;
  device_id: string | null;
  device: string | null;
  resource_type: string;
  resource_id: string;
  correlation_id: string;
  summary: string;
  details: Record<string, unknown>;
};

export type LogFilters = {
  start?: string;
  end?: string;
  device_id?: string;
  category?: string;
  status?: string;
  search?: string;
  limit?: number;
};

export type LogOptions = {
  categories: string[];
  statuses: string[];
  devices: { id: string; name: string }[];
};

export type Dashboard = {
  generated_at: string;
  infrastructure: {
    total_devices: number;
    online: number;
    offline: number;
    degraded: number;
    unknown: number;
    by_vendor: Record<string, number>;
  };
  topology: {
    nodes: number;
    devices: number;
    connections: number;
    corroborated_connections: number;
    unresolved_neighbors: number;
    external_nodes: number;
    ambiguous_identities: number;
  };
  backup: {
    last_successful_backup: string | null;
    failed_jobs: number;
    devices_never_backed_up: number;
    devices_stale_backup: number;
    stale_threshold_days: number;
    total_jobs: number;
  };
  discovery: {
    last_discovery: string | null;
    failed_discoveries: number;
    pending_devices: number;
  };
  schedules: { total: number; enabled: number; next_run_at: string | null };
  security_posture: SecurityPosture | null;
};

export type SchedulerStatus = { running: boolean; tick_seconds: number; due_now: number };

export type DiscoveryJob = {
  job_id: string;
  status: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  results: { target: string; status: string; device_id: string | null; error: string | null }[];
};

// ---------------------------------------------------------------------------
// Phase 4 — Security Monitoring, Policy Engine, Findings, Alerts, Evidence
// ---------------------------------------------------------------------------

export type TelemetryRecord = {
  id: string;
  device_id: string;
  collection_job_id: string;
  collected_at: string;
  cpu_percent: number | null;
  memory_percent: number | null;
  temperature_c: number | null;
  fan_speed_rpm: number | null;
  power_status: string | null;
  reachability: "online" | "timeout" | "error" | "unknown" | "not_collected";
  interface_summary: { total?: number; up?: number; down?: number };
};

export type ServiceObservation = {
  id: string;
  device_id: string;
  observed_at: string;
  port: number;
  protocol: string;
  service_name: string | null;
  state: string;
  first_seen_at: string;
  last_seen_at: string;
};

export type MonitoringDeviceCoverage = {
  device_id: string;
  device_name: string;
  device_status: string;
  last_collected_at: string | null;
  reachability: string;
  cpu_percent: number | null;
  memory_percent: number | null;
  temperature_c: number | null;
  fan_speed_rpm: number | null;
  power_status: string | null;
};

export type MonitoringOverview = {
  total_devices: number;
  devices_online: number;
  devices_offline: number;
  devices_not_collected: number;
  coverage: MonitoringDeviceCoverage[];
};

export type MonitoringDevice = {
  telemetry: TelemetryRecord | null;
  services: ServiceObservation[];
};

export type MonitoringJob = {
  id: string;
  status: string;
  kind: string;
  device_ids: string[];
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  triggered_by: string;
  success_count: number;
  error_count: number;
};

export type Policy = {
  id: string;
  name: string;
  description: string | null;
  category: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  vendor_scope: string[];
  device_type_scope: string[];
  rule_type: "config_pattern" | "telemetry_threshold" | "service_check" | "interface_check";
  rule_definition: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
  updated_at: string | null;
  created_by: string;
};

export type PolicyInput = Omit<Policy, "id" | "created_at" | "updated_at" | "created_by">;

export type PolicyEvaluation = {
  evaluation_id: string;
  policy_id: string;
  policy_name: string;
  device_id: string;
  device_name: string;
  evaluated_at: string;
  result: "pass" | "fail" | "unknown";
  details: Record<string, unknown>;
};

export type Finding = {
  id: string;
  device_id: string;
  policy_id: string | null;
  severity: "critical" | "high" | "medium" | "low" | "info";
  status: "open" | "acknowledged" | "resolved" | "suppressed";
  title: string;
  description: string | null;
  category: string;
  first_seen_at: string;
  last_seen_at: string;
  occurrence_count: number;
  evidence_refs: string[];
  related_config_version_id: string | null;
  related_telemetry_id: string | null;
  created_at: string;
  resolved_at: string | null;
  resolution_note: string | null;
};

export type Alert = {
  id: string;
  finding_id: string | null;
  device_id: string | null;
  category: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  status: "new" | "acknowledged" | "resolved";
  title: string;
  message: string | null;
  created_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
  actor: string | null;
  evidence_ref: string | null;
};

export type EvidenceRecord = {
  id: string;
  device_id: string | null;
  collection_job_id: string | null;
  collected_at: string;
  evidence_type: string;
  source_adapter: string | null;
  sha256: string;
  size_bytes: number;
  config_version_id: string | null;
  metadata: Record<string, unknown>;
};

export type SecurityPosture = {
  generated_at: string;
  total_devices: number;
  findings: {
    open: number;
    acknowledged: number;
    by_severity: Record<string, number>;
  };
  alerts: {
    new: number;
    acknowledged: number;
    by_severity: Record<string, number>;
  };
  compliance: {
    score: number | null;
    total_evaluations: number;
    pass: number;
    fail: number;
    unknown: number;
  };
};

export type SecurityReport = {
  id: string;
  device_id: string | null;
  generated_at: string;
  generated_by: string;
  evidence_refs: string[];
  compliance_summary: Record<string, unknown>;
  findings_summary: Record<string, unknown>;
  telemetry_summary: Record<string, unknown>;
  service_summary: Record<string, unknown>;
};

