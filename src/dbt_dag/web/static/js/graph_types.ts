export type GraphNodeRuntime = {
  execution_time_seconds: number | null;
  execution_time_source: string;
  last_updated_at: string | null;
  last_updated_source: string;
  freshness: string;
  border_width_px: number;
  border_color: string;
};

export type GraphNode = {
  id: string;
  label: string;
  type_badge: string;
  column: string;
  resource_type: string;
  package_name: string;
  runtime: GraphNodeRuntime;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
};

export type GraphGroup = {
  id: string;
  label: string;
  node_ids: string[];
};

export type ProjectSummary = {
  models_count: number;
  sources_count: number;
  tests_count: number;
};

export type GraphEdgePoint = {
  x: number;
  y: number;
};

export type RoutedGraphEdge = GraphEdge & {
  points: GraphEdgePoint[];
};

export type GraphPayload = {
  columns: string[];
  nodes: GraphNode[];
  edges: GraphEdge[];
  groups: GraphGroup[];
  project: ProjectSummary;
};

export type MetadataRevision = {
  revision: number;
  refreshed_at: string;
};

export type PositionedNode = GraphNode & {
  x: number;
  y: number;
  width: number;
  height: number;
  effectiveColumn: string;
};

export type FilterMode = "upstream" | "downstream" | "reset";

export type GraphLayout = {
  nodes: Map<string, PositionedNode>;
  edges: RoutedGraphEdge[];
  groups: PositionedGroup[];
  width: number;
  height: number;
};

export type PositionedGroup = GraphGroup & {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type ViewAnchor = {
  nodeId: string;
  screenX: number;
  screenY: number;
};

export type ViewBounds = {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
};

export type LayoutState = {
  layout: GraphLayout;
  upstream: Map<string, Set<string>>;
  downstream: Map<string, Set<string>>;
  activePackages: Set<string>;
  selectedNodeId: string | null;
  filterMode: FilterMode | null;
};
