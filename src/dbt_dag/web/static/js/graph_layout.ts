import ELK, { type ElkNode } from "elkjs/lib/elk.bundled.js";

import type { GraphEdge, GraphLayout, GraphNode, GraphPayload, PositionedNode } from "./graph_types";

export const graphPaddingX = 48;
export const graphPaddingY = 140;
export const laneTitleY = 124;
export const nodeWidth = 210;
export const nodeHeight = 42;

const laneGapX = 28;
const lanePaddingX = 64;
const nodeGapX = 34;
const nodeGapY = 38;
const otherGap = 76;
const minLaneWidth = 220;

const laneLabels: Record<string, string> = {
  sources: "Источники",
  stg: "Стейдж",
  int: "Инт",
  marts: "Март",
  exposures: "Дашборды",
  other: "Другое"
};

export async function layoutGraph(
  payload: GraphPayload,
  activePackages: Set<string>
): Promise<GraphLayout> {
  const visiblePayload = filterPayload(payload, activePackages);
  const nodesById = new Map(visiblePayload.nodes.map((node) => [node.id, node]));
  const effectiveColumns = effectiveColumnByNode(visiblePayload);
  const elkOrder = await layoutOrder(visiblePayload, nodesById);
  const mainColumns = visibleMainColumns(payload.columns);
  const nodesByColumn = groupNodesByColumn(visiblePayload.nodes, effectiveColumns, mainColumns);
  const sameColumnRanks = sameColumnRankByNode(visiblePayload.edges, effectiveColumns, nodesById);
  const lanes = [];
  const positionedNodes = new Map<string, PositionedNode>();
  let nextLaneX = graphPaddingX;
  const lanePlans = mainColumns
    .map((column) => ({
      column,
      nodes: orderedLaneNodes(nodesByColumn.get(column) ?? [], elkOrder, sameColumnRanks)
    }))
    .filter((plan) => plan.nodes.length > 0);
  const mainLaneHeight = Math.max(260, ...lanePlans.map((plan) => laneHeightForNodes(plan.nodes, sameColumnRanks)));

  for (const { column, nodes } of lanePlans) {
    const width = laneWidthForNodes(nodes, sameColumnRanks);
    lanes.push({ column, label: laneLabels[column] ?? column, x: nextLaneX, y: 0, width, height: mainLaneHeight });
    placeLayeredNodes(nodes, column, nextLaneX + lanePaddingX, graphPaddingY, sameColumnRanks, elkOrder, positionedNodes);
    nextLaneX += width + laneGapX;
  }

  const graphWidth = Math.max(nextLaneX + graphPaddingX - laneGapX, graphPaddingX * 2);
  const otherNodes = orderedLaneNodes(nodesByColumn.get("other") ?? [], elkOrder, sameColumnRanks);
  const otherY = otherNodes.length > 0 ? mainLaneHeight + otherGap : mainLaneHeight;
  const otherWidth = otherNodes.length > 0
    ? Math.max(graphWidth, laneWidthForNodes(otherNodes, sameColumnRanks))
    : graphWidth;
  const otherHeight = otherNodes.length > 0 ? laneHeightForNodes(otherNodes, sameColumnRanks) : 0;
  if (otherNodes.length > 0) {
    lanes.push({
      column: "other",
      label: laneLabels.other,
      x: 0,
      y: otherY,
      width: otherWidth,
      height: otherHeight
    });
    placeLayeredNodes(
      otherNodes,
      "other",
      lanePaddingX,
      otherY + graphPaddingY,
      sameColumnRanks,
      elkOrder,
      positionedNodes
    );
  }

  return {
    nodes: positionedNodes,
    edges: visiblePayload.edges,
    lanes,
    width: Math.max(graphWidth, otherWidth),
    height: otherY + otherHeight
  };
}

export function visibleMainColumns(columns: string[]): string[] {
  return columns.filter((column) => column !== "other");
}

function filterPayload(payload: GraphPayload, activePackages: Set<string>): GraphPayload {
  const nodes = payload.nodes.filter((node) => activePackages.has(node.package_name));
  const nodeIds = new Set(nodes.map((node) => node.id));
  return {
    columns: payload.columns,
    nodes,
    edges: payload.edges.filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
  };
}

function laneWidthForNodes(nodes: GraphNode[], sameColumnRanks: Map<string, number>): number {
  if (nodes.length === 0) return 0;
  const maxRank = Math.max(...nodes.map((node) => sameColumnRanks.get(node.id) ?? 0));
  return Math.max(minLaneWidth, lanePaddingX * 2 + (maxRank + 1) * nodeWidth + maxRank * nodeGapX);
}

function laneHeightForNodes(nodes: GraphNode[], sameColumnRanks: Map<string, number>): number {
  if (nodes.length === 0) return 0;
  const rowsByRank = new Map<number, number>();
  nodes.forEach((node) => {
    const rank = sameColumnRanks.get(node.id) ?? 0;
    rowsByRank.set(rank, (rowsByRank.get(rank) ?? 0) + 1);
  });
  const maxRows = Math.max(...rowsByRank.values());
  return graphPaddingY + maxRows * nodeHeight + Math.max(maxRows - 1, 0) * nodeGapY + 48;
}

