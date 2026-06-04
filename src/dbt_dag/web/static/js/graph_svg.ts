import type { GraphEdgePoint, GraphLayout, PositionedNode, ViewAnchor, ViewBounds } from "./graph_types";

type ViewTransform = {
  scale: number;
  x: number;
  y: number;
};

const laneColors: Record<string, string> = {
  sources: "#fbf3c7",
  stg: "#cef0d8",
  int: "#c8e3f5",
  marts: "#d7d4f2",
  exposures: "#efd0f0",
  other: "#e4e4e7"
};

const edgeColor = "#777";
const relatedEdgeColor = "#0ea5e9";
const selectedNodeColor = "#e0f2fe";
const edgeMarkerId = "dag-arrowhead";
const relatedEdgeMarkerId = "dag-arrowhead-related";
const dimmedEdgeMarkerId = "dag-arrowhead-dimmed";
const dimmedEdgeColor = "#eee";
const minScale = 0.005;
const maxScale = 2.5;

const transforms = new WeakMap<HTMLElement, ViewTransform>();

export function renderGraph(
  container: HTMLElement,
  layout: GraphLayout,
  relatedNodes: Set<string> | null,
  selectedNodeId: string | null,
  filterMode: string | null,
  onSelectNode: (nodeId: string) => void,
  fit: boolean,
  anchor: ViewAnchor | null = null,
  focusBounds: ViewBounds | null = null
): void {
  prepareContainer(container);
  const viewport = viewportSize(container);
  const fallbackTransform = fitTransform(layout, viewport);
  const transform = focusBounds
    ? fitTransform(focusBounds, viewport)
    : fit || !transforms.has(container)
      ? fallbackTransform
      : transforms.get(container) ?? fallbackTransform;
  if (!focusBounds) {
    applyAnchor(transform, layout, anchor);
  }
  if (!isFiniteTransform(transform)) {
    transform.scale = fallbackTransform.scale;
    transform.x = fallbackTransform.x;
    transform.y = fallbackTransform.y;
  }
  transforms.set(container, transform);

  const svgElement = svg("svg", {
    class: "dag-canvas",
    style:
      "display:block;width:100%;height:100%;background:#fafafa;cursor:grab;user-select:none;-webkit-user-select:none",
    viewBox: `0 0 ${viewport.width} ${viewport.height}`,
    width: String(viewport.width),
    height: String(viewport.height),
    role: "img",
    "aria-label": "dbt DAG"
  }) as SVGSVGElement;
  const content = svg("g", { class: "dag-content" });
  container.replaceChildren(svgElement);
  svgElement.append(renderDefs(), content);
  content.append(renderEdges(layout, relatedNodes, filterMode));
  content.append(renderNodes(layout, relatedNodes, selectedNodeId, onSelectNode));
  applyTransform(content, transform);
  bindViewportEvents(svgElement, content, transform);
}

export function getCenterAnchor(
  container: HTMLElement,
  layout: GraphLayout,
  allowedNodeIds: Set<string>
): ViewAnchor | null {
  const transform = transforms.get(container);
  if (!transform) return null;
  const viewport = viewportSize(container);
  const center = { x: viewport.width / 2, y: viewport.height / 2 };
  let best: ViewAnchor | null = null;
  let bestDistance = Number.POSITIVE_INFINITY;

  layout.nodes.forEach((node) => {
    if (!allowedNodeIds.has(node.id)) return;
    const screenX = (node.x + node.width / 2) * transform.scale + transform.x;
    const screenY = (node.y + node.height / 2) * transform.scale + transform.y;
    const distance = Math.hypot(screenX - center.x, screenY - center.y);
    if (distance >= bestDistance) return;
    bestDistance = distance;
    best = { nodeId: node.id, screenX, screenY };
  });

  return best;
}

function prepareContainer(container: HTMLElement): void {
  container.style.position = "relative";
  container.style.overflow = "hidden";
  container.style.touchAction = "none";
}

function viewportSize(container: HTMLElement): { width: number; height: number } {
  return {
    width: Math.max(container.clientWidth, 1),
    height: Math.max(container.clientHeight, 1)
  };
}

function fitTransform(
  bounds: GraphLayout | ViewBounds,
  viewport: { width: number; height: number }
): ViewTransform {
  const normalizedBounds = graphBounds(bounds);
  const minX = normalizedBounds.minX;
  const minY = normalizedBounds.minY;
  const maxX = normalizedBounds.maxX;
  const maxY = normalizedBounds.maxY;
  const width = Math.max(maxX - minX, 1);
  const height = Math.max(maxY - minY, 1);
  const scale = Math.min(
    1,
    Math.max(minScale, Math.min(viewport.width / width, viewport.height / height))
  );
  return {
    scale,
    x: (viewport.width - width * scale) / 2 - minX * scale,
    y: (viewport.height - height * scale) / 2 - minY * scale
  };
}

