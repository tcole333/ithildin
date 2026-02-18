import { useEffect, useRef, useState, useMemo } from 'react';
import * as d3 from 'd3';
import { graphStratify, sugiyama, layeringSimplex, coordSimplex } from 'd3-dag';

// --- Interfaces ---

interface StructureNode {
  id: string;
  name: string;
  nodeType: 'person' | 'entity';
  entityType?: string;
  jurisdiction?: string;
  status?: string;
  parentIds: string[];
  x?: number;
  y?: number;
}

interface StructureEdge {
  source: string;
  target: string;
  relationType: string;
  description?: string;
}

interface StructureData {
  id: string;
  title: string;
  subtitle?: string;
  nodes: StructureNode[];
  edges: StructureEdge[];
}

interface Props {
  data: StructureData;
  height?: number;
}

// --- Design tokens (mirroring CSS custom properties for SVG use) ---

const C = {
  void: '#0b0d10',
  stone: '#12151b',
  slate: '#1c222b',
  ash: '#2a313b',
  mithril: '#8c97a3',
  moonlight: '#c7d0d9',
  icy: '#8fd3e8',
  ember: '#d1b36a',
} as const;

const FONT = {
  ui: '"Space Grotesk", sans-serif',
  mono: '"IBM Plex Mono", monospace',
} as const;

// --- Colors by jurisdiction ---

const jurisdictionColors: Record<string, string> = {
  USVI: C.ember,
  NY: C.icy,
  DE: '#7ea7c1',
  FL: '#8fa6b8',
  NM: '#9aa6b2',
  OH: C.mithril,
  UK: '#b7b1a3',
  person: C.moonlight,
};

function nodeColor(node: StructureNode): string {
  if (node.nodeType === 'person') return jurisdictionColors.person;
  if (node.jurisdiction && jurisdictionColors[node.jurisdiction]) {
    return jurisdictionColors[node.jurisdiction];
  }
  return '#a09c8a';
}

// --- Edge styles ---

type StrokeStyle = { dash: string; width: number; color: string; markerColor: string };

function edgeStyle(relationType: string): StrokeStyle {
  const rt = relationType.toLowerCase();
  if (['owns', 'controls', 'subsidiary'].includes(rt)) {
    return { dash: '', width: 2, color: C.moonlight, markerColor: 'moon' };
  }
  if (['funds', 'financial'].includes(rt)) {
    return { dash: '8 4', width: 2, color: C.ember, markerColor: 'ember' };
  }
  if (['trustee', 'beneficiary'].includes(rt)) {
    return { dash: '4 4', width: 1.5, color: C.icy, markerColor: 'icy' };
  }
  return { dash: '2 4', width: 1.5, color: C.mithril, markerColor: 'mithril' };
}

// --- Node dimensions ---

function nodeWidth(node: StructureNode): number {
  return Math.max(140, Math.min(200, node.name.length * 7.5 + 30));
}

function nodeHeight(node: StructureNode): number {
  return node.nodeType === 'person' ? 38 : 42;
}

