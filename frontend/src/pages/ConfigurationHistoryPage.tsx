/**
 * Configuration versions and diff (Phase 2 behaviour, kept intact per Phase 3 section 17).
 *
 * Versions are immutable and the diff is deterministic `difflib` output computed on the server —
 * added / removed / unchanged, with nothing interpreted or summarized by a model. Stored content is
 * redacted before it is written, so what is shown here is exactly what is stored.
 *
 * Without a device in the route this page is a picker: version history is per device, and there is
 * no cross-device diff to offer.
 */

import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { Empty, ErrorBanner, KeyValues, Kpi, Loading, Pager, Panel, RoleNotice, Status } from "../components/ui";
import { bytes, relative, shortHash, time } from "../format";
import { useAsync } from "../hooks";
import type { ConfigurationContent, Diff, Role } from "../types";

export function ConfigurationHistoryPage({
  deviceId,
  role,
  navigate,
}: {
  deviceId: string | null;
  role: Role;
  navigate: (page: string, param?: string, tab?: string) => void;
}) {
  const canRead = role === "admin" || role === "operator";

  if (!canRead) {
    return (
      <div className="page">
        <RoleNotice needed="The operator or admin role" />
        <Panel title="Configuration versions">
          <p className="notice">
            Stored configuration text is only returned to an operator or admin, even though secrets are already redacted.
            Switch role in the account menu to read this page.
          </p>
        </Panel>
      </div>
    );
  }

  if (!deviceId) return <DevicePicker navigate={navigate} />;
  return <DeviceConfigurations deviceId={deviceId} navigate={navigate} />;
}

