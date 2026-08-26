/**
 * Presentational building blocks for NETRA Network Security Auditor.
 */

import type { ReactNode } from "react";
import { statusIcon, titleCase } from "../format";
import {
  AlertTriangleIcon,
  CheckCircleIcon,
  ChevronRightIcon,
  FanIcon,
  PowerIcon,
  ShieldAlertIcon,
  SparklesIcon,
  TempIcon,
} from "./icons";

export type Severity = "critical" | "serious" | "warning" | "info";

/**
 * Status Pill with glyph and color reinforcement.
 */
export function Status({ value }: { value?: string | null }) {
  const label = (value || "unknown").toLowerCase();
  const isGood = label === "online" || label === "success" || label === "healthy" || label === "resolved";
  const isWarn = label === "warning" || label === "degraded" || label === "acknowledged" || label === "partial";
  const isCrit = label === "offline" || label === "failed" || label === "critical" || label === "new";

  const cls = isGood ? "resolved" : isWarn ? "warning" : isCrit ? "critical" : "info";

  return (
    <span className={`badge ${cls}`}>
      <span aria-hidden="true">{statusIcon(label)}</span>
      <span>{titleCase(label)}</span>
    </span>
  );
}

export function SeverityBadge({ level }: { level: Severity | string }) {
  const key = level.toLowerCase();
  const cls = key === "critical" ? "critical" : key === "warning" || key === "serious" ? "warning" : "info";
  return (
    <span className={`badge ${cls}`}>
      {cls === "critical" ? <ShieldAlertIcon size={12} /> : <AlertTriangleIcon size={12} />}
      <span>{titleCase(level)}</span>
    </span>
  );
}

export function NetraBadge({
  type,
  label,
  score,
}: {
  type: "critical" | "warning" | "info" | "ai" | "system" | "new" | "acknowledged" | "resolved" | "score";
  label?: ReactNode;
  score?: number | string;
}) {
  if (type === "score") {
    return <span className="ai-score-pill">{score ?? label}%</span>;
  }

  return (
    <span className={`badge ${type}`}>
      {type === "ai" && <SparklesIcon size={11} />}
      <span>{label || titleCase(type)}</span>
    </span>
  );
}

/**
 * KPI Stat Card matching NETRA design
 */
export function StatCard({
  label,
  value,
  icon,
  iconTone = "green",
  indicators,
  onClick,
}: {
  label: string;
  value: ReactNode;
  icon: ReactNode;
  iconTone?: "green" | "purple" | "amber" | "blue" | "red";
  indicators?: { text: ReactNode; tone?: "green" | "red" | "amber" | "blue"; dot?: boolean }[];
  onClick?: () => void;
}) {
  const body = (
    <article className="stat-card" style={onClick ? { cursor: "pointer" } : undefined}>
      <div className="stat-card-top">
        <span className="stat-card-label">{label}</span>
        <div className={`stat-icon-wrap ${iconTone}`}>{icon}</div>
      </div>
      <div className="stat-value">{value}</div>
      {indicators && indicators.length > 0 && (
        <div className="stat-card-foot">
          {indicators.map((ind, i) => (
            <span key={i} className={`stat-indicator ${ind.tone || "green"}`}>
              {ind.dot && <span className={`dot-indicator ${ind.tone || "green"}`} />}
              {ind.text}
            </span>
          ))}
        </div>
      )}
    </article>
  );

  if (onClick) {
    return (
      <div onClick={onClick} role="button" tabIndex={0} style={{ display: "contents" }}>
        {body}
      </div>
    );
  }
  return body;
}

/** Backward compatibility Kpi */
export function Kpi({
  label,
  value,
  icon,
  tone,
  foot,
  text,
  onClick,
}: {
  label: string;
  value: ReactNode;
  icon: string | ReactNode;
  tone?: "good" | "warn" | "serious" | "crit";
  foot?: ReactNode;
  text?: boolean;
  onClick?: () => void;
}) {
  const iconTone = tone === "crit" ? "red" : tone === "serious" || tone === "warn" ? "amber" : "green";
  return (
    <StatCard
      label={label}
      value={value}
      icon={<span style={{ fontSize: "1.1rem" }}>{icon}</span>}
      iconTone={iconTone}
      indicators={foot ? [{ text: foot, tone: iconTone }] : undefined}
      onClick={onClick}
    />
  );
}

/**
 * Device Hardware Telemetry Card (Carousel card)
 */
