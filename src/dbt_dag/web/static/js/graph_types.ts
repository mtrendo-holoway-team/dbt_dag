export type GraphNode = {
  id: string;
  label: string;
  column: string;
  resource_type: string;
  package_name: string;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
};

export type GraphPayload = {
  columns: string[];
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export type PositionedNode = GraphNode & {
  x: number;
  y: number;
  width: number;
  height: number;
  effectiveColumn: string;
};

export type FilterMode = "upstream" | "downstream" | "reset";

export type LaneBounds = {
  column: string;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
};

export type GraphLayout = {
  nodes: Map<string, PositionedNode>;
  edges: GraphEdge[];
  lanes: LaneBounds[];
  width: number;
  height: number;
};

export type ViewAnchor = {
  nodeId: string;
  screenX: number;
  screenY: number;
};

export type LayoutState = {
  layout: GraphLayout;
  upstream: Map<string, Set<string>>;
  downstream: Map<string, Set<string>>;
  activePackages: Set<string>;
  selectedNodeId: string | null;
  filterMode: FilterMode | null;
};
