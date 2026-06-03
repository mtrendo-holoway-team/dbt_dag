import type { GraphLayout, LaneBounds, PositionedNode, ViewAnchor } from "./graph_types";

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

const edgeColor = "#52525b";
const relatedEdgeColor = "#0ea5e9";
const dimmedEdgeColor = "#d4d4d8";
const selectedNodeColor = "#e0f2fe";
const relatedNodeColor = "#ffffff";
const dimmedNodeColor = "#f4f4f5";
const edgeMarkerId = "dag-arrowhead";
const minScale = 0.005;
const maxScale = 2.5;
const toolbarSafeTop = 104;

const transforms = new WeakMap<HTMLElement, ViewTransform>();

export function renderGraph(
  container: HTMLElement,
  layout: GraphLayout,
  relatedNodes: Set<string> | null,
  selectedNodeId: string | null,
  filterMode: string | null,
  onSelectNode: (nodeId: string) => void,
  fit: boolean,
  anchor: ViewAnchor | null = null
): void {
  prepareContainer(container);
  const viewport = viewportSize(container);
  const transform = fit || !transforms.has(container)
    ? fitTransform(layout, viewport)
    : transforms.get(container) ?? fitTransform(layout, viewport);
  applyAnchor(transform, layout, anchor);
  transforms.set(container, transform);

  const svgElement = svg("svg", {
    class: "dag-canvas",
    style: "display:block;width:100%;height:100%;background:#fafafa;cursor:grab",
    viewBox: `0 0 ${viewport.width} ${viewport.height}`,
    width: String(viewport.width),
    height: String(viewport.height),
    role: "img",
    "aria-label": "dbt DAG"
  }) as SVGSVGElement;
  const content = svg("g", { class: "dag-content" });
  const overlay = document.createElement("div");
  overlay.className = "dag-lane-title-overlay";
  overlay.style.cssText = "position:absolute;inset:0;pointer-events:none;overflow:hidden";

  container.replaceChildren(svgElement, overlay);
  svgElement.append(renderDefs(), content);
  content.append(renderLanes(layout), renderEdges(layout, relatedNodes, filterMode));
  content.append(renderNodes(layout, relatedNodes, selectedNodeId, onSelectNode));
  applyTransform(content, transform);
  renderStickyTitles(overlay, layout.lanes, transform, viewport);
  bindViewportEvents(svgElement, content, overlay, layout, viewport, transform);
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
  layout: GraphLayout,
  viewport: { width: number; height: number }
): ViewTransform {
  const scale = Math.min(
    1,
    Math.max(minScale, Math.min(viewport.width / layout.width, viewport.height / layout.height))
  );
  return {
    scale,
    x: (viewport.width - layout.width * scale) / 2,
    y: (viewport.height - layout.height * scale) / 2
  };
}

function applyAnchor(
  transform: ViewTransform,
  layout: GraphLayout,
  anchor: ViewAnchor | null
): void {
  if (!anchor) return;
  const node = layout.nodes.get(anchor.nodeId);
  if (!node) return;
  transform.x = anchor.screenX - (node.x + node.width / 2) * transform.scale;
  transform.y = anchor.screenY - (node.y + node.height / 2) * transform.scale;
}