export function HardwareTelemetryCard({
  name,
  type,
  vendor,
  status,
  temp,
  power,
  powerFail,
  fan,
  fanFail,
  alertsCount,
  onClick,
}: {
  name: string;
  type: string;
  vendor: string;
  status: "online" | "warning" | "critical";
  temp?: string;
  power?: string;
  powerFail?: boolean;
  fan?: string;
  fanFail?: boolean;
  alertsCount?: number;
  onClick?: () => void;
}) {
  const isCrit = status === "critical";
  const isWarn = status === "warning";

  return (
    <div
      className={`telemetry-card ${status}`}
      onClick={onClick}
      style={{ cursor: onClick ? "pointer" : "default" }}
    >
      <div className="telemetry-card-top">
        <div>
          <div className="device-title">{name}</div>
          <div className="device-vendor">{type} • {vendor}</div>
        </div>
        <span className={`badge ${status}`}>
          <span className={`dot-indicator ${isCrit ? "red" : isWarn ? "amber" : "green"}`} />
          {titleCase(status)}
        </span>
      </div>

      <div className="telemetry-metrics-grid">
        <div className="telemetry-metric">
          <TempIcon size={14} />
          <span>Temp</span>
          <strong className={isCrit ? "fail" : ""}>{temp || "42°C"}</strong>
        </div>
        <div className="telemetry-metric">
          <PowerIcon size={14} />
          <span>Power</span>
          <strong className={powerFail ? "fail" : ""}>{power || "OK"}</strong>
        </div>
        {fan && (
          <div className="telemetry-metric" style={{ gridColumn: "span 2" }}>
            <FanIcon size={14} />
            <span>Fan</span>
            <strong className={fanFail ? "fail" : ""}>{fan}</strong>
          </div>
        )}
      </div>

      <div className={`telemetry-card-foot ${isCrit ? "crit" : isWarn ? "warn" : "good"}`}>
        {alertsCount && alertsCount > 0 ? (
          <>
            <span className={`dot-indicator ${isCrit ? "red" : "amber"}`} />
            <span>{alertsCount} active {alertsCount === 1 ? "alert" : "alerts"}</span>
          </>
        ) : (
          <>
            <CheckCircleIcon size={14} />
            <span>No active alerts</span>
          </>
        )}
      </div>
    </div>
  );
}

/**
 * Standard Panel container
 */
export function Panel({
  title,
  note,
  actions,
  provenance,
  flush,
  children,
}: {
  title: string;
  note?: string;
  actions?: ReactNode;
  provenance?: string;
  flush?: boolean;
  children: ReactNode;
}) {
  return (
    <section className="netra-panel" style={flush ? { padding: "0", overflow: "hidden" } : undefined}>
      <div className="netra-panel-header" style={flush ? { padding: "16px 20px 0" } : undefined}>
        <div className="panel-title-wrap">
          <h2 className="panel-title">{title}</h2>
          {note ? <span className="panel-subtitle">{note}</span> : null}
        </div>
        {actions ? <div>{actions}</div> : null}
      </div>
      {provenance ? (
        <p style={{ fontSize: "0.72rem", color: "var(--ink-3)", fontFamily: "var(--font-mono)", padding: flush ? "0 20px" : "0" }}>
          {provenance}
        </p>
      ) : null}
      <div style={flush ? { width: "100%" } : undefined}>{children}</div>
    </section>
  );
}

