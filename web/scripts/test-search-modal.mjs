/** Isolated real-browser regressions: no production data or HTTP server needed. */
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { chromium } from '@playwright/test';

const bundle = await build({
  stdin: { contents: `
    import React from 'react';
    import { createRoot } from 'react-dom/client';
    import SearchModal from './src/components/SearchModal';
    import { setTooltipContent } from './src/lib/tooltipContent';
    window.setTooltipContent = setTooltipContent;
    function Fixture() {
      React.useEffect(() => { window.fixtureReady = true; }, []);
      return <SearchModal />;
    }
    createRoot(document.getElementById('root')).render(<Fixture />);
  `, resolveDir: process.cwd(), loader: 'tsx' },
  bundle: true, write: false, format: 'iife', jsx: 'automatic',
  define: { 'process.env.NODE_ENV': '"test"' },
});
const browser = await chromium.launch();
try {
  for (const failFirst of [false, true]) {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setContent('<button id="opener">Open</button><div id="root"></div><div id="tooltip"></div>');
    await page.evaluate(fail => {
      window.requests = 0;
      window.fetch = () => {
        window.requests += 1;
        if (fail && window.requests === 1) return Promise.reject(new Error('offline'));
        return new Promise(resolve => { window.completeIndex = resolve; });
      };
      document.getElementById('opener').onclick = () => window.dispatchEvent(new Event('open-search'));
    }, failFirst);
    await page.addScriptTag({ content: bundle.outputFiles[0].text });
    // React has attached the global opening listener before interacting.
    await page.waitForFunction(() => window.fixtureReady === true);
    await page.locator('#opener').click();
    const input = page.getByRole('combobox');
    await input.waitFor();
    await input.fill('Example');
    if (failFirst) {
      await page.getByRole('alert').waitFor();
      await page.getByRole('button', { name: 'Try again' }).click();
    }
    await page.waitForFunction(() => typeof window.completeIndex === 'function');
    await page.evaluate(() => window.completeIndex({ ok: true, json: async () => [
      { id: 'article:example', type: 'article', title: 'Example article', slug: 'example', href: '/articles/example' },
    ] }));
    await page.getByRole('option').waitFor();
    assert.equal(await input.inputValue(), 'Example');
    assert.equal(await page.getByRole('option').getAttribute('href'), '/articles/example');
    await input.focus();
    await input.press('Shift+Tab');
    assert.equal(await page.evaluate(() => document.activeElement?.getAttribute('role')), 'option');
    await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(() => document.activeElement?.getAttribute('role')), 'combobox');
    await page.keyboard.press('Escape');
    await page.getByRole('dialog').waitFor({ state: 'detached' });
    assert.equal(await page.evaluate(() => document.activeElement?.id), 'opener');
    assert.equal(await page.evaluate(() => document.body.style.overflow), '');
    await page.evaluate(() => window.setTooltipContent(document.getElementById('tooltip'), '<img src=x onerror="window.injected=true">', ['<script>window.injected=true</script>']));
    assert.equal(await page.locator('#tooltip img, #tooltip script').count(), 0);
    assert.ok((await page.locator('#tooltip').textContent()).includes('<img'));
    assert.deepEqual(errors, []);
    await page.close();
  }
  console.log('Browser checks passed: delayed readiness, failure/retry, focus trap/restore, and tooltip text.');
} finally {
  await browser.close();
}
