/**
 * Single API client for the whole app.
 *
 * Identity lives here rather than being threaded through every call site: the backend
 * authorizes on the ``X-Role``/``X-Actor`` headers, so every request must carry them and
 * exactly one place should decide what they are. Nothing secret is ever sent from the
 * browser — the credential reference is a profile name and the backend redacts secrets
 * before configuration text leaves the server.
 */

import type {
  BackupJob,
  Configuration,
  ConfigurationContent,
  Dashboard,
  Device,
  DeviceInput,
  DeviceSlice,
  DeviceSummary,
  Diff,
  DiscoveryJob,
  Graph,
  Health,
  Interface,
  LogEvent,
  LogFilters,
  LogOptions,
  Neighbor,
  ResolvedNeighbor,
  Schedule,
  ScheduleInput,
  SchedulerStatus,
  SessionIdentity,
  TopologyEdge,
  TopologyFilters,
  TopologyNode,
  AppSettings,
} from "./types";

const STORAGE_KEY = "ivp.identity";

let identity: SessionIdentity = loadIdentity();

function loadIdentity(): SessionIdentity {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored) as SessionIdentity;
      if (parsed.role && parsed.actor) return parsed;
    }
  } catch {
    // A corrupt or unavailable localStorage must not stop the app from loading.
  }
  return { role: "operator", actor: "operator" };
}

export function getIdentity(): SessionIdentity {
  return identity;
}

export function setIdentity(next: SessionIdentity): void {
  identity = next;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Persistence is a convenience; the session still works without it.
  }
}

/** Thrown for any non-2xx response so callers can show the status as well as the message. */
export class ApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

function queryString(params: Record<string, unknown> | undefined): string {
  if (!params) return "";
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.append(key, String(value));
  }
  const encoded = search.toString();
  return encoded ? `?${encoded}` : "";
}

/** FastAPI reports validation problems as ``detail``; surface that text, not "422". */
function describeFailure(status: number, body: string): string {
  try {
    const parsed = JSON.parse(body) as { detail?: unknown };
    const detail = parsed.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          const entry = item as { loc?: unknown[]; msg?: string };
          const field = Array.isArray(entry.loc) ? entry.loc[entry.loc.length - 1] : "";
          return field ? `${field}: ${entry.msg ?? ""}` : entry.msg ?? "";
        })
        .filter(Boolean)
        .join("; ");
    }
  } catch {
    // Not JSON - fall through to the raw text.
  }
  return body || `request failed with status ${status}`;
}

async function request<T>(
  path: string,
  options: { method?: string; params?: Record<string, unknown>; body?: unknown } = {},
): Promise<T> {
  const { method = "GET", params, body } = options;
  const headers: Record<string, string> = {
    "X-Role": identity.role,
    "X-Actor": identity.actor,
  };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch(`${path}${queryString(params)}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    throw new ApiError(response.status, describeFailure(response.status, await response.text()));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  settings: () => request<AppSettings>("/api/settings"),
  updateSettings: (input: AppSettings) => request<AppSettings>("/api/settings", { method: "PUT", body: input }),
  // ---- Dashboard -----------------------------------------------------------
  dashboard: () => request<Dashboard>("/api/dashboard"),

  // ---- Devices -------------------------------------------------------------
  devices: () => request<Device[]>("/api/devices"),
  device: (id: string) => request<Device>(`/api/devices/${id}`),
  deviceSummary: (id: string) => request<DeviceSummary>(`/api/devices/${id}/summary`),
  interfaces: (id: string) => request<Interface[]>(`/api/devices/${id}/interfaces`),
  neighbors: (id: string) => request<Neighbor[]>(`/api/devices/${id}/neighbors`),
  resolvedNeighbors: (id: string) =>
    request<ResolvedNeighbor[]>(`/api/devices/${id}/neighbors`, { params: { resolved: true } }),
  health: (id: string) => request<Health>(`/api/devices/${id}/health`),
  createDevice: (input: DeviceInput) => request<Device>("/api/devices", { method: "POST", body: input }),
  updateDevice: (id: string, input: DeviceInput) =>
    request<Device>(`/api/devices/${id}`, { method: "PUT", body: input }),
  deleteDevice: (id: string) =>
    request<{ device: string; management_ip: string; configuration_versions_removed: number }>(
      `/api/devices/${id}`,
      { method: "DELETE" },
    ),
  runDiscovery: (id: string) => request<DiscoveryJob>(`/api/devices/${id}/discovery`, { method: "POST" }),

  // ---- Topology ------------------------------------------------------------
  topology: (filters?: TopologyFilters) => request<Graph>("/api/topology", { params: filters }),
  topologyNodes: (filters?: TopologyFilters) =>
    request<Omit<Graph, "edges"> & { nodes: TopologyNode[] }>("/api/topology/nodes", { params: filters }),
  topologyEdges: (filters?: TopologyFilters) =>
    request<{ edges: TopologyEdge[]; stats: Graph["stats"] }>("/api/topology/edges", { params: filters }),
  deviceTopology: (id: string) => request<DeviceSlice>(`/api/topology/devices/${id}`),

  // ---- Backups (Phase 2) ---------------------------------------------------
  jobs: () => request<BackupJob[]>("/api/backups"),
  job: (jobId: string) => request<BackupJob>(`/api/backups/${jobId}`),
  startBackup: (deviceIds: string[]) =>
    request<{ job_id: string; status: string }>("/api/backups", {
      method: "POST",
      body: { device_ids: deviceIds },
    }),

  // ---- Configuration history (Phase 2) -------------------------------------
  configurations: (id: string) => request<Configuration[]>(`/api/devices/${id}/configurations`),
  configuration: (id: string, versionId: string) =>
    request<ConfigurationContent>(`/api/devices/${id}/configurations/${versionId}`),
  diff: (id: string, versionA: string, versionB: string) =>
    request<Diff>(`/api/devices/${id}/configurations/${versionA}/diff/${versionB}`),

  // ---- Schedules -----------------------------------------------------------
  schedules: () => request<Schedule[]>("/api/schedules"),
  schedule: (id: string) => request<Schedule>(`/api/schedules/${id}`),
  createSchedule: (input: ScheduleInput) => request<Schedule>("/api/schedules", { method: "POST", body: input }),
  updateSchedule: (id: string, input: ScheduleInput) =>
    request<Schedule>(`/api/schedules/${id}`, { method: "PUT", body: input }),
  setScheduleEnabled: (id: string, enabled: boolean) =>
    request<Schedule>(`/api/schedules/${id}/enabled`, { method: "POST", params: { enabled } }),
  deleteSchedule: (id: string) => request<void>(`/api/schedules/${id}`, { method: "DELETE" }),
  runSchedule: (id: string) =>
    request<{ schedule_id: string; status: string }>(`/api/schedules/${id}/run`, { method: "POST" }),
  schedulerStatus: () => request<SchedulerStatus>("/api/scheduler"),

  // ---- Logs ----------------------------------------------------------------
  logs: (filters?: LogFilters) => request<LogEvent[]>("/api/logs", { params: filters }),
  logOptions: () => request<LogOptions>("/api/logs/options"),
};
