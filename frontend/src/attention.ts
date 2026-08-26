/**
 * Attention items, derived from records the platform already stores.
 *
 * There is no alerts table, no rule engine and no notification delivery in this build —
 * those belong to a later phase. What this module does is read the same rows the Devices,
 * Backups, Schedules and Topology pages read and sort them by how much they matter, so an
 * operator does not have to visit four pages to find out what is broken.
 *
 * Every item carries the rule that produced it. Severity is this module's judgement about
 * ordering, not a field the backend stores, and the Alerts page says so.
 */

import type { Severity } from "./components/ui";
import type { BackupJob, Dashboard, Device, Schedule } from "./types";

export type AttentionItem = {
  id: string;
  severity: Severity;
  source: string;
  subject: string;
  detail: string;
  when: string | null;
  rule: string;
  goto: { page: string; param?: string };
};

const ORDER: Record<Severity, number> = { critical: 0, serious: 1, warning: 2, info: 3 };

/** The rules, written out for the page that shows them. Keep in step with `deriveAttention`. */
export const DERIVATION_RULES: { severity: Severity; when: string }[] = [
  { severity: "critical", when: "A device's last discovery left it offline, or a backup job failed for every device in scope." },
  { severity: "serious", when: "A backup job was partial, a schedule's last run did not succeed, a device is degraded, or a device has no configuration version at all." },
  { severity: "warning", when: "A device was added but never reached, discovery failed while the device is still reachable, or a device's newest backup is older than the staleness threshold." },
  { severity: "info", when: "A reported neighbour name matched more than one device, so no link was drawn." },
];

/**
 * Count of open problems from the dashboard aggregates alone — one request, which is what
 * the topbar needs. This counts *aggregates* (for example "3 devices never backed up" is 3),
 * so it is not the same number as the row count on the Alerts page.
 */
export function dashboardAttentionCount(dashboard: Dashboard): number {
  const { infrastructure, backup, discovery, topology } = dashboard;
  return (
    infrastructure.offline +
    infrastructure.degraded +
    infrastructure.unknown +
    backup.failed_jobs +
    backup.devices_never_backed_up +
    backup.devices_stale_backup +
    discovery.failed_discoveries +
    topology.ambiguous_identities
  );
}

