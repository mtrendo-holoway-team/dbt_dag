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
export const laneTitleY = 124;
export const nodeWidth = 210;
export const nodeHeight = 42;

const lanePaddingX = 32;
const minLaneHeight = 260;

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
  const elkLayout = await layoutOrder(visiblePayload, nodesById);
  const mainColumns = visibleMainColumns(payload.columns);
  const positionedNodes = positionNodes(visiblePayload.nodes, effectiveColumns, elkLayout.nodePositions);
  const routedEdges = positionEdges(elkLayout.edges, elkLayout.nodePositions, positionedNodes);
  const graphBounds = graphBoundsForLayout(positionedNodes, routedEdges);
  const nodesByColumn = groupNodesByColumn(visiblePayload.nodes, mainColumns);
  const lanes = laneBoundsForColumns(
    [...mainColumns, "other"],
    nodesByColumn,
    positionedNodes,
    graphBounds.width,
    graphBounds.height
  );

  return {
    nodes: positionedNodes,
    edges: routedEdges,
    lanes,
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
      "elk.spacing.nodeNode": "44",
      "elk.layered.spacing.nodeNodeBetweenLayers": "72",
      "elk.layered.spacing.edgeNodeBetweenLayers": "28",
      "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
      "elk.layered.crossingMinimization.greedySwitch.activationThreshold": "0",
      "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
      "elk.layered.nodePlacement.bk.fixedAlignment": "BALANCED"
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

function groupNodesByColumn(nodes: GraphNode[], mainColumns: string[]): Map<string, GraphNode[]> {
  const grouped = new Map<string, GraphNode[]>();
  for (const column of [...mainColumns, "other"]) grouped.set(column, []);
  for (const node of nodes) {
    const column = normalizeColumn(node.column, mainColumns);
    grouped.get(column)?.push(node);
  }
  return grouped;
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
  if (nodes.size === 0) return { width: graphPaddingX * 2, height: minLaneHeight };
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
    height: Math.max(minLaneHeight, maxY + graphPaddingY)
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

function laneBoundsForColumns(
  columns: string[],
  nodesByColumn: Map<string, GraphNode[]>,
  positionedNodes: Map<string, PositionedNode>,
  graphWidth: number,
  graphHeight: number
): { column: string; label: string; x: number; y: number; width: number; height: number }[] {
  const columnCenters = columns.flatMap((column) => {
    const nodes = nodesByColumn.get(column) ?? [];
    const positionedColumnNodes = nodes
      .map((node) => positionedNodes.get(node.id))
      .filter((node): node is PositionedNode => node !== undefined);
    if (positionedColumnNodes.length === 0) return [];
    const sortedCenters = positionedColumnNodes
      .map((node) => node.x + node.width / 2)
      .sort((left, right) => left - right);
    const center = sortedCenters[Math.floor(sortedCenters.length / 2)];
    return [{ column, center }];
  });

  return columnCenters.map((columnCenter, index) => {
    const previousCenter = columnCenters[index - 1]?.center;
    const nextCenter = columnCenters[index + 1]?.center;
    const x = previousCenter === undefined
      ? 0
      : (previousCenter + columnCenter.center) / 2 - lanePaddingX;
    const right = nextCenter === undefined
      ? graphWidth
      : (columnCenter.center + nextCenter) / 2 + lanePaddingX;
    return [
      {
        column: columnCenter.column,
        label: laneLabels[columnCenter.column] ?? columnCenter.column,
        x: Math.max(0, x),
        y: 0,
        width: Math.max(right - x, lanePaddingX * 2),
        height: graphHeight
      }
    ];
  }).flat();
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

function normalizeColumn(column: string, mainColumns: string[]): string {
  return mainColumns.includes(column) ? column : "other";
}