function graphBounds(bounds: GraphLayout | ViewBounds): ViewBounds {
  if ("width" in bounds && "height" in bounds) {
    return {
      minX: 0,
      minY: 0,
      maxX: Number.isFinite(bounds.width) ? bounds.width : 1,
      maxY: Number.isFinite(bounds.height) ? bounds.height : 1
    };
  }
  return {
    minX: Number.isFinite(bounds.minX) ? bounds.minX : 0,
    minY: Number.isFinite(bounds.minY) ? bounds.minY : 0,
    maxX: Number.isFinite(bounds.maxX) ? bounds.maxX : 1,
    maxY: Number.isFinite(bounds.maxY) ? bounds.maxY : 1
  };
}

export function getNodeClusterBounds(
  layout: GraphLayout,
  nodeIds: Set<string>,
  padding = 120
): ViewBounds | null {
  const nodes = [...nodeIds]
    .map((nodeId) => layout.nodes.get(nodeId))
    .filter((node): node is PositionedNode => node !== undefined);
  if (nodes.length === 0) return null;

  const minX = Math.min(...nodes.map((node) => node.x)) - padding;
  const minY = Math.min(...nodes.map((node) => node.y)) - padding;
  const maxX = Math.max(...nodes.map((node) => node.x + node.width)) + padding;
  const maxY = Math.max(...nodes.map((node) => node.y + node.height)) + padding;
  return { minX, minY, maxX, maxY };
}

function applyAnchor(
  transform: ViewTransform,
  layout: GraphLayout,
  anchor: ViewAnchor | null
): void {
  if (!anchor) return;
  const node = layout.nodes.get(anchor.nodeId);
  if (!node) return;
  if (!Number.isFinite(anchor.screenX) || !Number.isFinite(anchor.screenY)) return;
  transform.x = anchor.screenX - (node.x + node.width / 2) * transform.scale;
  transform.y = anchor.screenY - (node.y + node.height / 2) * transform.scale;
}

function bindViewportEvents(
  svgElement: SVGSVGElement,
  content: SVGElement,
  transform: ViewTransform
): void {
  let dragging = false;
  let dragStart = { x: 0, y: 0 };
  let transformStart = { ...transform };

  svgElement.addEventListener(
    "wheel",
    (event) => {
      event.preventDefault();
      const nextScale = clamp(transform.scale * (event.deltaY > 0 ? 0.9 : 1.1), minScale, maxScale);
      const factor = nextScale / transform.scale;
      transform.x = event.offsetX - (event.offsetX - transform.x) * factor;
      transform.y = event.offsetY - (event.offsetY - transform.y) * factor;
      transform.scale = nextScale;
      applyTransform(content, transform);
    },
    { passive: false }
  );

  svgElement.addEventListener("pointerdown", (event) => {
    if ((event.target as Element).closest(".dag-node")) return;
    event.preventDefault();
    dragging = true;
    dragStart = { x: event.clientX, y: event.clientY };
    transformStart = { ...transform };
    svgElement.style.cursor = "grabbing";
    svgElement.setPointerCapture(event.pointerId);
  });
  svgElement.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    transform.x = transformStart.x + event.clientX - dragStart.x;
    transform.y = transformStart.y + event.clientY - dragStart.y;
    applyTransform(content, transform);
  });
  svgElement.addEventListener("pointerup", (event) => {
    dragging = false;
    svgElement.style.cursor = "grab";
    svgElement.releasePointerCapture(event.pointerId);
  });
}

function applyTransform(content: SVGElement, transform: ViewTransform): void {
  content.setAttribute("transform", `translate(${transform.x} ${transform.y}) scale(${transform.scale})`);
}

function isFiniteTransform(transform: ViewTransform): boolean {
  return (
    Number.isFinite(transform.scale) &&
    Number.isFinite(transform.x) &&
    Number.isFinite(transform.y)
  );
}

function renderDefs(): SVGElement {
  const defs = svg("defs");
  defs.append(
    edgeMarkerDef(edgeMarkerId, edgeColor),
    edgeMarkerDef(relatedEdgeMarkerId, relatedEdgeColor),
    edgeMarkerDef(dimmedEdgeMarkerId, dimmedEdgeColor)
  );
  return defs;
}