async function layoutOrder(
  payload: GraphPayload,
  nodesById: Map<string, GraphNode>
): Promise<Map<string, { x: number; y: number }>> {
  const elkGraph: ElkNode = {
    id: "root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "RIGHT",
      "elk.edgeRouting": "SPLINES",
      "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
      "elk.layered.crossingMinimization.greedySwitch.activationThreshold": "0",
      "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF"
    },
    children: payload.nodes.map((node) => ({
      id: node.id,
      width: nodeWidth,
      height: nodeHeight
    })),
    edges: payload.edges
      .filter((edge) => nodesById.has(edge.source) && nodesById.has(edge.target))
      .map((edge) => ({
        id: edge.id,
        sources: [edge.source],
        targets: [edge.target]
      }))
  };
  const layout = await new ELK().layout(elkGraph);
  return new Map(
    (layout.children ?? []).map((node) => [node.id, { x: node.x ?? 0, y: node.y ?? 0 }])
  );
}

function groupNodesByColumn(
  nodes: GraphNode[],
  effectiveColumns: Map<string, string>,
  mainColumns: string[]
): Map<string, GraphNode[]> {
  const grouped = new Map<string, GraphNode[]>();
  for (const column of [...mainColumns, "other"]) grouped.set(column, []);
  for (const node of nodes) {
    const column = effectiveColumns.get(node.id) ?? normalizeColumn(node.column, mainColumns);
    grouped.get(column)?.push(node);
  }
  return grouped;
}

function orderedLaneNodes(
  nodes: GraphNode[],
  elkOrder: Map<string, { x: number; y: number }>,
  sameColumnRanks: Map<string, number>
): GraphNode[] {
  return [...nodes].sort((left, right) => {
    const leftRank = sameColumnRanks.get(left.id) ?? 0;
    const rightRank = sameColumnRanks.get(right.id) ?? 0;
    if (leftRank !== rightRank) return leftRank - rightRank;
    const leftOrder = elkOrder.get(left.id) ?? { x: 0, y: 0 };
    const rightOrder = elkOrder.get(right.id) ?? { x: 0, y: 0 };
    if (leftOrder.x !== rightOrder.x) return leftOrder.x - rightOrder.x;
    if (leftOrder.y !== rightOrder.y) return leftOrder.y - rightOrder.y;
    const labelOrder = left.label.localeCompare(right.label);
    return labelOrder === 0 ? left.id.localeCompare(right.id) : labelOrder;
  });
}

function placeLayeredNodes(
  nodes: GraphNode[],
  effectiveColumn: string,
  startX: number,
  startY: number,
  sameColumnRanks: Map<string, number>,
  elkOrder: Map<string, { x: number; y: number }>,
  result: Map<string, PositionedNode>
): void {
  const nodesByRank = new Map<number, GraphNode[]>();
  nodes.forEach((node) => {
    const rank = sameColumnRanks.get(node.id) ?? 0;
    const rankNodes = nodesByRank.get(rank) ?? [];
    rankNodes.push(node);
    nodesByRank.set(rank, rankNodes);
  });
  nodesByRank.forEach((rankNodes, rank) => {
    orderedLaneNodes(rankNodes, elkOrder, sameColumnRanks).forEach((node, rowIndex) => {
      result.set(node.id, {
        ...node,
        effectiveColumn,
        x: startX + rank * (nodeWidth + nodeGapX),
        y: startY + rowIndex * (nodeHeight + nodeGapY),
        width: nodeWidth,
        height: nodeHeight
      });
    });
  });
}

function effectiveColumnByNode(payload: GraphPayload): Map<string, string> {
  const mainColumns = visibleMainColumns(payload.columns);
  const mainColumnIndex = new Map(mainColumns.map((column, index) => [column, index]));
  const nodesById = new Map(payload.nodes.map((node) => [node.id, node]));
  const effectiveIndexes = new Map(
    payload.nodes.map((node) => [
      node.id,
      mainColumnIndex.get(node.column) ?? mainColumns.length
    ])
  );

  for (let step = 0; step < payload.nodes.length; step += 1) {
    let changed = false;
    for (const edge of payload.edges) {
      if (!nodesById.has(edge.source) || !nodesById.has(edge.target)) continue;
      const sourceIndex = effectiveIndexes.get(edge.source);
      const targetIndex = effectiveIndexes.get(edge.target);
      if (sourceIndex === undefined || targetIndex === undefined || targetIndex >= sourceIndex) {
        continue;
      }
      effectiveIndexes.set(edge.target, sourceIndex);
      changed = true;
    }
    if (!changed) break;
  }

  return new Map(
    payload.nodes.map((node) => {
      const index = effectiveIndexes.get(node.id) ?? mainColumns.length;
      return [node.id, mainColumns[index] ?? "other"];
    })
  );
}

function sameColumnRankByNode(
  edges: GraphEdge[],
  effectiveColumns: Map<string, string>,
  nodesById: Map<string, GraphNode>
): Map<string, number> {
  const ranks = new Map([...nodesById.keys()].map((nodeId) => [nodeId, 0]));
  for (let step = 0; step < nodesById.size; step += 1) {
    let changed = false;
    for (const edge of edges) {
      if (effectiveColumns.get(edge.source) !== effectiveColumns.get(edge.target)) continue;
      const sourceRank = ranks.get(edge.source) ?? 0;
      const targetRank = ranks.get(edge.target) ?? 0;
      if (targetRank > sourceRank) continue;
      ranks.set(edge.target, sourceRank + 1);
      changed = true;
    }
    if (!changed) break;
  }
  return ranks;
}

function normalizeColumn(column: string, mainColumns: string[]): string {
  return mainColumns.includes(column) ? column : "other";
}
