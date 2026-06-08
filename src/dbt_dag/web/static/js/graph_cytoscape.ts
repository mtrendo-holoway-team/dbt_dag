import cytoscape, {
  type Core,
  type ElementDefinition,
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

type LayoutUtilitiesCore = Core & {
  layoutUtilities: (options?: Record<string, unknown>) => void;
};

type HorizontalPlacementConstraint = {
  left: string;
  right: string;
  gap: number;
};

type VerticalPlacementConstraint = {
  top: string;
  bottom: string;
  gap: number;
};

type RelativePlacementConstraint = HorizontalPlacementConstraint | VerticalPlacementConstraint;

type LayoutConstraints = {
  alignmentConstraint?: {
    vertical?: string[][];
  };
  relativePlacementConstraint?: RelativePlacementConstraint[];
};

type GraphNodeDataValue = string | number;

const nodeHeight = 42;
const minNodeWidth = 96;
const maxNodeWidth = 360;
const nodeHorizontalPadding = 15;
const averageLabelCharacterWidth = 7;
const nodeIndicatorRowWidth = 40;
const directionGap = 130;
const sourceNodeGap = 70;
const nodeSpacing = 32;
const maxDirectionConstraints = 300;
const maxSpacingIterations = 200;

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
  await runFcoseLayout(cy, visiblePayload, fit, anchor);
  applySelectionState(cy, selectedNodeId, filterMode, upstream, downstream);
}

export async function rearrangeVisibleNodes(
  cy: Core,
  payload: GraphPayload,
  visibleNodeIds: Set<string>,
  anchor: ViewAnchor | null
): Promise<void> {
  const visiblePayload = filterPayloadByNodeIds(payload, visibleNodeIds);
  if (visiblePayload.nodes.length === 0) return;

  const visibleElements = cy.elements().filter((element) => {
    if (element.isNode()) {
      const kind = element.data("kind");
      if (kind === "node") return visibleNodeIds.has(element.id());
      if (kind === "group") {
        return visiblePayload.groups.some((group) => group.id === element.id());
      }
    }
    if (element.isEdge()) {
      const source = element.data("source") as string;
      const target = element.data("target") as string;
      return visibleNodeIds.has(source) && visibleNodeIds.has(target);
    }
    return false;
  });

  await runFcoseLayout(visibleElements, visiblePayload, false, anchor, cy);
}
export function applySelectionState(
  cy: Core,
  selectedNodeId: string | null,
  filterMode: FilterMode | null,
  upstream: Map<string, Set<string>>,
  downstream: Map<string, Set<string>>
): void {
  const relatedNodes = selectedNodeId
    ? graphRelatedNodeIds(selectedNodeId, filterMode, upstream, downstream)
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
      if (isRelated) {
        edge.addClass("related");
      } else if (!isRelated) {
        edge.addClass("dimmed");
      }
    });
  });
}

export function applyIsolationState(cy: Core, visibleNodeIds: Set<string> | null): void {
  cy.batch(() => {
    cy.elements().removeClass("hidden");
    if (!visibleNodeIds) return;

    cy.nodes("[kind = 'node']").forEach((node) => {
      if (!visibleNodeIds.has(node.id())) {
        node.addClass("hidden");
      }
    });
    cy.nodes("[kind = 'group']").forEach((group) => {
      const groupNodes = group
        .children("[kind = 'node']")
        .filter((node): node is NodeSingular => node.isNode());
      const hasVisibleChild = groupNodes.some((node) => visibleNodeIds.has(node.id()));
      if (!hasVisibleChild) {
        group.addClass("hidden");
      }
    });
    cy.edges().forEach((edge) => {
      if (!visibleNodeIds.has(edge.source().id()) || !visibleNodeIds.has(edge.target().id())) {
        edge.addClass("hidden");
      }
    });
  });
}

