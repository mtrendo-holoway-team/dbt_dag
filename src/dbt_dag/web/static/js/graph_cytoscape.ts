import cytoscape, {
  type Core,
  type ElementDefinition,
  type NodeSingular,
  type Stylesheet
} from "cytoscape";
import fcose from "cytoscape-fcose";
import layoutUtilities from "cytoscape-layout-utilities";

import type {
  FilterMode,
  GraphGroup,
  GraphNode,
  GraphPayload,
  ViewAnchor
} from "./graph_types";

type LayoutConstraints = {
  alignmentConstraint?: {
    vertical?: string[][];
  };
  relativePlacementConstraint?: Array<{
    left: string;
    right: string;
    gap: number;
  }>;
};

type LayoutUtilitiesCore = Core & {
  layoutUtilities: (options?: Record<string, unknown>) => void;
};

const nodeWidth = 210;
const nodeHeight = 42;
const focusAnimationDurationMs = 260;
const columnGap = 180;
const edgeGap = 60;
const maxEdgeConstraints = 400;

const laneColors: Record<string, string> = {
  sources: "#fbf3c7",
  stg: "#cef0d8",
  int: "#c8e3f5",
  marts: "#d7d4f2",
  exposures: "#efd0f0",
  other: "#e4e4e7"
};

cytoscape.use(layoutUtilities);
cytoscape.use(fcose);

export function createGraph(container: HTMLElement): Core {
  const cy = cytoscape({
    container,
    elements: [],
    style: graphStyle(),
    minZoom: 0.005,
    maxZoom: 2.5,
    wheelSensitivity: 0.2,
    selectionType: "single",
    autoungrabify: false,
    boxSelectionEnabled: false
  });
  (cy as LayoutUtilitiesCore).layoutUtilities({});
  return cy;
}
export async function renderGraph(
  cy: Core,
  payload: GraphPayload,
  activePackages: Set<string>,
  selectedNodeId: string | null,
  filterMode: FilterMode | null,
  fit: boolean,
  anchor: ViewAnchor | null,
  focusNodeId: string | null,
  onSelectNode: (nodeId: string) => void,
  upstream: Map<string, Set<string>>,
  downstream: Map<string, Set<string>>
): Promise<void> {
  const visiblePayload = filterPayload(payload, activePackages);
  cy.off("tap", "node[kind = 'node']");
  cy.batch(() => {
    cy.elements().remove();
    cy.add(elementsForPayload(visiblePayload));
  });
  cy.on("tap", "node[kind = 'node']", (event) => {
    onSelectNode(event.target.id());
  });
  await runFcoseLayout(cy, visiblePayload, fit, anchor, focusNodeId);
  applySelectionState(cy, selectedNodeId, filterMode, upstream, downstream);
}
export function applySelectionState(
  cy: Core,
  selectedNodeId: string | null,
  filterMode: FilterMode | null,
  upstream: Map<string, Set<string>>,
  downstream: Map<string, Set<string>>
): void {
  const relatedNodes = selectedNodeId
    ? relatedNodeIds(selectedNodeId, filterMode, upstream, downstream)
    : null;
  cy.batch(() => {
    cy.elements().removeClass("selected related dimmed");
    if (!selectedNodeId) return;
    cy.getElementById(selectedNodeId).addClass("selected");
    cy.nodes("[kind = 'node']").forEach((node) => {
      if (relatedNodes?.has(node.id())) return;
      node.addClass("dimmed");
    });
    cy.edges().forEach((edge) => {
      const isRelated =
        relatedNodes?.has(edge.source().id()) && relatedNodes.has(edge.target().id());
      if (isRelated && filterMode) {
        edge.addClass("related");
      } else if (!isRelated) {
        edge.addClass("dimmed");
      }
    });
  });
}
export function getCenterAnchor(cy: Core, allowedNodeIds: Set<string>): ViewAnchor | null {
  const center = {
    x: cy.width() / 2,
    y: cy.height() / 2
  };
  let best: ViewAnchor | null = null;
  let bestDistance = Number.POSITIVE_INFINITY;
  cy.nodes("[kind = 'node']").forEach((node) => {
    if (!allowedNodeIds.has(node.id())) return;
    const screenPosition = node.renderedPosition();
    const distance = Math.hypot(screenPosition.x - center.x, screenPosition.y - center.y);
    if (distance >= bestDistance) return;
    bestDistance = distance;
    best = { nodeId: node.id(), screenX: screenPosition.x, screenY: screenPosition.y };
  });
  return best;
}
export function hasGraphNode(cy: Core, nodeId: string): boolean {
  return !cy.getElementById(nodeId).empty();
}
export function nextKeyboardNodeId(
  direction: string,
  cy: Core,
  selectedNodeId: string,
  upstream: Map<string, Set<string>>,
  downstream: Map<string, Set<string>>
): string | null {
  if (direction === "right") {
    return sortedRelatedNodes(cy, downstream.get(selectedNodeId))[0]?.id() ?? null;
  }

  const primaryParentId = selectPrimaryParent(cy, selectedNodeId, upstream);
  if (!primaryParentId) return null;

  if (direction === "left") return primaryParentId;

  const siblings = sortedRelatedNodes(cy, downstream.get(primaryParentId));
  const currentIndex = siblings.findIndex((node) => node.id() === selectedNodeId);
  if (currentIndex < 0) return null;
  if (direction === "up") return siblings[currentIndex - 1]?.id() ?? null;
  if (direction === "down") return siblings[currentIndex + 1]?.id() ?? null;
  return null;
}

