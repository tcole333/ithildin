import { useEffect, useRef, useState, useMemo } from 'react';
import * as d3 from 'd3';

interface Connection {
  target: string;
  type: string;
  strength: number;
  evidence_ref?: string;
  description?: string;
}

interface EgoNode {
  id: string;
  name?: string;
  type?: 'person' | 'entity';
  connections?: Connection[];
}

interface Props {
  center: string;
  connections: Connection[];
  secondHop?: Record<string, Connection[]>;
  depth?: 1 | 2;
  height?: number;
}

const RELATIONSHIP_COLORS: Record<string, string> = {
  financial: '#d1b36a',
  legal: '#b7b1a3',
  employment: '#8fa6b8',
  social: '#8fd3e8',
  corporate: '#7ea7c1',
  intelligence: '#a09c8a',
  advisory: '#9aa6b2',
};

const COLORS = {
  center: '#8fd3e8',
  firstHop: '#c7d0d9',
  secondHop: '#8c97a3',
  highlight: '#8fd3e8',
  edge: '#2a313b',
  text: '#c7d0d9',
  muted: '#8c97a3',
  panelBg: '#12151b',
  panelBorder: '#2a313b',
  void: '#0b0d10',
};

function relationshipColor(type: string): string {
  return RELATIONSHIP_COLORS[type] || '#6b7280';
}

