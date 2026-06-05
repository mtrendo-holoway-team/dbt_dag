import ELK, { type ElkNode } from "elkjs/lib/elk.bundled.js";

import type {
	GraphEdge,
	GraphEdgePoint,
	GraphGroup,
	GraphLayout,
	GraphNode,
	GraphPayload,
	PositionedGroup,
	PositionedNode,
	RoutedGraphEdge
} from "./graph_types";

export const graphPaddingX = 48;
export const graphPaddingY = 140;
export const nodeWidth = 210;
export const nodeHeight = 42;

const minGraphHeight = 260;
const groupPaddingX = 30;
const groupPaddingTop = 50;
const groupPaddingBottom = 40;

const edgeLaneGap = 14;
const edgeLaneStartOffset = 56;

export async function layoutGraph(
	payload: GraphPayload,
	activePackages: Set<string>
): Promise<GraphLayout> {
	const visiblePayload = filterPayload(payload, activePackages);
	const nodesById = new Map(visiblePayload.nodes.map((node) => [node.id, node]));
	const effectiveColumns = effectiveColumnByNode(visiblePayload);
	const elkLayout = await layoutOrder(visiblePayload, nodesById);
	const positionedNodes = positionNodes(visiblePayload.nodes, effectiveColumns, elkLayout.nodePositions);
	const routedEdges = positionEdges(elkLayout.edges, positionedNodes);
	const positionedGroups = positionGroups(visiblePayload.groups, positionedNodes);
	const graphBounds = graphBoundsForLayout(positionedNodes, routedEdges, positionedGroups);

	return {
		nodes: positionedNodes,
		edges: routedEdges,
		groups: positionedGroups,
		width: graphBounds.width,
		height: graphBounds.height
	};
}

export function visibleMainColumns(columns: string[]): string[] {
	return columns.filter((column) => column !== "other");
}

function filterPayload(payload: GraphPayload, activePackages: Set<string>): GraphPayload {
	const nodes = payload.nodes.filter((node) => activePackages.has(node.package_name));
	const nodeIds = new Set(nodes.map((node) => node.id));
	return {
		columns: payload.columns,
		nodes,
		edges: payload.edges.filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target)),
		groups: payload.groups
			.map((group) => ({
				...group,
				node_ids: group.node_ids.filter((nodeId) => nodeIds.has(nodeId))
			}))
			.filter((group) => group.node_ids.length > 0),
		project: payload.project
	};
}

async function layoutOrder(
	payload: GraphPayload,
	nodesById: Map<string, GraphNode>
): Promise<{ nodePositions: Map<string, { x: number; y: number }>; edges: RoutedGraphEdge[] }> {
	const edgesById = new Map(payload.edges.map((edge) => [edge.id, edge]));
	const groupIdByNode = groupIdByNodeId(payload.groups);

	const rootEdges = payload.edges
		.filter((edge) => nodesById.has(edge.source) && nodesById.has(edge.target))
		.filter((edge) => groupIdByNode.get(edge.source) !== groupIdByNode.get(edge.target))
		.map((edge) => ({
			id: edge.id,
			sources: [edge.source],
			targets: [edge.target]
		}));

	const elkGraph: ElkNode = {
		id: "root",
		layoutOptions: {

			"elk.algorithm": "layered",

			"elk.direction": "RIGHT",

			"elk.hierarchyHandling": "INCLUDE_CHILDREN",

			"elk.edgeRouting": "SPLINES",
			"org.eclipse.elk.layered.edgeRouting.splines.mode": "CONSERVATIVE_SOFT",

			"elk.spacing.nodeNode": "96",

			"elk.spacing.edgeEdge": "18",

			"elk.spacing.edgeNode": "40",

			"elk.layered.spacing.nodeNodeBetweenLayers": "180",

			"elk.layered.spacing.edgeNodeBetweenLayers": "56",

			"elk.layered.spacing.edgeEdgeBetweenLayers": "24",

			"elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",


			"elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",

			"elk.layered.crossingMinimization.greedySwitch.activationThreshold": "0",


			"elk.spacing.componentComponent": "140"

		},
		children: layoutChildren(payload, nodesById, groupIdByNode),
		edges: rootEdges
	};

	const layout = await new ELK().layout(elkGraph);

	return {
		nodePositions: absoluteNodePositions(layout.children ?? []),
		edges: absoluteRoutedEdges(layout, edgesById)
	};
}

