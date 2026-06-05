import type { Core } from "cytoscape";

type NodeData = {
  id: string;
  label: string;
  typeBadge: string;
  statusIconName: string;
  statusColorHex: string;
};

export type GraphHtmlLabels = {
  sync: () => void;
};

export function createGraphHtmlLabels(container: HTMLElement, cy: Core): GraphHtmlLabels {
  const layer = document.createElement("div");
  layer.className = "pointer-events-none absolute inset-0 z-[1] overflow-hidden";
  container.append(layer);

  const labelsByNodeId = new Map<string, HTMLDivElement>();
  let frameId: number | null = null;

  cy.on("pan zoom resize position add remove", scheduleSync);

  return { sync: scheduleSync };

  function scheduleSync(): void {
    if (frameId !== null) return;
    frameId = window.requestAnimationFrame(() => {
      frameId = null;
      syncLabels();
    });
  }

  function syncLabels(): void {
    const nextNodeIds = new Set<string>();
    cy.nodes("[kind = 'node']").forEach((node) => {
      const nodeId = node.id();
      nextNodeIds.add(nodeId);

      const data = node.data() as NodeData;
      const label = labelsByNodeId.get(nodeId) ?? createLabel(data);
      if (!labelsByNodeId.has(nodeId)) {
        labelsByNodeId.set(nodeId, label);
        layer.append(label);
      }
      updateLabel(label, node, data, cy.zoom());
    });

    for (const [nodeId, label] of labelsByNodeId.entries()) {
      if (nextNodeIds.has(nodeId)) continue;
      label.remove();
      labelsByNodeId.delete(nodeId);
    }
  }
}

function createLabel(data: NodeData): HTMLDivElement {
  const label = document.createElement("div");
  label.className = "absolute flex items-center justify-center gap-2 px-4 text-[13px] font-medium";
  label.innerHTML = `
    <span class="shrink-0 font-semibold text-zinc-900">${escapeHtml(data.typeBadge)}</span>
    <span class="truncate text-zinc-900">${escapeHtml(data.label)}</span>
    <span class="shrink-0">${statusIconSvg(data.statusIconName, data.statusColorHex)}</span>
  `;
  return label;
}

function updateLabel(
  label: HTMLDivElement,
  node: NodeSingular,
  data: NodeData,
  zoom: number
): void {
  const position = node.renderedPosition();
  label.style.left = `${position.x}px`;
  label.style.top = `${position.y}px`;
  label.style.width = `${node.width()}px`;
  label.style.display = node.hasClass("hidden") ? "none" : "flex";
  label.style.opacity = node.hasClass("dimmed") ? "0.72" : "1";
  label.style.transform = `translate(-50%, -50%) scale(${zoom})`;
  label.style.transformOrigin = "center center";

  const badge = label.children.item(0);
  if (badge) {
    badge.textContent = data.typeBadge;
  }
  const title = label.children.item(1);
  if (title) {
    title.textContent = data.label;
  }
  const status = label.children.item(2);
  if (status) {
    status.innerHTML = statusIconSvg(data.statusIconName, data.statusColorHex);
  }
}

function statusIconSvg(iconName: string, colorHex: string): string {
  return `
    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke-width="1.8" stroke="${colorHex}">
      <path stroke-linecap="round" stroke-linejoin="round" d="${iconPath(iconName)}" />
    </svg>
  `;
}

function iconPath(iconName: string): string {
  if (iconName === "check-circle") {
    return "M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z";
  }
  if (iconName === "check") {
    return "M4.5 12.75 10.5 18l9-13.5";
  }
  if (iconName === "exclamation-triangle") {
    return "m11.25 9.75.041-.02a.75.75 0 0 1 1.06.852l-.708 2.836a.75.75 0 0 1-1.455-.364l.708-2.836a.75.75 0 0 1 .354-.468ZM12 16.5h.008v.008H12V16.5ZM10.343 3.94c.563-1.01 2.01-1.01 2.572 0l6.392 11.48c.548.984-.165 2.205-1.286 2.205H5.237c-1.12 0-1.834-1.221-1.286-2.205l6.392-11.48Z";
  }
  return "M6 18 18 6M6 6l12 12";
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
