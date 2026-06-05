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
  description: string;
  indicators: string[];
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

export type FilterMode = "upstream" | "downstream" | "reset";

export type ViewAnchor = {
  nodeId: string;
  screenX: number;
  screenY: number;
};
