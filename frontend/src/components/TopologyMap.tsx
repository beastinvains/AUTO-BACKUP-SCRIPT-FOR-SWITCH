/**
 * Interactive Network Topology Canvas matching NETRA Screenshot 3.
 */

import { useState, useRef, useId, type ReactNode } from "react";
import {
  CheckCircleIcon,
  CloudIcon,
  DevicesIcon,
  FanIcon,
  PowerIcon,
  ShieldAlertIcon,
  SparklesIcon,
  SwitchIcon,
  TempIcon,
} from "./icons";
import type { TopologyNode, TopologyEdge } from "../types";

export interface TopoNodeVisual {
  id: string;
  name: string;
  type: "internet" | "router" | "switch" | "firewall" | "server" | "endpoint" | "ap" | "camera" | "printer";
  model: string;
  ip: string;
  vendor: string;
  status: "healthy" | "warning" | "critical" | "offline" | "unknown";
  x: number;
  y: number;
  cpu?: number;
  mem?: number;
  temp?: string;
  power?: string;
  fan?: string;
  uptime?: string;
  interfacesCount?: number;
  neighborsCount?: number;
  alertsCount?: number;
}

export interface TopoLinkVisual {
  id: string;
  source: string;
  target: string;
  status: "healthy" | "warning" | "critical";
  sourceInterface?: string;
  targetInterface?: string;
  bandwidth?: string;
  latency?: string;
  dashed?: boolean;
}

export const MOCK_TOPO_NODES: TopoNodeVisual[] = [
  // Tier 0
  {
    id: "Internet",
    name: "Internet",
    type: "internet",
    model: "WAN Gateway",
    ip: "0.0.0.0/0",
    vendor: "ISP",
    status: "healthy",
    x: 480,
    y: 50,
    uptime: "99.99%",
  },
  // Tier 1
  {
    id: "FW-JUN-01",
    name: "FW-JUN-01",
    type: "firewall",
    model: "Juniper SRX",
    ip: "192.168.1.1",
    vendor: "Juniper",
    status: "healthy",
    x: 450,
    y: 150,
    cpu: 24,
    mem: 38,
    temp: "41°C",
    power: "OK 2/2",
    fan: "4200 RPM",
    uptime: "28d 14h",
    interfacesCount: 16,
    neighborsCount: 4,
    alertsCount: 0,
  },
  {
    id: "DMZ-SW-01",
    name: "DMZ-SW-01",
    type: "switch",
    model: "Cisco Switch",
    ip: "10.10.10.1",
    vendor: "Cisco",
    status: "critical",
    x: 620,
    y: 150,
    cpu: 78,
    mem: 82,
    temp: "64°C",
    power: "PSU-1 Fail",
    fan: "1800 RPM",
    uptime: "5d 2h",
    interfacesCount: 24,
    neighborsCount: 3,
    alertsCount: 3,
  },
  {
    id: "Web-Server",
    name: "Web Server",
    type: "server",
    model: "Nginx Cluster",
    ip: "10.10.10.10",
    vendor: "Linux",
    status: "healthy",
    x: 740,
    y: 110,
    cpu: 42,
    mem: 55,
  },
  {
    id: "Mail-Server",
    name: "Mail Server",
    type: "server",
    model: "Postfix Mail",
    ip: "10.10.10.11",
    vendor: "Linux",
    status: "warning",
    x: 740,
    y: 190,
    cpu: 65,
    mem: 70,
  },
  // Tier 2 Core Switches
  {
    id: "CORE-JUN-01",
    name: "CORE-JUN-01",
    type: "switch",
    model: "Juniper EX4300",
    ip: "10.0.0.1",
    vendor: "Juniper",
    status: "healthy",
    x: 370,
    y: 260,
    cpu: 32,
    mem: 45,
    temp: "42°C",
    power: "OK 2/2",
    fan: "4200 RPM",
    uptime: "15d 4h 23m",
    interfacesCount: 48,
    neighborsCount: 12,
    alertsCount: 2,
  },
  {
    id: "CORE-JUN-02",
    name: "CORE-JUN-02",
    type: "switch",
    model: "Juniper EX4300",
    ip: "10.0.0.2",
    vendor: "Juniper",
    status: "healthy",
    x: 540,
    y: 260,
    cpu: 29,
    mem: 41,
    temp: "40°C",
    power: "OK 2/2",
    fan: "4100 RPM",
    uptime: "15d 4h 20m",
    interfacesCount: 48,
    neighborsCount: 10,
    alertsCount: 0,
  },
  // Tier 3 Distribution Switches
  {
    id: "DIST-SW-01",
    name: "DIST-SW-01",
    type: "switch",
    model: "Cisco 2960X",
    ip: "10.0.1.1",
    vendor: "Cisco",
    status: "warning",
    x: 290,
    y: 370,
    cpu: 58,
    mem: 62,
    temp: "52°C",
    power: "OK",
    fan: "3100 RPM",
    uptime: "12d 8h",
    interfacesCount: 24,
    neighborsCount: 4,
    alertsCount: 1,
  },
  {
    id: "DIST-SW-02",
    name: "DIST-SW-02",
    type: "switch",
    model: "Juniper EX3300",
    ip: "10.0.2.1",
    vendor: "Juniper",
    status: "healthy",
    x: 450,
    y: 370,
    cpu: 22,
    mem: 35,
    temp: "39°C",
    power: "OK",
    fan: "3800 RPM",
    uptime: "21d 6h",
    interfacesCount: 24,
    neighborsCount: 4,
    alertsCount: 0,
  },
  {
    id: "DIST-SW-03",
    name: "DIST-SW-03",
    type: "switch",
    model: "Cisco 2960X",
    ip: "10.0.3.1",
    vendor: "Cisco",
    status: "healthy",
    x: 620,
    y: 370,
    cpu: 25,
    mem: 39,
    temp: "41°C",
    power: "OK",
    fan: "3600 RPM",
    uptime: "18d 11h",
    interfacesCount: 24,
    neighborsCount: 4,
    alertsCount: 0,
  },
  // Tier 4 Endpoints
  { id: "PC-LAB-01", name: "PC-LAB-01", type: "endpoint", model: "Workstation", ip: "192.168.1.10", vendor: "Dell", status: "healthy", x: 210, y: 480 },
  { id: "PC-LAB-02", name: "PC-LAB-02", type: "endpoint", model: "Workstation", ip: "192.168.1.11", vendor: "Dell", status: "healthy", x: 320, y: 480 },
  { id: "AP-01", name: "AP-01", type: "ap", model: "Cisco AP", ip: "10.20.30.5", vendor: "Cisco", status: "healthy", x: 410, y: 480 },
  { id: "IP-Camera", name: "IP Camera", type: "camera", model: "Axis Cam", ip: "10.20.30.20", vendor: "Axis", status: "warning", x: 490, y: 480 },
  { id: "Printer-01", name: "Printer-01", type: "printer", model: "HP LaserJet", ip: "10.20.30.30", vendor: "HP", status: "healthy", x: 580, y: 480 },
  { id: "NVR-01", name: "NVR-01", type: "server", model: "Hikvision NVR", ip: "10.20.30.40", vendor: "Hikvision", status: "critical", x: 680, y: 480 },
];

