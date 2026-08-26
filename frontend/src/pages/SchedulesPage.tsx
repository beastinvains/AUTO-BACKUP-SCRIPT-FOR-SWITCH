/**
 * Schedules.
 *
 * A schedule row only says *when* and *on which devices*. Running it calls `ScheduleService.run`,
 * which calls the Phase 2 `BackupService` — the same code path the Backups page uses, so there is
 * no second scheduled-backup implementation to drift from it. A schedule that has run links to the
 * job it produced.
 *
 * Times are stored and shown in UTC, so a run does not move when the host's timezone does.
 */

import { useMemo, useState } from "react";
import { api } from "../api";
import {
  Empty,
  ErrorBanner,
  KeyValues,
  Kpi,
  Loading,
  Modal,
  Pager,
  Panel,
  RoleNotice,
  Select,
  Status,
} from "../components/ui";
import { WEEKDAYS, relative, time } from "../format";
import { useAsync } from "../hooks";
import type { Role, Schedule, ScheduleInput } from "../types";

function blank(): ScheduleInput {
  return { name: "", frequency: "daily", run_at: "02:00", day_of_week: null, device_ids: [], enabled: true };
}

function fromSchedule(schedule: Schedule): ScheduleInput {
  return {
    name: schedule.name,
    frequency: schedule.frequency,
    run_at: schedule.run_at,
    day_of_week: schedule.day_of_week,
    device_ids: [...schedule.device_ids],
    enabled: schedule.enabled,
  };
}

/** Earliest future run among the enabled schedules, or null if nothing is armed. */
function soonest(schedules: Schedule[]): string | null {
  const times = schedules
    .filter((schedule) => schedule.enabled && schedule.next_run_at)
    .map((schedule) => schedule.next_run_at as string)
    .sort();
  return times[0] ?? null;
}