function layoutChildren(
	payload: GraphPayload,
	nodesById: Map<string, GraphNode>,
	groupIdByNode: Map<string, string>
): ElkNode[] {
	const children: ElkNode[] = payload.groups.flatMap((group) => {
		const groupNodes = payload.nodes.filter((node) => groupIdByNode.get(node.id) === group.id);
		if (groupNodes.length === 0) return [];

		const groupEdges = payload.edges
			.filter((edge) => nodesById.has(edge.source) && nodesById.has(edge.target))
			.filter((edge) => groupIdByNode.get(edge.source) === group.id)
			.filter((edge) => groupIdByNode.get(edge.target) === group.id)
			.map((edge) => ({
				id: edge.id,
				sources: [edge.source],
				targets: [edge.target]
			}));

		return [
			{
				id: group.id,
				layoutOptions: {
					"elk.padding": `[top=${groupPaddingTop},left=${groupPaddingX},bottom=${groupPaddingBottom},right=${groupPaddingX}]`
				},
				children: groupNodes.map(elkNode),
				edges: groupEdges
			}
		];
	});

	children.push(...payload.nodes.filter((node) => !groupIdByNode.has(node.id)).map(elkNode));
	return children;
}

function absoluteRoutedEdges(
	root: ElkNode,
	edgesById: Map<string, GraphEdge>,
	offset: { x: number; y: number } = { x: 0, y: 0 }
): RoutedGraphEdge[] {
	const currentOffset = {
		x: offset.x + (root.x ?? 0),
		y: offset.y + (root.y ?? 0)
	};

	const localEdges = routedEdgesWithOffset(root.edges ?? [], edgesById, currentOffset);

	const childEdges = (root.children ?? []).flatMap((child) =>
		absoluteRoutedEdges(child, edgesById, currentOffset)
	);

	return [...localEdges, ...childEdges];
}

function routedEdgesWithOffset(
	edges: Array<{
		id?: string;
		sections?: Array<{
			startPoint?: { x?: number; y?: number };
			endPoint?: { x?: number; y?: number };
			bendPoints?: Array<{ x?: number; y?: number }>;
		}>;
	}>,
	edgesById: Map<string, GraphEdge>,
	offset: { x: number; y: number }
): RoutedGraphEdge[] {
	return edges.flatMap((edge) => {
		if (!edge.id) return [];

		const rawEdge = edgesById.get(edge.id);
		if (!rawEdge) return [];

		const points = mergeSectionPoints(edge.sections ?? []).map((point) => ({
			x: point.x + offset.x,
			y: point.y + offset.y
		}));

		if (points.length < 2) return [];

		return [{ ...rawEdge, points }];
	});
}

function groupIdByNodeId(groups: GraphGroup[]): Map<string, string> {
	const groupIdByNode = new Map<string, string>();
	groups.forEach((group) => {
		group.node_ids.forEach((nodeId) => {
			if (!groupIdByNode.has(nodeId)) {
				groupIdByNode.set(nodeId, group.id);
			}
		});
	});
	return groupIdByNode;
}

function elkNode(node: GraphNode): ElkNode {
	return {
		id: node.id,
		width: nodeWidth,
		height: nodeHeight
	};
}

