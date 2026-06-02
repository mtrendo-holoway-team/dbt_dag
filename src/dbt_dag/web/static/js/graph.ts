import Graph from "graphology";
import Sigma from "sigma";
import "htmx.org";

type GraphNode = {
  id: string;
  label: string;
  column: string;
  resource_type: string;
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

const colors: Record<string, string> = {
  sources: "#38bdf8",
  stg: "#22c55e",
  int: "#eab308",
  marts: "#f97316",
  exposures: "#a78bfa",
  other: "#94a3b8"
};

async function loadGraph(): Promise<void> {
  const container = document.getElementById("graph-root");
  if (!container) return;

  const response = await fetch("/api/graph");
  const payload = (await response.json()) as GraphPayload;
  const graph = new Graph();
  const byColumn = new Map<string, GraphNode[]>();

  for (const column of payload.columns) byColumn.set(column, []);
  for (const node of payload.nodes) byColumn.get(node.column)?.push(node);

  const columnWidth = Math.max(280, container.clientWidth / payload.columns.length);
  for (const [columnIndex, column] of payload.columns.entries()) {
    const columnNodes = byColumn.get(column) ?? [];
    const rowGap = Math.max(70, container.clientHeight / Math.max(columnNodes.length + 1, 2));
    columnNodes.forEach((node, rowIndex) => {
      graph.addNode(node.id, {
        label: node.label,
        x: columnIndex * columnWidth,
        y: (rowIndex + 1) * rowGap,
        size: 8,
        color: colors[column] ?? colors.other
      });
    });
  }

  for (const edge of payload.edges) {
    if (graph.hasNode(edge.source) && graph.hasNode(edge.target)) {
      graph.addEdgeWithKey(edge.id, edge.source, edge.target, { color: "#3f3f46", size: 1 });
    }
  }

  const renderer = new Sigma(graph, container);
  renderer.on("clickNode", ({ node }) => selectNode(node));
  window.dbtDagSelectNode = selectNode;
}

function selectNode(nodeId: string): void {
  const inspector = document.getElementById("inspector");
  if (!inspector) return;
  inspector.setAttribute("hx-get", `/inspector/node/${encodeURIComponent(nodeId)}`);
  window.htmx?.ajax("GET", `/inspector/node/${encodeURIComponent(nodeId)}`, {
    target: "#inspector",
    swap: "innerHTML"
  });
}

loadGraph();