export const MOCK_TOPO_LINKS: TopoLinkVisual[] = [
  { id: "e-1", source: "Internet", target: "FW-JUN-01", status: "healthy", sourceInterface: "eth0", targetInterface: "ge-0/0/0" },
  { id: "e-2", source: "FW-JUN-01", target: "DMZ-SW-01", status: "critical", sourceInterface: "ge-0/0/3", targetInterface: "Gi0/1", dashed: true },
  { id: "e-3", source: "DMZ-SW-01", target: "Web-Server", status: "healthy", sourceInterface: "Gi0/2", targetInterface: "eth0" },
  { id: "e-4", source: "DMZ-SW-01", target: "Mail-Server", status: "warning", sourceInterface: "Gi0/3", targetInterface: "eth0" },
  { id: "e-5", source: "FW-JUN-01", target: "CORE-JUN-01", status: "healthy", sourceInterface: "ge-0/0/1", targetInterface: "xe-0/0/0" },
  { id: "e-6", source: "FW-JUN-01", target: "CORE-JUN-02", status: "healthy", sourceInterface: "ge-0/0/2", targetInterface: "xe-0/0/0" },
  { id: "e-7", source: "CORE-JUN-01", target: "CORE-JUN-02", status: "healthy", sourceInterface: "ae0", targetInterface: "ae0", dashed: true },
  { id: "e-8", source: "CORE-JUN-01", target: "DIST-SW-01", status: "warning", sourceInterface: "ge-0/0/10", targetInterface: "Gi0/24" },
  { id: "e-9", source: "CORE-JUN-01", target: "DIST-SW-02", status: "healthy", sourceInterface: "ge-0/0/11", targetInterface: "ge-0/0/24" },
  { id: "e-10", source: "CORE-JUN-02", target: "DIST-SW-02", status: "healthy", sourceInterface: "ge-0/0/11", targetInterface: "ge-0/0/23" },
  { id: "e-11", source: "CORE-JUN-02", target: "DIST-SW-03", status: "healthy", sourceInterface: "ge-0/0/12", targetInterface: "Gi0/24" },
  { id: "e-12", source: "DIST-SW-01", target: "PC-LAB-01", status: "healthy", sourceInterface: "Fa0/1", targetInterface: "eth0" },
  { id: "e-13", source: "DIST-SW-01", target: "PC-LAB-02", status: "healthy", sourceInterface: "Fa0/2", targetInterface: "eth0" },
  { id: "e-14", source: "DIST-SW-02", target: "AP-01", status: "healthy", sourceInterface: "ge-0/0/1", targetInterface: "eth0" },
  { id: "e-15", source: "DIST-SW-02", target: "IP-Camera", status: "warning", sourceInterface: "ge-0/0/2", targetInterface: "eth0" },
  { id: "e-16", source: "DIST-SW-03", target: "Printer-01", status: "healthy", sourceInterface: "Fa0/1", targetInterface: "eth0" },
  { id: "e-17", source: "DIST-SW-03", target: "NVR-01", status: "critical", sourceInterface: "Fa0/2", targetInterface: "eth0", dashed: true },
];

