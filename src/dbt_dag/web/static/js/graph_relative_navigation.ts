import type { Core } from "cytoscape";

type RelativeNavigationController = {
  render: (
    selectedNodeId: string | null,
    visibleNodeIds: Set<string>,
    upstream: Map<string, Set<string>>,
    downstream: Map<string, Set<string>>
  ) => void;
};

type ShortcutBadge = {
  element: HTMLDivElement;
  shortcut: string;
};

const chordPrefix = "g";
const chordResolveDelayMs = 250;

export function createRelativeNavigation(
  container: HTMLElement,
  cy: Core,
  onFocusNode: (nodeId: string) => void
): RelativeNavigationController {
  const overlay = document.createElement("div");
  overlay.className = "pointer-events-none absolute inset-0 z-0 overflow-hidden opacity-60";
  container.append(overlay);

  const badgeByNodeId = new Map<string, ShortcutBadge>();
  const nodeIdByShortcut = new Map<string, string>();
  let pendingShortcut = "";
  let resolveTimer: number | null = null;
  let frameId: number | null = null;

  cy.on("pan zoom resize", schedulePositionSync);

  document.addEventListener("keydown", handleKeydown, true);

  return {
    render(selectedNodeId, visibleNodeIds, upstream, downstream) {
      clearPendingShortcut();
      if (!selectedNodeId) {
        clearBadges();
        return;
      }

      const orderedNodeIds = orderedShortcutNodeIds(
        cy,
        selectedNodeId,
        visibleNodeIds,
        upstream,
        downstream
      );
      nodeIdByShortcut.clear();
      badgeByNodeId.clear();

      overlay.replaceChildren(
        ...orderedNodeIds.map((nodeId, index) => {
          const shortcut = `${chordPrefix}${shortcutSuffix(index)}`;
          const element = document.createElement("div");
          element.className =
            "absolute rounded-r-md rounded-l-none bg-zinc-200/95 px-2 py-1 font-mono text-xs font-semibold text-zinc-700 transition-opacity";
          element.textContent = shortcut.toUpperCase();
          badgeByNodeId.set(nodeId, { element, shortcut });
          nodeIdByShortcut.set(shortcut, nodeId);
          return element;
        })
      );

      applyPendingShortcutState();
      schedulePositionSync();
    }
  };

  function handleKeydown(event: KeyboardEvent): void {
    if (event.defaultPrevented || nodeIdByShortcut.size === 0 || isEditableTarget(event.target)) {
      return;
    }
    if (event.key === "Escape") {
      clearPendingShortcut();
      return;
    }

    const key = normalizedLetter(event.key);
    if (!key) {
      clearPendingShortcut();
      return;
    }

    const nextShortcut = pendingShortcut ? `${pendingShortcut}${key}` : key;
    if (pendingShortcut === "" && key !== chordPrefix) {
      return;
    }
    const matchingShortcuts = [...nodeIdByShortcut.keys()].filter((shortcut) =>
      shortcut.startsWith(nextShortcut)
    );
    if (matchingShortcuts.length === 0) {
      clearPendingShortcut();
      return;
    }

    pendingShortcut = nextShortcut;
    applyPendingShortcutState();
    scheduleResolve();
    event.preventDefault();
    event.stopPropagation();

    const exactNodeId = nodeIdByShortcut.get(nextShortcut);
    const hasLongerMatch = matchingShortcuts.some((shortcut) => shortcut.length > nextShortcut.length);
    if (exactNodeId && !hasLongerMatch) {
      focusShortcutTarget(exactNodeId);
    }
  }

  function focusShortcutTarget(nodeId: string): void {
    clearPendingShortcut();
    onFocusNode(nodeId);
  }

  function scheduleResolve(): void {
    if (resolveTimer !== null) {
      window.clearTimeout(resolveTimer);
    }
    const exactNodeId = nodeIdByShortcut.get(pendingShortcut);
    if (!exactNodeId) return;
    resolveTimer = window.setTimeout(() => {
      focusShortcutTarget(exactNodeId);
    }, chordResolveDelayMs);
  }

  function clearPendingShortcut(): void {
    pendingShortcut = "";
    if (resolveTimer !== null) {
      window.clearTimeout(resolveTimer);
      resolveTimer = null;
    }
    applyPendingShortcutState();
  }

  function clearBadges(): void {
    badgeByNodeId.clear();
    nodeIdByShortcut.clear();
    overlay.replaceChildren();
  }

  function applyPendingShortcutState(): void {
    for (const { element, shortcut } of badgeByNodeId.values()) {
      if (!pendingShortcut) {
        element.style.opacity = "1";
        element.style.backgroundColor = "";
        element.style.color = "";
        continue;
      }
      const isMatch = shortcut.startsWith(pendingShortcut);
      element.style.opacity = isMatch ? "1" : "0.18";
      element.style.backgroundColor = isMatch ? "#d1fae5" : "";
      element.style.color = isMatch ? "#134e4a" : "";
    }
  }

  function schedulePositionSync(): void {
    if (frameId !== null) return;
    frameId = window.requestAnimationFrame(() => {
      frameId = null;
      syncBadgePositions();
    });
  }

  function syncBadgePositions(): void {
    for (const [nodeId, badge] of badgeByNodeId.entries()) {
      const node = cy.getElementById(nodeId);
      if (node.empty() || !node.isNode()) continue;

      const position = node.renderedPosition();
      const zoom = cy.zoom();
      const nodeWidth = node.width() * zoom;
      const rightEdge = position.x + nodeWidth / 2;

      badge.element.style.left = `${rightEdge}px`;
      badge.element.style.top = `${position.y}px`;
      badge.element.style.transform = `translateY(-50%) scale(${zoom})`;
      badge.element.style.transformOrigin = "left center";
    }
  }
}

