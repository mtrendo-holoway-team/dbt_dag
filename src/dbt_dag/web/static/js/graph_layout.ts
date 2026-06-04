import ELK, { type ElkNode } from "elkjs/lib/elk.bundled.js";

import type {
  GraphEdge,
  GraphEdgePoint,
  GraphLayout,
  GraphNode,
  GraphPayload,
  PositionedNode,
  RoutedGraphEdge
} from "./graph_types";

export const graphPaddingX = 48;
export const graphPaddingY = 140;
export const nodeWidth = 210;
export const nodeHeight = 42;

const minGraphHeight = 260;

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
  const graphBounds = graphBoundsForLayout(positionedNodes, routedEdges);

  return {
    nodes: positionedNodes,
    edges: routedEdges,
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
    edges: payload.edges.filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
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
  edges: RoutedGraphEdge[]
): { width: number; height: number } {
  if (nodes.size === 0) return { width: graphPaddingX * 2, height: minGraphHeight };
  let maxX = 0;
  let maxY = 0;
  nodes.forEach((node) => {
    maxX = Math.max(maxX, node.x + node.width);
    maxY = Math.max(maxY, node.y + node.height);
  });
  edges.forEach((edge) => {
    edge.points.forEach((point) => {
      maxX = Math.max(maxX, point.x);
      maxY = Math.max(maxY, point.y);
    });
  });
  return {
    width: maxX + graphPaddingX,
    height: Math.max(minGraphHeight, maxY + graphPaddingY)
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