export function SchedulesPage({ role, navigate }: { role: Role; navigate: (page: string, param?: string) => void }) {
  const schedules = useAsync(() => api.schedules(), []);
  const devices = useAsync(() => api.devices(), []);
  const scheduler = useAsync(() => api.schedulerStatus().catch(() => null), []);
  const [editing, setEditing] = useState<Schedule | null>(null);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [frequency, setFrequency] = useState("");
  const [state, setState] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(10);

  const isAdmin = role === "admin";
  const canRun = role === "admin" || role === "operator";
  const rows = schedules.data ?? [];

  const enabled = rows.filter((schedule) => schedule.enabled).length;
  const next = soonest(rows);
  const lastRun = useMemo(
    () =>
      rows
        .filter((schedule) => schedule.last_run_at)
        .sort((left, right) => (right.last_run_at ?? "").localeCompare(left.last_run_at ?? ""))[0] ?? null,
    [rows],
  );

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return rows.filter((schedule) => {
      if (frequency && schedule.frequency !== frequency) return false;
      if (state === "enabled" && !schedule.enabled) return false;
      if (state === "disabled" && schedule.enabled) return false;
      if (needle && !`${schedule.name} ${schedule.scope} ${schedule.device_names.join(" ")}`.toLowerCase().includes(needle))
        return false;
      return true;
    });
  }, [rows, frequency, state, search]);

  const act = async (label: string, action: () => Promise<string>) => {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      setMessage(await action());
      schedules.reload();
      scheduler.reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : `Unable to ${label}`);
    } finally {
      setBusy(false);
    }
  };

  const toggle = (schedule: Schedule) =>
    void act("change the schedule", async () => {
      await api.setScheduleEnabled(schedule.id, !schedule.enabled);
      return `${schedule.name} is now ${schedule.enabled ? "disabled" : "enabled"}.`;
    });

  const remove = (schedule: Schedule) => {
    if (!window.confirm(`Delete schedule "${schedule.name}"? Existing backups are not affected.`)) return;
    void act("delete the schedule", async () => {
      await api.deleteSchedule(schedule.id);
      return `Deleted schedule ${schedule.name}. Its stored backups were not touched.`;
    });
  };

  const runNow = (schedule: Schedule) =>
    void act("run the schedule", async () => {
      await api.runSchedule(schedule.id);
      return `${schedule.name} started. It runs through the same backup service as a manual backup — follow it on the Backups page.`;
    });

  const start = page * pageSize;
  const shown = filtered.slice(start, start + pageSize);
  const filtering = Boolean(frequency || state || search.trim());

  return (
    <div className="page">
      <ErrorBanner message={error ?? schedules.error} onDismiss={() => setError(null)} />
      {message && (
        <p className="notice" role="status">
          {message}
        </p>
      )}
      {!isAdmin && <RoleNotice needed="The admin role" />}

      <div className="kpis">
        <Kpi
          label="Schedules armed"
          value={`${enabled} / ${rows.length}`}
          icon="◷"
          tone={rows.length === 0 ? "warn" : enabled === 0 ? "warn" : "good"}
          foot={rows.length === 0 ? "Nothing is scheduled — backups only run when started by hand" : "Enabled of configured"}
        />
        <Kpi
          label="Next run"
          value={next ? relative(next) : "—"}
          icon="→"
          text
          foot={next ? `${time(next)} · UTC` : "No enabled schedule has a next run"}
        />
        <Kpi
          label="Scheduler loop"
          value={scheduler.data ? (scheduler.data.running ? "running" : "stopped") : "unknown"}
          icon="⟳"
          text
          tone={scheduler.data?.running ? "good" : scheduler.data ? "crit" : "warn"}
          foot={
            scheduler.data
              ? `Ticks every ${scheduler.data.tick_seconds}s · ${scheduler.data.due_now} due now`
              : "Scheduler state is not readable with this role"
          }
        />
        <Kpi
          label="Last scheduled run"
          value={lastRun ? relative(lastRun.last_run_at) : "—"}
          icon="✓"
          text
          tone={
            lastRun?.last_status === "SUCCESS"
              ? "good"
              : lastRun?.last_status === "FAILED"
                ? "crit"
                : lastRun
                  ? "warn"
                  : undefined
          }
          foot={
            lastRun
              ? `${lastRun.name} · ${(lastRun.last_status ?? "unknown").toLowerCase()}`
              : "No schedule has run yet"
          }
          onClick={lastRun ? () => navigate("backups") : undefined}
        />
      </div>

      <div className="filters">
        <label>
          Contains
          <input
            value={search}
            placeholder="schedule or device name"
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(0);
            }}
          />
        </label>
        <Select
          label="Cadence"
          value={frequency}
          options={["hourly", "daily", "weekly"]}
          onChange={(value) => {
            setFrequency(value);
            setPage(0);
          }}
          allLabel="Any cadence"
        />
        <Select
          label="State"
          value={state}
          options={["enabled", "disabled"]}
          onChange={(value) => {
            setState(value);
            setPage(0);
          }}
          allLabel="Enabled and disabled"
        />
        <span className="spacer" />
        <button
          className="ghost"
          disabled={!filtering}
          onClick={() => {
            setFrequency("");
            setState("");
            setSearch("");
            setPage(0);
          }}
        >
          Reset filters
        </button>
        {isAdmin && (
          <button className="primary" onClick={() => setAdding(true)}>
            Create schedule
          </button>
        )}
      </div>

      <div className="split">
        <div>
          <Panel
            title="Schedules"
            note={`${filtered.length} of ${rows.length}`}
            provenance="GET /api/schedules · run times are UTC · a run calls the Phase 2 backup service"
            flush
          >
            {schedules.loading && rows.length === 0 ? (
              <Loading what="schedules" />
            ) : rows.length === 0 ? (
              <Empty message="No schedules yet. Create one to back up on a cadence instead of by hand." />
            ) : shown.length === 0 ? (
              <Empty message="No schedule matches these filters." />
            ) : (
              <>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th scope="col">Name</th>
                        <th scope="col">Cadence</th>
                        <th scope="col">Target devices</th>
                        <th scope="col">Next run</th>
                        <th scope="col">Last run</th>
                        <th scope="col">Last result</th>
                        <th scope="col">State</th>
                        <th scope="col" aria-label="Actions" />
                      </tr>
                    </thead>
                    <tbody>
                      {shown.map((schedule) => (
                        <tr key={schedule.id}>
                          <td>
                            <strong>{schedule.name}</strong>
                            <br />
                            <code className="rule">created by {schedule.created_by}</code>
                          </td>
                          <td>{schedule.cadence}</td>
                          <td title={schedule.device_names.join(", ") || "Every managed device at run time"}>
                            {schedule.scope}
                          </td>
                          <td title={schedule.enabled ? time(schedule.next_run_at) : "Disabled schedules are not armed"}>
                            {schedule.enabled ? relative(schedule.next_run_at) : "—"}
                          </td>
                          <td title={time(schedule.last_run_at)}>{relative(schedule.last_run_at)}</td>
                          <td>
                            {schedule.last_status ? (
                              schedule.last_job_id ? (
                                <button className="link" onClick={() => navigate("backups")}>
                                  <Status value={schedule.last_status} />
                                </button>
                              ) : (
                                <Status value={schedule.last_status} />
                              )
                            ) : (
                              "—"
                            )}
                          </td>
                          <td>
                            <Status value={schedule.enabled ? "enabled" : "disabled"} />
                          </td>
                          <td className="row-actions">
                            {canRun && (
                              <button className="link" onClick={() => runNow(schedule)} disabled={busy}>
                                Run now
                              </button>
                            )}
                            {isAdmin && (
                              <>
                                <button className="link" onClick={() => setEditing(schedule)}>
                                  Edit
                                </button>
                                <button className="link" onClick={() => toggle(schedule)} disabled={busy}>
                                  {schedule.enabled ? "Disable" : "Enable"}
                                </button>
                                <button className="link danger" onClick={() => remove(schedule)} disabled={busy}>
                                  Delete
                                </button>
                              </>
                            )}
                            {!canRun && <span className="muted">view only</span>}
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
                  noun="schedules"
                />
              </>
            )}
          </Panel>
        </div>

        <aside className="rail-stack">
          <Panel title="Scheduler" provenance="GET /api/scheduler">
            {scheduler.data ? (
              <KeyValues
                rows={[
                  { label: "Loop", value: <Status value={scheduler.data.running ? "running" : "offline"} /> },
                  { label: "Tick", value: `${scheduler.data.tick_seconds}s` },
                  { label: "Due now", value: scheduler.data.due_now },
                  { label: "Schedules armed", value: `${enabled} / ${rows.length}` },
                  { label: "Next run (UTC)", value: time(next) },
                ]}
              />
            ) : (
              <Empty message="Scheduler state is not readable with this role." />
            )}
            {scheduler.data && !scheduler.data.running && (
              <p className="notice">
                The loop is not running, so nothing will fire on its own. Start the backend with the scheduler enabled, or
                use <strong>Run now</strong> for a one-off run.
              </p>
            )}
          </Panel>

          <Panel title="What a run actually does">
            <p className="notice">
              A due schedule calls the same backup service a manual run calls. Every scheduled run therefore appears in
              the Backups job history with <code>scheduler</code> as the requester, and produces a new version only when
              the configuration has changed.
            </p>
            <p className="notice">
              Deleting a schedule stops future runs. Versions and jobs it already produced are immutable and stay in the
              history.
            </p>
          </Panel>
        </aside>
      </div>

      {(adding || editing) && (
        <ScheduleForm
          schedule={editing}
          devices={(devices.data ?? []).map((device) => ({ id: device.id, name: device.name }))}
          onClose={() => {
            setAdding(false);
            setEditing(null);
          }}
          onSaved={(name) => {
            setAdding(false);
            setEditing(null);
            setMessage(`Saved schedule ${name}.`);
            schedules.reload();
            scheduler.reload();
          }}
        />
      )}
    </div>
  );
}

function ScheduleForm({
  schedule,
  devices,
  onClose,
  onSaved,
}: {
  schedule: Schedule | null;
  devices: { id: string; name: string }[];
  onClose: () => void;
  onSaved: (name: string) => void;
}) {
  const [input, setInput] = useState<ScheduleInput>(schedule ? fromSchedule(schedule) : blank());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const set = <K extends keyof ScheduleInput>(key: K, value: ScheduleInput[K]) =>
    setInput((current) => ({ ...current, [key]: value }));

  const submit = async () => {
    if (!input.name.trim()) {
      setError("Name is required.");
      return;
    }
    if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(input.run_at)) {
      setError("Run time must be HH:MM in 24-hour UTC.");
      return;
    }
    if (input.frequency === "weekly" && input.day_of_week === null) {
      setError("Weekly schedules need a day of the week.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const payload: ScheduleInput = {
        ...input,
        name: input.name.trim(),
        day_of_week: input.frequency === "weekly" ? input.day_of_week : null,
      };
      const saved = schedule ? await api.updateSchedule(schedule.id, payload) : await api.createSchedule(payload);
      onSaved(saved.name);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to save schedule");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title={schedule ? `Edit ${schedule.name}` : "Create schedule"} onClose={onClose}>
      <ErrorBanner message={error} />
      <div className="form-grid">
        <label>
          Name
          <input value={input.name} onChange={(event) => set("name", event.target.value)} autoFocus />
        </label>
        <label>
          Frequency
          <select
            value={input.frequency}
            onChange={(event) => set("frequency", event.target.value as ScheduleInput["frequency"])}
          >
            <option value="hourly">Hourly</option>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
          </select>
        </label>
        <label>
          Run at (UTC)
          <input value={input.run_at} onChange={(event) => set("run_at", event.target.value)} placeholder="02:00" />
          <small>{input.frequency === "hourly" ? "Only the minutes are used for an hourly schedule." : "24-hour HH:MM."}</small>
        </label>
        {input.frequency === "weekly" && (
          <label>
            Day of week
            <select
              value={input.day_of_week ?? ""}
              onChange={(event) => set("day_of_week", event.target.value === "" ? null : Number(event.target.value))}
            >
              <option value="">Select a day</option>
              {WEEKDAYS.map((day, index) => (
                <option key={day} value={index}>
                  {day}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="wide">
          Target devices
          <small>Select none to back up every managed device at run time.</small>
          <div className="chips">
            {devices.map((device) => (
              <label key={device.id} className={`chip${input.device_ids.includes(device.id) ? " on" : ""}`}>
                <input
                  type="checkbox"
                  checked={input.device_ids.includes(device.id)}
                  onChange={() =>
                    set(
                      "device_ids",
                      input.device_ids.includes(device.id)
                        ? input.device_ids.filter((id) => id !== device.id)
                        : [...input.device_ids, device.id],
                    )
                  }
                />
                {device.name}
              </label>
            ))}
          </div>
        </label>
      </div>

      <label className="inline">
        <input type="checkbox" checked={input.enabled} onChange={(event) => set("enabled", event.target.checked)} />
        Enabled
      </label>

      <div className="form-actions">
        <button className="ghost" onClick={onClose} disabled={busy}>
          Cancel
        </button>
        <button className="primary" onClick={() => void submit()} disabled={busy}>
          {busy ? "Saving…" : schedule ? "Save changes" : "Create schedule"}
        </button>
      </div>
    </Modal>
  );
}
