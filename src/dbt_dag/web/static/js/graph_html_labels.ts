import type { Core } from "cytoscape";

type NodeData = {
	id: string;
	label: string;
	typeBadge: string;
	freshness: "last_2h" | "last_24h" | "last_48h" | "stale" | "unknown";
	lastUpdatedAt: string;
	testStatus: "passed" | "stale" | "failed" | "missing";
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
	label.className = "absolute flex flex-col items-center justify-center gap-0.5 px-1";
	label.innerHTML = nodeLabelMarkup(data);
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
	label.innerHTML = nodeLabelMarkup(data);
}

function nodeLabelMarkup(data: NodeData): string {
	const freshnessVisual = freshnessVisualClass(data.freshness);
	return `
    <span class="truncate px-1 text-[13px] font-medium text-zinc-900">${escapeHtml(data.label)}</span>
    <span class="flex items-center justify-center gap-1">
      <span class="inline-flex size-3 shrink-0 items-center justify-center rounded-full ${freshnessVisual.circleClass}"
			title="${escapeHtml(freshnessTitle(data.freshness, data.lastUpdatedAt))}">${iconSvg("clock", freshnessVisual.iconColor)}</span>
      <span class="shrink-0 font-semibold text-zinc-100 bg-zinc-500 size-3 flex items-center justify-center rounded-full
			text-[10px] font-mono" title="Model type">${escapeHtml(data.typeBadge)}</span>
      <span class="${testStatusClass(data.testStatus)}" title="${escapeHtml(testStatusTitle(data.testStatus))}">T</span>
    </span>
  `;
}

function iconSvg(iconName: string, color: string): string {
	return `
    <svg xmlns="http://www.w3.org/2000/svg" class="size-2" fill="none" viewBox="0 0 24 24" stroke-width="2.25" stroke="${color}">
      <path stroke-linecap="round" stroke-linejoin="round" d="${iconPath(iconName)}" />
    </svg>
  `;
}

function iconPath(iconName: string): string {
	if (iconName === "clock") {
		return "M12 6v6l4 2.5M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z";
	}
	return "M6 18 18 6M6 6l12 12";
}

function freshnessVisualClass(freshness: NodeData["freshness"]): {
	circleClass: string;
	iconColor: string;
} {
	if (freshness === "last_2h") {
		return {
			circleClass: "bg-green-600",
			iconColor: "#bbf7d0",
		};
	}
	if (freshness === "last_24h") {
		return {
			circleClass: "bg-green-600",
			iconColor: "#d4d4d8",
		};
	}
	if (freshness === "last_48h") {
		return {
			circleClass: "bg-amber-600",
			iconColor: "#d4d4d8",
		};
	}
	if (freshness === "stale") {
		return {
			circleClass: "bg-red-600",
			iconColor: "#ffffff",
		};
	}
	return {
		circleClass: "bg-zinc-400",
		iconColor: "#ffffff",
	};
}

function freshnessTitle(freshness: NodeData["freshness"], lastUpdatedAt: string): string {
	const suffix = lastUpdatedAt ? ` (${lastUpdatedAt})` : "";
	if (freshness === "last_2h") {
		return `Model ran within 2 hours${suffix}`;
	}
	if (freshness === "last_24h") {
		return `Model ran within 24 hours${suffix}`;
	}
	if (freshness === "last_48h") {
		return `Model ran within 48 hours${suffix}`;
	}
	if (freshness === "stale") {
		return `Model ran more than 48 hours ago${suffix}`;
	}
	return "Model run time is unavailable";
}

function testStatusClass(status: NodeData["testStatus"]): string {
	if (status === "passed") {
		return "status-dot status-dot-passed";
	}
	if (status === "stale") {
		return "status-dot status-dot-stale";
	}
	if (status === "failed") {
		return "status-dot status-dot-failed";
	}
	return "status-dot status-dot-missing";
}

function testStatusTitle(status: NodeData["testStatus"]): string {
	if (status === "passed") {
		return "All tests passed";
	}
	if (status === "stale") {
		return "At least one test has not run for more than 24 hours";
	}
	if (status === "failed") {
		return "At least one test failed";
	}
	return "No tests";
}

function escapeHtml(value: string): string {
	return value
		.replaceAll("&", "&amp;")
		.replaceAll("<", "&lt;")
		.replaceAll(">", "&gt;")
		.replaceAll('"', "&quot;")
		.replaceAll("'", "&#39;");
}
