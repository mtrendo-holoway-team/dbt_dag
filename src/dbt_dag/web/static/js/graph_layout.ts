import ELK, { type ElkNode } from "elkjs/lib/elk.bundled.js";

import type {
  GraphEdge,
  GraphEdgePoint,
  GraphGroup,
  GraphLayout,
  GraphNode,
  GraphPayload,
  PositionedGroup,
  PositionedNode,
  RoutedGraphEdge
} from "./graph_types";

export const graphPaddingX = 48;
export const graphPaddingY = 140;
export const nodeWidth = 210;
export const nodeHeight = 42;

const minGraphHeight = 260;
const groupPaddingX = 20;
const groupPaddingTop = 36;
const groupPaddingBottom = 20;

export async function layoutGraph(
  payload: GraphPayload,
  activePackages: Set<string>
): Promise<GraphLayout> {
  const visiblePayload = filterPayload(payload, activePackages);
  const nodesById = new Map(visiblePayload.nodes.map((node) => [node.id, node]));
  const effectiveColumns = effectiveColumnByNode(visiblePayload);
  const elkLayout = await layoutOrder(visiblePayload, nodesById);
  const positionedNodes = positionNodes(visiblePayload.nodes, effectiveColumns, elkLayout.nodePositions);
  const routedEdges = positionEdges(elkLayout.edges, elkLayout.nodePositions, positionedNodes);
  const positionedGroups = positionGroups(visiblePayload.groups, positionedNodes);
  const graphBounds = graphBoundsForLayout(positionedNodes, routedEdges, positionedGroups);

  return {
    nodes: positionedNodes,
    edges: routedEdges,
    groups: positionedGroups,
    width: graphBounds.width,
    height: graphBounds.height
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
    edges: payload.edges.filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target)),
    groups: payload.groups
      .map((group) => ({
        ...group,
        node_ids: group.node_ids.filter((nodeId) => nodeIds.has(nodeId))
      }))
      .filter((group) => group.node_ids.length > 0),
    project: payload.project
  };
}

