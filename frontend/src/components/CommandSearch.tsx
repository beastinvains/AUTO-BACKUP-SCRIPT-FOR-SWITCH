/**
 * Topbar Command Search for NETRA.
 */

import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent } from "react";
import { api } from "../api";
import { SearchIcon } from "./icons";
import type { Device } from "../types";

export type Destination = { page: string; label: string; hint: string };

export function CommandSearch({
  destinations,
  navigate,
}: {
  destinations: Destination[];
  navigate: (page: string, param?: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [devices, setDevices] = useState<Device[] | null>(null);
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const boxRef = useRef<HTMLDivElement | null>(null);

  // Global shortcuts: `/` or `⌘K` / `Ctrl+K`
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typing = target ? ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName) || target.isContentEditable : false;
      const shortcut = event.key === "k" && (event.metaKey || event.ctrlKey);
      if (shortcut || (event.key === "/" && !typing)) {
        event.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Close when clicking outside
  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (!boxRef.current?.contains(event.target as Node)) setOpen(false);
    };
    window.addEventListener("mousedown", onDown);
    return () => window.removeEventListener("mousedown", onDown);
  }, [open]);

  // Load device list lazily
  useEffect(() => {
    if (!open || devices !== null) return;
    let live = true;
    api
      .devices()
      .then((rows) => {
        if (live) setDevices(rows);
      })
      .catch(() => {
        if (live) setDevices([]);
      });
    return () => {
      live = false;
    };
  }, [open, devices]);

  const needle = query.trim().toLowerCase();
  const sections = needle
    ? destinations.filter((item) => `${item.label} ${item.hint}`.toLowerCase().includes(needle)).slice(0, 5)
    : destinations.slice(0, 5);

  const matchedDevices = needle
    ? (devices ?? [])
        .filter((device) =>
          [device.name, device.management_ip, device.site ?? "", device.vendor ?? "", device.model ?? "", device.type]
            .join(" ")
            .toLowerCase()
            .includes(needle),
        )
        .slice(0, 6)
    : [];

  type Hit = { key: string; label: string; meta: string; go: () => void };
  const hits: Hit[] = [
    ...sections.map((item) => ({
      key: `page-${item.page}`,
      label: item.label,
      meta: item.hint,
      go: () => navigate(item.page),
    })),
    ...matchedDevices.map((device) => ({
      key: `device-${device.id}`,
      label: device.name,
      meta: `${device.management_ip} • ${device.vendor ?? "unknown vendor"}${device.site ? ` • ${device.site}` : ""}`,
      go: () => navigate("devices", device.id),
    })),
  ];

  const choose = (hit: Hit) => {
    hit.go();
    setOpen(false);
    setQuery("");
    inputRef.current?.blur();
  };

  const onKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Escape") {
      setOpen(false);
      inputRef.current?.blur();
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((index) => Math.min(index + 1, Math.max(hits.length - 1, 0)));
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((index) => Math.max(index - 1, 0));
      return;
    }
    if (event.key === "Enter" && hits[active]) {
      event.preventDefault();
      choose(hits[active]);
    }
  };

  return (
    <div className="search-container" ref={boxRef}>
      <div className="search-input-wrap">
        <SearchIcon size={16} style={{ color: "var(--ink-3)", flexShrink: 0 }} />
        <input
          ref={inputRef}
          className="search-input"
          value={query}
          placeholder="Search anything..."
          aria-label="Search anything..."
          onFocus={() => setOpen(true)}
          onChange={(event) => {
            setQuery(event.target.value);
            setActive(0);
            setOpen(true);
          }}
          onKeyDown={onKeyDown}
        />
        <span className="search-shortcut">/</span>
      </div>

      {open && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 6px)",
            left: 0,
            right: 0,
            background: "var(--surface-2)",
            border: "1px solid var(--line-strong)",
            borderRadius: "var(--radius-card)",
            padding: "8px",
            boxShadow: "var(--shadow-lg)",
            zIndex: 50,
            maxHeight: "360px",
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            gap: "4px",
          }}
          role="listbox"
        >
          {sections.length > 0 && (
            <div style={{ fontSize: "0.68rem", fontWeight: "600", textTransform: "uppercase", color: "var(--ink-3)", padding: "4px 8px" }}>
              Pages & Tools
            </div>
          )}
          {sections.map((item, index) => (
            <button
              key={`page-${item.page}`}
              role="option"
              aria-selected={index === active}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "flex-start",
                padding: "7px 10px",
                borderRadius: "var(--radius-control)",
                background: index === active ? "rgba(16, 185, 129, 0.15)" : "transparent",
                border: "none",
                cursor: "pointer",
                textAlign: "left",
                color: index === active ? "var(--brand-emerald-light)" : "var(--ink)",
                width: "100%",
              }}
              onMouseEnter={() => setActive(index)}
              onClick={() => choose(hits[index])}
            >
              <span style={{ fontSize: "0.84rem", fontWeight: "600" }}>{item.label}</span>
              <small style={{ fontSize: "0.72rem", color: "var(--ink-3)" }}>{item.hint}</small>
            </button>
          ))}

          {needle && (
            <div style={{ fontSize: "0.68rem", fontWeight: "600", textTransform: "uppercase", color: "var(--ink-3)", padding: "8px 8px 4px" }}>
              Devices {devices === null ? "— loading…" : ""}
            </div>
          )}
          {needle &&
            matchedDevices.map((device, index) => {
              const hitIndex = sections.length + index;
              return (
                <button
                  key={`device-${device.id}`}
                  role="option"
                  aria-selected={hitIndex === active}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "flex-start",
                    padding: "7px 10px",
                    borderRadius: "var(--radius-control)",
                    background: hitIndex === active ? "rgba(16, 185, 129, 0.15)" : "transparent",
                    border: "none",
                    cursor: "pointer",
                    textAlign: "left",
                    color: hitIndex === active ? "var(--brand-emerald-light)" : "var(--ink)",
                    width: "100%",
                  }}
                  onMouseEnter={() => setActive(hitIndex)}
                  onClick={() => choose(hits[hitIndex])}
                >
                  <span style={{ fontSize: "0.84rem", fontWeight: "600" }}>{device.name}</span>
                  <small style={{ fontSize: "0.72rem", color: "var(--ink-3)" }}>
                    {device.management_ip} • {device.vendor ?? "unknown vendor"}
                    {device.site ? ` • ${device.site}` : ""}
                  </small>
                </button>
              );
            })}

          {needle && hits.length === 0 && (
            <p style={{ padding: "12px", textAlign: "center", color: "var(--ink-3)", fontSize: "0.8rem" }}>
              No section or device matches “{query}”.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
