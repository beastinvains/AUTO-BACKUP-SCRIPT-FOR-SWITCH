/** Interactive topology canvas backed by the graph returned by the API. */

import { useMemo, useRef, useState } from "react";
import { DevicesIcon, ShieldAlertIcon, SwitchIcon } from "./icons";
import type { TopologyEdge, TopologyNode } from "../types";
import { anchors, layoutGraph, NODE_HEIGHT, NODE_WIDTH, type PlacedNode } from "./layout";

function statusColor(status: string): string {
  switch (status.toLowerCase()) {
    case "online": case "healthy": return "#10b981";
    case "degraded": case "warning": return "#f59e0b";
    case "offline": case "failed": case "critical": return "#ef4444";
    default: return "#3b82f6";
  }
}

function NodeIcon({ node }: { node: TopologyNode }) {
  const style = { color: statusColor(node.status) };
  if (node.type === "firewall") return <ShieldAlertIcon size={20} style={style} />;
  if (node.type === "server" || node.type === "hypervisor") return <DevicesIcon size={20} style={style} />;
  return <SwitchIcon size={20} style={style} />;
}

export function TopologyMap({ nodes, edges, selectedNodeId, onSelectNode, showLabels = true, showLinks = true }: {
  nodes: TopologyNode[]; edges: TopologyEdge[]; selectedNodeId: string | null;
  onSelectNode: (id: string | null) => void; showLabels?: boolean; showLinks?: boolean;
}) {
  const [hoveredLink, setHoveredLink] = useState<string | null>(null);
  const [pan, setPan] = useState({ x: 0, y: 0 }); const [zoom, setZoom] = useState(1);
  const [dragging, setDragging] = useState(false); const start = useRef({ x: 0, y: 0 });
  const graph = useMemo(() => layoutGraph(nodes, edges), [nodes, edges]);
  const byId = useMemo(() => new Map(graph.nodes.map((node) => [node.id, node])), [graph.nodes]);
  const beginPan = (event: React.PointerEvent) => { if (event.button !== 0) return; setDragging(true); start.current = { x: event.clientX - pan.x, y: event.clientY - pan.y }; };
  const movePan = (event: React.PointerEvent) => { if (dragging) setPan({ x: event.clientX - start.current.x, y: event.clientY - start.current.y }); };

  return <div className="topology-canvas-wrap" onPointerDown={beginPan} onPointerMove={movePan} onPointerUp={() => setDragging(false)} onPointerLeave={() => setDragging(false)} style={{ cursor: dragging ? "grabbing" : "grab" }}>
    <div style={{ position: "absolute", zIndex: 2, right: 12, top: 12, display: "flex", gap: 4 }}>
      <button className="minimap-btn" onClick={() => setZoom((value) => Math.min(2, value + 0.15))}>+</button>
      <button className="minimap-btn" onClick={() => setZoom((value) => Math.max(0.5, value - 0.15))}>−</button>
      <button className="minimap-btn" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}>Fit</button>
    </div>
    <svg width="100%" height="100%" viewBox={`0 0 ${graph.width} ${graph.height}`} style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`, transformOrigin: "center", transition: dragging ? "none" : "transform .15s" }}>
      <defs><filter id="topology-glow"><feGaussianBlur stdDeviation="3" result="blur" /><feComposite in="SourceGraphic" in2="blur" operator="over" /></filter></defs>
      {showLinks && <g>{edges.map((edge) => {
        const source = byId.get(edge.source); const target = byId.get(edge.target); if (!source || !target) return null;
        const line = anchors(source, target); const color = edge.confidence >= 0.95 ? "#10b981" : edge.confidence >= 0.7 ? "#f59e0b" : "#64748b";
        const midX = (line.x1 + line.x2) / 2; const midY = (line.y1 + line.y2) / 2; const path = `M ${line.x1} ${line.y1} Q ${midX} ${midY} ${line.x2} ${line.y2}`; const hovered = hoveredLink === edge.id;
        return <g key={edge.id} onMouseEnter={() => setHoveredLink(edge.id)} onMouseLeave={() => setHoveredLink(null)}><path d={path} fill="none" stroke="transparent" strokeWidth="14" /><path d={path} fill="none" stroke={color} strokeWidth={hovered ? 3 : 2} strokeDasharray={edge.corroborated ? undefined : "7 5"} opacity={hovered ? 1 : .8} filter="url(#topology-glow)" />{hovered && <text x={midX} y={midY - 8} textAnchor="middle" fill="#fff" fontSize="11" fontFamily="var(--font-mono)">{edge.source_interface ?? "?"} ↔ {edge.target_interface ?? "?"}</text>}</g>;
      })}</g>}
      <g>{graph.nodes.map((node: PlacedNode) => { const selected = node.id === selectedNodeId; const color = statusColor(node.status); return <g key={node.id} transform={`translate(${node.x}, ${node.y})`} onClick={(event) => { event.stopPropagation(); onSelectNode(node.id); }} style={{ cursor: "pointer" }}>
        <rect width={NODE_WIDTH} height={NODE_HEIGHT} rx="8" fill={node.kind === "external" ? "#172033" : "#0e1726"} stroke={selected ? "#10b981" : color} strokeWidth={selected ? 3 : 1.5} strokeDasharray={node.kind === "external" ? "5 4" : undefined} /><g transform="translate(12, 22)"><NodeIcon node={node} /></g><text x="42" y="25" fill="#fff" fontSize="11" fontWeight="700">{node.hostname}</text><text x="42" y="43" fill="#94a3b8" fontSize="9">{showLabels ? (node.management_ip ?? "unmanaged") : `${node.interface_count} interfaces`}</text><circle cx={NODE_WIDTH - 14} cy="15" r="6" fill={color} />
      </g>; })}</g>
    </svg>
  </div>;
}