async function layoutOrder(
  payload: GraphPayload,
  nodesById: Map<string, GraphNode>
): Promise<{ nodePositions: Map<string, { x: number; y: number }>; edges: RoutedGraphEdge[] }> {
  const edgesById = new Map(payload.edges.map((edge) => [edge.id, edge]));
  const elkGraph: ElkNode = {
    id: "root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "RIGHT",
      "elk.edgeRouting": "ORTHOGONAL",
      "elk.spacing.nodeNode": "56",
      "elk.layered.spacing.nodeNodeBetweenLayers": "92",
      "elk.layered.spacing.edgeNodeBetweenLayers": "28",
      "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
      "elk.layered.crossingMinimization.greedySwitch.activationThreshold": "0",
      "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
      "elk.layered.nodePlacement.favorStraightEdges": "false"
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
  const nodePositions = new Map(
    (layout.children ?? []).map((node) => [node.id, { x: node.x ?? 0, y: node.y ?? 0 }])
  );
  return {
    nodePositions,
    edges: routedEdges(layout.edges ?? [], edgesById)
  };
}

function positionNodes(
  nodes: GraphNode[],
  effectiveColumns: Map<string, string>,
  elkOrder: Map<string, { x: number; y: number }>
): Map<string, PositionedNode> {
  if (nodes.length === 0) return new Map();
  const minX = Math.min(...nodes.map((node) => elkOrder.get(node.id)?.x ?? 0));
  const minY = Math.min(...nodes.map((node) => elkOrder.get(node.id)?.y ?? 0));
  return new Map(
    nodes.map((node) => {
      const position = elkOrder.get(node.id) ?? { x: minX, y: minY };
      return [
        node.id,
        {
          ...node,
          effectiveColumn: effectiveColumns.get(node.id) ?? node.column,
          x: graphPaddingX + position.x - minX,
          y: graphPaddingY + position.y - minY,
          width: nodeWidth,
          height: nodeHeight
        }
      ];
    })
  );
}

function positionEdges(
  edges: RoutedGraphEdge[],
  nodePositions: Map<string, { x: number; y: number }>,
  positionedNodes: Map<string, PositionedNode>
): RoutedGraphEdge[] {
  if (positionedNodes.size === 0) return [];
  const minX = Math.min(...[...nodePositions.values()].map((point) => point.x));
  const minY = Math.min(...[...nodePositions.values()].map((point) => point.y));
  return edges.map((edge) => ({
    ...edge,
    points: edge.points.map((point) => ({
      x: graphPaddingX + point.x - minX,
      y: graphPaddingY + point.y - minY
    }))
  }));
}

function graphBoundsForLayout(
  nodes: Map<string, PositionedNode>,
  edges: RoutedGraphEdge[],
  groups: PositionedGroup[]
): { width: number; height: number } {
  if (nodes.size === 0) return { width: graphPaddingX * 2, height: minGraphHeight };
  let maxX = 0;
  let maxY = 0;
  let minX = graphPaddingX;
  let minY = graphPaddingY;
  nodes.forEach((node) => {
    minX = Math.min(minX, node.x);
    minY = Math.min(minY, node.y);
    maxX = Math.max(maxX, node.x + node.width);
    maxY = Math.max(maxY, node.y + node.height);
  });
  edges.forEach((edge) => {
    edge.points.forEach((point) => {
      minX = Math.min(minX, point.x);
      minY = Math.min(minY, point.y);
      maxX = Math.max(maxX, point.x);
      maxY = Math.max(maxY, point.y);
    });
  });
  groups.forEach((group) => {
    minX = Math.min(minX, group.x);
    minY = Math.min(minY, group.y);
    maxX = Math.max(maxX, group.x + group.width);
    maxY = Math.max(maxY, group.y + group.height);
  });
  return {
    width: maxX + Math.max(graphPaddingX, -Math.min(0, minX)),
    height: Math.max(minGraphHeight, maxY + Math.max(graphPaddingY, -Math.min(0, minY)))
  };
}

function routedEdges(
  edges: Array<{
    id?: string;
    sections?: Array<{
      startPoint?: { x?: number; y?: number };
      endPoint?: { x?: number; y?: number };
      bendPoints?: Array<{ x?: number; y?: number }>;
    }>;
  }>,
  edgesById: Map<string, GraphEdge>
): RoutedGraphEdge[] {
  return edges.flatMap((edge) => {
    if (!edge.id) return [];
    const rawEdge = edgesById.get(edge.id);
    if (!rawEdge) return [];
    const points = mergeSectionPoints(edge.sections ?? []);
    if (points.length < 2) return [];
    return [{ ...rawEdge, points }];
  });
}

function mergeSectionPoints(
  sections: Array<{
    startPoint?: { x?: number; y?: number };
    endPoint?: { x?: number; y?: number };
    bendPoints?: Array<{ x?: number; y?: number }>;
  }>
): GraphEdgePoint[] {
  const points: GraphEdgePoint[] = [];
  sections.forEach((section) => {
    const sectionPoints = [
      section.startPoint,
      ...(section.bendPoints ?? []),
      section.endPoint
    ].flatMap((point) => {
      if (point?.x === undefined || point.y === undefined) return [];
      return [{ x: point.x, y: point.y }];
    });
    sectionPoints.forEach((point) => {
      const previous = points[points.length - 1];
      if (previous && previous.x === point.x && previous.y === point.y) return;
      points.push(point);
    });
  });
  return points;
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

function positionGroups(
  groups: GraphGroup[],
  positionedNodes: Map<string, PositionedNode>
): PositionedGroup[] {
  return groups.flatMap((group) => {
    const nodes = group.node_ids
      .map((nodeId) => positionedNodes.get(nodeId))
      .filter((node): node is PositionedNode => node !== undefined);
    if (nodes.length === 0) return [];
    const clusters = mergeGroupNodeRects(nodes);
    return clusters.map((cluster, index) => ({
      ...group,
      id: `${group.id}:${index}`,
      label: index === 0 ? group.label : "",
      x: cluster.x,
      y: cluster.y,
      width: cluster.width,
      height: cluster.height
    }));
  });
}

function mergeGroupNodeRects(nodes: PositionedNode[]): Array<{
  x: number;
  y: number;
  width: number;
  height: number;
}> {
  const pending = nodes.map((node) => ({
    x: node.x - groupPaddingX,
    y: node.y - groupPaddingTop,
    width: node.width + groupPaddingX * 2,
    height: node.height + groupPaddingTop + groupPaddingBottom
  }));
  const merged: typeof pending = [];

  pending.forEach((rect) => {
    let nextRect = rect;
    let mergedIndex = merged.findIndex((existing) => rectsTouch(existing, nextRect));
    while (mergedIndex >= 0) {
      nextRect = unionRect(merged[mergedIndex], nextRect);
      merged.splice(mergedIndex, 1);
      mergedIndex = merged.findIndex((existing) => rectsTouch(existing, nextRect));
    }
    merged.push(nextRect);
  });

  return merged.sort((left, right) => left.y - right.y || left.x - right.x);
}

function rectsTouch(
  left: { x: number; y: number; width: number; height: number },
  right: { x: number; y: number; width: number; height: number }
): boolean {
  const mergeGapX = 24;
  const mergeGapY = 28;
  return (
    left.x <= right.x + right.width + mergeGapX &&
    left.x + left.width + mergeGapX >= right.x &&
    left.y <= right.y + right.height + mergeGapY &&
    left.y + left.height + mergeGapY >= right.y
  );
}

function unionRect(
  left: { x: number; y: number; width: number; height: number },
  right: { x: number; y: number; width: number; height: number }
): { x: number; y: number; width: number; height: number } {
  const minX = Math.min(left.x, right.x);
  const minY = Math.min(left.y, right.y);
  const maxX = Math.max(left.x + left.width, right.x + right.width);
  const maxY = Math.max(left.y + left.height, right.y + right.height);
  return {
    x: minX,
    y: minY,
    width: maxX - minX,
    height: maxY - minY
  };
}