function edgeMarkerDef(id: string, color: string): SVGElement {
  const marker = svg("marker", {
    id,
    markerWidth: "5",
    markerHeight: "5",
    refX: "4",
    refY: "2.5",
    orient: "auto",
    markerUnits: "strokeWidth"
  });
  marker.append(svg("path", { d: "M 0 0 L 5 2.5 L 0 5 z", fill: color }));
  return marker;
}

function renderEdges(
  layout: GraphLayout,
  relatedNodes: Set<string> | null,
  filterMode: string | null
): SVGElement {
  const group = svg("g", { class: "dag-edges" });
  layout.edges.forEach((edge) => {
    const isRelated =
      relatedNodes === null || (relatedNodes.has(edge.source) && relatedNodes.has(edge.target));
    group.append(renderEdge(edge.points, isRelated, Boolean(filterMode)));
  });
  return group;
}

function renderNodes(
  layout: GraphLayout,
  relatedNodes: Set<string> | null,
  selectedNodeId: string | null,
  onSelectNode: (nodeId: string) => void
): SVGElement {
  const group = svg("g", { class: "dag-nodes" });
  const hasSelection = selectedNodeId !== null;
  layout.nodes.forEach((node) => {
    const isSelected = selectedNodeId === node.id;
    const isRelated = relatedNodes?.has(node.id) ?? true;
    group.append(renderNode(node, isSelected, isRelated, hasSelection, onSelectNode));
  });
  return group;
}

function renderEdge(
  points: GraphEdgePoint[],
  isRelated: boolean,
  hasMode: boolean
): SVGPathElement {
  const strokeColor = edgeStrokeColor(isRelated, hasMode);
  const strokeWidth = isRelated && hasMode ? "1.67" : "1";
  return svg("path", {
    d: roundedPolylinePath(points),
    class: "dag-edge",
    stroke: strokeColor,
    "stroke-width": strokeWidth,
    fill: "none",
    "marker-end": `url(#${edgeMarker(isRelated, hasMode)})`
  }) as SVGPathElement;
}

function roundedPolylinePath(points: GraphEdgePoint[]): string {
  if (points.length === 0) return "";
  if (points.length === 1) return `M ${points[0].x} ${points[0].y}`;
  const radius = 12;
  const segments = [`M ${points[0].x} ${points[0].y}`];

  for (let index = 1; index < points.length - 1; index += 1) {
    const previous = points[index - 1];
    const current = points[index];
    const next = points[index + 1];
    const previousDistance = distanceBetween(previous, current);
    const nextDistance = distanceBetween(current, next);
    const cornerRadius = Math.min(radius, previousDistance / 2, nextDistance / 2);

    if (cornerRadius < 1) {
      segments.push(`L ${current.x} ${current.y}`);
      continue;
    }

    const entry = moveToward(current, previous, cornerRadius);
    const exit = moveToward(current, next, cornerRadius);
    segments.push(`L ${entry.x} ${entry.y}`);
    segments.push(`Q ${current.x} ${current.y} ${exit.x} ${exit.y}`);
  }

  const last = points[points.length - 1];
  segments.push(`L ${last.x} ${last.y}`);
  return segments.join(" ");
}

function distanceBetween(first: GraphEdgePoint, second: GraphEdgePoint): number {
  return Math.hypot(second.x - first.x, second.y - first.y);
}

function moveToward(from: GraphEdgePoint, to: GraphEdgePoint, distance: number): GraphEdgePoint {
  const fullDistance = distanceBetween(from, to);
  if (fullDistance === 0) return from;
  const ratio = distance / fullDistance;
  return {
    x: from.x + (to.x - from.x) * ratio,
    y: from.y + (to.y - from.y) * ratio
  };
}

