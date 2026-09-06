/**
 * Article Visualization Hydrator
 *
 * Convention for embedding interactive visualizations in MDX articles:
 *
 *   <div data-viz="TimelineChart" data-src="/content/timelines/apollo.json" data-height="400"></div>
 *   <div data-viz="TransactionTable" data-src="/content/financials/apollo-transactions.json"></div>
 *   <div data-viz="EgoNetwork" data-src="/content/ego/leon-black.json" data-depth="2"></div>
 *
 * The `data-src` attribute points to a JSON file that provides the component props.
 * Optional `data-height` and `data-depth` override props from the JSON.
 *
 * Articles remain readable without JS — the div is empty but the surrounding
 * prose provides context. When JS loads, the script finds all data-viz markers
 * and mounts React components into them.
 */

const COMPONENTS = {
  TimelineChart: () => import('../components/TimelineChart'),
  TransactionTable: () => import('../components/TransactionTable'),
  EgoNetwork: () => import('../components/EgoNetwork'),
  SankeyDiagram: () => import('../components/SankeyDiagram'),
  CorporateStructure: () => import('../components/CorporateStructure'),
};

/** Components that expect the JSON payload nested under a `data` prop. */
const NESTED_DATA_COMPONENTS = new Set(['SankeyDiagram', 'CorporateStructure']);

export async function hydrateArticleViz() {
  const markers = document.querySelectorAll<HTMLElement>('[data-viz]');
  if (markers.length === 0) return;

  const { createElement } = await import('react');
  const { createRoot } = await import('react-dom/client');
  await Promise.all(Array.from(markers, async el => {
    const name = el.dataset.viz;
    if (!name || !Object.hasOwn(COMPONENTS, name)) {
      console.warn(`[viz-hydrator] Unknown component: ${name}`);
      return;
    }
    if (el.dataset.vizMounted === 'true') return;

    const src = el.dataset.src;
    if (!src) {
      console.warn(`[viz-hydrator] Missing data-src for ${name}`);
      return;
    }

    try {
      // Show loading state
      const message = document.createElement('div');
      message.textContent = 'Loading visualization...';
      message.style.cssText = 'padding:2rem;text-align:center;color:#8c97a3;font-size:0.85rem;';
      el.replaceChildren(message);
      el.dataset.vizMounted = 'true';

      const [res, module] = await Promise.all([fetch(src), COMPONENTS[name as keyof typeof COMPONENTS]()]);
      if (!res.ok) throw new Error(`Failed to fetch ${src}: ${res.status}`);
      const data = await res.json();
      if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('Visualization data must be an object');

      // Merge data-* overrides
      const overrides: Record<string, any> = {};
      if (el.dataset.height) overrides.height = parseInt(el.dataset.height, 10);
      if (el.dataset.depth) overrides.depth = parseInt(el.dataset.depth, 10);
      if (el.dataset.groupBy) overrides.groupBy = el.dataset.groupBy;
      if (el.dataset.title) overrides.title = el.dataset.title;

      const props = NESTED_DATA_COMPONENTS.has(name!)
        ? { data, ...overrides }
        : { ...data, ...overrides };
      const root = createRoot(el);
      // Each selected module owns its source-specific prop shape.
      root.render(createElement(module.default as React.ComponentType<any>, props));
    } catch (err) {
      console.error(`[viz-hydrator] Error mounting ${name}:`, err);
      delete el.dataset.vizMounted;
      const message = document.createElement('div');
      message.textContent = `Visualization unavailable: ${name}`;
      message.style.cssText = 'padding:1rem;color:#b7b1a3;font-size:0.85rem;border:1px solid #2a313b;border-radius:4px;';
      el.replaceChildren(message);
    }
  }));
}