function runFcoseLayout(
  cy: Core,
  payload: GraphPayload,
  fit: boolean,
  anchor: ViewAnchor | null,
  focusNodeId: string | null
): Promise<void> {
  return new Promise((resolve) => {
    const layout = cy.layout({
      name: "fcose",
      quality: "default",
      randomize: true,
      animate: true,
      fit: true,
      padding: 40,
      uniformNodeDimensions: false,
      packComponents: true,
      tile: true,
      nodeRepulsion: 3000,
      idealEdgeLength: 50,
      edgeElasticity: 0.45,
      nestingFactor: 1,
      gravity: 0.25,
      gravityRange: 5,
      gravityCompound: 1,
      gravityRangeCompound: 1.5,
      numIter: 10000,
      tilingPaddingVertical: 20,
      tilingPaddingHorizontal: 20,
      initialEnergyOnIncremental: 0.5,
      ...layoutConstraints(payload),
      stop: () => {
        if (anchor) {
          applyAnchor(cy, anchor);
        } else if (focusNodeId) {
          centerNode(cy, focusNodeId);
        } else if (fit) {
          cy.fit(undefined, 40);
        }
        resolve();
      }
    });
    layout.run();
  });
}

function elementsForPayload(payload: GraphPayload): ElementDefinition[] {
  const groupIdByNode = groupIdByNodeId(payload.groups);
  const groupElements = payload.groups.map((group) => ({
    data: { id: group.id, label: group.label, kind: "group" },
    classes: group.id === "tag:product" ? "product-group" : "source-group"
  }));
  const nodeElements = payload.nodes.map((node) => {
    const parent = groupIdByNode.get(node.id);
    const data: Record<string, string | number> = {
      id: node.id,
      label: node.label,
      displayLabel: `${node.type_badge}  ${node.label}`,
      kind: "node",
      column: node.column,
      fillColor: nodeFill(node),
      borderColor: node.runtime.border_color,
      borderWidth: Math.max(node.runtime.border_width_px, 1)
    };
    if (parent) data.parent = parent;
    return { data, classes: "graph-node" };
  });
  const edgeElements = payload.edges.map((edge) => ({
    data: { id: edge.id, source: edge.source, target: edge.target, kind: "edge" }
  }));
  return [...groupElements, ...nodeElements, ...edgeElements];
}