export function ErrorBanner({ message, onDismiss }: { message?: string | null; onDismiss?: () => void }) {
  if (!message) return null;
  return (
    <div style={{ background: "var(--crit-wash)", border: "1px solid rgba(239, 68, 68, 0.4)", borderRadius: "var(--radius-control)", padding: "10px 14px", color: "var(--crit-light)", fontSize: "0.82rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <span>{message}</span>
      {onDismiss && (
        <button className="panel-link" onClick={onDismiss} style={{ color: "var(--crit-light)" }}>
          dismiss
        </button>
      )}
    </div>
  );
}

export function Empty({ message }: { message: string }) {
  return <p style={{ padding: "24px", textAlign: "center", color: "var(--ink-3)", fontSize: "0.84rem" }}>{message}</p>;
}

export function Loading({ what }: { what: string }) {
  return (
    <div style={{ padding: "32px", display: "flex", alignItems: "center", justifyContent: "center", gap: "10px", color: "var(--ink-2)", fontSize: "0.88rem" }}>
      <div style={{ width: "18px", height: "18px", borderRadius: "50%", border: "2px solid rgba(16, 185, 129, 0.3)", borderTopColor: "var(--brand-emerald)", animation: "spin 0.8s linear infinite" }} />
      <span>Loading {what}…</span>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

export function Select({
  label,
  value,
  options,
  onChange,
  allLabel = "All",
  format = titleCase,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
  allLabel?: string;
  format?: (value: string) => string;
}) {
  return (
    <label style={{ display: "inline-flex", alignItems: "center", gap: "8px", fontSize: "0.82rem", color: "var(--ink-2)" }}>
      <span>{label}</span>
      <select
        className="filter-select"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">{allLabel}</option>
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {format(opt)}
          </option>
        ))}
      </select>
    </label>
  );
}

export function Pager({
  total,
  page,
  pageSize,
  onPage,
  onPageSize,
  noun = "items",
}: {
  total: number;
  page: number;
  pageSize: number;
  onPage: (page: number) => void;
  onPageSize?: (size: number) => void;
  noun?: string;
}) {
  const pages = Math.max(Math.ceil(total / pageSize), 1);
  return (
    <div className="table-pagination">
      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        <span>
          Showing {total === 0 ? 0 : page * pageSize + 1}–{Math.min((page + 1) * pageSize, total)} of {total} {noun}
        </span>
        {onPageSize && (
          <label style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span>Rows:</span>
            <select
              className="filter-select"
              value={pageSize}
              onChange={(e) => onPageSize(Number(e.target.value))}
              style={{ padding: "2px 6px", fontSize: "0.76rem" }}
            >
              {[10, 25, 50, 100].map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      <div className="pagination-controls">
        <button
          className="page-num-btn"
          disabled={page <= 0}
          onClick={() => onPage(page - 1)}
        >
          ‹
        </button>
        {Array.from({ length: Math.min(pages, 5) }).map((_, i) => (
          <button
            key={i}
            className={`page-num-btn${page === i ? " active" : ""}`}
            onClick={() => onPage(i)}
          >
            {i + 1}
          </button>
        ))}
        {pages > 5 && <span style={{ padding: "0 4px" }}>…</span>}
        <button
          className="page-num-btn"
          disabled={page >= pages - 1}
          onClick={() => onPage(page + 1)}
        >
          ›
        </button>
      </div>
    </div>
  );
}

export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{title}</h3>
          <button
            className="action-icon-btn"
            onClick={onClose}
            style={{ fontSize: "1.2rem", lineHeight: 1 }}
          >
            ✕
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}

export function Drawer({
  title,
  subtitle,
  onClose,
  children,
}: {
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div className="drawer-panel" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-header">
          <div>
            <h3 style={{ fontSize: "1.1rem", fontWeight: "600", color: "var(--ink-heading)" }}>{title}</h3>
            {subtitle && <p style={{ fontSize: "0.75rem", color: "var(--ink-3)", marginTop: "2px" }}>{subtitle}</p>}
          </div>
          <button className="action-icon-btn" onClick={onClose} aria-label="Close drawer">
            ✕
          </button>
        </div>
        <div className="drawer-body">{children}</div>
      </div>
    </div>
  );
}

export function KeyValues({ rows }: { rows: { label: string; value: ReactNode }[] }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
      {rows.map((row) => (
        <div
          key={row.label}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            fontSize: "0.82rem",
            borderBottom: "1px solid var(--line-subtle)",
            paddingBottom: "8px",
          }}
        >
          <span style={{ color: "var(--ink-2)" }}>{row.label}</span>
          <span style={{ fontWeight: "500", color: "var(--ink)" }}>{row.value}</span>
        </div>
      ))}
    </div>
  );
}

export function Fact({
  label,
  value,
  caption,
  children,
}: {
  label: string;
  value?: ReactNode;
  caption?: ReactNode;
  children?: ReactNode;
}) {
  const content = children !== undefined ? children : value;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "3px" }}>
      <span style={{ fontSize: "0.72rem", color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.04em" }}>{label}</span>
      <div style={{ fontSize: "0.95rem", fontWeight: "600", color: "var(--ink-heading)" }}>{content}</div>
      {caption && <span style={{ fontSize: "0.72rem", color: "var(--ink-2)" }}>{caption}</span>}
    </div>
  );
}

export function RoleNotice({ needed }: { needed: string }) {
  return (
    <div style={{ background: "var(--warn-wash)", border: "1px solid rgba(245, 158, 11, 0.3)", borderRadius: "var(--radius-control)", padding: "12px 16px", color: "var(--warn-light)", fontSize: "0.84rem", marginBottom: "16px" }}>
      <strong>Permission required:</strong> {needed} is needed to perform actions on this section.
    </div>
  );
}

export function Tabs<T extends string = string>({
  tabs,
  active,
  onChange,
  onSelect,
}: {
  tabs: { id: T; label: string; count?: number }[];
  active: T;
  onChange?: (id: T) => void;
  onSelect?: (id: T) => void;
}) {
  const handleSelect = (id: T) => {
    if (onChange) onChange(id);
    if (onSelect) onSelect(id);
  };
  return (
    <div className="tabs-bar">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          className={`tab-btn${active === tab.id ? " active" : ""}`}
          onClick={() => handleSelect(tab.id)}
        >
          {tab.label} {tab.count !== undefined ? `(${tab.count})` : ""}
        </button>
      ))}
    </div>
  );
}
