import hotkeys from "hotkeys-js";
import htmx from "htmx.org";

import {
  applyIsolationState,
  applySelectionState,
  centerGraphNode,
  createGraph,
  directlyRelatedNodeIds,
  frameGraphNodes,
  graphRelatedNodeIds,
  getCenterAnchor,
  hasGraphNode,
  rearrangeVisibleNodes,
  renderGraph
} from "./graph_cytoscape";
import { createGraphHtmlLabels } from "./graph_html_labels";
import { createRelativeNavigation } from "./graph_relative_navigation";
import { refreshInspectorMetadataBlocks } from "./inspectors";
import type {
  FilterMode,
  GraphNode,
  GraphPayload,
  MetadataRevision,
  ViewAnchor
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

  prepareContainer(container);
  const response = await fetch("/api/graph");
  let payload = (await response.json()) as GraphPayload;
  const activePackages = new Set(
    graphPackages(payload.nodes).filter((packageName) => !defaultHiddenPackages.has(packageName))
  );
  const { upstream, downstream } = buildAdjacency(payload);
  const state = {
    cy: createGraph(container),
    upstream,
    downstream,
    activePackages,
    selectedNodeId: null as string | null,
    filterMode: null as FilterMode | null,
    isolatedNodeIds: null as Set<string> | null
  };
  const htmlLabels = createGraphHtmlLabels(container, state.cy);
  const relativeNavigation = createRelativeNavigation(container, state.cy, focusNode);
  let renderVersion = 0;
  let refreshVersion = 0;
  let currentRevision = await loadMetadataRevision();
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
    const anchor = getCenterAnchor(state.cy, visibleNodeIds(payload.nodes, nextPackages));
    state.activePackages = nextPackages;
    clearHiddenSelection();
    await renderCurrentGraph(false, anchor);
  };

  renderPackageFilters(payload.nodes, activePackages, packageChangeHandler);
  await renderCurrentGraph(true);
  observeResize(container, state);
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
    applyCurrentSelection();
  });

  hotkeys("esc", (event, handler) => {
    if (isEditableTarget(event.target)) return;
    if (handler.key === "esc") {
      event.preventDefault();
      if (state.isolatedNodeIds) {
        clearIsolation();
        return;
      }
      if (!state.selectedNodeId) return;
      clearSelection();
    }
  });
  hotkeys("f,z,i", (event, handler) => {
    if (isEditableTarget(event.target)) return;

    if (!state.selectedNodeId) return;

    if (handler.key === "f") {
      event.preventDefault();
      frameGraphNodes(
        state.cy,
        graphRelatedNodeIds(state.selectedNodeId, null, state.upstream, state.downstream)
      );
      return;
    }

    if (handler.key === "z") {
      event.preventDefault();
      frameGraphNodes(
        state.cy,
        directlyRelatedNodeIds(state.selectedNodeId, state.upstream, state.downstream)
      );
      return;
    }

    if (handler.key === "i") {
      event.preventDefault();
      if (state.isolatedNodeIds) {
        void clearIsolation();
        return;
      }
      void isolateSelection();
    }
  });

  async function renderCurrentGraph(
    fit = false,
    anchor: ViewAnchor | null = null
  ): Promise<void> {
    const currentVersion = (renderVersion += 1);
    await renderGraph(
      state.cy,
      payload,
      state.activePackages,
      state.selectedNodeId,
      state.filterMode,
      fit,
      anchor,
      selectNode,
      state.upstream,
      state.downstream
    );
    if (currentVersion !== renderVersion) return;
    applyCurrentSelection();
    htmlLabels.sync();
  }

  function selectNode(nodeId: string): void {
    if (!hasGraphNode(state.cy, nodeId)) return;
    state.selectedNodeId = nodeId;
    state.filterMode = null;
    applyCurrentSelection();
    openInspector(nodeId);
  }

  function focusNode(nodeId: string): void {
    selectNode(nodeId);
    centerGraphNode(state.cy, nodeId);
  }

  function clearSelection(): void {
    state.selectedNodeId = null;
    state.filterMode = null;
    state.isolatedNodeIds = null;
    applyCurrentSelection();
    openProjectInspector();
  }

  function applyCurrentSelection(): void {
    applyIsolationState(state.cy, state.isolatedNodeIds);
    applySelectionState(
      state.cy,
      state.selectedNodeId,
      state.filterMode,
      state.upstream,
      state.downstream
    );
    htmlLabels.sync();
    relativeNavigation.render(
      state.selectedNodeId,
      currentVisibleNodeIds(),
      state.upstream,
      state.downstream
    );
  }

  async function isolateSelection(): Promise<void> {
    if (!state.selectedNodeId) return;
    state.isolatedNodeIds = graphRelatedNodeIds(
      state.selectedNodeId,
      null,
      state.upstream,
      state.downstream
    );
    await rearrangeCurrentVisibleNodes();
    applyCurrentSelection();
    frameGraphNodes(state.cy, state.isolatedNodeIds);
  }

  async function clearIsolation(): Promise<void> {
    if (!state.isolatedNodeIds) return;
    state.isolatedNodeIds = null;
    applyCurrentSelection();
    window.requestAnimationFrame(() => {
      void rearrangeCurrentVisibleNodes().then(() => {
        applyCurrentSelection();
      });
    });
  }

  function clearHiddenSelection(): void {
    if (state.selectedNodeId && !visibleNodeIds(payload.nodes, state.activePackages).has(state.selectedNodeId)) {
      state.selectedNodeId = null;
      state.filterMode = null;
      state.isolatedNodeIds = null;
    }
  }

  function currentVisibleNodeIds(): Set<string> {
    const activeNodeIds = visibleNodeIds(payload.nodes, state.activePackages);
    if (!state.isolatedNodeIds) return activeNodeIds;
    return new Set([...activeNodeIds].filter((nodeId) => state.isolatedNodeIds?.has(nodeId)));
  }

  async function rearrangeCurrentVisibleNodes(): Promise<void> {
    const visibleNodeIds = currentVisibleNodeIds();
    const anchor = getCenterAnchor(state.cy, visibleNodeIds);
    await rearrangeVisibleNodes(state.cy, payload, visibleNodeIds, anchor);
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
    const anchor = getCenterAnchor(state.cy, visibleNodeIds(nextPayload.nodes, nextPackages));
    if (currentRefresh !== refreshVersion) return;

    payload = nextPayload;
    const adjacency = buildAdjacency(nextPayload);
    state.upstream = adjacency.upstream;
    state.downstream = adjacency.downstream;
    state.activePackages = nextPackages;
    clearHiddenSelection();
    renderPackageFilters(payload.nodes, state.activePackages, packageChangeHandler);
    await renderCurrentGraph(false, anchor);
    if (state.selectedNodeId) {
      refreshInspectorMetadataBlocks();
    } else {
      openProjectInspector();
    }
  }

  function observeResize(
    containerElement: HTMLElement,
    graphState: { cy: ReturnType<typeof createGraph>; selectedNodeId: string | null }
  ): void {
    const resizeObserver = new ResizeObserver(() => {
      const nextSize = {
        width: Math.max(containerElement.clientWidth, 0),
        height: Math.max(containerElement.clientHeight, 0)
      };
      if (
        nextSize.width === lastContainerSize.width &&
        nextSize.height === lastContainerSize.height
      ) {
        return;
      }
      lastContainerSize = nextSize;
      graphState.cy.resize();
      if (!graphState.selectedNodeId) {
        graphState.cy.fit(undefined, 40);
      }
    });
    resizeObserver.observe(containerElement);
  }
}

function prepareContainer(container: HTMLElement): void {
  container.style.position = "relative";
  container.style.overflow = "hidden";
  container.style.touchAction = "none";
  container.style.background = "#fafafa";
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
  const result = new Set([...activePackages].filter((name) => nextPackages.includes(name)));
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
