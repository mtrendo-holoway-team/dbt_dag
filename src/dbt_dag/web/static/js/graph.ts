import hotkeys from "hotkeys-js";
import htmx from "htmx.org";

import { layoutGraph } from "./graph_layout";
import { getCenterAnchor, renderGraph } from "./graph_svg";
import { refreshInspectorMetadataBlocks } from "./inspectors";
import type {
  FilterMode,
  GraphNode,
  GraphPayload,
  LayoutState,
  MetadataRevision,
  PositionedNode,
  ViewAnchor,
} from "./graph_types";

declare global {
  interface Window {
    dbtDagSelectNode?: (nodeId: string) => void;
    dbtDagFocusNode?: (nodeId: string) => void;
    dbtDagClearSelection?: () => void;
  }
}

type PackageChangeHandler = (packageName: string, enabled: boolean) => void | Promise<void>;

type FilterEvent = CustomEvent<{
  mode?: FilterMode;
}>;

const defaultHiddenPackages = new Set(["dbt_project_evaluator"]);

async function loadGraph(): Promise<void> {
  const container = document.getElementById("graph-root");
  if (!container) return;

  const response = await fetch("/api/graph");
  let payload = (await response.json()) as GraphPayload;
  const activePackages = new Set(
    graphPackages(payload.nodes).filter((packageName) => !defaultHiddenPackages.has(packageName))
  );
  const { upstream, downstream } = buildAdjacency(payload);
  const state: LayoutState = {
    layout: await layoutGraph(payload, activePackages),
    upstream,
    downstream,
    activePackages,
    selectedNodeId: null,
    filterMode: null
  };
  let renderVersion = 0;
  let layoutVersion = 0;
  let refreshVersion = 0;
  let currentRevision = await loadMetadataRevision();
  let pendingFocusNodeId: string | null = null;
  let lastContainerSize = {
    width: Math.max(container.clientWidth, 0),
    height: Math.max(container.clientHeight, 0)
  };

  window.dbtDagSelectNode = selectNode;
  window.dbtDagFocusNode = focusNode;
  window.dbtDagClearSelection = clearSelection;
  const packageChangeHandler = async (packageName: string, enabled: boolean) => {
    const nextPackages = new Set(state.activePackages);
    if (enabled) {
      nextPackages.add(packageName);
    } else {
      nextPackages.delete(packageName);
    }
    const anchor = getCenterAnchor(container, state.layout, visibleNodeIds(payload.nodes, nextPackages));
    const currentLayoutVersion = (layoutVersion += 1);
    const nextLayout = await layoutGraph(payload, nextPackages);
    if (currentLayoutVersion !== layoutVersion) return;
    state.activePackages = nextPackages;
    state.layout = nextLayout;
    if (state.selectedNodeId && !state.layout.nodes.has(state.selectedNodeId)) {
      state.selectedNodeId = null;
      state.filterMode = null;
    }
    renderCurrentGraph(false, anchor);
  };
  renderPackageFilters(payload.nodes, activePackages, packageChangeHandler);
  renderCurrentGraph(true);
  const resizeObserver = new ResizeObserver(() => {
    const nextSize = {
      width: Math.max(container.clientWidth, 0),
      height: Math.max(container.clientHeight, 0)
    };
    if (
      nextSize.width === lastContainerSize.width &&
      nextSize.height === lastContainerSize.height
    ) {
      return;
    }
    lastContainerSize = nextSize;
    renderCurrentGraph(!state.selectedNodeId);
  });
  resizeObserver.observe(container);
  window.setInterval(() => {
    void refreshIfNeeded();
  }, 5000);

  document.addEventListener("dbt-dag-filter", (event) => {
    const mode = (event as FilterEvent).detail.mode;
    if (!mode) return;
    if (mode === "reset") {
      clearSelection();
      return;
    }
    if (!state.selectedNodeId) return;
    state.filterMode = mode;
    renderCurrentGraph(false);
  });

  hotkeys("esc,left,right,up,down", (event, handler) => {
    if (isEditableTarget(event.target)) return;
    if (handler.key === "esc") {
      if (!state.selectedNodeId) return;
      event.preventDefault();
      clearSelection();
      return;
    }
    if (!state.selectedNodeId) return;
    const nextNodeId = nextKeyboardNodeId(handler.key, state);
    if (!nextNodeId) return;
    event.preventDefault();
    selectNode(nextNodeId);
  });

  function renderCurrentGraph(fit = false, anchor: ViewAnchor | null = null): void {
    const currentVersion = (renderVersion += 1);
    const relatedNodes = state.selectedNodeId
      ? relatedNodeIds(state.selectedNodeId, state.filterMode, state.upstream, state.downstream)
      : null;
    if (currentVersion !== renderVersion) return;
    const focusNodeId = pendingFocusNodeId;
    pendingFocusNodeId = null;
    renderGraph(
      container,
      state.layout,
      relatedNodes,
      state.selectedNodeId,
      state.filterMode,
      selectNode,
      fit,
      anchor,
      focusNodeId
    );
  }

  function selectNode(nodeId: string): void {
    if (!state.layout.nodes.has(nodeId)) return;
    state.selectedNodeId = nodeId;
    state.filterMode = null;
    pendingFocusNodeId = nodeId;
    renderCurrentGraph(false);
    openInspector(nodeId);
  }

  function focusNode(nodeId: string): void {
    selectNode(nodeId);
  }

  function clearSelection(): void {
    state.selectedNodeId = null;
    state.filterMode = null;
    renderCurrentGraph(false);
    openProjectInspector();
  }

  async function refreshIfNeeded(): Promise<void> {
    const nextRevision = await loadMetadataRevision();
    if (nextRevision <= currentRevision) return;
    currentRevision = nextRevision;
    await refreshGraph();
  }

  async function refreshGraph(): Promise<void> {
    const currentRefresh = (refreshVersion += 1);
    const nextResponse = await fetch("/api/graph");
    const nextPayload = (await nextResponse.json()) as GraphPayload;
    const nextPackages = reconcileActivePackages(payload, nextPayload, state.activePackages);
    const anchor = getCenterAnchor(container, state.layout, visibleNodeIds(payload.nodes, nextPackages));
    const nextLayout = await layoutGraph(nextPayload, nextPackages);
    if (currentRefresh !== refreshVersion) return;

    payload = nextPayload;
    const adjacency = buildAdjacency(nextPayload);
    state.upstream = adjacency.upstream;
    state.downstream = adjacency.downstream;
    state.activePackages = nextPackages;
    state.layout = nextLayout;
    if (state.selectedNodeId && !state.layout.nodes.has(state.selectedNodeId)) {
      state.selectedNodeId = null;
      state.filterMode = null;
    }
    renderPackageFilters(payload.nodes, state.activePackages, packageChangeHandler);
    renderCurrentGraph(false, anchor);
    if (state.selectedNodeId) {
      refreshInspectorMetadataBlocks();
    } else {
      openProjectInspector();
    }
  }
}

