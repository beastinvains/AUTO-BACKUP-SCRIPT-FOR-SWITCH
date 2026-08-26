/**
 * High performance SVG chart primitives for NETRA Network Security Auditor.
 */

import { useId, useRef, useState } from "react";
import type { ReactNode } from "react";

export type Tone = "series" | "good" | "warn" | "serious" | "crit" | "neutral" | "purple" | "blue";

export function toneColor(tone: Tone): string {
  switch (tone) {
    case "good":
      return "#10b981";
    case "warn":
      return "#f59e0b";
    case "serious":
      return "#f97316";
    case "crit":
      return "#ef4444";
    case "neutral":
      return "#64748b";
    case "purple":
      return "#8b5cf6";
    case "blue":
      return "#3b82f6";
    default:
      return "#10b981";
  }
}

export type Segment = {
  label: string;
  value: number;
  tone?: Tone;
  color?: string;
  percentage?: number;
};

/**
 * Donut Chart with center value & label, matching NETRA visual style.
 */
export function NetraDonut({
  segments,
  centerValue,
  centerLabel = "Total",
  size = 140,
  strokeWidth = 14,
  showLegend = true,
  emptyMessage = "No data recorded",
}: {
  segments: Segment[];
  centerValue?: number | string;
  centerLabel?: string;
  size?: number;
  strokeWidth?: number;
  showLegend?: boolean;
  emptyMessage?: string;
}) {
  const total = segments.reduce((sum, s) => sum + s.value, 0);
  const displayTotal = centerValue !== undefined ? centerValue : total;

  if (total <= 0) {
    return <p className="viz-empty" style={{ padding: "20px", textAlign: "center", color: "var(--ink-3)", fontSize: "0.82rem" }}>{emptyMessage}</p>;
  }

  const drawn = segments.filter((s) => s.value > 0);
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const gap = drawn.length > 1 ? 2 : 0;
  let consumed = 0;

  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "20px", width: "100%" }}>
      <div style={{ position: "relative", width: size, height: size, flexShrink: 0 }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="rgba(255, 255, 255, 0.06)"
            strokeWidth={strokeWidth}
          />
          <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
            {drawn.map((segment) => {
              const segColor = segment.color || (segment.tone ? toneColor(segment.tone) : "#10b981");
              const length = (segment.value / total) * circumference;
              const visible = Math.max(length - gap, 0.8);
              const offset = -consumed;
              consumed += length;

              return (
                <circle
                  key={segment.label}
                  cx={size / 2}
                  cy={size / 2}
                  r={radius}
                  fill="none"
                  stroke={segColor}
                  strokeWidth={strokeWidth}
                  strokeDasharray={`${visible} ${circumference - visible}`}
                  strokeDashoffset={offset}
                  strokeLinecap="butt"
                >
                  <title>{`${segment.label}: ${segment.value}`}</title>
                </circle>
              );
            })}
          </g>
          <text
            x={size / 2}
            y={size / 2 - 4}
            textAnchor="middle"
            dominantBaseline="middle"
            fill="#ffffff"
            style={{ fontSize: "1.35rem", fontWeight: "700", fontFamily: "var(--font-sans)" }}
          >
            {displayTotal}
          </text>
          <text
            x={size / 2}
            y={size / 2 + 14}
            textAnchor="middle"
            dominantBaseline="middle"
            fill="var(--ink-3)"
            style={{ fontSize: "0.68rem", fontWeight: "500", textTransform: "capitalize" }}
          >
            {centerLabel}
          </text>
        </svg>
      </div>

      {showLegend && (
        <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "8px", flex: 1 }}>
          {segments.map((segment) => {
            const segColor = segment.color || (segment.tone ? toneColor(segment.tone) : "#10b981");
            const pct = segment.percentage !== undefined
              ? segment.percentage
              : total > 0 ? Math.round((segment.value / total) * 100) : 0;

            return (
              <li
                key={segment.label}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  fontSize: "0.78rem",
                  color: "var(--ink-2)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span
                    style={{
                      width: "8px",
                      height: "8px",
                      borderRadius: "2px",
                      background: segColor,
                      display: "inline-block",
                      flexShrink: 0,
                    }}
                  />
                  <span>{segment.label}</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <strong style={{ color: "#ffffff", fontWeight: "600" }}>{segment.value}</strong>
                  {pct > 0 && <span style={{ color: "var(--ink-3)", fontSize: "0.72rem" }}>({pct}%)</span>}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export type TrendPoint = { label: string; caption?: string; value: number };

/**
 * Compliance Trend Chart (smooth line chart with area fill and percentage Y-axis)
 */
export function ComplianceTrendChart({
  points,
  rangeLabel = "Last 7 Days",
  onRangeChange,
}: {
  points: { date: string; value: number }[];
  rangeLabel?: string;
  onRangeChange?: (range: string) => void;
}) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const gradientId = useId();

  const width = 520;
  const height = 180;
  const pad = { top: 15, right: 20, bottom: 25, left: 35 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;

  const yTicks = [100, 75, 50, 25, 0];
  const stepX = points.length > 1 ? plotW / (points.length - 1) : 0;
  const getX = (idx: number) => pad.left + idx * stepX;
  const getY = (val: number) => pad.top + plotH - (val / 100) * plotH;

  const pathD = points
    .map((pt, idx) => `${idx === 0 ? "M" : "L"} ${getX(idx)} ${getY(pt.value)}`)
    .join(" ");

  const areaD = points.length > 0
    ? `${pathD} L ${getX(points.length - 1)} ${pad.top + plotH} L ${getX(0)} ${pad.top + plotH} Z`
    : "";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "10px", width: "100%" }}>
      <div style={{ position: "relative", width: "100%" }}>
        <svg
          viewBox={`0 0 ${width} ${height}`}
          style={{ width: "100%", height: "auto", overflow: "visible" }}
        >
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b981" stopOpacity="0.35" />
              <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines & Y-axis labels */}
          {yTicks.map((tick) => {
            const yPos = getY(tick);
            return (
              <g key={tick}>
                <line
                  x1={pad.left}
                  y1={yPos}
                  x2={width - pad.right}
                  y2={yPos}
                  stroke="rgba(255, 255, 255, 0.05)"
                  strokeDasharray={tick === 0 ? undefined : "3 3"}
                  strokeWidth="1"
                />
                <text
                  x={pad.left - 8}
                  y={yPos + 3}
                  textAnchor="end"
                  fill="var(--ink-3)"
                  style={{ fontSize: "10px", fontFamily: "var(--font-mono)" }}
                >
                  {tick}%
                </text>
              </g>
            );
          })}

          {/* Area Fill */}
          {areaD && <path d={areaD} fill={`url(#${gradientId})`} />}

          {/* Line Path */}
          {pathD && (
            <path
              d={pathD}
              fill="none"
              stroke="#10b981"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* Data Points */}
          {points.map((pt, idx) => {
            const cx = getX(idx);
            const cy = getY(pt.value);
            const isHover = hoverIndex === idx;
            return (
              <g key={idx} onMouseEnter={() => setHoverIndex(idx)} onMouseLeave={() => setHoverIndex(null)}>
                <circle
                  cx={cx}
                  cy={cy}
                  r={isHover ? 5 : 3.5}
                  fill="#10b981"
                  stroke="#080c14"
                  strokeWidth="2"
                  style={{ cursor: "pointer", transition: "all 0.15s ease" }}
                />
                {/* X-axis label */}
                <text
                  x={cx}
                  y={height - 6}
                  textAnchor="middle"
                  fill="var(--ink-3)"
                  style={{ fontSize: "10px", fontFamily: "var(--font-sans)" }}
                >
                  {pt.date}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Hover Tooltip */}
        {hoverIndex !== null && points[hoverIndex] && (
          <div
            style={{
              position: "absolute",
              top: `${(getY(points[hoverIndex].value) / height) * 100}%`,
              left: `${(getX(hoverIndex) / width) * 100}%`,
              transform: "translate(-50%, -120%)",
              background: "#141f32",
              border: "1px solid #10b981",
              borderRadius: "6px",
              padding: "4px 8px",
              fontSize: "0.75rem",
              color: "#ffffff",
              whiteSpace: "nowrap",
              boxShadow: "0 4px 12px rgba(0,0,0,0.5)",
              pointerEvents: "none",
              zIndex: 10,
            }}
          >
            <strong>{points[hoverIndex].date}</strong>: {points[hoverIndex].value}%
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Backward compatibility Donut alias
 */
export function Donut({
  segments,
  centreLabel = "Total",
  emptyMessage,
}: {
  segments: Segment[];
  centreLabel?: string;
  emptyMessage?: string;
}) {
  return <NetraDonut segments={segments} centerLabel={centreLabel} emptyMessage={emptyMessage} />;
}

/**
 * Backward compatibility Trend chart
 */
export function Trend({
  points,
  seriesLabel,
  emptyMessage,
}: {
  points: TrendPoint[];
  seriesLabel?: string;
  emptyMessage?: string;
}) {
  const compPoints = points.map((p) => ({ date: p.label, value: p.value }));
  return <ComplianceTrendChart points={compPoints} />;
}

export function BarList({
  items,
  emptyMessage = "No items",
}: {
  items: { label: string; value: number }[];
  emptyMessage?: string;
}) {
  if (items.length === 0) return <p style={{ color: "var(--ink-3)", fontSize: "0.8rem" }}>{emptyMessage}</p>;
  const max = Math.max(...items.map((item) => item.value), 1);

  return (
    <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "8px" }}>
      {items.map((item) => (
        <li key={item.label} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "10px", fontSize: "0.82rem" }}>
          <span style={{ color: "var(--ink-2)", width: "90px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {item.label}
          </span>
          <div style={{ flex: 1, height: "6px", background: "rgba(255,255,255,0.06)", borderRadius: "3px", overflow: "hidden" }}>
            <div
              style={{
                height: "100%",
                width: `${(item.value / max) * 100}%`,
                background: "var(--brand-emerald)",
                borderRadius: "3px",
              }}
            />
          </div>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: "var(--ink)" }}>{item.value}</span>
        </li>
      ))}
    </ul>
  );
}

export function Meter({
  label,
  value,
  total,
  tone = "good",
  note,
}: {
  label: string;
  value: number;
  total: number;
  tone?: Tone;
  note?: string;
}) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.82rem" }}>
        <span style={{ color: "var(--ink)" }}>{label}</span>
        <span style={{ fontFamily: "var(--font-mono)", color: "var(--ink-2)" }}>{value} / {total} ({pct}%)</span>
      </div>
      <div style={{ height: "6px", background: "rgba(255,255,255,0.06)", borderRadius: "3px", overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${pct}%`, background: toneColor(tone), borderRadius: "3px" }} />
      </div>
      {note && <span style={{ fontSize: "0.72rem", color: "var(--ink-3)" }}>{note}</span>}
    </div>
  );
}