function renderNode(
  node: PositionedNode,
  isSelected: boolean,
  isRelated: boolean,
  hasSelection: boolean,
  onSelectNode: (nodeId: string) => void
): SVGElement {
  const dimNode = hasSelection && !isRelated;
  const shadow = nodeShadow(isSelected, isRelated, hasSelection);
  const group = svg("g", {
    class: "dag-node",
    transform: `translate(${node.x} ${node.y})`,
    "data-node-id": node.id,
    tabindex: "0",
    role: "button",
    style: `cursor:pointer;outline:none;filter:${shadow};user-select:none;-webkit-user-select:none`
  });
  const rect = svg("rect", {
    width: String(node.width),
    height: String(node.height),
    rx: "12",
    fill: nodeFill(node, isSelected, dimNode),
    stroke: nodeBorderColor(node, dimNode),
    "stroke-width": String(Math.max(node.runtime.border_width_px, isSelected ? 2 : 1))
  });
  const label = svg("foreignObject", {
    x: "12",
    y: "8",
    width: String(node.width - 24),
    height: String(node.height - 16)
  });
  const text = document.createElementNS("http://www.w3.org/1999/xhtml", "div");
  text.setAttribute(
    "style",
    [
      "height:100%",
      "display:flex",
      "align-items:center",
      "gap:8px",
      "user-select:none",
      "font:13px system-ui,sans-serif",
      "line-height:26px",
      `color:${nodeTextColor(dimNode)}`
    ].join(";")
  );
  const badge = document.createElementNS("http://www.w3.org/1999/xhtml", "span");
  badge.setAttribute(
    "style",
    [
      "display:inline-flex",
      "align-items:center",
      "justify-content:center",
      "width:16px",
      "height:16px",
      "flex:0 0 16px",
      "border-radius:4px",
      "background:#44403c",
      "color:#fafaf9",
      "font-size:10px",
      "font-weight:600",
      "line-height:1"
    ].join(";")
  );
  badge.textContent = node.type_badge;
  const labelText = document.createElementNS("http://www.w3.org/1999/xhtml", "span");
  labelText.setAttribute(
    "style",
    [
      "min-width:0",
      "overflow:hidden",
      "text-overflow:ellipsis",
      "white-space:nowrap"
    ].join(";")
  );
  labelText.textContent = node.label;
  text.append(badge, labelText);
  label.append(text);
  group.append(rect, label);
  group.addEventListener("click", () => onSelectNode(node.id));
  group.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelectNode(node.id);
    }
  });
  return group;
}

function nodeFill(node: PositionedNode, isSelected: boolean, dimNode: boolean): string {
  if (isSelected) return selectedNodeColor;
  const fillColor = laneColors[normalizeNodeColumn(node.column)] ?? laneColors.other;
  return dimNode ? lightenColor(fillColor, 0.72) : fillColor;
}

function nodeBorderColor(node: PositionedNode, dimNode: boolean): string {
  const borderColor = node.runtime.border_color;
  return dimNode ? lightenColor(borderColor, 0.72) : borderColor;
}

function nodeTextColor(dimNode: boolean): string {
  return dimNode ? lightenColor("#18181b", 0.72) : "#18181b";
}

function nodeShadow(isSelected: boolean, isRelated: boolean, hasSelection: boolean): string {
  if (!hasSelection || !isRelated) return "none";
  if (isSelected) return "drop-shadow(0 4px 10px rgba(15, 23, 42, 0.18))";
  return "drop-shadow(0 2px 5px rgba(15, 23, 42, 0.1))";
}

function edgeStrokeColor(isRelated: boolean, hasMode: boolean): string {
  if (isRelated) return hasMode ? relatedEdgeColor : edgeColor;
  return dimmedEdgeColor;
}

function edgeMarker(isRelated: boolean, hasMode: boolean): string {
  if (isRelated) return hasMode ? relatedEdgeMarkerId : edgeMarkerId;
  return dimmedEdgeMarkerId;
}

function normalizeNodeColumn(column: string): string {
  return column in laneColors ? column : "other";
}

function lightenColor(color: string, amount: number): string {
  const match = /^#([0-9a-f]{6})$/i.exec(color);
  if (!match) return color;
  const hex = match[1];
  const red = parseInt(hex.slice(0, 2), 16);
  const green = parseInt(hex.slice(2, 4), 16);
  const blue = parseInt(hex.slice(4, 6), 16);
  return rgbToHex(
    mixChannel(red, amount),
    mixChannel(green, amount),
    mixChannel(blue, amount)
  );
}

function mixChannel(channel: number, amount: number): number {
  return Math.round(channel + (255 - channel) * amount);
}

function rgbToHex(red: number, green: number, blue: number): string {
  return `#${[red, green, blue].map((channel) => channel.toString(16).padStart(2, "0")).join("")}`;
}

function clamp(value: number, min: number, max: number): number {
  const safeMax = Math.max(min, max);
  return Math.min(Math.max(value, min), safeMax);
}

function svg(name: "path", attributes?: Record<string, string>): SVGPathElement;
function svg(name: "text", attributes?: Record<string, string>): SVGTextElement;
function svg(name: string, attributes: Record<string, string> = {}): SVGElement {
  const element = document.createElementNS("http://www.w3.org/2000/svg", name);
  for (const [key, value] of Object.entries(attributes)) {
    element.setAttribute(key, value);
  }
  return element;
}