export function TopologyMap({
  selectedNodeId,
  onSelectNode,
  showLabels = true,
  showLinks = true,
  showAlerts = true,
}: {
  selectedNodeId: string | null;
  onSelectNode: (id: string | null) => void;
  showLabels?: boolean;
  showLinks?: boolean;
  showAlerts?: boolean;
}) {
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [hoveredLink, setHoveredLink] = useState<string | null>(null);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const startPos = useRef({ x: 0, y: 0 });

  const handlePointerDown = (e: React.PointerEvent) => {
    if (e.button !== 0) return;
    setDragging(true);
    startPos.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    if (!dragging) return;
    setPan({
      x: e.clientX - startPos.current.x,
      y: e.clientY - startPos.current.y,
    });
  };

  const handlePointerUp = () => setDragging(false);

  const nodeMap = new Map(MOCK_TOPO_NODES.map((n) => [n.id, n]));

  const getNodeColor = (status: string) => {
    switch (status) {
      case "healthy": return "#10b981";
      case "warning": return "#f59e0b";
      case "critical": return "#ef4444";
      case "offline": return "#64748b";
      default: return "#3b82f6";
    }
  };

  return (
    <div
      className="topology-canvas-wrap"
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      style={{ cursor: dragging ? "grabbing" : "grab" }}
    >
      <svg
        width="100%"
        height="100%"
        viewBox="0 0 960 560"
        style={{
          transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoomLevel})`,
          transformOrigin: "center center",
          transition: dragging ? "none" : "transform 0.15s ease-out",
        }}
      >
        <defs>
          <filter id="glow-green" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
          <filter id="glow-red" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
          <marker id="arrow-green" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#10b981" />
          </marker>
          <marker id="arrow-red" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#ef4444" />
          </marker>
        </defs>

        {/* Links Layer */}
        {showLinks && (
          <g className="links-layer">
            {MOCK_TOPO_LINKS.map((link) => {
              const src = nodeMap.get(link.source);
              const tgt = nodeMap.get(link.target);
              if (!src || !tgt) return null;

              const isHovered = hoveredLink === link.id;
              const isCrit = link.status === "critical";
              const isWarn = link.status === "warning";
              const strokeColor = isCrit ? "#ef4444" : isWarn ? "#f59e0b" : "#10b981";

              // Draw smooth quadratic curved connector
              const midX = (src.x + tgt.x) / 2;
              const midY = (src.y + tgt.y) / 2;
              const pathD = `M ${src.x} ${src.y} Q ${midX} ${midY + (src.x === tgt.x ? 0 : 5)} ${tgt.x} ${tgt.y}`;

              return (
                <g
                  key={link.id}
                  onMouseEnter={() => setHoveredLink(link.id)}
                  onMouseLeave={() => setHoveredLink(null)}
                  style={{ cursor: "pointer" }}
                >
                  <path
                    d={pathD}
                    fill="none"
                    stroke="transparent"
                    strokeWidth="12"
                  />
                  <path
                    d={pathD}
                    fill="none"
                    stroke={strokeColor}
                    strokeWidth={isHovered ? 3 : isCrit ? 2.2 : 1.8}
                    strokeDasharray={link.dashed ? "5 4" : undefined}
                    opacity={isHovered ? 1 : 0.85}
                    filter={isCrit ? "url(#glow-red)" : "url(#glow-green)"}
                  />
                  {/* Plus / joint node indicator in center */}
                  <circle cx={midX} cy={midY} r={5} fill="#0d1422" stroke={strokeColor} strokeWidth="1.5" />
                  <text x={midX} y={midY + 3} textAnchor="middle" fill={strokeColor} fontSize="8" fontWeight="bold">+</text>

                  {/* Interface tooltip on hover */}
                  {isHovered && (
                    <g transform={`translate(${midX}, ${midY - 12})`}>
                      <rect x="-45" y="-12" width="90" height="18" rx="4" fill="#141f32" stroke="var(--line-strong)" />
                      <text x="0" y="1" textAnchor="middle" fill="#ffffff" fontSize="9" fontFamily="var(--font-mono)">
                        {link.sourceInterface} ↔ {link.targetInterface}
                      </text>
                    </g>
                  )}
                </g>
              );
            })}
          </g>
        )}

        {/* Nodes Layer */}
        <g className="nodes-layer">
          {MOCK_TOPO_NODES.map((node) => {
            const isSelected = selectedNodeId === node.id;
            const isHovered = hoveredNode === node.id;
            const statusColor = getNodeColor(node.status);
            const isCrit = node.status === "critical";
            const isWarn = node.status === "warning";

            if (node.type === "internet") {
              return (
                <g
                  key={node.id}
                  transform={`translate(${node.x}, ${node.y})`}
                  onClick={(e) => { e.stopPropagation(); onSelectNode(node.id); }}
                  onMouseEnter={() => setHoveredNode(node.id)}
                  onMouseLeave={() => setHoveredNode(null)}
                  style={{ cursor: "pointer" }}
                >
                  <circle cx="0" cy="0" r="28" fill="#141f32" stroke={isSelected ? "#10b981" : "rgba(255,255,255,0.2)"} strokeWidth={isSelected ? 3 : 1.5} filter="url(#glow-green)" />
                  <CloudIcon size={24} style={{ color: "#34d399", transform: "translate(-12px, -12px)" }} />
                  <circle cx="16" cy="-14" r="7" fill="#10b981" />
                  <text x="16" y="-11" textAnchor="middle" fill="#000" fontSize="8" fontWeight="bold">✓</text>
                  <text x="0" y="42" textAnchor="middle" fill="#ffffff" fontSize="12" fontWeight="600">Internet</text>
                </g>
              );
            }

            const width = node.type === "endpoint" || node.type === "ap" || node.type === "camera" || node.type === "printer" ? 105 : 125;
            const height = 48;

            return (
              <g
                key={node.id}
                transform={`translate(${node.x - width / 2}, ${node.y - height / 2})`}
                onClick={(e) => { e.stopPropagation(); onSelectNode(node.id); }}
                onMouseEnter={() => setHoveredNode(node.id)}
                onMouseLeave={() => setHoveredNode(null)}
                style={{ cursor: "pointer" }}
              >
                {/* Node Box */}
                <rect
                  width={width}
                  height={height}
                  rx="8"
                  fill="#0e1726"
                  stroke={isSelected ? "#10b981" : isCrit ? "#ef4444" : isWarn ? "#f59e0b" : "rgba(255,255,255,0.15)"}
                  strokeWidth={isSelected ? 2.5 : isCrit || isWarn ? 1.8 : 1.2}
                  filter={isSelected ? "url(#glow-green)" : isCrit ? "url(#glow-red)" : undefined}
                />

                {/* Left Mini Icon */}
                <g transform="translate(10, 14)">
                  {node.type === "switch" && <SwitchIcon size={18} style={{ color: statusColor }} />}
                  {node.type === "router" && <SwitchIcon size={18} style={{ color: statusColor }} />}
                  {node.type === "firewall" && <ShieldAlertIcon size={18} style={{ color: statusColor }} />}
                  {node.type === "server" && <DevicesIcon size={18} style={{ color: statusColor }} />}
                  {node.type === "endpoint" && <DevicesIcon size={18} style={{ color: statusColor }} />}
                  {node.type === "ap" && <SwitchIcon size={18} style={{ color: statusColor }} />}
                  {node.type === "camera" && <ShieldAlertIcon size={18} style={{ color: statusColor }} />}
                  {node.type === "printer" && <DevicesIcon size={18} style={{ color: statusColor }} />}
                </g>

                {/* Node Text */}
                <text x="34" y="20" fill="#ffffff" fontSize="10.5" fontWeight="700" fontFamily="var(--font-sans)">
                  {node.name}
                </text>
                <text x="34" y="34" fill="#94a3b8" fontSize="8.5" fontFamily="var(--font-sans)">
                  {showLabels ? node.ip : node.model}
                </text>

                {/* Status Dot / Badge */}
                <circle
                  cx={width - 12}
                  cy="14"
                  r="6.5"
                  fill={statusColor}
                />
                <text
                  x={width - 12}
                  y="17"
                  textAnchor="middle"
                  fill="#000000"
                  fontSize="7.5"
                  fontWeight="bold"
                >
                  {isCrit || isWarn ? "!" : "✓"}
                </text>
              </g>
            );
          })}
        </g>
      </svg>
    </div>
  );
}