/** Draw shape at (0,0) center. */
function drawNodeShape(
  g: d3.Selection<SVGGElement, unknown, null, undefined>,
  node: StructureNode,
  w: number,
  h: number,
) {
  const fill = nodeColor(node);
  const dissolved = node.status === 'dissolved';
  const opacity = dissolved ? 0.4 : 0.85;
  const strokeDash = dissolved ? '4 3' : '';
  const et = (node.entityType || '').toLowerCase();

  if (node.nodeType === 'person') {
    g.append('ellipse')
      .attr('rx', w / 2).attr('ry', h / 2)
      .attr('fill', fill).attr('fill-opacity', opacity)
      .attr('stroke', C.ash).attr('stroke-width', 1.2)
      .attr('stroke-dasharray', strokeDash);
  } else if (et === 'trust') {
    const pts = [
      [0, -h / 2], [w / 2, -h / 6], [w / 2, h / 2], [-w / 2, h / 2], [-w / 2, -h / 6],
    ];
    g.append('polygon')
      .attr('points', pts.map(p => p.join(',')).join(' '))
      .attr('fill', fill).attr('fill-opacity', opacity)
      .attr('stroke', C.ash).attr('stroke-width', 1.2)
      .attr('stroke-dasharray', strokeDash);
  } else if (['foundation', 'nonprofit'].includes(et)) {
    g.append('rect')
      .attr('x', -w / 2).attr('y', -h / 2).attr('width', w).attr('height', h)
      .attr('rx', 12)
      .attr('fill', fill).attr('fill-opacity', opacity)
      .attr('stroke', C.ash).attr('stroke-width', 1.2)
      .attr('stroke-dasharray', strokeDash);
  } else if (['fund', 'partnership'].includes(et)) {
    const skew = 10;
    const pts = [
      [-w / 2 + skew, -h / 2], [w / 2 + skew, -h / 2],
      [w / 2 - skew, h / 2], [-w / 2 - skew, h / 2],
    ];
    g.append('polygon')
      .attr('points', pts.map(p => p.join(',')).join(' '))
      .attr('fill', fill).attr('fill-opacity', opacity)
      .attr('stroke', C.ash).attr('stroke-width', 1.2)
      .attr('stroke-dasharray', strokeDash);
  } else if (['llc', 'inc', 'ltd', 'company'].includes(et)) {
    g.append('rect')
      .attr('x', -w / 2).attr('y', -h / 2).attr('width', w).attr('height', h)
      .attr('rx', 3)
      .attr('fill', fill).attr('fill-opacity', opacity)
      .attr('stroke', C.ash).attr('stroke-width', 1.2)
      .attr('stroke-dasharray', strokeDash);
  } else {
    g.append('rect')
      .attr('x', -w / 2).attr('y', -h / 2).attr('width', w).attr('height', h)
      .attr('rx', 3)
      .attr('fill', fill).attr('fill-opacity', opacity)
      .attr('stroke', C.ash).attr('stroke-width', 1.2)
      .attr('stroke-dasharray', '4 3');
  }
}

// --- Legend data ---

const shapeEntries = [
  { label: 'Person', type: 'person' },
  { label: 'LLC / Inc', type: 'inc' },
  { label: 'Trust', type: 'trust' },
  { label: 'Foundation', type: 'foundation' },
  { label: 'Fund', type: 'fund' },
];

const jurisdictionEntries = [
  { label: 'USVI', color: C.ember },
  { label: 'NY', color: C.icy },
  { label: 'DE', color: '#7ea7c1' },
  { label: 'FL', color: '#8fa6b8' },
  { label: 'Offshore', color: '#a09c8a' },
];

const edgeEntries = [
  { label: 'Owns / Controls', dash: '', color: C.moonlight },
  { label: 'Funds', dash: '6 3', color: C.ember },
  { label: 'Trustee / Beneficiary', dash: '3 3', color: C.icy },
  { label: 'Officer / Director', dash: '2 3', color: C.mithril },
];

// --- Component ---