function absoluteNodePositions(
	nodes: ElkNode[],
	offset: { x: number; y: number } = { x: 0, y: 0 }
): Map<string, { x: number; y: number }> {
	const positions = new Map<string, { x: number; y: number }>();
	nodes.forEach((node) => {
		const x = offset.x + (node.x ?? 0);
		const y = offset.y + (node.y ?? 0);
		if (node.children && node.children.length > 0) {
			absoluteNodePositions(node.children, { x, y }).forEach((position, nodeId) => {
				positions.set(nodeId, position);
			});
			return;
		}
		positions.set(node.id, { x, y });
	});
	return positions;
}

function positionNodes(
	nodes: GraphNode[],
	effectiveColumns: Map<string, string>,
	elkOrder: Map<string, { x: number; y: number }>
): Map<string, PositionedNode> {
	if (nodes.length === 0) return new Map();
	const minX = Math.min(...nodes.map((node) => elkOrder.get(node.id)?.x ?? 0));
	const minY = Math.min(...nodes.map((node) => elkOrder.get(node.id)?.y ?? 0));
	return new Map(
		nodes.map((node) => {
			const position = elkOrder.get(node.id) ?? { x: minX, y: minY };
			return [
				node.id,
				{
					...node,
					effectiveColumn: effectiveColumns.get(node.id) ?? node.column,
					x: graphPaddingX + position.x - minX,
					y: graphPaddingY + position.y - minY,
					width: nodeWidth,
					height: nodeHeight
				}
			];
		})
	);
}

const edgeBusGap = 28;
const edgeBusPadding = 80;

function positionEdges(
  edges: RoutedGraphEdge[],
  positionedNodes: Map<string, PositionedNode>
): RoutedGraphEdge[] {
  const groups = new Map<string, RoutedGraphEdge[]>();

  edges.forEach((edge) => {
    const source = positionedNodes.get(edge.source);
    const target = positionedNodes.get(edge.target);
    if (!source || !target) return;

    const key = `${source.effectiveColumn}->${target.effectiveColumn}->${target.id}`;
    const groupedEdges = groups.get(key) ?? [];
    groupedEdges.push(edge);
    groups.set(key, groupedEdges);
  });

  const result: RoutedGraphEdge[] = [];
  let busIndex = 0;

  groups.forEach((groupEdges) => {
    const firstEdge = groupEdges[0];
    const firstSource = positionedNodes.get(firstEdge.source);
    const target = positionedNodes.get(firstEdge.target);

    if (!firstSource || !target) return;

    const sourceRightMax = Math.max(
      ...groupEdges.flatMap((edge) => {
        const source = positionedNodes.get(edge.source);
        return source ? [source.x + source.width] : [];
      })
    );

    const targetLeft = target.x;
    const gap = targetLeft - sourceRightMax;

    const busX =
      gap > edgeBusPadding * 2
        ? sourceRightMax + edgeBusPadding + busIndex * edgeBusGap
        : sourceRightMax + Math.max(40, gap / 2);

    busIndex += 1;

    const targetPoint = {
      x: target.x,
      y: target.y + target.height / 2
    };

    groupEdges.forEach((edge) => {
      const source = positionedNodes.get(edge.source);
      if (!source) return;

      const sourcePoint = {
        x: source.x + source.width,
        y: source.y + source.height / 2
      };

      result.push({
        ...edge,
        points: [
          sourcePoint,
          { x: busX, y: sourcePoint.y },
          { x: busX, y: targetPoint.y },
          targetPoint
        ]
      });
    });
  });

  return result;
}

function graphBoundsForLayout(
	nodes: Map<string, PositionedNode>,
	edges: RoutedGraphEdge[],
	groups: PositionedGroup[]
): { width: number; height: number } {
	if (nodes.size === 0) return { width: graphPaddingX * 2, height: minGraphHeight };
	let maxX = 0;
	let maxY = 0;
	let minX = graphPaddingX;
	let minY = graphPaddingY;
	nodes.forEach((node) => {
		minX = Math.min(minX, node.x);
		minY = Math.min(minY, node.y);
		maxX = Math.max(maxX, node.x + node.width);
		maxY = Math.max(maxY, node.y + node.height);
	});
	edges.forEach((edge) => {
		edge.points.forEach((point) => {
			minX = Math.min(minX, point.x);
			minY = Math.min(minY, point.y);
			maxX = Math.max(maxX, point.x);
			maxY = Math.max(maxY, point.y);
		});
	});
	groups.forEach((group) => {
		minX = Math.min(minX, group.x);
		minY = Math.min(minY, group.y);
		maxX = Math.max(maxX, group.x + group.width);
		maxY = Math.max(maxY, group.y + group.height);
	});
	return {
		width: maxX + Math.max(graphPaddingX, -Math.min(0, minX)),
		height: Math.max(minGraphHeight, maxY + Math.max(graphPaddingY, -Math.min(0, minY)))
	};
}

