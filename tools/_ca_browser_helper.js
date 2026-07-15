#!/usr/bin/env node
/**
 * California SOS BizFile browser helper.
 *
 * Uses one short-lived, headed Playwright Chrome context per bounded command.
 * A dedicated persistent profile retains Imperva clearance between invocations;
 * no browser daemon or TCP debugging port is used.
 */

'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');

const SEARCH_URL = 'https://bizfileonline.sos.ca.gov/search/business';
const USER_DATA_DIR = process.env.CA_BROWSER_CACHE_DIR ||
    path.join(os.homedir(), '.cache', 'ca-bizfile-browser');
const DEFAULT_LIMIT = 25;
const MAX_RESULTS = 500;
const MAX_DOM_ATTEMPTS = 2;

class RuntimeDependencyError extends Error {}

function loadChromium() {
    const override = process.env.CA_PLAYWRIGHT_MODULE;
    const candidates = override ? [override] : ['playwright', 'playwright-core'];
    const failures = [];
    for (const moduleName of candidates) {
        try {
            const loaded = require(moduleName);
            if (loaded.chromium) return { chromium: loaded.chromium, moduleName };
            failures.push(`${moduleName}: module has no chromium export`);
        } catch (error) {
            failures.push(`${moduleName}: ${error.message}`);
        }
    }
    throw new RuntimeDependencyError(
        'Playwright runtime not found. Install with: npm install playwright ' +
        `(checked ${candidates.join(', ')}; ${failures.join('; ')})`
    );
}

function systemChromePath() {
    const candidates = process.platform === 'darwin'
        ? [
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            path.join(os.homedir(), 'Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),
        ]
        : process.platform === 'win32'
            ? [
                path.join(process.env.PROGRAMFILES || '', 'Google/Chrome/Application/chrome.exe'),
                path.join(process.env['PROGRAMFILES(X86)'] || '', 'Google/Chrome/Application/chrome.exe'),
                path.join(process.env.LOCALAPPDATA || '', 'Google/Chrome/Application/chrome.exe'),
            ]
            : ['/usr/bin/google-chrome', '/usr/bin/google-chrome-stable'];
    return candidates.find(candidate => candidate && fs.existsSync(candidate)) || null;
}

function runtimeInfo() {
    const { moduleName } = loadChromium();
    const executable = systemChromePath();
    if (!executable) {
        throw new RuntimeDependencyError(
            'Google Chrome runtime not found. Install Chrome; this helper does not ' +
            'attach to an existing Codex or MCP browser session.'
        );
    }
    return {
        ok: true,
        node: process.version,
        playwright_module: moduleName,
        browser_channel: 'chrome',
        browser_executable: executable,
        cache_dir: USER_DATA_DIR,
        headless: process.env.CA_BROWSER_HEADLESS === '1',
    };
}

async function launchBrowser() {
    const info = runtimeInfo();
    const { chromium } = loadChromium();
    fs.mkdirSync(USER_DATA_DIR, { recursive: true });
    try {
        const context = await chromium.launchPersistentContext(USER_DATA_DIR, {
            channel: 'chrome',
            headless: info.headless,
            viewport: { width: 1440, height: 1000 },
            locale: 'en-US',
            timezoneId: 'America/Los_Angeles',
            args: [
                '--disable-blink-features=AutomationControlled',
                '--no-first-run',
                '--no-default-browser-check',
            ],
            ignoreDefaultArgs: ['--enable-automation'],
        });
        await context.addInitScript(`
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            if (!window.chrome) window.chrome = {};
        `);
        const page = context.pages()[0] || await context.newPage();
        page.setDefaultTimeout(30000);
        page.setDefaultNavigationTimeout(60000);
        return { context, page };
    } catch (error) {
        throw new RuntimeDependencyError(
            `Could not launch the dedicated Chrome profile: ${error.message}. ` +
            'Close another California BizFile helper if one is running, then retry.'
        );
    }
}

async function challengeMessage(page) {
    const body = await page.locator('body').innerText().catch(() => '');
    if (/Incapsula|Request unsuccessful|incident ID/i.test(body)) {
        return 'Imperva challenge blocked the California BizFile page. ' +
            'Retry with headed Chrome (unset CA_BROWSER_HEADLESS), and complete any ' +
            'visible challenge in the temporary Chrome window.';
    }
    return 'California BizFile search form did not stabilize.';
}

async function openStableSearchPage(page, maxAttempts = MAX_DOM_ATTEMPTS) {
    let lastError = null;
    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
        try {
            await page.goto(SEARCH_URL, { waitUntil: 'domcontentloaded' });
            const box = page.getByRole('textbox', {
                name: 'Search by name or file number', exact: true,
            });
            await box.waitFor({ state: 'visible', timeout: 45000 });
            await page.waitForTimeout(500);
            await box.inputValue();
            return;
        } catch (error) {
            lastError = error;
            if (attempt < maxAttempts) await page.waitForTimeout(750);
        }
    }
    throw new Error(`${await challengeMessage(page)} ${lastError ? lastError.message : ''}`.trim());
}