function graphStyle(): Stylesheet[] {
  return [
    { selector: "core", style: { "active-bg-opacity": 0 } },
    {
      selector: "node[kind = 'node']",
      style: {
        width: nodeWidth,
        height: nodeHeight,
        shape: "round-rectangle",
        "background-color": "data(fillColor)",
        "border-color": "data(borderColor)",
        "border-width": "data(borderWidth)",
        label: "data(displayLabel)",
        color: "#18181b",
        "font-family": "system-ui, sans-serif",
        "font-size": 13,
        "text-halign": "center",
        "text-valign": "center",
        "text-wrap": "none",
        "text-max-width": 174,
        "overlay-opacity": 0
      }
    },
    {
      selector: "node[kind = 'group']",
      style: {
        shape: "round-rectangle",
        "background-color": "#e7e5e4",
        "background-opacity": 0.72,
        "border-color": "#d6d3d1",
        "border-width": 1,
        label: "data(label)",
        color: "#44403c",
        "font-family": "system-ui, sans-serif",
        "font-size": 13,
        "font-weight": 600,
        "text-halign": "left",
        "text-valign": "top",
        "text-margin-x": 16,
        "text-margin-y": 12,
        padding: 28,
        "overlay-opacity": 0
      }
    },
    {
      selector: "node.product-group",
      style: { "background-color": "#e0f2fe", "border-color": "#bae6fd" }
    },
    {
      selector: "edge",
      style: {
        width: 1,
        "line-color": "#777",
        "target-arrow-color": "#777",
        "target-arrow-shape": "triangle",
        "curve-style": "bezier",
        "arrow-scale": 0.85,
        "overlay-opacity": 0
      }
    },
    {
      selector: ".selected",
      style: {
        "background-color": "#e0f2fe",
        "border-color": "#a1a1aa",
        "border-width": 2,
        "border-style": "dashed",
        "shadow-blur": 10,
        "shadow-color": "#0f172a",
        "shadow-opacity": 0.18,
        "shadow-offset-y": 4
      }
    },
    {
      selector: "edge.related",
      style: { width: 1.67, "line-color": "#0ea5e9", "target-arrow-color": "#0ea5e9" }
    },
    { selector: ".dimmed", style: { opacity: 0.24, "text-opacity": 0.72 } }
  ];
}

function layoutConstraints(payload: GraphPayload): LayoutConstraints {
  const effectiveColumns = effectiveColumnByNode(payload);
  const nodesByColumn = new Map<string, string[]>();
  for (const node of payload.nodes) {
    const column = effectiveColumns.get(node.id) ?? node.column;
    const nodeIds = nodesByColumn.get(column) ?? [];
    nodeIds.push(node.id);
    nodesByColumn.set(column, nodeIds);
  }
  const orderedColumns = payload.columns.filter((column) => nodesByColumn.has(column));
  const vertical = [...nodesByColumn.values()].filter((nodeIds) => nodeIds.length > 1);
  const relativePlacementConstraint = relativeColumnConstraints(orderedColumns, nodesByColumn);

  for (const edge of payload.edges) {
    if (relativePlacementConstraint.length >= maxEdgeConstraints) break;
    const sourceIndex = orderedColumns.indexOf(effectiveColumns.get(edge.source) ?? "");
    const targetIndex = orderedColumns.indexOf(effectiveColumns.get(edge.target) ?? "");
    if (sourceIndex < 0 || targetIndex < 0 || sourceIndex >= targetIndex) continue;
    relativePlacementConstraint.push({ left: edge.source, right: edge.target, gap: edgeGap });
  }

  return {
    alignmentConstraint: vertical.length > 0 ? { vertical } : undefined,
    relativePlacementConstraint:
      relativePlacementConstraint.length > 0 ? relativePlacementConstraint : undefined
  };
}

function relativeColumnConstraints(
  orderedColumns: string[],
  nodesByColumn: Map<string, string[]>
): Array<{ left: string; right: string; gap: number }> {
  const constraints: Array<{ left: string; right: string; gap: number }> = [];
  for (let index = 1; index < orderedColumns.length; index += 1) {
    const left = nodesByColumn.get(orderedColumns[index - 1])?.[0];
    const right = nodesByColumn.get(orderedColumns[index])?.[0];
    if (left && right) constraints.push({ left, right, gap: columnGap });
  }
  return constraints;
}

