/**
 * Devices: the inventory list, and one device's discovered detail.
 *
 * The list is the administrative entry point (add, edit, delete, discover, back up) and the
 * detail view shows what discovery actually recorded. Both read the same rows the topology
 * reads — there is no second device store.
 *
 * Administrative controls appear only for the roles that may use them, and the server checks
 * again on every request: hiding a button is a courtesy, not the enforcement.
 */

import { useMemo, useState } from "react";
import { api } from "../api";
import { Meter } from "../components/charts";
import { DeviceForm } from "../components/DeviceForm";
import {
  Empty,
  ErrorBanner,
  Fact,
  Kpi,
  Loading,
  Pager,
  Panel,
  RoleNotice,
  Select,
  Status,
  Tabs,
} from "../components/ui";
import { percent, relative, time, titleCase } from "../format";
import { useAsync } from "../hooks";
import type { Device, Role } from "../types";

export function DevicesPage({
  role,
  navigate,
}: {
  role: Role;
  navigate: (page: string, param?: string, tab?: string) => void;
}) {
  const devices = useAsync(() => api.devices(), []);
  const [vendor, setVendor] = useState("");
  const [type, setType] = useState("");
  const [status, setStatus] = useState("");
  const [site, setSite] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [editing, setEditing] = useState<Device | null>(null);
  const [adding, setAdding] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);

  const rows = devices.data ?? [];
  const options = useMemo(
    () => ({
      vendors: [...new Set(rows.map((device) => device.vendor).filter((value): value is string => !!value))].sort(),
      types: [...new Set(rows.map((device) => device.type))].sort(),
      statuses: [...new Set(rows.map((device) => device.status))].sort(),
      sites: [...new Set(rows.map((device) => device.site).filter((value): value is string => !!value))].sort(),
    }),
    [rows],
  );

  const counts = useMemo(() => {
    const tally = { online: 0, offline: 0, degraded: 0, unknown: 0 };
    for (const device of rows) {
      const key = device.status.toLowerCase();
      if (key === "online") tally.online += 1;
      else if (key === "offline") tally.offline += 1;
      else if (key === "degraded") tally.degraded += 1;
      else tally.unknown += 1;
    }
    return tally;
  }, [rows]);

  const filtered = rows.filter(
    (device) =>
      (!vendor || device.vendor === vendor) &&
      (!type || device.type === type) &&
      (!status || device.status === status) &&
      (!site || device.site === site) &&
      (!search ||
        device.name.toLowerCase().includes(search.toLowerCase()) ||
        device.management_ip.includes(search)),
  );

  const isAdmin = role === "admin";
  const canOperate = role === "admin" || role === "operator";
  const filtering = Boolean(vendor || type || status || site || search);
  const start = page * pageSize;
  const shown = filtered.slice(start, start + pageSize);

  const act = async (label: string, action: () => Promise<string>) => {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      setMessage(await action());
      devices.reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : `Unable to ${label}`);
    } finally {
      setBusy(false);
    }
  };

  const remove = (device: Device) => {
    if (!window.confirm(`Delete ${device.name}? Discovered interfaces and neighbours are removed with it.`)) return;
    void act("delete device", async () => {
      const result = await api.deleteDevice(device.id);
      setSelected((current) => current.filter((id) => id !== device.id));
      return `Deleted ${result.device}. ${result.configuration_versions_removed} configuration version record(s) were released; stored artifacts were not deleted.`;
    });
  };

  const discover = (device: Device) =>
    void act("run discovery", async () => {
      const job = await api.runDiscovery(device.id);
      const outcome = job.results[0];
      return outcome?.status === "success"
        ? `Discovery succeeded for ${device.name}.`
        : `Discovery for ${device.name} finished as ${job.status}${outcome?.error ? `: ${outcome.error}` : ""}.`;
    });

  const backup = () =>
    void act("start backup", async () => {
      const job = await api.startBackup(selected);
      const scope = selected.length ? `${selected.length} device(s)` : "all devices";
      setSelected([]);
      return `Backup job ${job.job_id.slice(0, 8)} started for ${scope}. Follow it on the Backups page.`;
    });

  const filterStatus = (value: string) => {
    setStatus(status === value ? "" : value);
    setPage(0);
  };

  return (
    <div className="page">
      <ErrorBanner message={error ?? devices.error} onDismiss={() => setError(null)} />
      {message && (
        <p className="notice" role="status">
          {message}
        </p>
      )}

      <div className="kpis">
        <Kpi
          label="In inventory"
          value={rows.length}
          icon="▤"
          foot="Credentials are referenced by profile name and never stored in this browser"
        />
        <Kpi
          label="Online"
          value={counts.online}
          icon="◉"
          tone={counts.online > 0 ? "good" : undefined}
          foot={status === "online" ? "Filtering on online — click to clear" : "Click to filter the table"}
          onClick={() => filterStatus("online")}
        />
        <Kpi
          label="Offline or degraded"
          value={counts.offline + counts.degraded}
          icon="✕"
          tone={counts.offline > 0 ? "crit" : counts.degraded > 0 ? "warn" : undefined}
          foot={`${counts.offline} unreachable · ${counts.degraded} degraded`}
          onClick={() => filterStatus("offline")}
        />
        <Kpi
          label="Never reached"
          value={counts.unknown}
          icon="○"
          tone={counts.unknown > 0 ? "warn" : undefined}
          foot="Registered but no successful discovery yet"
          onClick={() => filterStatus("unknown")}
        />
      </div>

      <div className="filters">
        <label>
          Search
          <input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(0);
            }}
            placeholder="name or IP"
          />
        </label>
        <Select label="Vendor" value={vendor} options={options.vendors} onChange={setVendor} />
        <Select label="Type" value={type} options={options.types} onChange={setType} />
        <Select label="Status" value={status} options={options.statuses} onChange={setStatus} />
        <Select label="Site" value={site} options={options.sites} onChange={setSite} />
        <span className="spacer" />
        <button
          className="ghost"
          disabled={!filtering}
          onClick={() => {
            setVendor("");
            setType("");
            setStatus("");
            setSite("");
            setSearch("");
            setPage(0);
          }}
        >
          Reset filters
        </button>
        {canOperate && (
          <button className="ghost" onClick={backup} disabled={busy || rows.length === 0}>
            {selected.length ? `Back up ${selected.length} selected` : "Back up all"}
          </button>
        )}
        {isAdmin ? (
          <button className="primary" onClick={() => setAdding(true)}>
            Add device
          </button>
        ) : null}
      </div>

      {!isAdmin && <RoleNotice needed="The admin role" />}

      <Panel
        title="Inventory"
        note={`${filtered.length} of ${rows.length} shown`}
        provenance="GET /api/devices · status and discovery state are what the last discovery run recorded"
        flush
      >
        {devices.loading && rows.length === 0 ? (
          <Loading what="devices" />
        ) : filtered.length === 0 ? (
          <Empty message={rows.length === 0 ? "No devices are registered yet." : "No devices match these filters."} />
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col" aria-label="Select" />
                    <th scope="col">Device</th>
                    <th scope="col">Type</th>
                    <th scope="col">Vendor / model</th>
                    <th scope="col">Management</th>
                    <th scope="col">Site</th>
                    <th scope="col">Status</th>
                    <th scope="col">Discovery</th>
                    <th scope="col">Actions</th>
                    <th scope="col" aria-label="Open" />
                  </tr>
                </thead>
                <tbody>
                  {shown.map((device) => (
                    <tr key={device.id}>
                      <td>
                        <input
                          type="checkbox"
                          aria-label={`Select ${device.name}`}
                          checked={selected.includes(device.id)}
                          onChange={() =>
                            setSelected((current) =>
                              current.includes(device.id)
                                ? current.filter((id) => id !== device.id)
                                : [...current, device.id],
                            )
                          }
                        />
                      </td>
                      <td>
                        <button className="link" onClick={() => navigate("devices", device.id)}>
                          {device.name}
                        </button>
                      </td>
                      <td>{titleCase(device.type)}</td>
                      <td>{[device.vendor, device.model].filter(Boolean).join(" · ") || "—"}</td>
                      <td>
                        <code>
                          {device.management_ip}:{device.management_port}
                        </code>
                      </td>
                      <td>{device.site ?? "—"}</td>
                      <td>
                        <Status value={device.status} />
                      </td>
                      <td title={time(device.last_seen_at)}>
                        {titleCase(device.discovery_state)}
                        <small className="muted"> · {relative(device.last_seen_at)}</small>
                      </td>
                      <td className="row-actions">
                        {canOperate && (
                          <button className="link" onClick={() => discover(device)} disabled={busy}>
                            Discover
                          </button>
                        )}
                        {isAdmin && (
                          <>
                            <button className="link" onClick={() => setEditing(device)}>
                              Edit
                            </button>
                            <button className="link danger" onClick={() => remove(device)} disabled={busy}>
                              Delete
                            </button>
                          </>
                        )}
                        {!canOperate && <span className="muted">view only</span>}
                      </td>
                      <td>
                        <button
                          className="chev"
                          aria-label={`Open ${device.name}`}
                          onClick={() => navigate("devices", device.id)}
                        >
                          ›
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager
              total={filtered.length}
              page={page}
              pageSize={pageSize}
              onPage={setPage}
              onPageSize={(size) => {
                setPageSize(size);
                setPage(0);
              }}
              noun="devices"
            />
          </>
        )}
      </Panel>

      {(adding || editing) && (
        <DeviceForm
          device={editing}
          onClose={() => {
            setAdding(false);
            setEditing(null);
          }}
          onSaved={(device, runDiscovery) => {
            setAdding(false);
            setEditing(null);
            setMessage(`Saved ${device.name}.`);
            devices.reload();
            if (runDiscovery) discover(device);
          }}
        />
      )}
    </div>
  );
}

/** One device: identity, discovered interfaces, neighbours, health, and backup history. */
export function DeviceDetailPage({
  deviceId,
  tab,
  role,
  navigate,
}: {
  deviceId: string;
  tab: string | null;
  role: Role;
  navigate: (page: string, param?: string, tab?: string) => void;
}) {
  const summary = useAsync(() => api.deviceSummary(deviceId), [deviceId]);
  const interfaces = useAsync(() => api.interfaces(deviceId), [deviceId]);
  const neighbors = useAsync(() => api.resolvedNeighbors(deviceId), [deviceId]);
  const health = useAsync(() => api.health(deviceId).catch(() => null), [deviceId]);
  const jobs = useAsync(() => (role === "viewer" ? Promise.resolve([]) : api.jobs()), [deviceId, role]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const active = tab ?? "overview";

  const device = summary.data;
  if (summary.loading && !device) return <Loading what="the device" />;
  if (!device) return <ErrorBanner message={summary.error ?? "Device not found"} />;

  const deviceJobs = (jobs.data ?? [])
    .map((job) => ({ job, result: job.results.find((item) => item.device_id === deviceId) }))
    .filter((entry) => entry.result);

  const backupNow = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.startBackup([deviceId]);
      window.setTimeout(() => jobs.reload(), 1500);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to start backup");
    } finally {
      setBusy(false);
    }
  };

  const tabs = [
    { id: "overview", label: "Overview" },
    { id: "interfaces", label: `Interfaces (${device.interface_count})` },
    { id: "neighbors", label: `Neighbours (${device.neighbor_count})` },
    { id: "backups", label: "Backup history" },
  ];

  return (
    <div className="page">
      <div className="subhead">
        <div>
          <button className="link back" onClick={() => navigate("devices")}>
            ← All devices
          </button>
          <h2>{device.name}</h2>
          <p>
            {[titleCase(device.type), device.vendor ?? "unknown vendor", device.model ?? "unknown model", device.management_ip]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        <div className="actions">
          {role !== "viewer" && (
            <button className="ghost" onClick={() => void backupNow()} disabled={busy}>
              {busy ? "Starting…" : "Back up now"}
            </button>
          )}
          <button className="primary" onClick={() => navigate("configurations", deviceId)}>
            Configuration history
          </button>
        </div>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      <div className="kpis">
        <Kpi
          label="Reachability"
          value={<Status value={device.status} />}
          icon="◉"
          text
          foot={`Last seen ${relative(device.last_seen_at)}`}
        />
        <Kpi
          label="Stored versions"
          value={device.configuration_version_count}
          icon="▤"
          tone={device.configuration_version_count > 0 ? "good" : "warn"}
          foot={
            device.last_backup_at
              ? `Newest ${relative(device.last_backup_at)}`
              : "No configuration has been captured yet"
          }
          onClick={() => navigate("configurations", deviceId)}
        />
        <Kpi label="Interfaces" value={device.interface_count} icon="≡" foot="Recorded by the last discovery run" />
        <Kpi
          label="Neighbours"
          value={device.neighbor_count}
          icon="⋔"
          foot="LLDP entries this device reported"
          onClick={() => navigate("devices", deviceId, "neighbors")}
        />
      </div>

      <Tabs tabs={tabs} active={active} onSelect={(id) => navigate("devices", deviceId, id)} />

      {active === "overview" && (
        <div className="split">
          <div>
            <Panel
              title="Identity and freshness"
              provenance="GET /api/devices/{id}/summary · every field is what discovery recorded, nothing is inferred"
            >
              <dl className="facts">
                <Fact label="Status">
                  <Status value={device.status} />
                </Fact>
                <Fact label="Discovery state">{titleCase(device.discovery_state)}</Fact>
                <Fact label="Management">
                  <code>
                    {device.management_ip}:{device.management_port}
                  </code>
                </Fact>
                <Fact label="Platform">
                  {[device.platform, device.os_version].filter(Boolean).join(" ") || "unknown"}
                </Fact>
                <Fact label="Serial number">{device.serial_number ?? "unknown"}</Fact>
                <Fact label="Site">{device.site ?? "—"}</Fact>
                <Fact label="Credential reference">
                  <code>{device.credentials_reference_id}</code>
                </Fact>
                <Fact label="Capabilities">{device.capabilities.join(", ") || "—"}</Fact>
                <Fact label="Last seen">{time(device.last_seen_at)}</Fact>
                <Fact label="Last discovery">{time(device.last_discovery_at)}</Fact>
                <Fact label="Last backup">{time(device.last_backup_at)}</Fact>
                <Fact label="Identity confidence">{percent(device.confidence)}</Fact>
              </dl>
              <p className="provenance" style={{ margin: "14px 0 0" }}>
                The credential reference is a profile name. No password, key or secret is sent to this browser.
              </p>
            </Panel>
          </div>

          <aside className="rail-stack">
            <Panel title="Health" provenance="GET /api/devices/{id}/health">
              {health.data ? (
                <div className="meters">
                  <Meter
                    label="CPU"
                    value={health.data.cpu_percent ?? 0}
                    total={100}
                    tone={(health.data.cpu_percent ?? 0) >= 85 ? "crit" : (health.data.cpu_percent ?? 0) >= 70 ? "warn" : "good"}
                    note={health.data.cpu_percent === null ? "Not reported by this device" : "Percent used at the last read"}
                  />
                  <Meter
                    label="Memory"
                    value={health.data.memory_percent ?? 0}
                    total={100}
                    tone={(health.data.memory_percent ?? 0) >= 85 ? "crit" : (health.data.memory_percent ?? 0) >= 70 ? "warn" : "good"}
                    note={
                      health.data.memory_percent === null ? "Not reported by this device" : "Percent used at the last read"
                    }
                  />
                </div>
              ) : (
                <Empty message="No health reading is available for this device." />
              )}
              {health.data && (
                <dl className="facts" style={{ marginTop: "16px" }}>
                  <Fact label="Uptime">{health.data.uptime ?? "—"}</Fact>
                  <Fact label="Hardware">
                    <Status value={health.data.hardware_status} />
                  </Fact>
                </dl>
              )}
              <p className="notice">
                CPU, memory, uptime and hardware state are the only sensor values the platform collects. Temperature,
                fan and power readings are not implemented, so none are shown.
              </p>
            </Panel>
          </aside>
        </div>
      )}

      {active === "interfaces" && (
        <Panel
          title="Interfaces"
          note={`${interfaces.data?.length ?? 0} discovered`}
          provenance="GET /api/devices/{id}/interfaces"
          flush
        >
          {interfaces.loading ? (
            <Loading what="interfaces" />
          ) : (interfaces.data ?? []).length === 0 ? (
            <Empty message="No interfaces recorded. Run discovery against this device." />
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Interface</th>
                    <th scope="col">Admin</th>
                    <th scope="col">Operational</th>
                    <th scope="col">Addresses</th>
                    <th scope="col">Speed</th>
                    <th scope="col">Description</th>
                  </tr>
                </thead>
                <tbody>
                  {(interfaces.data ?? []).map((item) => (
                    <tr key={item.id}>
                      <td>
                        <code>{item.name}</code>
                      </td>
                      <td>
                        <Status value={item.admin_state} />
                      </td>
                      <td>
                        <Status value={item.operational_state} />
                      </td>
                      <td>{item.addresses.join(", ") || "—"}</td>
                      <td>{item.speed ?? "—"}</td>
                      <td>{item.description ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      )}

      {active === "neighbors" && (
        <Panel
          title="LLDP neighbours"
          note="Raw evidence plus the device it was correlated to"
          provenance="GET /api/devices/{id}/neighbors?resolved=true · a neighbour with no confident match stays unresolved rather than being guessed"
          flush
        >
          {neighbors.loading ? (
            <Loading what="neighbours" />
          ) : (neighbors.data ?? []).length === 0 ? (
            <Empty message="No LLDP neighbours recorded." />
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Local interface</th>
                    <th scope="col">Remote system</th>
                    <th scope="col">Remote interface</th>
                    <th scope="col">Chassis ID</th>
                    <th scope="col">Correlated device</th>
                  </tr>
                </thead>
                <tbody>
                  {(neighbors.data ?? []).map((neighbor, index) => (
                    <tr key={`${neighbor.local_interface}-${index}`}>
                      <td>
                        <code>{neighbor.local_interface}</code>
                      </td>
                      <td>{neighbor.remote_system_name ?? "—"}</td>
                      <td>
                        <code>{neighbor.remote_interface ?? "—"}</code>
                      </td>
                      <td>
                        <code>{neighbor.remote_chassis_id ?? "—"}</code>
                      </td>
                      <td>
                        {neighbor.managed && neighbor.resolved_device_id ? (
                          <button className="link" onClick={() => navigate("devices", neighbor.resolved_device_id!)}>
                            {neighbor.resolved_device_name}
                          </button>
                        ) : (
                          <span className="muted">not in inventory</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      )}

      {active === "backups" && (
        <Panel
          title="Backup history"
          note="Jobs that included this device"
          provenance="GET /api/backups · filtered in the browser to this device's result rows"
          flush
        >
          {role === "viewer" ? (
            <RoleNotice needed="The operator or admin role" />
          ) : deviceJobs.length === 0 ? (
            <Empty message="This device has not appeared in a backup job yet." />
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Started</th>
                    <th scope="col">Job</th>
                    <th scope="col">Result</th>
                    <th scope="col">Change</th>
                    <th scope="col">Duration</th>
                    <th scope="col">Version</th>
                  </tr>
                </thead>
                <tbody>
                  {deviceJobs.map(({ job, result }) => (
                    <tr key={job.job_id}>
                      <td title={time(job.started_at ?? job.created_at)}>{relative(job.started_at ?? job.created_at)}</td>
                      <td>
                        <code>{job.job_id.slice(0, 8)}</code>
                      </td>
                      <td>
                        <Status value={result!.status} />
                      </td>
                      <td>
                        {result!.change_status ? (
                          <Status value={result!.change_status.toLowerCase()} />
                        ) : (
                          (result!.error_category ?? "—")
                        )}
                      </td>
                      <td className="num">{result!.duration_seconds.toFixed(1)} s</td>
                      <td>{result!.version_id ? <code>{result!.version_id.slice(0, 8)}</code> : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      )}
    </div>
  );
}
