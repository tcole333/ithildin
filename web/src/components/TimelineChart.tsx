import { useEffect, useRef, useState, useMemo } from 'react';
import * as d3 from 'd3';

interface TimelineEvent {
  date: string;
  label: string;
  type: 'financial' | 'legal' | 'communication' | 'corporate' | string;
  evidence_ref?: string;
  entity?: string;
  detail?: string;
}

interface Props {
  events: TimelineEvent[];
  groupBy?: 'entity' | 'type' | 'none';
  height?: number;
}

const EVENT_COLORS: Record<string, string> = {
  financial: '#d1b36a',
  legal: '#b7b1a3',
  communication: '#8fd3e8',
  corporate: '#7ea7c1',
};

const COLORS = {
  text: '#c7d0d9',
  muted: '#8c97a3',
  edge: '#2a313b',
  panelBg: '#12151b',
  panelBorder: '#2a313b',
  void: '#0b0d10',
};

function eventColor(type: string): string {
  return EVENT_COLORS[type] || '#8c97a3';
}

function formatDate(d: Date): string {
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

export default function TimelineChart({ events, groupBy = 'none', height = 500 }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);

  const parsed = useMemo(() => {
    return events
      .map(e => ({ ...e, _date: new Date(e.date) }))
      .filter(e => !isNaN(e._date.getTime()))
      .sort((a, b) => a._date.getTime() - b._date.getTime());
  }, [events]);

  const groups = useMemo(() => {
    if (groupBy === 'none' || parsed.length === 0) return ['All'];
    const key = groupBy === 'entity' ? 'entity' : 'type';
    const set = new Set(parsed.map(e => (e as any)[key] || 'Unknown'));
    return Array.from(set).sort();
  }, [parsed, groupBy]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const update = () => {
      const rect = container.getBoundingClientRect();
      const nextWidth = Math.floor(rect.width);
      if (nextWidth) setWidth(nextWidth);
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

  useEffect(() => {
    if (!svgRef.current || parsed.length === 0 || !width) return;

    const margin = { top: 30, right: 30, bottom: 40, left: 30 };
    const innerWidth = width - margin.left - margin.right;
    const rowHeight = groupBy === 'none' ? height - margin.top - margin.bottom : Math.max(40, Math.floor((height - margin.top - margin.bottom) / groups.length));
    const innerHeight = groupBy === 'none' ? rowHeight : rowHeight * groups.length;
    const totalHeight = innerHeight + margin.top + margin.bottom;

    d3.select(svgRef.current).selectAll('*').remove();
    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', totalHeight)
      .attr('viewBox', `0 0 ${width} ${totalHeight}`);

    const extent = d3.extent(parsed, d => d._date) as [Date, Date];
    const pad = (extent[1].getTime() - extent[0].getTime()) * 0.05 || 86400000;
    const xScale = d3.scaleTime()
      .domain([new Date(extent[0].getTime() - pad), new Date(extent[1].getTime() + pad)])
      .range([0, innerWidth]);

    const groupScale = d3.scaleBand()
      .domain(groups)
      .range([0, innerHeight])
      .padding(0.15);

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    // Zoom
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([1, 20])
      .translateExtent([[0, 0], [width, totalHeight]])
      .extent([[0, 0], [width, totalHeight]])
      .on('zoom', (event) => {
        const newX = event.transform.rescaleX(xScale);
        xAxis.call(d3.axisBottom(newX).tickFormat(d3.timeFormat('%b %Y') as any).tickSizeOuter(0));
        xAxis.selectAll('text').attr('fill', COLORS.muted).attr('font-size', '10px');
        xAxis.selectAll('line').attr('stroke', COLORS.edge);
        xAxis.selectAll('.domain').attr('stroke', COLORS.edge);

        dots.attr('cx', (d: any) => newX(d._date));
        stems.attr('x1', (d: any) => newX(d._date)).attr('x2', (d: any) => newX(d._date));
      });

    svg.call(zoom as any);

    // Group rows
    if (groupBy !== 'none') {
      groups.forEach(group => {
        const y = groupScale(group) || 0;
        g.append('line')
          .attr('x1', 0).attr('x2', innerWidth)
          .attr('y1', y).attr('y2', y)
          .attr('stroke', COLORS.edge).attr('stroke-opacity', 0.5);
        g.append('text')
          .attr('x', -4).attr('y', y + (groupScale.bandwidth() / 2))
          .attr('text-anchor', 'end').attr('dominant-baseline', 'middle')
          .attr('fill', COLORS.muted).attr('font-size', '10px')
          .text(group.length > 18 ? group.slice(0, 16) + '...' : group);
      });
    }

    // X axis
    const xAxis = g.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(d3.axisBottom(xScale).tickFormat(d3.timeFormat('%b %Y') as any).tickSizeOuter(0));
    xAxis.selectAll('text').attr('fill', COLORS.muted).attr('font-size', '10px');
    xAxis.selectAll('line').attr('stroke', COLORS.edge);
    xAxis.selectAll('.domain').attr('stroke', COLORS.edge);

    // Assign y position
    const getY = (e: typeof parsed[0]): number => {
      if (groupBy === 'none') {
        return innerHeight / 2;
      }
      const key = groupBy === 'entity' ? (e.entity || 'Unknown') : e.type;
      return (groupScale(key) || 0) + groupScale.bandwidth() / 2;
    };

    // Stems
    const stems = g.append('g').selectAll('line')
      .data(parsed)
      .join('line')
      .attr('x1', d => xScale(d._date))
      .attr('x2', d => xScale(d._date))
      .attr('y1', d => getY(d))
      .attr('y2', innerHeight)
      .attr('stroke', d => eventColor(d.type))
      .attr('stroke-opacity', 0.2)
      .attr('stroke-width', 1);

    // Dots
    const dots = g.append('g').selectAll('circle')
      .data(parsed)
      .join('circle')
      .attr('cx', d => xScale(d._date))
      .attr('cy', d => getY(d))
      .attr('r', 5)
      .attr('fill', d => eventColor(d.type))
      .attr('fill-opacity', 0.85)
      .attr('stroke', COLORS.void)
      .attr('stroke-width', 1)
      .style('cursor', 'pointer');

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
      .style('max-width', '300px');

    dots.on('mouseover', (_event: any, d: any) => {
      tooltip.style('visibility', 'visible')
        .html([
          `<strong>${d.label}</strong>`,
          `<span style="color:${eventColor(d.type)}">${d.type}</span> &middot; ${formatDate(d._date)}`,
          d.entity ? `Entity: ${d.entity}` : '',
          d.detail || '',
          d.evidence_ref ? `<span style="color:${COLORS.muted}">Ref: ${d.evidence_ref}</span>` : '',
        ].filter(Boolean).join('<br/>'));
    })
      .on('mousemove', (event: any) => {
        tooltip.style('top', (event.pageY - 10) + 'px').style('left', (event.pageX + 10) + 'px');
      })
      .on('mouseout', () => tooltip.style('visibility', 'hidden'));

    return () => {
      tooltip.remove();
    };
  }, [parsed, width, height, groups, groupBy]);

  const legend = Object.entries(EVENT_COLORS);

  return (
    <div ref={containerRef} className="surface p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex gap-4">
          {legend.map(([type, color]) => (
            <div key={type} className="flex items-center gap-2 text-xs text-mithril">
              <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: color }} />
              {type}
            </div>
          ))}
        </div>
        <div className="text-xs text-mithril font-mono">{parsed.length} events</div>
      </div>
      <svg ref={svgRef} className="w-full graph-canvas" style={{ height: `${height}px` }} />
      <div className="mt-2 text-xs text-mithril text-center">
        Scroll to zoom &middot; Drag to pan
      </div>
    </div>
  );
}