function bindViewportEvents(
  svgElement: SVGSVGElement,
  content: SVGElement,
  overlay: HTMLElement,
  layout: GraphLayout,
  viewport: { width: number; height: number },
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
      renderStickyTitles(overlay, layout.lanes, transform, viewport);
    },
    { passive: false }
  );

  svgElement.addEventListener("pointerdown", (event) => {
    if ((event.target as Element).closest(".dag-node")) return;
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
    renderStickyTitles(overlay, layout.lanes, transform, viewport);
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

function renderStickyTitles(
  overlay: HTMLElement,
  lanes: LaneBounds[],
  transform: ViewTransform,
  viewport: { width: number; height: number }
): void {
  const lane = currentLane(lanes, transform, viewport);
  if (!lane) {
    overlay.replaceChildren();
    return;
  }
  const title = document.createElement("div");
  const left = clamp(
    lane.x * transform.scale + transform.x + 14,
    12,
    Math.max(12, (lane.x + lane.width) * transform.scale + transform.x - 120)
  );
  const top = clamp(
    lane.y * transform.scale + transform.y + 24,
    toolbarSafeTop,
    Math.max(toolbarSafeTop, (lane.y + lane.height) * transform.scale + transform.y - 28)
  );
  title.textContent = lane.label;
  title.style.cssText = [
    "position:absolute",
    `left:${left}px`,
    `top:${top}px`,
    "font:20px system-ui,sans-serif",
    "color:#111827",
    "white-space:nowrap",
    "text-shadow:0 1px 0 rgba(255,255,255,.55)"
  ].join(";");
  overlay.replaceChildren(title);
}

function currentLane(
  lanes: LaneBounds[],
  transform: ViewTransform,
  viewport: { width: number; height: number }
): LaneBounds | null {
  const visibleLanes = lanes.filter((lane) => laneIsVisible(lane, transform, viewport));
  if (visibleLanes.length === 0) return null;
  const graphCenter = {
    x: (viewport.width / 2 - transform.x) / transform.scale,
    y: (viewport.height / 2 - transform.y) / transform.scale
  };
  const containingLane = visibleLanes.find(
    (lane) =>
      graphCenter.x >= lane.x &&
      graphCenter.x <= lane.x + lane.width &&
      graphCenter.y >= lane.y &&
      graphCenter.y <= lane.y + lane.height
  );
  if (containingLane) return containingLane;
  return visibleLanes.sort((left, right) => {
    const leftDistance = laneDistanceToPoint(left, graphCenter);
    const rightDistance = laneDistanceToPoint(right, graphCenter);
    return leftDistance - rightDistance;
  })[0];
}

function laneDistanceToPoint(lane: LaneBounds, point: { x: number; y: number }): number {
  return Math.hypot(lane.x + lane.width / 2 - point.x, lane.y + lane.height / 2 - point.y);
}

function laneIsVisible(
  lane: LaneBounds,
  transform: ViewTransform,
  viewport: { width: number; height: number }
): boolean {
  const left = lane.x * transform.scale + transform.x;
  const right = (lane.x + lane.width) * transform.scale + transform.x;
  const top = lane.y * transform.scale + transform.y;
  const bottom = (lane.y + lane.height) * transform.scale + transform.y;
  return right > 0 && left < viewport.width && bottom > 0 && top < viewport.height;
}

function renderDefs(): SVGElement {
  const defs = svg("defs");
  const marker = svg("marker", {
    id: edgeMarkerId,
    markerWidth: "10",
    markerHeight: "10",
    refX: "8",
    refY: "5",
    orient: "auto",
    markerUnits: "strokeWidth"
  });
  marker.append(svg("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: edgeColor }));
  defs.append(marker);
  return defs;
}

function renderLanes(layout: GraphLayout): SVGElement {
  const group = svg("g", { class: "dag-lanes" });
  layout.lanes.forEach((lane) => {
    group.append(
      svg("rect", {
        x: String(lane.x),
        y: String(lane.y),
        width: String(lane.width),
        height: String(lane.height),
        fill: laneColors[lane.column] ?? laneColors.other
      }),
      laneTitle(lane)
    );
  });
  return group;
}

function laneTitle(lane: LaneBounds): SVGTextElement {
  const title = svg("text", {
    x: String(lane.x + 14),
    y: String(lane.y + 34),
    style: "font:20px system-ui,sans-serif;fill:#111827"
  }) as SVGTextElement;
  title.textContent = lane.label;
  return title;
}

function renderEdges(
  layout: GraphLayout,
  relatedNodes: Set<string> | null,
  filterMode: string | null
): SVGElement {
  const group = svg("g", { class: "dag-edges" });
  layout.edges.forEach((edge) => {
    const source = layout.nodes.get(edge.source);
    const target = layout.nodes.get(edge.target);
    if (!source || !target) return;
    const isRelated =
      relatedNodes === null || (relatedNodes.has(edge.source) && relatedNodes.has(edge.target));
    group.append(renderEdge(source, target, isRelated, Boolean(filterMode)));
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
  layout.nodes.forEach((node) => {
    const isSelected = selectedNodeId === node.id;
    const isRelated = relatedNodes?.has(node.id) ?? true;
    group.append(renderNode(node, isSelected, isRelated, onSelectNode));
  });
  return group;
}

function renderEdge(
  source: PositionedNode,
  target: PositionedNode,
  isRelated: boolean,
  hasMode: boolean
): SVGPathElement {
  const sourcePoint = { x: source.x + source.width, y: source.y + source.height / 2 };
  const targetPoint = { x: target.x, y: target.y + target.height / 2 };
  const distance = Math.max(80, Math.abs(targetPoint.x - sourcePoint.x) / 2);
  return svg("path", {
    d: [
      `M ${sourcePoint.x} ${sourcePoint.y}`,
      `C ${sourcePoint.x + distance} ${sourcePoint.y}`,
      `${targetPoint.x - distance} ${targetPoint.y}`,
      `${targetPoint.x} ${targetPoint.y}`
    ].join(" "),
    class: "dag-edge",
    stroke: isRelated ? (hasMode ? relatedEdgeColor : edgeColor) : dimmedEdgeColor,
    "stroke-width": isRelated && hasMode ? "2.5" : "1.5",
    fill: "none",
    "marker-end": `url(#${edgeMarkerId})`
  }) as SVGPathElement;
}

function renderNode(
  node: PositionedNode,
  isSelected: boolean,
  isRelated: boolean,
  onSelectNode: (nodeId: string) => void
): SVGElement {
  const group = svg("g", {
    class: "dag-node",
    transform: `translate(${node.x} ${node.y})`,
    "data-node-id": node.id,
    tabindex: "0",
    role: "button",
    style: "cursor:pointer;outline:none"
  });
  const rect = svg("rect", {
    width: String(node.width),
    height: String(node.height),
    rx: "12",
    fill: nodeFill(isSelected, isRelated),
    stroke: isSelected ? relatedEdgeColor : "#a1a1aa",
    "stroke-width": isSelected ? "2" : "1.5"
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
      "overflow:hidden",
      "text-overflow:ellipsis",
      "white-space:nowrap",
      "font:13px system-ui,sans-serif",
      "line-height:26px",
      "color:#18181b"
    ].join(";")
  );
  text.textContent = node.label;
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

function nodeFill(isSelected: boolean, isRelated: boolean): string {
  if (isSelected) return selectedNodeColor;
  if (isRelated) return relatedNodeColor;
  return dimmedNodeColor;
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
