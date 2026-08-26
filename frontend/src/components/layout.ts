/**
 * Deterministic layout for the topology map.
 *
 * The same graph must always draw the same way, so every ordering decision falls back to
 * the node id: an operator comparing two screenshots should not see nodes move because a
 * dictionary iterated differently. There is no animation and no force simulation — the
 * layout is a breadth-first layering per connected component, which reads like a network
 * diagram (upstream at the top, downstream below) without needing a physics library.
 */

import type { TopologyEdge, TopologyNode } from "../types";

export const NODE_WIDTH = 176;
export const NODE_HEIGHT = 66;
const COLUMN_GAP = 56;
const ROW_GAP = 118;
const COMPONENT_GAP = 90;
const MARGIN = 60;

export type PlacedNode = TopologyNode & { x: number; y: number };
export type Layout = {
  nodes: PlacedNode[];
  position: Map<string, { x: number; y: number }>;
  width: number;
  height: number;
};

/** Rank used to pick a component root and to break ties inside a row. */
function rootScore(node: TopologyNode): number {
  const byType = node.type === "router" ? 3 : node.type === "firewall" ? 2 : node.type === "switch" ? 1 : 0;
  return node.degree * 10 + byType;
}

export function layoutGraph(nodes: TopologyNode[], edges: TopologyEdge[]): Layout {
  const ordered = [...nodes].sort((left, right) => left.id.localeCompare(right.id));
  const byId = new Map(ordered.map((node) => [node.id, node]));

  const adjacency = new Map<string, string[]>();
  for (const node of ordered) adjacency.set(node.id, []);
  for (const edge of edges) {
    if (!adjacency.has(edge.source) || !adjacency.has(edge.target)) continue;
    adjacency.get(edge.source)!.push(edge.target);
    adjacency.get(edge.target)!.push(edge.source);
  }
  for (const [id, peers] of adjacency) {
    adjacency.set(id, [...new Set(peers)].sort((left, right) => left.localeCompare(right)));
  }

  const seen = new Set<string>();
  const components: string[][] = [];
  for (const node of ordered) {
    if (seen.has(node.id)) continue;
    const queue = [node.id];
    const members: string[] = [];
    seen.add(node.id);
    while (queue.length) {
      const current = queue.shift()!;
      members.push(current);
      for (const peer of adjacency.get(current) ?? []) {
        if (seen.has(peer)) continue;
        seen.add(peer);
        queue.push(peer);
      }
    }
    components.push(members);
  }

  // Bigger components first so the important part of the estate is at the top of the canvas.
  components.sort((left, right) => right.length - left.length || left[0].localeCompare(right[0]));

  const placed: PlacedNode[] = [];
  let cursorY = MARGIN;
  let widest = 0;

  for (const members of components) {
    const root = members
      .map((id) => byId.get(id)!)
      .sort((left, right) => rootScore(right) - rootScore(left) || left.id.localeCompare(right.id))[0];

    const depth = new Map<string, number>([[root.id, 0]]);
    const queue = [root.id];
    while (queue.length) {
      const current = queue.shift()!;
      for (const peer of adjacency.get(current) ?? []) {
        if (depth.has(peer)) continue;
        depth.set(peer, depth.get(current)! + 1);
        queue.push(peer);
      }
    }

    const rows = new Map<number, string[]>();
    for (const id of members) {
      const level = depth.get(id) ?? 0;
      if (!rows.has(level)) rows.set(level, []);
      rows.get(level)!.push(id);
    }

    const levels = [...rows.keys()].sort((left, right) => left - right);
    const rowWidth = (count: number) => count * NODE_WIDTH + (count - 1) * COLUMN_GAP;
    const componentWidth = Math.max(...levels.map((level) => rowWidth(rows.get(level)!.length)));
    widest = Math.max(widest, componentWidth);

    for (const level of levels) {
      // Keep unmanaged endpoints to the right of the row so evidence-only nodes group together.
      const row = rows.get(level)!.sort((left, right) => {
        const a = byId.get(left)!;
        const b = byId.get(right)!;
        if (a.kind !== b.kind) return a.kind === "device" ? -1 : 1;
        return a.hostname.localeCompare(b.hostname) || a.id.localeCompare(b.id);
      });
      const offset = MARGIN + (componentWidth - rowWidth(row.length)) / 2;
      row.forEach((id, index) => {
        placed.push({
          ...byId.get(id)!,
          x: offset + index * (NODE_WIDTH + COLUMN_GAP),
          y: cursorY + level * ROW_GAP,
        });
      });
    }

    cursorY += levels.length * ROW_GAP + COMPONENT_GAP;
  }

  const position = new Map(placed.map((node) => [node.id, { x: node.x, y: node.y }]));
  return {
    nodes: placed,
    position,
    width: Math.max(widest + MARGIN * 2, 720),
    height: Math.max(cursorY - COMPONENT_GAP + NODE_HEIGHT + MARGIN, 360),
  };
}

/** Centre points used to draw an edge between two placed nodes. */
export function anchors(
  from: { x: number; y: number },
  to: { x: number; y: number },
): { x1: number; y1: number; x2: number; y2: number } {
  return {
    x1: from.x + NODE_WIDTH / 2,
    y1: from.y + NODE_HEIGHT / 2,
    x2: to.x + NODE_WIDTH / 2,
    y2: to.y + NODE_HEIGHT / 2,
  };
}
