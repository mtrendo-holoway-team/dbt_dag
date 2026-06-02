import Graph from "graphology";
import htmx from "htmx.org";
import Sigma from "sigma";

type GraphNode = {
  id: string;
  label: string;
  column: string;
  resource_type: string;
  package_name: string;
};

type GraphEdge = {
  id: string;
  source: string;
  target: string;
};

type GraphPayload = {
  columns: string[];
  nodes: GraphNode[];
  edges: GraphEdge[];
};

declare global {
  interface Window {
    dbtDagSelectNode?: (nodeId: string) => void;
  }
}

type FilterMode = "upstream" | "downstream" | "reset";
type PackageChangeHandler = (packageName: string, enabled: boolean) => void;

type FilterEvent = CustomEvent<{
  mode?: FilterMode;
}>;

const colors: Record<string, string> = {
  sources: "#38bdf8",
  stg: "#22c55e",
  int: "#eab308",
  marts: "#f97316",
  exposures: "#a78bfa",
  other: "#94a3b8"
};

const edgeColor = "#3f3f46";
const relatedEdgeColor = "#94a3b8";
const dimmedColor = "#27272a";
const selectedColor = "#f8fafc";

const nodeSize = 8;
const selectedNodeSize = 13;
const relatedNodeSize = 10;
const dimmedNodeSize = 5;
const defaultHiddenPackages = new Set(["dbt_project_evaluator"]);

async function loadGraph(): Promise<void> {
  const container = document.getElementById("graph-root");
  if (!container) return;

  const response = await fetch("/api/graph");
  const payload = (await response.json()) as GraphPayload;
  const graph = new Graph();
  const byColumn = new Map<string, GraphNode[]>();
  const nodesById = new Map(payload.nodes.map((node) => [node.id, node]));
  const activePackages = new Set(
    graphPackages(payload.nodes).filter((packageName) => !defaultHiddenPackages.has(packageName))
  );
  const columnIndexByName = new Map(payload.columns.map((column, index) => [column, index]));
  const downstream = new Map<string, Set<string>>();
  const upstream = new Map<string, Set<string>>();

  for (const column of payload.columns) byColumn.set(column, []);
  for (const node of payload.nodes) {
    byColumn.get(node.column)?.push(node);
    downstream.set(node.id, new Set());
    upstream.set(node.id, new Set());
  }

  for (const edge of payload.edges) {
    if (!nodesById.has(edge.source) || !nodesById.has(edge.target)) continue;
    downstream.get(edge.source)?.add(edge.target);
    upstream.get(edge.target)?.add(edge.source);
  }

  const columnWidth = Math.max(300, container.clientWidth / Math.max(payload.columns.length, 1));
  const graphPaddingX = 120;
  const graphPaddingY = 90;
  for (const [columnIndex, column] of payload.columns.entries()) {
    const columnNodes = sortColumnNodes(
      byColumn.get(column) ?? [],
      upstream,
      downstream,
      nodesById,
      columnIndexByName
    );
    const rowGap = Math.max(
      72,
      (container.clientHeight - graphPaddingY * 2) / Math.max(columnNodes.length - 1, 1)
    );
    columnNodes.forEach((node, rowIndex) => {
      graph.addNode(node.id, {
        label: node.label,
        x: graphPaddingX + columnIndex * columnWidth,
        y: graphPaddingY + rowIndex * rowGap,
        size: nodeSize,
        color: nodeColor(node),
        baseColor: nodeColor(node),
        baseSize: nodeSize,
        packageName: node.package_name
      });
    });
  }

  for (const edge of payload.edges) {
    if (graph.hasNode(edge.source) && graph.hasNode(edge.target)) {
      graph.addEdgeWithKey(edge.id, edge.source, edge.target, {
        color: edgeColor,
        baseColor: edgeColor,
        size: 1,
        baseSize: 1
      });
    }
  }

  const renderer = new Sigma(graph, container, {
    allowInvalidContainer: true,
    defaultEdgeColor: edgeColor,
    defaultNodeColor: colors.other,
    labelDensity: 0.08,
    labelGridCellSize: 90,
    labelRenderedSizeThreshold: 8
  });

  let selectedNodeId: string | null = null;

  window.dbtDagSelectNode = selectNode;
  renderer.on("clickNode", ({ node }) => selectNode(node));
  renderPackageFilters(payload.nodes, activePackages, (packageName, enabled) => {
    if (enabled) {
      activePackages.add(packageName);
    } else {
      activePackages.delete(packageName);
    }
    applySelection(graph, renderer, selectedNodeId, null, upstream, downstream, activePackages);
  });
  applySelection(graph, renderer, null, null, upstream, downstream, activePackages);

  document.addEventListener("dbt-dag-filter", (event) => {
    const mode = (event as FilterEvent).detail.mode;
    if (!mode) return;
    if (mode === "reset") {
      applySelection(graph, renderer, null, null, upstream, downstream, activePackages);
      return;
    }
    if (!selectedNodeId) return;
    applySelection(graph, renderer, selectedNodeId, mode, upstream, downstream, activePackages);
  });

  function selectNode(nodeId: string): void {
    if (!graph.hasNode(nodeId)) return;
    selectedNodeId = nodeId;
    applySelection(graph, renderer, selectedNodeId, null, upstream, downstream, activePackages);
    openInspector(nodeId);
  }
}