export default function EgoNetwork({ center, connections, secondHop = {}, depth = 1, height = 500 }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const update = () => {
      const rect = container.getBoundingClientRect();
      const w = Math.floor(rect.width);
      if (w) setWidth(w);
    };

    update();

    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', update);
      return () => window.removeEventListener('resize', update);
    }

    const observer = new ResizeObserver(update);
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  const graph = useMemo(() => {
    const nodeMap = new Map<string, { id: string; hop: number; connectionCount: number }>();
    const edges: { source: string; target: string; type: string; strength: number; evidence_ref?: string; description?: string }[] = [];

    nodeMap.set(center, { id: center, hop: 0, connectionCount: connections.length });

    // First hop - limit to top 30 by strength
    const sorted1 = [...connections].sort((a, b) => b.strength - a.strength).slice(0, 30);
    for (const c of sorted1) {
      if (!nodeMap.has(c.target)) {
        nodeMap.set(c.target, { id: c.target, hop: 1, connectionCount: 0 });
      }
      edges.push({ source: center, target: c.target, type: c.type, strength: c.strength, evidence_ref: c.evidence_ref, description: c.description });
    }

    // Second hop
    if (depth === 2) {
      const firstHopIds = new Set(sorted1.map(c => c.target));
      let secondHopBudget = Math.max(0, 30 - nodeMap.size);

      for (const [sourceId, conns] of Object.entries(secondHop)) {
        if (!firstHopIds.has(sourceId) || secondHopBudget <= 0) continue;
        const sorted2 = [...conns]
          .filter(c => c.target !== center && !firstHopIds.has(c.target))
          .sort((a, b) => b.strength - a.strength)
          .slice(0, 3);

        for (const c of sorted2) {
          if (secondHopBudget <= 0) break;
          if (!nodeMap.has(c.target)) {
            nodeMap.set(c.target, { id: c.target, hop: 2, connectionCount: 0 });
            secondHopBudget--;
          }
          edges.push({ source: sourceId, target: c.target, type: c.type, strength: c.strength, evidence_ref: c.evidence_ref, description: c.description });
        }
      }
    }

    // Count connections per node
    for (const e of edges) {
      const sn = nodeMap.get(e.source);
      const tn = nodeMap.get(e.target);
      if (sn) sn.connectionCount++;
      if (tn) tn.connectionCount++;
    }

    return {
      nodes: Array.from(nodeMap.values()),
      edges,
    };
  }, [center, connections, secondHop, depth]);

  useEffect(() => {
    if (!svgRef.current || graph.nodes.length === 0 || !width) return;
    const h = height;

    d3.select(svgRef.current).selectAll('*').remove();
    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', h)
      .attr('viewBox', `0 0 ${width} ${h}`);

    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 5])
      .on('zoom', (event) => g.attr('transform', event.transform));

    const g = svg.append('g');
    svg.call(zoom as any);

    // Radial gradient for subtle center focus
    const defs = svg.append('defs');
    const gradient = defs.append('radialGradient')
      .attr('id', 'ego-bg-glow')
      .attr('cx', '50%').attr('cy', '50%').attr('r', '50%');
    gradient.append('stop').attr('offset', '0%').attr('stop-color', 'rgba(143,211,232,0.06)');
    gradient.append('stop').attr('offset', '100%').attr('stop-color', 'rgba(0,0,0,0)');
    g.append('rect').attr('width', width).attr('height', h).attr('fill', 'url(#ego-bg-glow)');

    const maxConn = Math.max(...graph.nodes.map(n => n.connectionCount));
    const radiusScale = d3.scaleSqrt().domain([0, maxConn]).range([8, 32]).clamp(true);

    const nodes = graph.nodes.map(n => ({ ...n }));
    const edges = graph.edges.map(e => ({ ...e }));

    const simulation = d3.forceSimulation(nodes as any)
      .alphaDecay(0.06)
      .force('link', d3.forceLink(edges as any).id((d: any) => d.id).distance((d: any) => 80 / Math.max(d.strength, 0.3)))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, h / 2))
      .force('collision', d3.forceCollide().radius((d: any) => radiusScale(d.connectionCount) + 8));

    // Edges
    const link = g.append('g')
      .selectAll('line')
      .data(edges)
      .join('line')
      .attr('stroke', d => relationshipColor(d.type))
      .attr('stroke-width', d => Math.max(1.5, d.strength * 3))
      .attr('stroke-opacity', 0.65);

    // Nodes
    const node = g.append('g')
      .selectAll('g')
      .data(nodes)
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
      .attr('r', (d: any) => d.id === center ? radiusScale(d.connectionCount) * 1.2 : radiusScale(d.connectionCount))
      .attr('fill', (d: any) => d.hop === 0 ? COLORS.center : d.hop === 1 ? COLORS.firstHop : COLORS.secondHop)
      .attr('stroke', (d: any) => d.hop === 0 ? COLORS.center : COLORS.text)
      .attr('stroke-width', (d: any) => d.hop === 0 ? 2 : 1)
      .style('cursor', 'pointer');

    // Labels
    const labels = g.append('g')
      .selectAll('text')
      .data(nodes)
      .join('text')
      .text((d: any) => {
        const name = d.id;
        return name.length > 20 ? name.slice(0, 18) + '...' : name;
      })
      .attr('text-anchor', 'middle')
      .attr('fill', COLORS.text)
      .attr('font-size', (d: any) => d.hop === 0 ? '12px' : '10px')
      .attr('font-weight', (d: any) => d.hop === 0 ? '600' : '400')
      .style('paint-order', 'stroke')
      .style('stroke', COLORS.void)
      .style('stroke-width', '3px')
      .style('stroke-linejoin', 'round')
      .style('pointer-events', 'none');

    // Tooltip
    const tooltip = d3.select('body')
      .append('div')
      .style('position', 'absolute')
      .style('visibility', 'hidden')
      .style('background', COLORS.panelBg)
      .style('color', COLORS.text)
      .style('border', `1px solid ${COLORS.panelBorder}`)
      .style('padding', '8px 12px')
      .style('border-radius', '6px')
      .style('font-size', '12px')
      .style('pointer-events', 'none')
      .style('z-index', '1000')
      .style('max-width', '280px');

    // Hover behavior: highlight connected subgraph
    const adjacency = new Map<string, Set<string>>();
    edges.forEach(e => {
      const s = typeof e.source === 'string' ? e.source : (e.source as any).id;
      const t = typeof e.target === 'string' ? e.target : (e.target as any).id;
      if (!adjacency.has(s)) adjacency.set(s, new Set());
      if (!adjacency.has(t)) adjacency.set(t, new Set());
      adjacency.get(s)!.add(t);
      adjacency.get(t)!.add(s);
    });

    node.on('mouseover', (_event: any, d: any) => {
      const connected = adjacency.get(d.id) || new Set();
      node.selectAll('circle')
        .attr('opacity', (n: any) => {
          if (n.id === d.id) return 1;
          if (connected.has(n.id)) return 1;
          return 0.2;
        });
      link.attr('stroke-opacity', (e: any) => {
        const s = typeof e.source === 'string' ? e.source : e.source.id;
        const t = typeof e.target === 'string' ? e.target : e.target.id;
        return s === d.id || t === d.id ? 0.9 : 0.1;
      });
      labels.attr('fill-opacity', (n: any) => {
        if (n.id === d.id || connected.has(n.id)) return 1;
        return 0.2;
      });
      tooltip.style('visibility', 'visible')
        .html(`<strong>${d.id}</strong><br/>${d.connectionCount} connections<br/>Hop: ${d.hop}`);
    })
      .on('mousemove', (event: any) => {
        tooltip.style('top', (event.pageY - 10) + 'px').style('left', (event.pageX + 10) + 'px');
      })
      .on('mouseout', () => {
        node.selectAll('circle').attr('opacity', 1);
        link.attr('stroke-opacity', 0.65);
        labels.attr('fill-opacity', 1);
        tooltip.style('visibility', 'hidden');
      });

    link.on('mouseover', function (_event: any, d: any) {
      d3.select(this).attr('stroke-opacity', 0.8);
      const s = typeof d.source === 'string' ? d.source : d.source.id;
      const t = typeof d.target === 'string' ? d.target : d.target.id;
      tooltip.style('visibility', 'visible')
        .html([
          `<strong>${s} &rarr; ${t}</strong>`,
          `Type: ${d.type}`,
          `Strength: ${d.strength}`,
          d.description || '',
          d.evidence_ref ? `Ref: ${d.evidence_ref}` : '',
        ].filter(Boolean).join('<br/>'));
    })
      .on('mousemove', (event: any) => {
        tooltip.style('top', (event.pageY - 10) + 'px').style('left', (event.pageX + 10) + 'px');
      })
      .on('mouseout', function () {
        d3.select(this).attr('stroke-opacity', 0.35);
        tooltip.style('visibility', 'hidden');
      });

    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y);
      node.attr('transform', (d: any) => `translate(${d.x},${d.y})`);
      labels
        .attr('x', (d: any) => d.x)
        .attr('y', (d: any) => d.y + radiusScale(d.connectionCount) + 12);
    });

    return () => {
      simulation.stop();
      tooltip.remove();
    };
  }, [graph, width, height, center]);

  const typeLegend = Object.entries(RELATIONSHIP_COLORS);

  return (
    <div ref={containerRef} className="surface p-4">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-lg font-semibold text-moon">{center}</h3>
          <div className="text-xs text-mithril font-mono mt-1">
            {graph.nodes.length} nodes &middot; {graph.edges.length} edges &middot; {depth === 2 ? '2-hop' : '1-hop'}
          </div>
        </div>
        <div className="flex flex-wrap gap-3">
          {typeLegend.map(([type, color]) => (
            <div key={type} className="flex items-center gap-1.5 text-xs text-mithril">
              <span className="inline-block w-3 h-0.5" style={{ background: color }} />
              {type}
            </div>
          ))}
        </div>
      </div>
      <svg ref={svgRef} className="w-full graph-canvas" style={{ height: `${height}px` }} />
    </div>
  );
}
