/**
 * Add / Edit Device form for NETRA.
 */

import { useState } from "react";
import { api } from "../api";
import type { Device, DeviceInput } from "../types";
import { ErrorBanner, Modal } from "./ui";
import { DevicesIcon, PlusIcon, CheckCircleIcon } from "./icons";

const DEVICE_TYPES = [
  "switch",
  "router",
  "firewall",
  "load_balancer",
  "server",
  "hypervisor",
  "virtual_machine",
  "access_point",
  "other",
];

const IPV4 = /^(\d{1,3}\.){3}\d{1,3}$/;
const REFERENCE = /^[A-Za-z0-9][A-Za-z0-9_.\-]{0,63}$/;
const FORBIDDEN = ["password", "secret", "passphrase", "privatekey", "private_key"];

function blank(): DeviceInput {
  return {
    name: "",
    management_ip: "",
    management_port: 22,
    credentials_reference_id: "lab_juniper",
    type: "switch",
    vendor: "juniper",
    site: "datacenter-1",
  };
}

function fromDevice(device: Device): DeviceInput {
  return {
    name: device.name,
    management_ip: device.management_ip,
    management_port: device.management_port ?? 22,
    credentials_reference_id: device.credentials_reference_id,
    type: device.type,
    vendor: device.vendor,
    site: device.site,
  };
}

function validate(input: DeviceInput): string | null {
  if (!input.name.trim()) return "Device Hostname / Name is required.";
  if (!input.management_ip.trim()) return "Management IP is required.";
  if (!IPV4.test(input.management_ip.trim()) && !input.management_ip.includes(":")) {
    return "Management IP must be a valid IPv4 or IPv6 address.";
  }
  if (IPV4.test(input.management_ip.trim())) {
    const octets = input.management_ip.trim().split(".").map(Number);
    if (octets.some((octet) => octet > 255)) return "Management IP must be a valid IPv4 address.";
  }
  if (!Number.isInteger(input.management_port) || input.management_port < 1 || input.management_port > 65535) {
    return "Management port must be between 1 and 65535.";
  }
  if (!REFERENCE.test(input.credentials_reference_id)) {
    return "Credential reference must be a profile name (letters, digits, dot, dash, underscore).";
  }
  if (FORBIDDEN.some((word) => input.credentials_reference_id.toLowerCase().includes(word))) {
    return "Credential reference must name a credential profile, not a plaintext password or secret.";
  }
  return null;
}

export function DeviceForm({
  device,
  onClose,
  onSaved,
}: {
  device: Device | null;
  onClose: () => void;
  onSaved: (device: Device, runDiscovery: boolean) => void;
}) {
  const [input, setInput] = useState<DeviceInput>(device ? fromDevice(device) : blank());
  const [runDiscovery, setRunDiscovery] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const set = <K extends keyof DeviceInput>(key: K, value: DeviceInput[K]) =>
    setInput((current) => ({ ...current, [key]: value }));

  const submit = async () => {
    const problem = validate(input);
    if (problem) {
      setError(problem);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const payload: DeviceInput = {
        ...input,
        name: input.name.trim(),
        management_ip: input.management_ip.trim(),
        vendor: input.vendor?.trim() ? input.vendor.trim() : null,
        site: input.site?.trim() ? input.site.trim() : null,
      };
      const saved = device ? await api.updateDevice(device.id, payload) : await api.createDevice(payload);
      onSaved(saved, runDiscovery);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to save device");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title={device ? `Edit Device: ${device.name}` : "Register Network Device"} onClose={onClose}>
      <ErrorBanner message={error} />

      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        <div className="form-grid">
          <label>
            Device Hostname / Name *
            <input
              value={input.name}
              onChange={(e) => set("name", e.target.value)}
              placeholder="e.g. CORE-JUN-01"
              autoFocus
            />
          </label>

          <label>
            Device Type *
            <select value={input.type} onChange={(e) => set("type", e.target.value)}>
              {DEVICE_TYPES.map((type) => (
                <option key={type} value={type}>
                  {type.replace(/_/g, " ").toUpperCase()}
                </option>
              ))}
            </select>
          </label>

          <label>
            Management IP Address *
            <input
              value={input.management_ip}
              onChange={(e) => set("management_ip", e.target.value)}
              placeholder="10.0.0.1"
            />
          </label>

          <label>
            SSH Management Port *
            <input
              type="number"
              min={1}
              max={65535}
              value={input.management_port}
              onChange={(e) => set("management_port", Number(e.target.value))}
            />
          </label>

          <label>
            Vendor / OS
            <input
              value={input.vendor ?? ""}
              onChange={(e) => set("vendor", e.target.value)}
              placeholder="juniper, cisco, fortigate"
            />
          </label>

          <label>
            Site / Datacenter
            <input
              value={input.site ?? ""}
              onChange={(e) => set("site", e.target.value)}
              placeholder="e.g. datacenter-1, branch-a"
            />
          </label>

          <label className="wide">
            Credential Reference Profile *
            <input
              value={input.credentials_reference_id}
              onChange={(e) => set("credentials_reference_id", e.target.value)}
              placeholder="lab_juniper"
            />
            <small>
              Reference key for Vault or server environment profile (e.g. <code>lab_juniper</code>).
              Plaintext passwords are never entered in the browser.
            </small>
          </label>
        </div>

        <div className="notice" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <CheckCircleIcon size={16} style={{ color: "var(--brand-emerald-light)", flexShrink: 0 }} />
          <span>
            NETRA adheres to Zero-Trust credentials: the browser holds references only, while adapters resolve credentials securely just-in-time.
          </span>
        </div>

        <label className="inline">
          <input
            type="checkbox"
            checked={runDiscovery}
            onChange={(e) => setRunDiscovery(e.target.checked)}
          />
          <strong>Run automatic LLDP discovery immediately after registration</strong>
        </label>

        <div className="form-actions" style={{ padding: "12px 0 0 0", background: "transparent" }}>
          <button className="btn btn-ghost" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={() => void submit()} disabled={busy}>
            {busy ? "Registering…" : device ? "Save Changes" : "+ Register Device"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
