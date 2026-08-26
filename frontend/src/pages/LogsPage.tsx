/**
 * Audit log (Phase 3 section 15).
 *
 * A view over records the platform already writes — audit rows for discovery, backup, schedule,
 * device and system events — filtered by date, device, event type and status. Details are collapsed
 * by default, and the server has already removed secret-shaped keys and bulk command output, so
 * nothing sensitive is displayed by accident.
 *
 * Filtering happens on the server; the fetch limit says how many records were asked for, and
 * paging below walks the records that came back. Both numbers are shown so neither is mistaken for
 * the total in the database.
 */

import { Fragment, useMemo, useState } from "react";
import { api } from "../api";
import { BarList } from "../components/charts";
import { Empty, ErrorBanner, Kpi, Loading, Pager, Panel, Select, Status } from "../components/ui";
import { fromLocalInput, relative, time, titleCase } from "../format";
import { useAsync } from "../hooks";
import type { LogEvent, LogFilters } from "../types";

export function LogsPage({ navigate }: { navigate: (page: string, param?: string) => void }) {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [deviceId, setDeviceId] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [limit, setLimit] = useState(200);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);

  const options = useAsync(() => api.logOptions(), []);
  const filters: LogFilters = {
    start: fromLocalInput(start),
    end: fromLocalInput(end),
    device_id: deviceId || undefined,
    category: category || undefined,
    status: status || undefined,
    search: search || undefined,
    limit,
  };
  const events = useAsync(() => api.logs(filters), [start, end, deviceId, category, status, search, limit]);
  const rows = events.data ?? [];

  const failures = useMemo(() => rows.filter((event) => /fail|error/i.test(event.status ?? "")).length, [rows]);
  const actors = useMemo(() => new Set(rows.map((event) => event.actor).filter(Boolean)).size, [rows]);
  const byCategory = useMemo(() => {
    const tally = new Map<string, number>();
    for (const event of rows) tally.set(event.category, (tally.get(event.category) ?? 0) + 1);
    return Array.from(tally.entries())
      .map(([label, value]) => ({ label: titleCase(label), value }))
      .sort((left, right) => right.value - left.value);
  }, [rows]);
  const newest = rows[0]?.timestamp ?? null;
  const oldest = rows.length > 0 ? rows[rows.length - 1].timestamp : null;

  const filtering = Boolean(start || end || deviceId || category || status || search || limit !== 200);
  const reset = () => {
    setStart("");
    setEnd("");
    setDeviceId("");
    setCategory("");
    setStatus("");
    setSearch("");
    setLimit(200);
    setPage(0);
  };

  const from = page * pageSize;
  const shown = rows.slice(from, from + pageSize);

  return (
    <div className="page">
      <ErrorBanner message={events.error ?? options.error} />

      <div className="kpis">
        <Kpi
          label="Events returned"
          value={rows.length}
          icon="▤"
          foot={rows.length === limit ? `Capped by the fetch limit of ${limit} — raise it to see more` : "Everything matching these filters"}
        />
        <Kpi
          label="Failures in view"
          value={failures}
          icon="✕"
          tone={failures > 0 ? "crit" : "good"}
          foot={failures > 0 ? "Events whose status records a failure or error" : "No returned event recorded a failure"}
          onClick={() => {
            setStatus(status === "FAILED" ? "" : "FAILED");
            setPage(0);
          }}
        />
        <Kpi
          label="Distinct actors"
          value={actors}
          icon="◉"
          foot="Who or what performed the returned actions"
        />
        <Kpi
          label="Newest event"
          value={newest ? relative(newest) : "—"}
          icon="✓"
          text
          foot={
            newest && oldest
              ? `Range in view: ${time(oldest)} → ${time(newest)}`
              : "Nothing matched these filters"
          }
        />
      </div>

      <div className="filters">
        <label>
          From
          <input
            type="datetime-local"
            value={start}
            onChange={(event) => {
              setStart(event.target.value);
              setPage(0);
            }}
          />
        </label>
        <label>
          To
          <input
            type="datetime-local"
            value={end}
            onChange={(event) => {
              setEnd(event.target.value);
              setPage(0);
            }}
          />
        </label>
        <label>
          Device
          <select
            value={deviceId}
            onChange={(event) => {
              setDeviceId(event.target.value);
              setPage(0);
            }}
          >
            <option value="">All devices</option>
            {(options.data?.devices ?? []).map((device) => (
              <option key={device.id} value={device.id}>
                {device.name}
              </option>
            ))}
          </select>
        </label>
        <Select
          label="Event type"
          value={category}
          options={options.data?.categories ?? []}
          onChange={(value) => {
            setCategory(value);
            setPage(0);
          }}
          allLabel="All types"
        />
        <Select
          label="Status"
          value={status}
          options={options.data?.statuses ?? []}
          onChange={(value) => {
            setStatus(value);
            setPage(0);
          }}
          allLabel="All statuses"
        />
        <label>
          Contains
          <input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(0);
            }}
            placeholder="text or actor"
          />
        </label>
        <label>
          Fetch limit
          <select
            value={limit}
            onChange={(event) => {
              setLimit(Number(event.target.value));
              setPage(0);
            }}
          >
            {[50, 100, 200, 500, 1000].map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <span className="spacer" />
        <button className="ghost" onClick={() => exportCsv(rows)} disabled={rows.length === 0}>
          Export CSV
        </button>
        <button className="ghost" onClick={reset} disabled={!filtering}>
          Reset filters
        </button>
        <button className="ghost" onClick={events.reload}>
          Refresh
        </button>
      </div>

      <div className="split">
        <div>
          <Panel
            title="Events"
            note={`${rows.length} returned, newest first`}
            provenance="GET /api/logs · the stored audit record, unmodified · secret-shaped values and raw command output are removed before storage"
            flush
          >
            {events.loading && rows.length === 0 ? (
              <Loading what="events" />
            ) : rows.length === 0 ? (
              <Empty message="No events match these filters." />
            ) : (
              <>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th scope="col">When</th>
                        <th scope="col">Type</th>
                        <th scope="col">Event</th>
                        <th scope="col">Device</th>
                        <th scope="col">Actor</th>
                        <th scope="col">Status</th>
                        <th scope="col">Summary</th>
                        <th scope="col" aria-label="Details" />
                      </tr>
                    </thead>
                    <tbody>
                      {shown.map((event) => {
                        const hasDetails = Object.keys(event.details).length > 0;
                        return (
                          <Fragment key={event.id}>
                            <tr>
                              <td title={time(event.timestamp)}>{relative(event.timestamp)}</td>
                              <td>{titleCase(event.category)}</td>
                              <td>
                                <code>{event.event}</code>
                              </td>
                              <td>
                                {event.device_id ? (
                                  <button className="link" onClick={() => navigate("devices", event.device_id ?? undefined)}>
                                    {event.device ?? event.device_id}
                                  </button>
                                ) : (
                                  "—"
                                )}
                              </td>
                              <td>{event.actor}</td>
                              <td>
                                <Status value={event.status} />
                              </td>
                              <td>{event.summary}</td>
                              <td>
                                {hasDetails ? (
                                  <button
                                    className="chev"
                                    aria-label={expanded === event.id ? "Hide details" : "Show details"}
                                    aria-expanded={expanded === event.id}
                                    onClick={() => setExpanded(expanded === event.id ? null : event.id)}
                                  >
                                    {expanded === event.id ? "⌄" : "›"}
                                  </button>
                                ) : null}
                              </td>
                            </tr>
                            {expanded === event.id && hasDetails && (
                              <tr className="detail-row">
                                <td colSpan={8}>
                                  <dl className="details">
                                    {Object.entries(event.details).map(([key, value]) => (
                                      <div key={key}>
                                        <dt>{key}</dt>
                                        <dd>{typeof value === "object" ? JSON.stringify(value) : String(value)}</dd>
                                      </div>
                                    ))}
                                  </dl>
                                </td>
                              </tr>
                            )}
                          </Fragment>
                        );
                      })}
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
                  noun="events"
                />
              </>
            )}
          </Panel>
        </div>

        <aside className="rail-stack">
          <Panel title="Events by type" provenance="Counted from the records currently returned">
            <BarList items={byCategory} emptyMessage="No events matched these filters." />
          </Panel>

          <Panel title="What the log does not contain">
            <p className="notice">
              Passwords, SSH keys, community strings and environment values are removed before an event is written, and
              raw command output is never stored. A detail row therefore shows metadata, not device output.
            </p>
            <p className="notice">
              Records are append-only. Nothing on this page edits or deletes an event; Export CSV saves the rows in view
              to your own machine and uploads nothing.
            </p>
          </Panel>
        </aside>
      </div>
    </div>
  );
}

/** Save the returned rows as CSV locally. The rows are already in the page, so nothing is sent. */
function exportCsv(rows: LogEvent[]): void {
  const header = ["timestamp", "category", "event", "device", "actor", "status", "summary"];
  const escape = (value: string) => `"${value.replace(/"/g, '""')}"`;
  const body = rows.map((event) =>
    [
      event.timestamp ?? "",
      event.category,
      event.event,
      event.device ?? "",
      event.actor,
      event.status ?? "",
      event.summary ?? "",
    ]
      .map((value) => escape(String(value)))
      .join(","),
  );
  const blob = new Blob([[header.join(","), ...body].join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `audit-log-${new Date().toISOString().slice(0, 10)}.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}