export function frameGraphNodes(cy: Core, nodeIds: Iterable<string>): void {
  const nodes = [...nodeIds]
    .map((nodeId) => cy.getElementById(nodeId))
    .filter((node) => !node.empty() && node.isNode());
  if (nodes.length === 0) return;
  cy.fit(cy.collection(nodes), 80);
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

function runFcoseLayout(
  layoutTarget: Core | CollectionReturnValue,
  payload: GraphPayload,
  fit: boolean,
  anchor: ViewAnchor | null,
  cy: Core = layoutTarget as Core
): Promise<void> {
  return new Promise((resolve) => {
    const payloadNodeIds = new Set(payload.nodes.map((node) => node.id));
    const layout = layoutTarget.layout({
      name: "fcose",
      quality: "default",
      randomize: true,
      animate: false,
      fit: true,
      padding: 40,
      uniformNodeDimensions: false,
      packComponents: true,
      tile: true,
      nodeRepulsion: 6000,
      idealEdgeLength: 170,
      edgeElasticity: 0.25,
      nestingFactor: 0.4,
      gravity: 0.08,
      gravityRange: 3.5,
      gravityCompound: 3,
      gravityRangeCompound: 1.5,
      numIter: 10000,
      tilingPaddingVertical: 60,
      tilingPaddingHorizontal: 60,
      initialEnergyOnIncremental: 0.5,
      ...layoutConstraints(payload),
      stop: () => {
        enforceNodeSpacing(
          cy
            .nodes("[kind = 'node']")
            .filter((node): node is NodeSingular => node.isNode() && payloadNodeIds.has(node.id()))
        );
        if (anchor) {
          applyAnchor(cy, anchor);
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
    const displayLabel = `${node.type_badge}  ${node.label}`;
    const data: Record<string, string | number> = {
      id: node.id,
      label: node.label,
      kind: "node",
      nodeWidth: nodeWidthForLabel(displayLabel),
      typeBadge: node.type_badge,
      freshness: node.runtime.freshness,
      lastUpdatedAt: node.runtime.last_updated_at ?? "",
      testStatus: node.test_indicator.status,
      column: node.column,
      fillColor: nodeFill(node),
      borderColor: node.runtime.border_color,
      borderWidth: Math.max(node.runtime.border_width_px, 1)
    } satisfies Record<string, GraphNodeDataValue>;
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
        width: "data(nodeWidth)",
        height: nodeHeight,
        shape: "round-rectangle",
        "background-color": "data(fillColor)",
        "border-color": "data(borderColor)",
        "border-width": "data(borderWidth)",
        label: "",
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
        "text-halign": "center",
        "text-valign": "top",
        "text-margin-x": 0,
        "text-margin-y": 28,
        padding: 40,
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
        "curve-style": "unbundled-bezier",
        "control-point-distances": 70,
        "control-point-weights": 0.5,
        "arrow-scale": 0.85,
        "overlay-opacity": 0
      }
    },
    {
      selector: ".selected",
      style: {
        "outline-color": "#0ea5e9",
        "outline-width": 3,
        "outline-style": "dashed",
        "outline-offset": 5,
        "shadow-blur": 10,
        "shadow-color": "#0f172a",
        "shadow-opacity": 0.18,
        "shadow-offset-y": 4
      }
    },
    {
      selector: "edge.related",
      style: { width: 2 }
    },
    { selector: ".hidden", style: { display: "none" } },
    { selector: ".dimmed", style: { opacity: 0.24, "text-opacity": 0.72 } }
  ];
}

export function centerGraphNode(cy: Core, nodeId: string): void {
  const node = cy.getElementById(nodeId);
  if (node.empty()) return;
  cy.center(node);
}

function layoutConstraints(payload: GraphPayload): LayoutConstraints {
  const sourceLaneNodeIds = sourceGroupNodeIds(payload.groups);
  const relativePlacementConstraint = [
    ...sourceSpacingConstraints(payload.groups),
    ...directionConstraints(payload)
  ];
  return {
    alignmentConstraint:
      sourceLaneNodeIds.length > 1 ? { vertical: [sourceLaneNodeIds] } : undefined,
    relativePlacementConstraint:
      relativePlacementConstraint.length > 0 ? relativePlacementConstraint : undefined
  };
}

function sourceGroupNodeIds(groups: GraphGroup[]): string[] {
  return sourceGroups(groups).flatMap((group) => group.node_ids);
}

function sourceGroups(groups: GraphGroup[]): GraphGroup[] {
  return groups.filter((group) => group.id !== "tag:product");
}

function sourceSpacingConstraints(groups: GraphGroup[]): VerticalPlacementConstraint[] {
  const constraints: VerticalPlacementConstraint[] = [];
  for (const group of sourceGroups(groups)) {
    for (let index = 1; index < group.node_ids.length; index += 1) {
      constraints.push({
        top: group.node_ids[index - 1],
        bottom: group.node_ids[index],
        gap: sourceNodeGap
      });
    }
  }
  return constraints;
}

function directionConstraints(payload: GraphPayload): HorizontalPlacementConstraint[] {
  const constraints: HorizontalPlacementConstraint[] = [];
  for (const edge of payload.edges) {
    if (constraints.length >= maxDirectionConstraints) break;
    constraints.push({ left: edge.source, right: edge.target, gap: directionGap });
  }
  return constraints;
}

function enforceNodeSpacing(nodes: CollectionReturnValue): void {
  for (let iteration = 0; iteration < maxSpacingIterations; iteration += 1) {
    let moved = false;
    for (let leftIndex = 0; leftIndex < nodes.length; leftIndex += 1) {
      for (let rightIndex = leftIndex + 1; rightIndex < nodes.length; rightIndex += 1) {
        moved = separateNodes(nodes[leftIndex], nodes[rightIndex]) || moved;
      }
    }
    if (!moved) return;
  }
}

function separateNodes(left: NodeSingular, right: NodeSingular): boolean {
  const leftPosition = left.position();
  const rightPosition = right.position();
  const deltaX = rightPosition.x - leftPosition.x;
  const deltaY = rightPosition.y - leftPosition.y;
  const overlapX = (left.width() + right.width()) / 2 + nodeSpacing - Math.abs(deltaX);
  const overlapY = (left.height() + right.height()) / 2 + nodeSpacing - Math.abs(deltaY);
  if (overlapX <= 0 || overlapY <= 0) return false;

  if (overlapX < overlapY) {
    const shift = overlapX / 2;
    const direction = deltaX >= 0 ? 1 : -1;
    left.position("x", leftPosition.x - shift * direction);
    right.position("x", rightPosition.x + shift * direction);
    return true;
  }

  const shift = overlapY / 2;
  const direction = deltaY >= 0 ? 1 : -1;
  left.position("y", leftPosition.y - shift * direction);
  right.position("y", rightPosition.y + shift * direction);
  return true;
}

function nodeWidthForLabel(label: string): number {
  return clamp(
    label.length * averageLabelCharacterWidth + nodeHorizontalPadding + nodeIndicatorRowWidth,
    minNodeWidth,
    maxNodeWidth
  );
}

function clamp(value: number, minValue: number, maxValue: number): number {
  return Math.min(Math.max(value, minValue), maxValue);
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

function filterPayload(payload: GraphPayload, activePackages: Set<string>): GraphPayload {
  const nodes = payload.nodes.filter((node) => activePackages.has(node.package_name));
  const nodeIds = new Set(nodes.map((node) => node.id));
  return filterPayloadByNodeIds(payload, nodeIds);
}

function filterPayloadByNodeIds(payload: GraphPayload, nodeIds: Set<string>): GraphPayload {
  return {
    columns: payload.columns,
    nodes: payload.nodes.filter((node) => nodeIds.has(node.id)),
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

function nodeFill(node: GraphNode): string {
  return laneColors[node.column] ?? laneColors.other;
}

export function graphRelatedNodeIds(
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

export function directlyRelatedNodeIds(
  selectedNodeId: string,
  upstream: Map<string, Set<string>>,
  downstream: Map<string, Set<string>>
): Set<string> {
  return new Set([
    selectedNodeId,
    ...(upstream.get(selectedNodeId) ?? []),
    ...(downstream.get(selectedNodeId) ?? [])
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