/** Device chooser. Version history belongs to one device, so the page asks which one first. */
function DevicePicker({ navigate }: { navigate: (page: string, param?: string, tab?: string) => void }) {
  const devices = useAsync(() => api.devices(), []);
  const [search, setSearch] = useState("");
  const rows = devices.data ?? [];

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter((device) =>
      `${device.name} ${device.management_ip} ${device.vendor ?? ""} ${device.site ?? ""}`.toLowerCase().includes(needle),
    );
  }, [rows, search]);

  return (
    <div className="page">
      <ErrorBanner message={devices.error} />

      <div className="filters">
        <label>
          Contains
          <input
            value={search}
            placeholder="device, address, vendor or site"
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <span className="spacer" />
        <button className="ghost" onClick={() => navigate("backups")}>
          Run a backup
        </button>
      </div>

      <div className="split">
        <div>
          <Panel
            title="Choose a device"
            note={`${filtered.length} of ${rows.length}`}
            provenance="GET /api/devices · versions are stored per device, so there is no cross-device diff"
            flush
          >
            {devices.loading && rows.length === 0 ? (
              <Loading what="devices" />
            ) : rows.length === 0 ? (
              <Empty message="No devices in inventory yet. Add one on the Devices page, then back it up." />
            ) : filtered.length === 0 ? (
              <Empty message="No device matches that search." />
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Device</th>
                      <th scope="col">Vendor</th>
                      <th scope="col">Address</th>
                      <th scope="col">Site</th>
                      <th scope="col">Last seen</th>
                      <th scope="col" aria-label="Open version history" />
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((device) => (
                      <tr key={device.id}>
                        <td>
                          <button className="link" onClick={() => navigate("configurations", device.id)}>
                            {device.name}
                          </button>
                        </td>
                        <td>{device.vendor ?? "—"}</td>
                        <td>
                          <code>{device.management_ip}</code>
                        </td>
                        <td>{device.site ?? "—"}</td>
                        <td title={time(device.last_seen_at)}>{relative(device.last_seen_at)}</td>
                        <td>
                          <button
                            className="chev"
                            aria-label={`Open the version history for ${device.name}`}
                            onClick={() => navigate("configurations", device.id)}
                          >
                            ›
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </div>

        <aside className="rail-stack">
          <Panel title="What a version is">
            <p className="notice">
              Each backup that finds changed content writes a new version: the redacted text, its SHA-256, its size, and a
              pointer to the version it replaced. Nothing is ever rewritten, so a version you looked at yesterday reads the
              same today.
            </p>
            <p className="notice">
              A backup that finds identical content writes nothing and is recorded as no change, which is why the version
              count is lower than the job count.
            </p>
          </Panel>
        </aside>
      </div>
    </div>
  );
}

function DeviceConfigurations({
  deviceId,
  navigate,
}: {
  deviceId: string;
  navigate: (page: string, param?: string, tab?: string) => void;
}) {
  const device = useAsync(() => api.device(deviceId), [deviceId]);
  const versions = useAsync(() => api.configurations(deviceId), [deviceId]);
  const [left, setLeft] = useState("");
  const [right, setRight] = useState("");
  const [diff, setDiff] = useState<Diff | null>(null);
  const [content, setContent] = useState<ConfigurationContent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(10);

  const rows = versions.data ?? [];

  // Default the comparison to the two most recent versions, which is what an operator almost
  // always wants after a backup reported a change.
  useEffect(() => {
    if (rows.length === 0) return;
    setLeft((current) => current || rows[1]?.version_id || "");
    setRight((current) => current || rows[0]?.version_id || "");
  }, [rows]);

  const stored = useMemo(() => rows.reduce((sum, version) => sum + version.size_bytes, 0), [rows]);
  const newest = rows[0] ?? null;

  const compare = async () => {
    if (!left || !right || left === right) return;
    setBusy(true);
    setError(null);
    try {
      setDiff(await api.diff(deviceId, left, right));
      setContent(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to compare versions");
    } finally {
      setBusy(false);
    }
  };

  const view = async (versionId: string) => {
    setBusy(true);
    setError(null);
    try {
      setContent(await api.configuration(deviceId, versionId));
      setDiff(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load configuration");
    } finally {
      setBusy(false);
    }
  };

  const start = page * pageSize;
  const shown = rows.slice(start, start + pageSize);
  const label = (versionId: string) => {
    const version = rows.find((row) => row.version_id === versionId);
    return version ? `${time(version.timestamp)} · ${shortHash(version.sha256)}` : "—";
  };

  return (
    <div className="page">
      <div className="subhead">
        <div>
          <button className="link back" onClick={() => navigate("configurations")}>
            ← All devices
          </button>
          <h2>{device.data?.name ?? deviceId}</h2>
          <p>
            {[
              device.data?.vendor ?? "unknown vendor",
              device.data?.model ?? device.data?.platform ?? "unknown model",
              device.data?.management_ip,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        <div className="actions">
          <button className="ghost" onClick={() => navigate("devices", deviceId)}>
            Open device
          </button>
          <button className="ghost" onClick={() => navigate("backups")}>
            Back up now
          </button>
        </div>
      </div>

      <ErrorBanner message={error ?? versions.error} onDismiss={() => setError(null)} />

      <div className="kpis">
        <Kpi
          label="Versions stored"
          value={rows.length}
          icon="▤"
          tone={rows.length === 0 ? "crit" : undefined}
          foot={rows.length === 0 ? "This device has never been backed up" : "Immutable — none can be edited or replaced"}
        />
        <Kpi
          label="Newest version"
          value={newest ? relative(newest.timestamp) : "—"}
          icon="✓"
          text
          tone={newest ? "good" : "warn"}
          foot={newest ? time(newest.timestamp) : "Run a backup to create the first version"}
        />
        <Kpi
          label="Stored size"
          value={bytes(stored)}
          icon="≡"
          text
          foot={rows.length > 1 ? `Across ${rows.length} versions of redacted text` : "Redacted configuration text"}
        />
        <Kpi
          label="Newest hash"
          value={newest ? shortHash(newest.sha256) : "—"}
          icon="#"
          text
          foot={newest ? "SHA-256 of the stored text — the identity a backup compares against" : "No hash yet"}
        />
      </div>

      <div className="toolbar">
        <span className="toolbar-label">Compare</span>
        <select value={left} onChange={(event) => setLeft(event.target.value)} aria-label="Older version">
          <option value="">Older version</option>
          {rows.map((version) => (
            <option key={version.version_id} value={version.version_id}>
              {time(version.timestamp)} · {shortHash(version.sha256)}
            </option>
          ))}
        </select>
        <span className="toolbar-note">against</span>
        <select value={right} onChange={(event) => setRight(event.target.value)} aria-label="Newer version">
          <option value="">Newer version</option>
          {rows.map((version) => (
            <option key={version.version_id} value={version.version_id}>
              {time(version.timestamp)} · {shortHash(version.sha256)}
            </option>
          ))}
        </select>
        <button className="primary" onClick={() => void compare()} disabled={busy || !left || !right || left === right}>
          {busy ? "Working…" : "Compare"}
        </button>
        <span className="spacer" />
        {(diff || content) && (
          <button
            className="ghost"
            onClick={() => {
              setDiff(null);
              setContent(null);
            }}
          >
            Clear output
          </button>
        )}
      </div>

      <div className="split">
        <div>
          <Panel
            title="Versions"
            note={`${rows.length} immutable version${rows.length === 1 ? "" : "s"}`}
            provenance={`GET /api/devices/${deviceId}/configurations · newest first`}
            flush
          >
            {versions.loading && rows.length === 0 ? (
              <Loading what="versions" />
            ) : rows.length === 0 ? (
              <Empty message="No configuration versions yet. Run a backup for this device to create the first one." />
            ) : (
              <>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th scope="col">Captured</th>
                        <th scope="col">SHA-256</th>
                        <th scope="col">Size</th>
                        <th scope="col">Status</th>
                        <th scope="col">Retention</th>
                        <th scope="col">Replaces</th>
                        <th scope="col" aria-label="View" />
                      </tr>
                    </thead>
                    <tbody>
                      {shown.map((version) => (
                        <tr key={version.version_id}>
                          <td title={time(version.timestamp)}>
                            {relative(version.timestamp)}
                            <br />
                            <code className="rule">{version.version_id.slice(0, 8)}</code>
                          </td>
                          <td title={version.sha256}>
                            <code>{shortHash(version.sha256)}</code>
                          </td>
                          <td className="num">{bytes(version.size_bytes)}</td>
                          <td>
                            <Status value={version.status} />
                          </td>
                          <td>{version.retention_state}</td>
                          <td>
                            {version.parent_version_id ? (
                              <code>{version.parent_version_id.slice(0, 8)}</code>
                            ) : (
                              "first capture"
                            )}
                          </td>
                          <td>
                            <button
                              className="chev"
                              aria-label={`View the stored text of version ${version.version_id.slice(0, 8)}`}
                              onClick={() => void view(version.version_id)}
                              disabled={busy}
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
                  total={rows.length}
                  page={page}
                  pageSize={pageSize}
                  onPage={setPage}
                  onPageSize={(size) => {
                    setPageSize(size);
                    setPage(0);
                  }}
                  noun="versions"
                />
              </>
            )}
          </Panel>

          {diff && (
            <Panel
              title="Line diff"
              note={`${label(left)} → ${label(right)}`}
              provenance={`GET /api/devices/${deviceId}/configurations/{a}/diff/{b} · Python difflib on the server, no interpretation`}
            >
              <p className="diff-summary">
                <strong>+{diff.summary.added}</strong> added · <strong>−{diff.summary.removed}</strong> removed ·{" "}
                {diff.summary.unchanged} unchanged
              </p>
              <pre className="diff">
                {diff.lines.map((line, index) => (
                  <div key={index} className={line.kind}>
                    {line.kind === "added" ? "+ " : line.kind === "removed" ? "− " : "  "}
                    {line.text}
                  </div>
                ))}
              </pre>
            </Panel>
          )}

          {content && (
            <Panel
              title="Stored configuration"
              note={label(content.version_id)}
              provenance={`GET /api/devices/${deviceId}/configurations/${content.version_id.slice(0, 8)}… · redacted before storage`}
            >
              <p className="diff-summary">
                Version <code>{content.version_id.slice(0, 8)}</code> · SHA-256 <code>{shortHash(content.sha256)}</code> ·
                passwords, keys and community strings were replaced before this text was written
              </p>
              <pre className="diff">{content.content}</pre>
            </Panel>
          )}
        </div>

        <aside className="rail-stack">
          <Panel title="Selected pair" provenance="Local selection — nothing is requested until Compare">
            <KeyValues
              rows={[
                { label: "Older", value: left ? label(left) : "not selected" },
                { label: "Newer", value: right ? label(right) : "not selected" },
                {
                  label: "Same version",
                  value: left && left === right ? "yes — pick two different versions" : "no",
                },
              ]}
            />
          </Panel>

          <Panel title="How the diff is produced">
            <p className="notice">
              The server runs Python's <code>difflib</code> over the two stored texts and returns added, removed and
              unchanged lines. The same pair always produces the same diff, and no model rewrites or summarizes it.
            </p>
            <p className="notice">
              Added lines are marked <code>+</code> and removed lines <code>−</code>, so the diff is readable without
              relying on colour.
            </p>
          </Panel>
        </aside>
      </div>
    </div>
  );
}
