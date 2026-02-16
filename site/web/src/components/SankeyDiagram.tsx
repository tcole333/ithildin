import { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import { sankey, sankeyLinkHorizontal, sankeyCenter } from 'd3-sankey';

interface FlowNode {
  id: string;
  name: string;
  category?: string;
}

interface FlowLink {
  source: string;
  target: string;
  value: number;
  label?: string;
}

interface FlowData {
  title: string;
  subtitle?: string;
  nodes: FlowNode[];
  links: FlowLink[];
}

interface Props {
  data: FlowData;
  height?: number;
}

const categoryColors: Record<string, string> = {
  person: '#3b82f6',
  trust: '#8b5cf6',
  entity: '#06b6d4',
  company: '#10b981',
  property: '#f59e0b',
  nonprofit: '#ec4899',
};

function formatAmount(value: number): string {
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  if (value <= 1) return ''; // non-monetary links
  return `$${value.toLocaleString()}`;
}

export default function SankeyDiagram({ data, height = 500 }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || data.nodes.length === 0) return;

    const width = svgRef.current.clientWidth;
    const margin = { top: 20, right: 160, bottom: 20, left: 160 };

    d3.select(svgRef.current).selectAll('*').remove();
    const svg = d3.select(svgRef.current)
      .attr('viewBox', `0 0 ${width} ${height}`);

    // Build node index and filter links to only reference existing nodes
    const nodeIds = new Set(data.nodes.map(n => n.id));
    const validLinks = data.links.filter(l => nodeIds.has(l.source) && nodeIds.has(l.target));

    if (validLinks.length === 0) return;

    // Create sankey layout
    const sankeyLayout = sankey()
      .nodeId((d: any) => d.id)
      .nodeWidth(20)
      .nodePadding(16)
      .nodeAlign(sankeyCenter)
      .extent([[margin.left, margin.top], [width - margin.right, height - margin.bottom]]);

    const sankeyData = sankeyLayout({
      nodes: data.nodes.map(d => ({ ...d })),
      links: validLinks.map(d => ({
        source: d.source,
        target: d.target,
        value: Math.max(d.value, 1),
        label: d.label,
      })),
    } as any);

    // Links
    const linkGroup = svg.append('g').attr('fill', 'none');

    linkGroup.selectAll('path')
      .data(sankeyData.links)
      .join('path')
      .attr('d', sankeyLinkHorizontal())
      .attr('stroke', (d: any) => {
        const sourceNode = d.source as any;
        return categoryColors[sourceNode.category] || '#6b7280';
      })
      .attr('stroke-opacity', 0.3)
      .attr('stroke-width', (d: any) => Math.max(2, d.width))
      .on('mouseover', function (event: any, d: any) {
        d3.select(this).attr('stroke-opacity', 0.6);
        tooltip.style('visibility', 'visible')
          .html(`<strong>${d.source.name} → ${d.target.name}</strong>${d.label ? `<br/>${d.label}` : ''}${d.value > 1 ? `<br/>${formatAmount(d.value)}` : ''}`);
      })
      .on('mousemove', (event: any) => {
        tooltip.style('top', (event.pageY - 10) + 'px').style('left', (event.pageX + 10) + 'px');
      })
      .on('mouseout', function () {
        d3.select(this).attr('stroke-opacity', 0.3);
        tooltip.style('visibility', 'hidden');
      });

    // Link labels
    linkGroup.selectAll('text')
      .data(sankeyData.links.filter((d: any) => d.value > 1))
      .join('text')
      .attr('x', (d: any) => ((d.source as any).x1 + (d.target as any).x0) / 2)
      .attr('y', (d: any) => (d.y0 + d.y1) / 2)
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'middle')
      .attr('fill', '#9ca3af')
      .attr('font-size', '10px')
      .text((d: any) => d.label || formatAmount(d.value));

    // Nodes
    const nodeGroup = svg.append('g');

    nodeGroup.selectAll('rect')
      .data(sankeyData.nodes)
      .join('rect')
      .attr('x', (d: any) => d.x0)
      .attr('y', (d: any) => d.y0)
      .attr('width', (d: any) => d.x1 - d.x0)
      .attr('height', (d: any) => Math.max(1, d.y1 - d.y0))
      .attr('fill', (d: any) => categoryColors[d.category] || '#6b7280')
      .attr('rx', 3);

    // Node labels
    nodeGroup.selectAll('text')
      .data(sankeyData.nodes)
      .join('text')
      .attr('x', (d: any) => d.x0 < width / 2 ? d.x0 - 6 : d.x1 + 6)
      .attr('y', (d: any) => (d.y0 + d.y1) / 2)
      .attr('text-anchor', (d: any) => d.x0 < width / 2 ? 'end' : 'start')
      .attr('dominant-baseline', 'middle')
      .attr('fill', '#e5e7eb')
      .attr('font-size', '12px')
      .attr('font-weight', '500')
      .text((d: any) => d.name);

    // Tooltip
    const tooltip = d3.select('body')
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

    return () => {
      tooltip.remove();
    };
  }, [data, height]);

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-white">{data.title}</h3>
        {data.subtitle && <p className="text-sm text-gray-400 mt-1">{data.subtitle}</p>}
      </div>
      <svg ref={svgRef} className="w-full" style={{ height: `${height}px` }} />
    </div>
  );
}