export function deriveAttention(input: {
  dashboard: Dashboard | null;
  devices: Device[];
  jobs: BackupJob[];
  schedules: Schedule[];
}): AttentionItem[] {
  const items: AttentionItem[] = [];

  for (const device of input.devices) {
    const status = device.status.toLowerCase();
    if (status === "offline") {
      items.push({
        id: `device-offline-${device.id}`,
        severity: "critical",
        source: "Device",
        subject: device.name,
        detail: `Unreachable at ${device.management_ip}:${device.management_port}. Backups and discovery for it will fail until it answers.`,
        when: device.last_seen_at,
        rule: "device.status = offline",
        goto: { page: "devices", param: device.id },
      });
    } else if (status === "degraded") {
      items.push({
        id: `device-degraded-${device.id}`,
        severity: "serious",
        source: "Device",
        subject: device.name,
        detail: "Reachable, but the last discovery reported a hardware or resource problem.",
        when: device.last_seen_at,
        rule: "device.status = degraded",
        goto: { page: "devices", param: device.id },
      });
    } else if (status === "unknown") {
      items.push({
        id: `device-unknown-${device.id}`,
        severity: "warning",
        source: "Device",
        subject: device.name,
        detail: "Registered but never reached, so it has no interfaces, no neighbours and no topology links.",
        when: null,
        rule: "device.status = unknown",
        goto: { page: "devices", param: device.id },
      });
    }

    // Only report the discovery state separately when reachability is not already the story.
    const discoveryState = device.discovery_state.toLowerCase();
    if (status !== "offline" && status !== "unknown" && discoveryState === "failed") {
      items.push({
        id: `discovery-failed-${device.id}`,
        severity: "warning",
        source: "Discovery",
        subject: device.name,
        detail: "The last discovery run for this device did not complete, so its inventory may be out of date.",
        when: device.last_seen_at,
        rule: "device.discovery_state = failed",
        goto: { page: "devices", param: device.id },
      });
    }
  }

  for (const job of input.jobs) {
    const failed = job.results.filter((result) => result.status === "FAILED");
    if (job.status === "FAILED") {
      items.push({
        id: `job-failed-${job.job_id}`,
        severity: "critical",
        source: "Backup",
        subject: `Job ${job.job_id.slice(0, 8)}`,
        detail: `Every device in scope failed (${job.failure_count} of ${job.failure_count}). Requested by ${job.requested_by}.`,
        when: job.completed_at ?? job.created_at,
        rule: "backup_job.status = FAILED",
        goto: { page: "backups" },
      });
    } else if (job.status === "PARTIAL") {
      const names = failed.map((result) => result.device).join(", ");
      items.push({
        id: `job-partial-${job.job_id}`,
        severity: "serious",
        source: "Backup",
        subject: `Job ${job.job_id.slice(0, 8)}`,
        detail: `${job.failure_count} of ${job.success_count + job.failure_count} devices failed${names ? `: ${names}` : ""}. Requested by ${job.requested_by}.`,
        when: job.completed_at ?? job.created_at,
        rule: "backup_job.status = PARTIAL",
        goto: { page: "backups" },
      });
    }
  }

  for (const schedule of input.schedules) {
    const last = (schedule.last_status ?? "").toUpperCase();
    if (last === "FAILED" || last === "PARTIAL") {
      items.push({
        id: `schedule-${schedule.id}`,
        severity: last === "FAILED" ? "serious" : "warning",
        source: "Schedule",
        subject: schedule.name,
        detail: `Last run finished ${last.toLowerCase()}. Scope: ${schedule.scope}. Cadence: ${schedule.cadence}.`,
        when: schedule.last_run_at,
        rule: "schedule.last_status in (FAILED, PARTIAL)",
        goto: { page: "schedules" },
      });
    }
  }

  const dashboard = input.dashboard;
  if (dashboard) {
    if (dashboard.backup.devices_never_backed_up > 0) {
      items.push({
        id: "backup-never",
        severity: "serious",
        source: "Coverage",
        subject: `${dashboard.backup.devices_never_backed_up} device(s) never backed up`,
        detail: "These devices have no stored configuration version, so there is nothing to restore or compare against.",
        when: null,
        rule: "device has zero configuration versions",
        goto: { page: "backups" },
      });
    }
    if (dashboard.backup.devices_stale_backup > 0) {
      items.push({
        id: "backup-stale",
        severity: "warning",
        source: "Coverage",
        subject: `${dashboard.backup.devices_stale_backup} device(s) with a stale backup`,
        detail: `Newest configuration version is older than ${dashboard.backup.stale_threshold_days} days.`,
        when: null,
        rule: `newest version older than STALE_BACKUP_DAYS (${dashboard.backup.stale_threshold_days})`,
        goto: { page: "configurations" },
      });
    }
    if (dashboard.topology.ambiguous_identities > 0) {
      items.push({
        id: "topology-ambiguous",
        severity: "info",
        source: "Topology",
        subject: `${dashboard.topology.ambiguous_identities} ambiguous neighbour identit(ies)`,
        detail: "A reported neighbour name matched more than one device. No link was drawn — the platform leaves an ambiguous identity undrawn rather than guessing.",
        when: null,
        rule: "two or more devices matched one reported identity",
        goto: { page: "topology" },
      });
    }
  }

  return items.sort((left, right) => {
    const bySeverity = ORDER[left.severity] - ORDER[right.severity];
    if (bySeverity !== 0) return bySeverity;
    const leftTime = left.when ? Date.parse(left.when) : 0;
    const rightTime = right.when ? Date.parse(right.when) : 0;
    if (leftTime !== rightTime) return rightTime - leftTime;
    return left.subject.localeCompare(right.subject);
  });
}