function applyAnchor(cy: Core, anchor: ViewAnchor): void {
  const node = cy.getElementById(anchor.nodeId);
  if (node.empty()) return;
  const position = node.position();
  const zoom = cy.zoom();
  cy.pan({
    x: anchor.screenX - position.x * zoom,
    y: anchor.screenY - position.y * zoom
  });
}

function centerNode(cy: Core, nodeId: string): void {
  const node = cy.getElementById(nodeId);
  if (node.empty()) return;
  cy.animate({ center: { eles: node }, duration: focusAnimationDurationMs });
}

function filterPayload(payload: GraphPayload, activePackages: Set<string>): GraphPayload {
  const nodes = payload.nodes.filter((node) => activePackages.has(node.package_name));
  const nodeIds = new Set(nodes.map((node) => node.id));
  return {
    columns: payload.columns,
    nodes,
    edges: payload.edges.filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target)),
    groups: payload.groups
      .map((group) => ({ ...group, node_ids: group.node_ids.filter((id) => nodeIds.has(id)) }))
      .filter((group) => group.node_ids.length > 0),
    project: payload.project
  };
}

function groupIdByNodeId(groups: GraphGroup[]): Map<string, string> {
  const groupIdByNode = new Map<string, string>();
  groups.forEach((group) => {
    group.node_ids.forEach((nodeId) => {
      if (!groupIdByNode.has(nodeId)) groupIdByNode.set(nodeId, group.id);
    });
  });
  return groupIdByNode;
}

function effectiveColumnByNode(payload: GraphPayload): Map<string, string> {
  const mainColumns = payload.columns.filter((column) => column !== "other");
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

function nodeFill(node: GraphNode): string {
  return laneColors[node.column] ?? laneColors.other;
}

function relatedNodeIds(
  selectedNodeId: string,
  mode: FilterMode | null,
  upstream: Map<string, Set<string>>,
  downstream: Map<string, Set<string>>
): Set<string> {
  if (mode === "upstream") return walkGraph(selectedNodeId, upstream);
  if (mode === "downstream") return walkGraph(selectedNodeId, downstream);
  return new Set([
    ...walkGraph(selectedNodeId, upstream),
    ...walkGraph(selectedNodeId, downstream)
  ]);
}

function walkGraph(startNodeId: string, adjacency: Map<string, Set<string>>): Set<string> {
  const visited = new Set<string>([startNodeId]);
  const queue = [...(adjacency.get(startNodeId) ?? [])];
  while (queue.length > 0) {
    const nodeId = queue.shift();
    if (!nodeId || visited.has(nodeId)) continue;
    visited.add(nodeId);
    queue.push(...(adjacency.get(nodeId) ?? []));
  }
  return visited;
}

function selectPrimaryParent(
  cy: Core,
  nodeId: string,
  upstream: Map<string, Set<string>>
): string | null {
  const currentNode = cy.getElementById(nodeId);
  if (currentNode.empty()) return null;
  const currentPosition = currentNode.position();
  return (
    sortedRelatedNodes(cy, upstream.get(nodeId)).sort((left, right) => {
      const leftPosition = left.position();
      const rightPosition = right.position();
      return (
        Math.abs(leftPosition.x - currentPosition.x) -
          Math.abs(rightPosition.x - currentPosition.x) ||
        Math.abs(leftPosition.y - currentPosition.y) -
          Math.abs(rightPosition.y - currentPosition.y)
      );
    })[0]?.id() ?? null
  );
}

function sortedRelatedNodes(cy: Core, nodeIds: Set<string> | undefined): NodeSingular[] {
  return [...(nodeIds ?? new Set<string>())]
    .map((nodeId) => cy.getElementById(nodeId))
    .filter((node): node is NodeSingular => !node.empty() && node.isNode())
    .sort((left, right) => {
      const leftPosition = left.position();
      const rightPosition = right.position();
      return leftPosition.y - rightPosition.y || leftPosition.x - rightPosition.x;
    });
}