function nextKeyboardNodeId(direction: string, state: LayoutState): string | null {
  const currentNodeId = state.selectedNodeId;
  if (!currentNodeId) return null;

  if (direction === "right") {
    return sortedRelatedNodes(state.downstream.get(currentNodeId), state.layout)[0]?.id ?? null;
  }

  const primaryParentId = selectPrimaryParent(currentNodeId, state);
  if (!primaryParentId) return null;

  if (direction === "left") {
    return primaryParentId;
  }

  const siblings = sortedRelatedNodes(state.downstream.get(primaryParentId), state.layout);
  const currentIndex = siblings.findIndex((node) => node.id === currentNodeId);
  if (currentIndex < 0) return null;
  if (direction === "up") {
    return siblings[currentIndex - 1]?.id ?? null;
  }
  if (direction === "down") {
    return siblings[currentIndex + 1]?.id ?? null;
  }
  return null;
}

function selectPrimaryParent(nodeId: string, state: LayoutState): string | null {
  const currentNode = state.layout.nodes.get(nodeId);
  if (!currentNode) return null;
  return (
    sortedRelatedNodes(state.upstream.get(nodeId), state.layout).sort(
      (left, right) =>
        horizontalDistance(currentNode, left) - horizontalDistance(currentNode, right) ||
        verticalDistance(currentNode, left) - verticalDistance(currentNode, right)
    )[0]?.id ?? null
  );
}