export default function CorporateStructure({ data, height = 600 }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(0);
  const [collapsedSet, setCollapsedSet] = useState<Set<string>>(new Set());
  const [highlightedIds, setHighlightedIds] = useState<Set<string> | null>(null);

  // Responsive width
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const update = () => {
      const rect = container.getBoundingClientRect();
      if (rect.width) setContainerWidth(Math.floor(rect.width));
    };
    update();
    if (typeof ResizeObserver !== 'undefined') {
      const obs = new ResizeObserver(update);
      obs.observe(container);
      return () => obs.disconnect();
    }
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, []);

  // Compute visible nodes/edges after collapsing subtrees
  const { visibleNodes, visibleEdges, childCounts } = useMemo(() => {
    const childrenOf = new Map<string, string[]>();
    for (const n of data.nodes) {
      for (const pid of n.parentIds) {
        if (!childrenOf.has(pid)) childrenOf.set(pid, []);
        childrenOf.get(pid)!.push(n.id);
      }
    }

    const hidden = new Set<string>();
    for (const cid of collapsedSet) {
      const queue = [...(childrenOf.get(cid) || [])];
      for (const q of queue) {
        if (!hidden.has(q)) {
          hidden.add(q);
          for (const ch of childrenOf.get(q) || []) queue.push(ch);
        }
      }
    }

    const counts = new Map<string, number>();
    for (const [pid, ch] of childrenOf.entries()) {
      counts.set(pid, ch.length);
    }

    const vNodes = data.nodes.filter(n => !hidden.has(n.id));
    const nodeIds = new Set(vNodes.map(n => n.id));
    const filteredNodes = vNodes.map(n => ({
      ...n,
      parentIds: n.parentIds.filter(pid => nodeIds.has(pid)),
    }));
    const vEdges = data.edges.filter(e => nodeIds.has(e.source) && nodeIds.has(e.target));

    return { visibleNodes: filteredNodes, visibleEdges: vEdges, childCounts: counts };
  }, [data, collapsedSet]);

  // Edge lookup for styling
  const edgeLookup = useMemo(() => {
    const map = new Map<string, StructureEdge>();
    for (const e of visibleEdges) {
      map.set(`${e.source}|${e.target}`, e);
    }
    return map;
  }, [visibleEdges]);

  // Ancestor/descendant maps for click highlighting
  const { ancestors, descendants } = useMemo(() => {
    const anc = new Map<string, Set<string>>();
    const desc = new Map<string, Set<string>>();
    const parentMap = new Map<string, string[]>();
    const childMap = new Map<string, string[]>();
    for (const n of visibleNodes) {
      parentMap.set(n.id, n.parentIds);
      for (const pid of n.parentIds) {
        if (!childMap.has(pid)) childMap.set(pid, []);
        childMap.get(pid)!.push(n.id);
      }
    }

    function getAncestors(id: string, visited: Set<string>): Set<string> {
      if (anc.has(id)) return anc.get(id)!;
      const result = new Set<string>();
      for (const pid of parentMap.get(id) || []) {
        if (visited.has(pid)) continue;
        visited.add(pid);
        result.add(pid);
        for (const a of getAncestors(pid, visited)) result.add(a);
      }
      anc.set(id, result);
      return result;
    }

    function getDescendants(id: string, visited: Set<string>): Set<string> {
      if (desc.has(id)) return desc.get(id)!;
      const result = new Set<string>();
      for (const cid of childMap.get(id) || []) {
        if (visited.has(cid)) continue;
        visited.add(cid);
        result.add(cid);
        for (const d of getDescendants(cid, visited)) result.add(d);
      }
      desc.set(id, result);
      return result;
    }

    for (const n of visibleNodes) {
      getAncestors(n.id, new Set([n.id]));
      getDescendants(n.id, new Set([n.id]));
    }

    return { ancestors: anc, descendants: desc };
  }, [visibleNodes]);

  // Main render
  useEffect(() => {
    if (!svgRef.current || visibleNodes.length === 0 || !containerWidth) return;

    // Build DAG
    let dag;
    try {
      const builder = graphStratify()
        .id((d: StructureNode) => d.id)
        .parentIds((d: StructureNode) => d.parentIds);
      dag = builder(visibleNodes);
    } catch (err) {
      console.error('[CorporateStructure] graphStratify failed:', err);
      return;
    }

    // Layout
    const layout = sugiyama()
      .nodeSize((node: any) => {
        const d: StructureNode = node.data;
        return [nodeWidth(d) + 40, nodeHeight(d) + 60];
      })
      .gap([40, 60])
      .layering(layeringSimplex())
      .coord(coordSimplex());

    let layoutW: number, layoutH: number;
    try {
      const result = layout(dag);
      layoutW = result.width;
      layoutH = result.height;
    } catch (err) {
      console.error('[CorporateStructure] sugiyama layout failed:', err);
      return;
    }

    // Build a position map from dag nodes for reliable edge drawing
    const posMap = new Map<string, { x: number; y: number }>();
    for (const dagNode of dag.nodes()) {
      posMap.set(dagNode.data.id, { x: dagNode.x!, y: dagNode.y! });
    }

    // Viewport: fit content width to container, derive height proportionally
    const pad = 40;
    const totalW = layoutW + pad * 2;
    const totalH = layoutH + pad * 2;

    // Scale so layout width fills container, then compute pixel height from that
    const fitScale = containerWidth / totalW;
    const svgH = Math.max(300, Math.min(height, Math.ceil(totalH * fitScale) + 10));

    const svgEl = d3.select(svgRef.current);
    svgEl.selectAll('*').remove();
    svgEl
      .attr('width', containerWidth)
      .attr('height', svgH);

    // Zoom group
    const g = svgEl.append('g');

    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.15, 4])
      .on('zoom', (event) => g.attr('transform', event.transform));
    svgEl.call(zoom);

    // Initial transform: center content in SVG pixel space
    const tx = (containerWidth - totalW * fitScale) / 2;
    const ty = (svgH - totalH * fitScale) / 2;
    svgEl.call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(fitScale));

    // Arrow marker defs
    const defs = svgEl.append('defs');
    const markerDefs = [
      { id: 'arr-moon', color: C.moonlight },
      { id: 'arr-ember', color: C.ember },
      { id: 'arr-icy', color: C.icy },
      { id: 'arr-mithril', color: C.mithril },
    ];
    for (const { id, color } of markerDefs) {
      defs.append('marker')
        .attr('id', id)
        .attr('viewBox', '0 0 10 7')
        .attr('refX', 9).attr('refY', 3.5)
        .attr('markerWidth', 9).attr('markerHeight', 7)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,0.5 L9,3.5 L0,6.5 Z')
        .attr('fill', color);
    }

    function markerFor(mc: string) { return `url(#arr-${mc})`; }

    // Tooltip
    const tooltip = d3.select('body')
      .append('div')
      .style('position', 'absolute')
      .style('visibility', 'hidden')
      .style('background', C.stone)
      .style('color', C.moonlight)
      .style('border', `1px solid ${C.ash}`)
      .style('padding', '8px 12px')
      .style('border-radius', '4px')
      .style('font-family', FONT.ui)
      .style('font-size', '12px')
      .style('line-height', '1.5')
      .style('max-width', '300px')
      .style('pointer-events', 'none')
      .style('z-index', '1000')
      .style('box-shadow', '0 6px 18px rgba(0,0,0,0.45)');

    // --- Draw edges using node positions directly ---
    const edgeGroup = g.append('g');

    for (const link of dag.links()) {
      const sourceId: string = link.source.data.id;
      const targetId: string = link.target.data.id;
      const edgeData = edgeLookup.get(`${sourceId}|${targetId}`);
      const rt = edgeData?.relationType || 'unknown';
      const style = edgeStyle(rt);

      const src = posMap.get(sourceId)!;
      const tgt = posMap.get(targetId)!;

      // Source node bottom edge, target node top edge
      const srcNode = visibleNodes.find(n => n.id === sourceId)!;
      const tgtNode = visibleNodes.find(n => n.id === targetId)!;
      const srcH = nodeHeight(srcNode) / 2;
      const tgtH = nodeHeight(tgtNode) / 2;

      const x1 = src.x + pad;
      const y1 = src.y + srcH + pad;
      const x2 = tgt.x + pad;
      const y2 = tgt.y - tgtH + pad;

      const dimmed = highlightedIds && (!highlightedIds.has(sourceId) || !highlightedIds.has(targetId));

      // Curved path: vertical drop from source, horizontal shift, vertical drop to target
      const midY = (y1 + y2) / 2;
      const pathD = `M${x1},${y1} C${x1},${midY} ${x2},${midY} ${x2},${y2}`;

      edgeGroup.append('path')
        .attr('d', pathD)
        .attr('fill', 'none')
        .attr('stroke', style.color)
        .attr('stroke-width', style.width)
        .attr('stroke-dasharray', style.dash || 'none')
        .attr('stroke-opacity', dimmed ? 0.06 : 0.75)
        .attr('marker-end', markerFor(style.markerColor))
        .style('transition', 'stroke-opacity 0.2s ease')
        .on('mouseover', function (event: any) {
          d3.select(this).attr('stroke-opacity', 1).attr('stroke-width', style.width + 1);
          const label = edgeData?.description || rt;
          tooltip.style('visibility', 'visible')
            .html(`<span style="color:${style.color};font-weight:600">${rt}</span><br/>${label}`);
        })
        .on('mousemove', (event: any) => {
          tooltip.style('top', (event.pageY - 10) + 'px').style('left', (event.pageX + 14) + 'px');
        })
        .on('mouseout', function () {
          d3.select(this).attr('stroke-opacity', dimmed ? 0.06 : 0.75).attr('stroke-width', style.width);
          tooltip.style('visibility', 'hidden');
        });

      // Edge label at midpoint (relation type, small)
      const labelX = (x1 + x2) / 2;
      const labelY = midY;
      if (Math.abs(x1 - x2) > 20 || Math.abs(y1 - y2) > 40) {
        edgeGroup.append('text')
          .attr('x', labelX)
          .attr('y', labelY)
          .attr('text-anchor', 'middle')
          .attr('dominant-baseline', 'central')
          .attr('fill', style.color)
          .attr('fill-opacity', dimmed ? 0.06 : 0.5)
          .attr('font-size', '8px')
          .attr('font-family', FONT.mono)
          .attr('letter-spacing', '0.06em')
          .style('paint-order', 'stroke')
          .style('stroke', C.void)
          .style('stroke-width', '3px')
          .style('stroke-linejoin', 'round')
          .style('pointer-events', 'none')
          .text(rt);
      }
    }

    // --- Draw nodes ---
    const nodeGroup = g.append('g');

    for (const dagNode of dag.nodes()) {
      const d: StructureNode = dagNode.data;
      const x = dagNode.x! + pad;
      const y = dagNode.y! + pad;
      const w = nodeWidth(d);
      const h = nodeHeight(d);
      const dimmed = highlightedIds && !highlightedIds.has(d.id);

      const nodeG = nodeGroup.append('g')
        .attr('transform', `translate(${x},${y})`)
        .attr('opacity', dimmed ? 0.12 : 1)
        .style('cursor', 'pointer')
        .style('transition', 'opacity 0.2s ease');

      drawNodeShape(nodeG as any, d, w, h);

      // Name label
      const displayName = d.name.length > 22 ? d.name.slice(0, 20) + '\u2026' : d.name;
      nodeG.append('text')
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'central')
        .attr('fill', C.void)
        .attr('font-size', '11px')
        .attr('font-family', FONT.ui)
        .attr('font-weight', '500')
        .attr('letter-spacing', '0.01em')
        .style('pointer-events', 'none')
        .text(displayName);

      // Sub-label: entity type + jurisdiction
      if (d.nodeType === 'entity') {
        const subLabel = [d.entityType?.toUpperCase(), d.jurisdiction].filter(Boolean).join(' \u00b7 ');
        if (subLabel) {
          nodeG.append('text')
            .attr('y', h / 2 + 14)
            .attr('text-anchor', 'middle')
            .attr('fill', C.mithril)
            .attr('font-size', '8.5px')
            .attr('font-family', FONT.mono)
            .attr('letter-spacing', '0.08em')
            .style('pointer-events', 'none')
            .text(subLabel);
        }
      }

      // Collapse indicator
      const numChildren = childCounts.get(d.id) || 0;
      if (numChildren > 0) {
        const isCollapsed = collapsedSet.has(d.id);
        const indicator = nodeG.append('g')
          .attr('transform', `translate(${w / 2 - 2}, ${-h / 2 + 2})`)
          .style('cursor', 'pointer');

        indicator.append('circle')
          .attr('r', 7)
          .attr('fill', C.slate)
          .attr('stroke', C.ash)
          .attr('stroke-width', 1);

        indicator.append('text')
          .attr('text-anchor', 'middle')
          .attr('dominant-baseline', 'central')
          .attr('fill', C.moonlight)
          .attr('font-size', '10px')
          .attr('font-family', FONT.ui)
          .attr('font-weight', '700')
          .style('pointer-events', 'none')
          .text(isCollapsed ? '+' : '\u2212');

        indicator.on('click', (event: MouseEvent) => {
          event.stopPropagation();
          setCollapsedSet(prev => {
            const next = new Set(prev);
            if (next.has(d.id)) next.delete(d.id);
            else next.add(d.id);
            return next;
          });
        });
      }

      // Hover
      nodeG.on('mouseover', (event: MouseEvent) => {
        const lines = [`<strong>${d.name}</strong>`];
        if (d.nodeType === 'entity') {
          if (d.entityType) lines.push(`Type: ${d.entityType}`);
          if (d.jurisdiction) lines.push(`Jurisdiction: ${d.jurisdiction}`);
          if (d.status && d.status !== 'active') lines.push(`Status: ${d.status}`);
        }
        const connected = visibleEdges.filter(e => e.source === d.id || e.target === d.id);
        for (const e of connected.slice(0, 4)) {
          const dir = e.source === d.id ? '\u2192' : '\u2190';
          const other = e.source === d.id ? e.target : e.source;
          const otherName = visibleNodes.find(n => n.id === other)?.name || other;
          lines.push(`<span style="color:${C.mithril};font-size:11px">${dir} ${otherName} <em>(${e.relationType})</em></span>`);
        }
        if (connected.length > 4) {
          lines.push(`<span style="color:${C.mithril};font-size:11px">+${connected.length - 4} more</span>`);
        }
        tooltip.style('visibility', 'visible').html(lines.join('<br/>'));
      })
        .on('mousemove', (event: MouseEvent) => {
          tooltip.style('top', (event.pageY - 10) + 'px').style('left', (event.pageX + 14) + 'px');
        })
        .on('mouseout', () => tooltip.style('visibility', 'hidden'));

      // Click to highlight chain
      nodeG.on('click', () => {
        if (highlightedIds?.has(d.id) && highlightedIds.size > 1) {
          setHighlightedIds(null);
          return;
        }
        const anc = ancestors.get(d.id) || new Set();
        const desc = descendants.get(d.id) || new Set();
        setHighlightedIds(new Set([d.id, ...anc, ...desc]));
      });
    }

    return () => { tooltip.remove(); };
  }, [visibleNodes, visibleEdges, edgeLookup, containerWidth, height, collapsedSet, highlightedIds, childCounts, ancestors, descendants]);

  return (
    <div ref={containerRef} className="surface p-5">
      <div className="mb-4">
        <h3 className="text-lg text-moon" style={{ fontFamily: 'var(--font-ui)', fontWeight: 600 }}>
          {data.title}
        </h3>
        {data.subtitle && (
          <p className="text-sm text-mithril mt-1" style={{ fontFamily: 'var(--font-body)' }}>
            {data.subtitle}
          </p>
        )}
      </div>
      <svg ref={svgRef} className="w-full graph-canvas" style={{ minHeight: '300px', maxHeight: `${height}px`, borderRadius: '4px' }} />

      {/* Legend */}
      <div className="mt-4 pt-3 flex flex-wrap gap-6" style={{ borderTop: `1px solid ${C.ash}`, fontFamily: 'var(--font-ui)' }}>
        <div>
          <div className="text-moon mb-1.5" style={{ fontSize: '0.65rem', letterSpacing: '0.2em', textTransform: 'uppercase', fontWeight: 500 }}>
            Entity Shapes
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-mithril">
            {shapeEntries.map(s => (
              <div key={s.type} className="flex items-center gap-1.5">
                <svg width="18" height="14" viewBox="0 0 18 14">
                  {s.type === 'person' ? (
                    <ellipse cx="9" cy="7" rx="8" ry="6" fill={C.moonlight} fillOpacity={0.7} stroke={C.ash} strokeWidth={0.8} />
                  ) : s.type === 'trust' ? (
                    <polygon points="9,1 17,5 17,13 1,13 1,5" fill={C.ember} fillOpacity={0.7} stroke={C.ash} strokeWidth={0.8} />
                  ) : s.type === 'foundation' ? (
                    <rect x="1" y="1" width="16" height="12" rx="5" fill="#9aa6b2" fillOpacity={0.7} stroke={C.ash} strokeWidth={0.8} />
                  ) : s.type === 'fund' ? (
                    <polygon points="4,1 17,1 14,13 1,13" fill="#8fa6b8" fillOpacity={0.7} stroke={C.ash} strokeWidth={0.8} />
                  ) : (
                    <rect x="1" y="1" width="16" height="12" rx="2" fill="#7ea7c1" fillOpacity={0.7} stroke={C.ash} strokeWidth={0.8} />
                  )}
                </svg>
                <span>{s.label}</span>
              </div>
            ))}
          </div>
        </div>
        <div>
          <div className="text-moon mb-1.5" style={{ fontSize: '0.65rem', letterSpacing: '0.2em', textTransform: 'uppercase', fontWeight: 500 }}>
            Jurisdiction
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-mithril">
            {jurisdictionEntries.map(j => (
              <div key={j.label} className="flex items-center gap-1.5">
                <span className="inline-block w-3 h-3 rounded-sm" style={{ background: j.color, opacity: 0.8 }} />
                <span>{j.label}</span>
              </div>
            ))}
          </div>
        </div>
        <div>
          <div className="text-moon mb-1.5" style={{ fontSize: '0.65rem', letterSpacing: '0.2em', textTransform: 'uppercase', fontWeight: 500 }}>
            Relationships
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-mithril">
            {edgeEntries.map(e => (
              <div key={e.label} className="flex items-center gap-1.5">
                <svg width="26" height="8" viewBox="0 0 26 8">
                  <line x1="0" y1="4" x2="20" y2="4" stroke={e.color} strokeWidth={2} strokeDasharray={e.dash} />
                  <polygon points="20,1 26,4 20,7" fill={e.color} />
                </svg>
                <span>{e.label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {highlightedIds && (
        <button
          onClick={() => setHighlightedIds(null)}
          className="mt-2 text-icy transition-colors"
          style={{ fontSize: '0.7rem', letterSpacing: '0.12em', textTransform: 'uppercase', fontFamily: 'var(--font-ui)' }}
        >
          Clear highlight
        </button>
      )}
    </div>
  );
}