function graphPackages(nodes: GraphNode[]): string[] {
  return [...new Set(nodes.map((node) => node.package_name).filter(Boolean))].sort((left, right) =>
    left.localeCompare(right)
  );
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

function sortColumnNodes(
  nodes: GraphNode[],
  upstream: Map<string, Set<string>>,
  downstream: Map<string, Set<string>>,
  nodesById: Map<string, GraphNode>,
  columnIndexByName: Map<string, number>
): GraphNode[] {
  return [...nodes].sort((left, right) => {
    const leftConnectivity = connectivityScore(
      left,
      upstream,
      downstream,
      nodesById,
      columnIndexByName
    );
    const rightConnectivity = connectivityScore(
      right,
      upstream,
      downstream,
      nodesById,
      columnIndexByName
    );
    if (leftConnectivity !== rightConnectivity) return rightConnectivity - leftConnectivity;
    return left.label.localeCompare(right.label);
  });
}

function connectivityScore(
  node: GraphNode,
  upstream: Map<string, Set<string>>,
  downstream: Map<string, Set<string>>,
  nodesById: Map<string, GraphNode>,
  columnIndexByName: Map<string, number>
): number {
  const columnIndex = columnIndexByName.get(node.column);
  if (columnIndex === undefined) return 0;
  return [...(upstream.get(node.id) ?? []), ...(downstream.get(node.id) ?? [])].filter(
    (neighborId) => {
      const neighbor = nodesById.get(neighborId);
      const neighborColumnIndex = neighbor ? columnIndexByName.get(neighbor.column) : undefined;
      return neighborColumnIndex !== undefined && Math.abs(neighborColumnIndex - columnIndex) === 1;
    }
  ).length;
}

function nodeColor(node: GraphNode): string {
  return colors[node.column] ?? colors.other;
}

function applySelection(
  graph: Graph,
  renderer: Sigma,
  selectedNodeId: string | null,
  mode: FilterMode | null,
  upstream: Map<string, Set<string>>,
  downstream: Map<string, Set<string>>,
  activePackages: Set<string>
): void {
  const relatedNodes = selectedNodeId
    ? relatedNodeIds(selectedNodeId, mode, upstream, downstream)
    : null;

  graph.forEachNode((nodeId, attributes) => {
    const isSelected = selectedNodeId === nodeId;
    const isRelated = relatedNodes?.has(nodeId) ?? true;
    const isPackageVisible = activePackages.has(String(attributes.packageName));
    graph.mergeNodeAttributes(nodeId, {
      color: nodeStateColor(attributes.baseColor, isSelected, isRelated),
      hidden: !isPackageVisible,
      size: nodeStateSize(isSelected, isRelated)
    });
  });

  graph.forEachEdge((edgeId, attributes, source, target) => {
    const sourcePackage = String(graph.getNodeAttribute(source, "packageName"));
    const targetPackage = String(graph.getNodeAttribute(target, "packageName"));
    const isPackageVisible = activePackages.has(sourcePackage) && activePackages.has(targetPackage);
    const isRelated =
      relatedNodes === null || (relatedNodes.has(source) && relatedNodes.has(target));
    graph.mergeEdgeAttributes(edgeId, {
      color: isRelated ? (mode ? relatedEdgeColor : attributes.baseColor) : dimmedColor,
      hidden: !isPackageVisible,
      size: isRelated ? (mode ? 2 : attributes.baseSize) : 0.5
    });
  });

  renderer.refresh();
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

function nodeStateColor(baseColor: string, isSelected: boolean, isRelated: boolean): string {
  if (isSelected) return selectedColor;
  if (isRelated) return baseColor;
  return dimmedColor;
}

function nodeStateSize(isSelected: boolean, isRelated: boolean): number {
  if (isSelected) return selectedNodeSize;
  if (isRelated) return relatedNodeSize;
  return dimmedNodeSize;
}

function openInspector(nodeId: string): void {
  const inspector = document.getElementById("inspector");
  if (!inspector) return;
  inspector.setAttribute("hx-get", `/inspector/node/${encodeURIComponent(nodeId)}`);
  htmx.ajax("GET", `/inspector/node/${encodeURIComponent(nodeId)}`, {
    target: "#inspector",
    swap: "innerHTML"
  });
}

loadGraph();
