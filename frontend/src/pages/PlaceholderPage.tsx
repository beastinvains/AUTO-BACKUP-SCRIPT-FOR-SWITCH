/**
 * Navigation destinations Phase 3 exposes but does not implement.
 *
 * The AI assistant and settings belong to later phases of the blueprint. They are shown as explicit
 * placeholders rather than half-built screens, so an empty panel is never mistaken for a working
 * feature — and each one points at the pages that do hold real records today.
 */

import { Panel } from "../components/ui";

type Placeholder = {
  lead: string;
  planned: string[];
  today: { label: string; page: string; why: string }[];
  note: string;
};

const PLACEHOLDERS: Record<string, Placeholder> = {
  ai: {
    lead: "No AI is used anywhere in this build. Configuration diffs are computed with Python's difflib and topology comes from recorded LLDP evidence only.",
    planned: [
      "Natural-language questions over discovered inventory and topology",
      "Plain-language explanation of a configuration change, alongside and never replacing the deterministic diff",
      "Suggested remediation for repeated backup failures",
    ],
    today: [
      { label: "Versions & diff", page: "configurations", why: "Deterministic line diffs between stored versions" },
      { label: "Topology", page: "topology", why: "Links drawn only where evidence supports them" },
    ],
    note: "The blueprint places this after topology and backup are trustworthy on their own. A model will not be allowed to invent topology links or replace the diff.",
  },
  settings: {
    lead: "Platform settings are still configured on the server, through environment variables and the database. There is no settings endpoint for this page to read or write.",
    planned: [
      "Retention policy for configuration versions",
      "Storage backend selection and paths",
      "Credential-store configuration — references only, never secrets in the browser",
      "Real authentication and user management, replacing the role header seam",
    ],
    today: [
      { label: "Schedules", page: "schedules", why: "The one operational setting that is editable today" },
      { label: "Audit log", page: "logs", why: "Who changed what, with the actor recorded" },
    ],
    note: "The role selector in the account menu is a development seam for exercising authorization. It is not a login, and the server re-checks every request regardless of what it is set to.",
  },
};

const DESTINATIONS = [
  { label: "Dashboard", page: "dashboard", why: "Reachability, coverage and recorded activity" },
  { label: "Devices", page: "devices", why: "The registered inventory" },
  { label: "Backups", page: "backups", why: "Jobs and per-device results" },
  { label: "Audit log", page: "logs", why: "Every recorded action" },
];

export function PlaceholderPage({ page, navigate }: { page: string; navigate: (page: string, param?: string) => void }) {
  const content = PLACEHOLDERS[page];

  if (!content) {
    return (
      <div className="page">
        <div className="split">
          <div>
            <Panel title="Nothing at that address" provenance={`No section is registered at “${page}”`}>
              <p className="notice">
                The link may be out of date, or the address may have been typed by hand. Pick a section below, or use the
                search in the topbar — it matches sections and devices.
              </p>
              <ul className="pointers">
                {DESTINATIONS.map((item) => (
                  <li key={item.page}>
                    <button className="link" onClick={() => navigate(item.page)}>
                      {item.label}
                    </button>
                    <p>{item.why}</p>
                  </li>
                ))}
              </ul>
            </Panel>
          </div>
          <aside className="rail-stack" />
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="split">
        <div>
          <Panel title="Not implemented in this build" provenance="No endpoint backs this section — nothing on this page is fetched">
            <p className="notice">{content.lead}</p>
          </Panel>

          <Panel title="Planned for a later phase" note="Not part of Phase 3">
            <ul className="inline-list">
              {content.planned.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            <p className="muted">{content.note}</p>
          </Panel>
        </div>

        <aside className="rail-stack">
          <Panel title="What exists today">
            <ul className="pointers">
              {content.today.map((item) => (
                <li key={item.page}>
                  <button className="link" onClick={() => navigate(item.page)}>
                    {item.label}
                  </button>
                  <p>{item.why}</p>
                </li>
              ))}
            </ul>
          </Panel>
        </aside>
      </div>
    </div>
  );
}
