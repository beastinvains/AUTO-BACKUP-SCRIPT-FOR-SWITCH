/**
 * Backups.
 *
 * Jobs, per-device outcomes, and a "Back up now" control. Both this page and the scheduler go
 * through the same `BackupService`, so a scheduled run and a manual run appear in this one
 * table — `Requested by` is how you tell them apart.
 *
 * While a job is pending or running the table refreshes on its own and says so in the panel
 * note, rather than replacing what you were reading with a skeleton.
 */

import { Fragment, useMemo, useState } from "react";
import { api } from "../api";
import { Empty, ErrorBanner, Kpi, Loading, Pager, Panel, RoleNotice, Select, Status } from "../components/ui";
import { relative, time } from "../format";
import { useAsync, usePolling } from "../hooks";
import type { BackupJob, Device, Role } from "../types";

function duration(job: BackupJob): string {
  if (!job.started_at || !job.completed_at) return "—";
  const seconds = (new Date(job.completed_at).getTime() - new Date(job.started_at).getTime()) / 1000;
  return `${seconds.toFixed(1)} s`;
}

export function BackupsPage({ role, navigate }: { role: Role; navigate: (page: string, param?: string) => void }) {
  const canOperate = role === "admin" || role === "operator";
  const jobs = useAsync(() => (canOperate ? api.jobs() : Promise.resolve([])), [canOperate]);
  const devices = useAsync(() => api.devices(), []);
  const [selected, setSelected] = useState<string[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(10);

  const rows = jobs.data ?? [];
  const running = rows.some((job) => job.status === "PENDING" || job.status === "RUNNING");
  usePolling(() => jobs.reload(), running);

  const changed = useMemo(
    () => rows.flatMap((job) => job.results).filter((result) => result.change_status === "CONFIGURATION_CHANGED").length,
    [rows],
  );
  const unchanged = useMemo(
    () => rows.flatMap((job) => job.results).filter((result) => result.change_status === "NO_CHANGE").length,
    [rows],
  );
  const statuses = useMemo(() => Array.from(new Set(rows.map((job) => job.status))).sort(), [rows]);
  const latest = rows[0];

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return rows.filter((job) => {
      if (status && job.status !== status) return false;
      if (needle && !`${job.requested_by} ${job.job_id}`.toLowerCase().includes(needle)) return false;
      return true;
    });
  }, [rows, status, search]);

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.startBackup(selected);
      setSelected([]);
      jobs.reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to start backup");
    } finally {
      setBusy(false);
    }
  };

  if (!canOperate) {
    return (
      <div className="page">
        <RoleNotice needed="The operator or admin role" />
        <Panel title="Backups">
          <p className="notice">
            Backup jobs contain device configuration metadata, so the API only returns them to an operator or admin.
            Switch role in the account menu to read this page.
          </p>
        </Panel>
      </div>
    );
  }

  const start_ = page * pageSize;
  const shown = filtered.slice(start_, start_ + pageSize);
  const filtering = Boolean(status || search.trim());

  return (
    <div className="page">
      <ErrorBanner message={error ?? jobs.error} onDismiss={() => setError(null)} />

      <div className="kpis">
        <Kpi label="Jobs recorded" value={rows.length} icon="▤" foot="Manual and scheduled runs, in one history" />
        <Kpi
          label="Last run"
          value={relative(latest?.completed_at ?? latest?.created_at)}
          icon="✓"
          text
          tone={latest?.status === "SUCCESS" ? "good" : latest?.status === "FAILED" ? "crit" : latest ? "warn" : undefined}
          foot={
            latest
              ? `${latest.status.toLowerCase()} · ${latest.success_count} captured, ${latest.failure_count} failed`
              : "No backup job has run yet"
          }
        />
        <Kpi
          label="New versions written"
          value={changed}
          icon="＋"
          tone={changed > 0 ? "good" : undefined}
          foot="Across every job — the configuration had actually changed"
        />
        <Kpi
          label="Runs with no change"
          value={unchanged}
          icon="＝"
          foot="Identical to the newest stored version, so nothing was written"
        />
      </div>

      <div className="filters">
        <label>
          Contains
          <input
            value={search}
            placeholder="job id or requester"
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(0);
            }}
          />
        </label>
        <Select
          label="Job status"
          value={status}
          options={statuses}
          onChange={(value) => {
            setStatus(value);
            setPage(0);
          }}
          allLabel="All statuses"
        />
        <span className="spacer" />
        <button className="ghost" disabled={!filtering} onClick={() => { setStatus(""); setSearch(""); setPage(0); }}>
          Reset filters
        </button>
        <button className="primary" onClick={() => void start()} disabled={busy}>
          {busy ? "Starting…" : selected.length ? `Back up ${selected.length} selected` : "Back up now (all devices)"}
        </button>
      </div>

      <div className="split">
        <div>
          <Panel
            title="Backup jobs"
            note={running ? "A job is running — refreshing every few seconds" : `${filtered.length} of ${rows.length}`}
            provenance="GET /api/backups · the same service the scheduler calls, so scheduled runs appear here too"
            flush
          >
            {jobs.loading && rows.length === 0 ? (
              <Loading what="backup jobs" />
            ) : rows.length === 0 ? (
              <Empty message="No backup jobs yet. Use Back up now, or create a schedule." />
            ) : shown.length === 0 ? (
              <Empty message="No job matches these filters." />
            ) : (
              <>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th scope="col">Started</th>
                        <th scope="col">Requested by</th>
                        <th scope="col">Status</th>
                        <th scope="col">Devices</th>
                        <th scope="col">Captured</th>
                        <th scope="col">Failed</th>
                        <th scope="col">Duration</th>
                        <th scope="col" aria-label="Details" />
                      </tr>
                    </thead>
                    <tbody>
                      {shown.map((job) => (
                        <Fragment key={job.job_id}>
                          <tr>
                            <td title={time(job.started_at ?? job.created_at)}>
                              {relative(job.started_at ?? job.created_at)}
                              <br />
                              <code>{job.job_id.slice(0, 8)}</code>
                            </td>
                            <td>{job.requested_by}</td>
                            <td>
                              <Status value={job.status} />
                            </td>
                            <td className="num">{job.results.length || job.target_scope.length || "all"}</td>
                            <td className="num">{job.success_count}</td>
                            <td className="num">{job.failure_count}</td>
                            <td className="num">{duration(job)}</td>
                            <td>
                              <button
                                className="chev"
                                aria-label={expanded === job.job_id ? "Hide per-device results" : "Show per-device results"}
                                aria-expanded={expanded === job.job_id}
                                onClick={() => setExpanded(expanded === job.job_id ? null : job.job_id)}
                              >
                                {expanded === job.job_id ? "⌄" : "›"}
                              </button>
                            </td>
                          </tr>
                          {expanded === job.job_id && (
                            <tr className="detail-row">
                              <td colSpan={8}>
                                {job.results.length === 0 ? (
                                  <Empty message="This job has not produced per-device results yet." />
                                ) : (
                                  <table className="nested">
                                    <thead>
                                      <tr>
                                        <th scope="col">Device</th>
                                        <th scope="col">Result</th>
                                        <th scope="col">Change</th>
                                        <th scope="col">Version</th>
                                        <th scope="col">Duration</th>
                                        <th scope="col" aria-label="History" />
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {job.results.map((result) => (
                                        <tr key={`${job.job_id}-${result.device_id}`}>
                                          <td>{result.device}</td>
                                          <td>
                                            <Status value={result.status} />
                                          </td>
                                          <td>
                                            {result.change_status ? (
                                              <Status value={result.change_status.toLowerCase()} />
                                            ) : (
                                              (result.error_category ?? "—")
                                            )}
                                          </td>
                                          <td>{result.version_id ? <code>{result.version_id.slice(0, 8)}</code> : "—"}</td>
                                          <td className="num">{result.duration_seconds.toFixed(1)} s</td>
                                          <td>
                                            <button
                                              className="link"
                                              onClick={() => navigate("configurations", result.device_id)}
                                            >
                                              History
                                            </button>
                                          </td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                )}
                              </td>
                            </tr>
                          )}
                        </Fragment>
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
                  noun="jobs"
                />
              </>
            )}
          </Panel>
        </div>

        <aside className="rail-stack">
          <Panel
            title="Scope of the next run"
            note={selected.length ? `${selected.length} selected` : "All devices"}
            provenance="Selection is sent as device_ids on POST /api/backups"
          >
            {devices.loading ? (
              <Loading what="devices" />
            ) : (devices.data ?? []).length === 0 ? (
              <Empty message="No devices are registered yet." />
            ) : (
              <>
                <div className="chips">
                  {(devices.data ?? []).map((device: Device) => (
                    <label key={device.id} className={`chip${selected.includes(device.id) ? " on" : ""}`}>
                      <input
                        type="checkbox"
                        checked={selected.includes(device.id)}
                        onChange={() =>
                          setSelected((current) =>
                            current.includes(device.id)
                              ? current.filter((id) => id !== device.id)
                              : [...current, device.id],
                          )
                        }
                      />
                      {device.name}
                    </label>
                  ))}
                </div>
                {selected.length > 0 && (
                  <button className="ghost" style={{ marginTop: "12px" }} onClick={() => setSelected([])}>
                    Clear selection
                  </button>
                )}
              </>
            )}
          </Panel>

          <Panel title="How a version is decided">
            <p className="notice">
              The fetched configuration is hashed with SHA-256 and compared to the newest stored version. Identical
              content is recorded as <strong>no change</strong> and no new version is written; different content becomes
              a new immutable version with the previous one as its parent.
            </p>
            <p className="notice">
              Secrets are redacted on the server before the text is stored, so no password, key or community string
              reaches this browser or the version history.
            </p>
          </Panel>
        </aside>
      </div>
    </div>
  );
}