function parseSearchResponse(raw, requestedLimit) {
    const rows = raw && raw.rows && typeof raw.rows === 'object' ? raw.rows : {};
    const results = [];
    for (const [internalId, row] of Object.entries(rows)) {
        let title = row.TITLE || '';
        if (Array.isArray(title)) title = title[0] || '';
        const match = title.match(/\(([^)]+)\)\s*$/);
        results.push({
            internal_id: String(internalId),
            entity_number: match ? match[1] : null,
            entity_name: match ? title.slice(0, match.index).trim() : title,
            title,
            record_num: row.RECORD_NUM || '',
            initial_filing_date: row.INITIAL_FILING_DATE || '',
            status: row.STATUS || '',
            entity_type: row.ENTITY_TYPE || '',
            standing_sos: row.STANDING_SOS || '',
            standing_ftb: row.STANDING_FTB || '',
            standing_agent: row.STANDING_AGENT || '',
            standing_vcfcf: row.STANDING_VCFCF || '',
            agent: row.AGENT || '',
        });
    }
    const limit = Math.max(1, Math.min(requestedLimit, MAX_RESULTS));
    return {
        count: results.length,
        returned: Math.min(results.length, limit),
        truncated: results.length > limit,
        results: results.slice(0, limit),
        source: 'ca_bizfile_browser_api',
        url: SEARCH_URL,
    };
}

function parseSearchBody(body, contentType = '') {
    try {
        return JSON.parse(body);
    } catch (error) {
        if (/html/i.test(contentType) || /^\s*</.test(body)) {
            throw new Error(
                'official business search returned non-JSON HTML, likely an ' +
                'Imperva challenge; run the probe command in headed Chrome to ' +
                'refresh clearance, then retry the search'
            );
        }
        throw new Error(`official business search returned invalid JSON: ${error.message}`);
    }
}

async function search(page, query, requestedLimit) {
    let lastError = null;
    for (let attempt = 1; attempt <= MAX_DOM_ATTEMPTS; attempt += 1) {
        try {
            // The outer loop owns the two-attempt budget for the complete
            // navigation/fill/submit operation. Avoid multiplying it by the
            // search-page helper's own retry budget.
            await openStableSearchPage(page, 1);
            const box = page.getByRole('textbox', {
                name: 'Search by name or file number', exact: true,
            });
            await box.click();
            await box.press(process.platform === 'darwin' ? 'Meta+a' : 'Control+a');
            await box.press('Backspace');
            await box.type(query, { delay: 50 });
            await page.waitForTimeout(600);
            const [response] = await Promise.all([
                page.waitForResponse(
                    item => item.url().includes('/api/Records/businesssearch'),
                    { timeout: 30000 }
                ),
                page.getByRole('button', { name: 'Execute search', exact: true })
                    .click({ force: true }),
            ]);
            if (response.status() !== 200) {
                throw new Error(`official business search returned HTTP ${response.status()}`);
            }
            const headers = await response.allHeaders();
            const raw = parseSearchBody(
                await response.text(), headers['content-type'] || ''
            );
            return parseSearchResponse(raw, requestedLimit);
        } catch (error) {
            lastError = error;
            if (attempt < MAX_DOM_ATTEMPTS &&
                /detached|Timeout|not attached|stabilize/i
                    .test(error.message)) {
                await page.waitForTimeout(750);
                continue;
            }
            break;
        }
    }
    throw new Error(`${await challengeMessage(page)} ${lastError ? lastError.message : ''}`.trim());
}

async function probe(page) {
    await openStableSearchPage(page);
    return page.evaluate(() => ({
        url: window.location.href,
        title: document.title,
        search_box_count: document.querySelectorAll(
            'input[aria-label="Search by name or file number"]'
        ).length,
        execute_search_count: document.querySelectorAll(
            'button[aria-label="Execute search"]'
        ).length,
    }));
}

function optionValue(args, option, fallback = null) {
    const index = args.indexOf(option);
    return index >= 0 && args[index + 1] ? args[index + 1] : fallback;
}

async function withBrowser(action) {
    const { context, page } = await launchBrowser();
    try {
        return await action(page);
    } finally {
        await context.close();
    }
}

async function main() {
    const args = process.argv.slice(2);
    const command = args[0];
    let result;
    if (command === 'runtime-check') {
        result = runtimeInfo();
    } else if (command === 'probe') {
        result = await withBrowser(page => probe(page));
    } else if (command === 'search') {
        const query = args[1];
        if (!query) throw new Error('Search query is required');
        const limit = Number(optionValue(args, '--limit', DEFAULT_LIMIT));
        if (!Number.isInteger(limit) || limit < 1 || limit > MAX_RESULTS) {
            throw new Error(`--limit must be an integer from 1 to ${MAX_RESULTS}`);
        }
        result = await withBrowser(page => search(page, query, limit));
    } else {
        throw new Error(
            'Usage: _ca_browser_helper.js runtime-check|probe|search <query> [--limit 1..500]'
        );
    }
    process.stdout.write(JSON.stringify(result));
}

if (require.main === module) {
    main().catch(error => {
        const prefix = error instanceof RuntimeDependencyError ? 'RUNTIME ERROR' : 'ERROR';
        process.stderr.write(`${prefix}: ${error.message}\n`);
        process.exit(1);
    });
}

module.exports = { parseSearchBody };