function mergeSectionPoints(
	sections: Array<{
		startPoint?: { x?: number; y?: number };
		endPoint?: { x?: number; y?: number };
		bendPoints?: Array<{ x?: number; y?: number }>;
	}>
): GraphEdgePoint[] {
	const points: GraphEdgePoint[] = [];
	sections.forEach((section) => {
		const sectionPoints = [
			section.startPoint,
			...(section.bendPoints ?? []),
			section.endPoint
		].flatMap((point) => {
			if (point?.x === undefined || point.y === undefined) return [];
			return [{ x: point.x, y: point.y }];
		});
		sectionPoints.forEach((point) => {
			const previous = points[points.length - 1];
			if (previous && previous.x === point.x && previous.y === point.y) return;
			points.push(point);
		});
	});
	return points;
}

function effectiveColumnByNode(payload: GraphPayload): Map<string, string> {
	const mainColumns = visibleMainColumns(payload.columns);
	const mainColumnIndex = new Map(mainColumns.map((column, index) => [column, index]));
	const nodesById = new Map(payload.nodes.map((node) => [node.id, node]));
	const effectiveIndexes = new Map(
		payload.nodes.map((node) => [
			node.id,
			mainColumnIndex.get(node.column) ?? mainColumns.length
		])
	);

	for (let step = 0; step < payload.nodes.length; step += 1) {
		let changed = false;
		for (const edge of payload.edges) {
			if (!nodesById.has(edge.source) || !nodesById.has(edge.target)) continue;
			const sourceIndex = effectiveIndexes.get(edge.source);
			const targetIndex = effectiveIndexes.get(edge.target);
			if (sourceIndex === undefined || targetIndex === undefined || targetIndex >= sourceIndex) {
				continue;
			}
			effectiveIndexes.set(edge.target, sourceIndex);
			changed = true;
		}
		if (!changed) break;
	}

	return new Map(
		payload.nodes.map((node) => {
			const index = effectiveIndexes.get(node.id) ?? mainColumns.length;
			return [node.id, mainColumns[index] ?? "other"];
		})
	);
}

function positionGroups(
	groups: GraphGroup[],
	positionedNodes: Map<string, PositionedNode>
): PositionedGroup[] {
	return groups.flatMap((group) => {
		const nodes = group.node_ids
			.map((nodeId) => positionedNodes.get(nodeId))
			.filter((node): node is PositionedNode => node !== undefined);
		if (nodes.length === 0) return [];
		const bounds = groupNodeBounds(nodes);
		return [
			{
				...group,
				x: bounds.x,
				y: bounds.y,
				width: bounds.width,
				height: bounds.height
			}
		];
	});
}

function groupNodeBounds(nodes: PositionedNode[]): {
	x: number;
	y: number;
	width: number;
	height: number;
} {
	const minX = Math.min(...nodes.map((node) => node.x));
	const minY = Math.min(...nodes.map((node) => node.y));
	const maxX = Math.max(...nodes.map((node) => node.x + node.width));
	const maxY = Math.max(...nodes.map((node) => node.y + node.height));
	return {
		x: minX - groupPaddingX,
		y: minY - groupPaddingTop,
		width: maxX - minX + groupPaddingX * 2,
		height: maxY - minY + groupPaddingTop + groupPaddingBottom
	};
}
