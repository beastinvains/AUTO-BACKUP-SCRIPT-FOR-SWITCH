/** Presentation helpers shared by every page. No data fetching and no business rules here. */

/** Backend timestamps are UTC; render them in the operator's locale. */
export function time(value?: string | null): string {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "—" : parsed.toLocaleString();
}

export function relative(value?: string | null): string {
  if (!value) return "never";
  const parsed = new Date(value).getTime();
  if (Number.isNaN(parsed)) return "never";
  const seconds = Math.round((Date.now() - parsed) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} h ago`;
  return `${Math.round(hours / 24)} d ago`;
}

/** Hashes are 64 hex characters; show a recognisable prefix and keep the rest in a tooltip. */
export function shortHash(value: string): string {
  return `${value.slice(0, 12)}…`;
}

export function bytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

export function titleCase(value: string): string {
  return value.replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

/**
 * Glyph for a status, so status is never carried by colour alone (Phase 3 section 9).
 * The pill renders this next to the status word itself.
 */
export function statusIcon(value: string): string {
  switch (value.toLowerCase()) {
    case "online":
    case "success":
    case "reachable":
      return "●";
    case "offline":
    case "failed":
    case "unreachable":
      return "✕";
    case "degraded":
    case "partial":
      return "▲";
    case "running":
    case "pending":
      return "◌";
    default:
      return "○";
  }
}

/** Short label for a device type, used inside topology nodes where space is tight. */
export function typeGlyph(value: string): string {
  switch (value) {
    case "router":
      return "RTR";
    case "firewall":
      return "FW";
    case "switch":
      return "SW";
    case "load_balancer":
      return "LB";
    case "server":
      return "SRV";
    case "hypervisor":
      return "HV";
    case "virtual_machine":
      return "VM";
    default:
      return "DEV";
  }
}

/** Confidence is a 0-1 score from discovery/correlation; operators read percentages faster. */
export function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

/** `datetime-local` input value for an ISO timestamp, or "" when absent. */
export function toLocalInput(value?: string | null): string {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())}T${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`;
}

/** Turn a `datetime-local` value back into the ISO string the API filters on. */
export function fromLocalInput(value: string): string | undefined {
  if (!value) return undefined;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? undefined : parsed.toISOString();
}

export const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
