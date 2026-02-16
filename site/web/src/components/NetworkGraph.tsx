import { useEffect, useRef, useMemo, useState } from 'react';
import * as d3 from 'd3';

interface NetworkNode {
  id: string;
  name: string;
  slug: string;
  type: 'person' | 'entity';
  connections: number;
  finding_count?: number;
  entity_type?: string;
  jurisdiction?: string;
  // D3 simulation fields
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
  color?: string;
  baseColor?: string;
  val?: number;
}

interface NetworkEdge {
  source: string | NetworkNode;
  target: string | NetworkNode;
  relationship_type: string;
  description: string;
  strength: string;
  verified: boolean;
}

interface NetworkData {
  nodes: NetworkNode[];
  edges: NetworkEdge[];
  stats: {
    total_nodes: number;
    person_nodes: number;
    entity_nodes: number;
    total_edges: number;
  };
}

interface Props {
  data: NetworkData;
}

const EPSTEIN_ID = 'Jeffrey Epstein';

export default function NetworkGraph({ data }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const tooltipRef = useRef<d3.Selection<HTMLDivElement, unknown, HTMLElement, any> | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [densityFilter, setDensityFilter] = useState(30);
  const [debouncedDensity, setDebouncedDensity] = useState(30);
  const [showEntities, setShowEntities] = useState(false);

  // Debounce density filter — visual state updates immediately, computation uses debounced value
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedDensity(densityFilter), 300);
    return () => clearTimeout(timer);
  }, [densityFilter]);

  const graphData = useMemo(() => {
    // Filter nodes
    let filteredNodes = data.nodes.filter(n => {
      if (!showEntities && n.type === 'entity') return false;
      return true;
    });

    // Build adjacency and BFS from Epstein — hoist Set above filter
    const adjacency = new Map<string, Set<string>>();
    const filteredNodeIds = new Set(filteredNodes.map(n => n.id));
    const edgesForFiltered = data.edges.filter(e => {
      const sid = typeof e.source === 'string' ? e.source : e.source.id;
      const tid = typeof e.target === 'string' ? e.target : e.target.id;
      return filteredNodeIds.has(sid) && filteredNodeIds.has(tid);
    });

    edgesForFiltered.forEach(e => {
      const sid = typeof e.source === 'string' ? e.source : e.source.id;
      const tid = typeof e.target === 'string' ? e.target : e.target.id;
      if (!adjacency.has(sid)) adjacency.set(sid, new Set());
      if (!adjacency.has(tid)) adjacency.set(tid, new Set());
      adjacency.get(sid)!.add(tid);
      adjacency.get(tid)!.add(sid);
    });

    // BFS distances
    const distances = new Map<string, number>();
    const queue: string[] = [];
    if (filteredNodes.some(n => n.id === EPSTEIN_ID)) {
      distances.set(EPSTEIN_ID, 0);
      queue.push(EPSTEIN_ID);
    }
    while (queue.length > 0) {
      const current = queue.shift()!;
      const dist = distances.get(current)!;
      for (const neighbor of adjacency.get(current) || []) {
        if (!distances.has(neighbor)) {
          distances.set(neighbor, dist + 1);
          queue.push(neighbor);
        }
      }
    }

    // Density filtering: keep nodes with connections above threshold for their hop distance
    const connectionsByHop = new Map<number, number[]>();
    for (const node of filteredNodes) {
      const hop = distances.get(node.id) ?? Infinity;
      if (hop !== Infinity) {
        if (!connectionsByHop.has(hop)) connectionsByHop.set(hop, []);
        connectionsByHop.get(hop)!.push(node.connections);
      }
    }

    const avgByHop = new Map<number, number>();
    for (const [hop, conns] of connectionsByHop) {
      avgByHop.set(hop, conns.reduce((a, b) => a + b, 0) / conns.length);
    }

    const threshold = debouncedDensity / 100;
    const keepIds = new Set<string>();
    keepIds.add(EPSTEIN_ID);

    for (const node of filteredNodes) {
      const hop = distances.get(node.id) ?? Infinity;
      const avg = avgByHop.get(hop);
      if (avg !== undefined && node.connections >= avg * threshold) {
        keepIds.add(node.id);
      }
    }

    // Color nodes
    const directToEpstein = new Map<string, number>();
    edgesForFiltered.forEach(e => {
      const sid = typeof e.source === 'string' ? e.source : e.source.id;
      const tid = typeof e.target === 'string' ? e.target : e.target.id;
      if (sid === EPSTEIN_ID) directToEpstein.set(tid, (directToEpstein.get(tid) || 0) + 1);
      if (tid === EPSTEIN_ID) directToEpstein.set(sid, (directToEpstein.get(sid) || 0) + 1);
    });
    const maxDirect = Math.max(...Array.from(directToEpstein.values()), 1);

    const nodes = filteredNodes
      .filter(n => keepIds.has(n.id))
      .map(n => {
        const dist = distances.get(n.id) ?? Infinity;
        const direct = directToEpstein.get(n.id) || 0;
        let color: string;

        if (n.id === EPSTEIN_ID) {
          color = '#dc2626';
        } else if (n.type === 'entity') {
          color = '#8b5cf6'; // purple for entities
        } else if (direct > 0) {
          const ratio = direct / maxDirect;
          const hue = 45 - ratio * 30;
          color = `hsl(${hue}, 80%, 60%)`;
        } else if (dist <= 3) {
          color = 'hsl(270, 70%, 65%)';
        } else {
          color = 'hsl(120, 50%, 50%)';
        }

        return { ...n, val: n.connections, color, baseColor: color };
      });

    const nodeIds = new Set(nodes.map(n => n.id));
    const edges = edgesForFiltered.filter(e => {
      const sid = typeof e.source === 'string' ? e.source : e.source.id;
      const tid = typeof e.target === 'string' ? e.target : e.target.id;
      return nodeIds.has(sid) && nodeIds.has(tid);
    });

    return { nodes, edges };
  }, [data, debouncedDensity, showEntities]);

  useEffect(() => {
    if (!svgRef.current || graphData.nodes.length === 0) return;

    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;

    d3.select(svgRef.current).selectAll('*').remove();
    const svg = d3.select(svgRef.current);

    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.01, 10])
      .on('zoom', (event) => g.attr('transform', event.transform));

    const g = svg.append('g');

    const initialScale = 0.2;
    const initialTransform = d3.zoomIdentity
      .translate(width / 2, height / 2)
      .scale(initialScale)
      .translate(-width / 2, -height / 2);

    svg.call(zoom).call(zoom.transform as any, initialTransform);

    const maxConn = Math.max(...graphData.nodes.map(n => n.val || 1));
    const radiusScale = d3.scalePow()
      .exponent(0.5)
      .domain([1, maxConn])
      .range([5, 80])
      .clamp(true);

    const simulation = d3.forceSimulation(graphData.nodes as any)
      .alphaDecay(0.05)
      .alphaMin(0.01)
      .force('link', d3.forceLink(graphData.edges as any).id((d: any) => d.id).distance(50))
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius((d: any) => radiusScale(d.val || 1) + 5))
      .force('radial', d3.forceRadial(
        (d: any) => (50 - Math.min(d.val || 1, 50)) * 33 + 200,
        width / 2,
        height / 2,
      ).strength(0.2));

    const link = g.append('g')
      .selectAll('line')
      .data(graphData.edges)
      .join('line')
      .attr('stroke', '#4b5563')
      .attr('stroke-width', 1.5)
      .attr('stroke-opacity', 0.5);

    const node = g.append('g')
      .selectAll('g')
      .data(graphData.nodes)
      .join('g')
      .call(d3.drag<any, any>()
        .on('start', (event, d) => { d.fx = d.x; d.fy = d.y; })
        .on('drag', (event, d) => {
          d.fx = event.x; d.fy = event.y;
          if (!event.active) simulation.alphaTarget(0.3).restart();
        })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null; d.fy = null;
        }) as any);

    node.append('circle')
      .attr('r', (d: any) => radiusScale(d.val || 1))
      .attr('fill', (d: any) => d.color)
      .attr('stroke', '#fff')
      .attr('stroke-width', 0.5)
      .style('cursor', 'pointer')
      .on('click', (_event: any, d: any) => {
        setSelectedNode(prev => prev === d.id ? null : d.id);
      });

    node.append('text')
      .text((d: any) => d.name)
      .attr('x', 0)
      .attr('y', (d: any) => radiusScale(d.val || 1) * 1.4)
      .attr('text-anchor', 'middle')
      .attr('fill', '#d1d5db')
      .attr('font-size', '4px')
      .style('pointer-events', 'none');

    // Tooltip — reuse across renders via ref
    if (!tooltipRef.current) {
      tooltipRef.current = d3.select('body')
        .append('div')
        .style('position', 'absolute')
        .style('visibility', 'hidden')
        .style('background', 'rgba(0,0,0,0.9)')
        .style('color', 'white')
        .style('padding', '8px 12px')
        .style('border-radius', '6px')
        .style('font-size', '12px')
        .style('pointer-events', 'none')
        .style('z-index', '1000');
    }
    const tooltip = tooltipRef.current;
    tooltip.style('visibility', 'hidden');

    node.on('mouseover', (_event: any, d: any) => {
      tooltip.style('visibility', 'visible')
        .html(`<strong>${d.name}</strong><br/>${d.connections} connections${d.finding_count ? `<br/>${d.finding_count} findings` : ''}${d.type === 'entity' ? `<br/>${d.entity_type || ''} (${d.jurisdiction || '?'})` : ''}`);
    })
    .on('mousemove', (event: any) => {
      tooltip.style('top', (event.pageY - 10) + 'px').style('left', (event.pageX + 10) + 'px');
    })
    .on('mouseout', () => tooltip.style('visibility', 'hidden'));

    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y);
      node.attr('transform', (d: any) => `translate(${d.x},${d.y})`);
    });

    return () => {
      simulation.stop();
      // Tooltip lives in ref — hide but don't remove (reused across renders)
      tooltip.style('visibility', 'hidden');
    };
  }, [graphData]);

  // Update colors when selection changes
  useEffect(() => {
    const svg = d3.select(svgRef.current);
    svg.selectAll<SVGCircleElement, any>('circle')
      .attr('fill', (d: any) => selectedNode && d.id === selectedNode ? '#06b6d4' : d.baseColor);
    svg.selectAll<SVGLineElement, any>('line')
      .attr('stroke', (d: any) => {
        if (!selectedNode) return '#4b5563';
        const sid = typeof d.source === 'string' ? d.source : d.source.id;
        const tid = typeof d.target === 'string' ? d.target : d.target.id;
        return sid === selectedNode || tid === selectedNode ? '#06b6d4' : '#4b5563';
      })
      .attr('stroke-opacity', (d: any) => {
        if (!selectedNode) return 0.5;
        const sid = typeof d.source === 'string' ? d.source : d.source.id;
        const tid = typeof d.target === 'string' ? d.target : d.target.id;
        return sid === selectedNode || tid === selectedNode ? 1 : 0.2;
      });
  }, [selectedNode]);

  return (
    <div className="relative w-full h-full">
      {/* Controls */}
      <div className="absolute top-4 left-4 z-10 bg-gray-900/90 backdrop-blur-sm rounded-lg p-3 space-y-3 text-sm">
        <div>
          <label className="text-gray-400 text-xs block mb-1">Density Filter: {densityFilter}%</label>
          <input
            type="range"
            min={0}
            max={100}
            value={densityFilter}
            onChange={e => setDensityFilter(Number(e.target.value))}
            className="w-40"
          />
        </div>
        <label className="flex items-center gap-2 text-gray-400 text-xs cursor-pointer">
          <input
            type="checkbox"
            checked={showEntities}
            onChange={e => setShowEntities(e.target.checked)}
            className="rounded"
          />
          Show entities ({data.stats.entity_nodes})
        </label>
        <div className="text-xs text-gray-500">
          {graphData.nodes.length} nodes / {graphData.edges.length} edges
        </div>
      </div>

      {/* Selected node info */}
      {selectedNode && (
        <div className="absolute top-4 right-4 z-10 bg-gray-900/90 backdrop-blur-sm rounded-lg p-4 max-w-xs">
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-semibold text-white text-sm">{selectedNode}</h3>
            <button onClick={() => setSelectedNode(null)} className="text-gray-500 hover:text-gray-300 text-xs">close</button>
          </div>
          <a
            href={`/dossiers/${selectedNode.toLowerCase().replace(/\s+/g, '-').replace(/[.']/g, '')}`}
            className="text-xs text-blue-400 hover:text-blue-300"
          >
            View dossier →
          </a>
        </div>
      )}

      <svg ref={svgRef} className="w-full h-full bg-gray-950" />

      <div className="absolute bottom-0 left-0 right-0 bg-gray-900/50 backdrop-blur-sm px-4 py-2 text-xs text-gray-400 text-center">
        Click nodes to select · Scroll to zoom · Drag to pan
      </div>
    </div>
  );
}