function orderedShortcutNodeIds(
  cy: Core,
  selectedNodeId: string,
  visibleNodeIds: Set<string>,
  upstream: Map<string, Set<string>>,
  downstream: Map<string, Set<string>>
): string[] {
  const graphDistances = visibleGraphDistances(selectedNodeId, visibleNodeIds, upstream, downstream);
  const selectedNode = cy.getElementById(selectedNodeId);
  const selectedPosition = selectedNode.empty() ? null : selectedNode.renderedPosition();

  return [...visibleNodeIds]
    .filter((nodeId) => nodeId !== selectedNodeId && !cy.getElementById(nodeId).empty())
    .sort((left, right) => {
      const leftDistance = graphDistances.get(left) ?? Number.POSITIVE_INFINITY;
      const rightDistance = graphDistances.get(right) ?? Number.POSITIVE_INFINITY;
      if (leftDistance !== rightDistance) return leftDistance - rightDistance;

      const leftScreenDistance = renderedDistance(cy, left, selectedPosition);
      const rightScreenDistance = renderedDistance(cy, right, selectedPosition);
      if (leftScreenDistance !== rightScreenDistance) {
        return leftScreenDistance - rightScreenDistance;
      }
      return left.localeCompare(right);
    });
}

function visibleGraphDistances(
  selectedNodeId: string,
  visibleNodeIds: Set<string>,
  upstream: Map<string, Set<string>>,
  downstream: Map<string, Set<string>>
): Map<string, number> {
  const distances = new Map<string, number>([[selectedNodeId, 0]]);
  const queue = [selectedNodeId];

  while (queue.length > 0) {
    const nodeId = queue.shift();
    if (!nodeId) continue;

    const currentDistance = distances.get(nodeId);
    if (currentDistance === undefined) continue;

    for (const neighborId of relatedNodeIds(nodeId, visibleNodeIds, upstream, downstream)) {
      if (distances.has(neighborId)) continue;
      distances.set(neighborId, currentDistance + 1);
      queue.push(neighborId);
    }
  }

  return distances;
}

function relatedNodeIds(
  nodeId: string,
  visibleNodeIds: Set<string>,
  upstream: Map<string, Set<string>>,
  downstream: Map<string, Set<string>>
): Set<string> {
  const result = new Set<string>();
  for (const neighborId of upstream.get(nodeId) ?? new Set<string>()) {
    if (visibleNodeIds.has(neighborId)) result.add(neighborId);
  }
  for (const neighborId of downstream.get(nodeId) ?? new Set<string>()) {
    if (visibleNodeIds.has(neighborId)) result.add(neighborId);
  }
  return result;
}

function renderedDistance(
  cy: Core,
  nodeId: string,
  selectedPosition: { x: number; y: number } | null
): number {
  if (!selectedPosition) return Number.POSITIVE_INFINITY;
  const node = cy.getElementById(nodeId);
  if (node.empty()) return Number.POSITIVE_INFINITY;
  const position = node.renderedPosition();
  return Math.hypot(position.x - selectedPosition.x, position.y - selectedPosition.y);
}

function shortcutSuffix(index: number): string {
  let value = index;
  let suffix = "";
  do {
    suffix = String.fromCharCode(97 + (value % 26)) + suffix;
    value = Math.floor(value / 26) - 1;
  } while (value >= 0);
  return suffix;
}

function normalizedLetter(value: string): string | null {
  return /^[a-z]$/i.test(value) ? value.toLowerCase() : null;
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) return true;
  return target.isContentEditable;
}