function sortedRelatedNodes(
  nodeIds: Set<string> | undefined,
  layout: LayoutState["layout"]
): PositionedNode[] {
  return [...(nodeIds ?? new Set<string>())]
    .map((nodeId) => layout.nodes.get(nodeId))
    .filter((node): node is PositionedNode => node !== undefined)
    .sort((left, right) => left.y - right.y || left.x - right.x);
}

function horizontalDistance(currentNode: PositionedNode, candidateNode: PositionedNode): number {
  return Math.abs(candidateNode.x - currentNode.x);
}

function verticalDistance(currentNode: PositionedNode, candidateNode: PositionedNode): number {
  return Math.abs(candidateNode.y - currentNode.y);
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) return true;
  return target.isContentEditable;
}

function buildAdjacency(payload: GraphPayload): {
  upstream: Map<string, Set<string>>;
  downstream: Map<string, Set<string>>;
} {
  const nodesById = new Map(payload.nodes.map((node) => [node.id, node]));
  const downstream = new Map<string, Set<string>>();
  const upstream = new Map<string, Set<string>>();
  for (const node of payload.nodes) {
    downstream.set(node.id, new Set());
    upstream.set(node.id, new Set());
  }
  for (const edge of payload.edges) {
    if (!nodesById.has(edge.source) || !nodesById.has(edge.target)) continue;
    downstream.get(edge.source)?.add(edge.target);
    upstream.get(edge.target)?.add(edge.source);
  }
  return { upstream, downstream };
}

function graphPackages(nodes: GraphNode[]): string[] {
  return [...new Set(nodes.map((node) => node.package_name).filter(Boolean))].sort((left, right) =>
    left.localeCompare(right)
  );
}

function visibleNodeIds(nodes: GraphNode[], activePackages: Set<string>): Set<string> {
  return new Set(
    nodes.filter((node) => activePackages.has(node.package_name)).map((node) => node.id)
  );
}

function reconcileActivePackages(
  previousPayload: GraphPayload,
  nextPayload: GraphPayload,
  activePackages: Set<string>
): Set<string> {
  const previousPackages = new Set(graphPackages(previousPayload.nodes));
  const nextPackages = graphPackages(nextPayload.nodes);
  const result = new Set([...activePackages].filter((packageName) => nextPackages.includes(packageName)));
  for (const packageName of nextPackages) {
    if (!previousPackages.has(packageName) && !defaultHiddenPackages.has(packageName)) {
      result.add(packageName);
    }
  }
  return result;
}

function renderPackageFilters(
  nodes: GraphNode[],
  activePackages: Set<string>,
  onChange: PackageChangeHandler
): void {
  const container = document.getElementById("package-filters");
  if (!container) return;

  container.replaceChildren(
    ...graphPackages(nodes).map((packageName) => {
      const label = document.createElement("label");
      label.className =
        "flex items-center gap-1 rounded border border-zinc-700 bg-zinc-900 px-2 py-2";

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.className = "accent-cyan-500";
      checkbox.checked = activePackages.has(packageName);
      checkbox.addEventListener("change", () => onChange(packageName, checkbox.checked));

      const text = document.createElement("span");
      text.textContent = packageName;

      label.append(checkbox, text);
      return label;
    })
  );
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

function openInspector(nodeId: string): void {
  const inspector = document.getElementById("inspector");
  if (!inspector) return;
  const selectionToken = createSelectionToken();
  const url = `/inspector/node/${encodeURIComponent(nodeId)}?selection_token=${selectionToken}`;
  inspector.setAttribute("hx-get", url);
  htmx.ajax("GET", url, {
    target: "#inspector",
    swap: "innerHTML"
  });
}

function openProjectInspector(): void {
  const inspector = document.getElementById("inspector");
  if (!inspector) return;
  inspector.setAttribute("hx-get", "/inspector/project");
  htmx.ajax("GET", "/inspector/project", {
    target: "#inspector",
    swap: "innerHTML"
  });
}

function createSelectionToken(): string {
  if (globalThis.crypto && "randomUUID" in globalThis.crypto) {
    return globalThis.crypto.randomUUID().replaceAll("-", "");
  }
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
}

async function loadMetadataRevision(): Promise<number> {
  const response = await fetch("/api/metadata/revision");
  const payload = (await response.json()) as MetadataRevision;
  return payload.revision;
}

void loadGraph();
