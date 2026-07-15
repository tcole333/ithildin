#!/usr/bin/env node
/**
 * Nevada Secretary of State (SilverFlume) browser helper.
 *
 * SilverFlume is protected by Incapsula and its entity-detail routes depend on
 * browser session state. This helper uses a persistent Playwright Chrome context
 * and scrapes only the browser pages verified at esos.nv.gov/EntitySearch.
 *
 * Usage:
 *   node tools/_nv_browser_helper.js runtime-check
 *   node tools/_nv_browser_helper.js warmup
 *   node tools/_nv_browser_helper.js probe
 *   node tools/_nv_browser_helper.js search "APOLLO" --mode starts --limit 25
 *   node tools/_nv_browser_helper.js entity E0125332010-5
 *   node tools/_nv_browser_helper.js full E0125332010-5
 *
 * Structured JSON is written to stdout. Progress and actionable runtime errors
 * are written to stderr.
 */

'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');

const BASE_URL = 'https://esos.nv.gov/EntitySearch';
const SEARCH_URL = `${BASE_URL}/OnlineEntitySearch`;
const USER_DATA_DIR = process.env.NV_BROWSER_CACHE_DIR ||
    path.join(os.homedir(), '.cache', 'nv-silverflume-browser');
const DEFAULT_LIMIT = 25;
const MAX_RESULTS = 250;

const STEALTH_SCRIPT = `
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    if (!window.chrome) window.chrome = {};
    if (!window.chrome.runtime) window.chrome.runtime = { id: undefined };
`;

class RuntimeDependencyError extends Error {}

function loadChromium() {
    const override = process.env.NV_PLAYWRIGHT_MODULE;
    const candidates = override ? [override] : ['playwright', 'playwright-core'];
    const failures = [];

    for (const moduleName of candidates) {
        try {
            const loaded = require(moduleName);
            if (!loaded.chromium) {
                failures.push(`${moduleName}: module has no chromium export`);
                continue;
            }
            return { chromium: loaded.chromium, moduleName };
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
            : [
                '/usr/bin/google-chrome',
                '/usr/bin/google-chrome-stable',
                '/usr/bin/chromium',
                '/usr/bin/chromium-browser',
            ];
    return candidates.find(candidate => candidate && fs.existsSync(candidate)) || null;
}

function runtimeInfo() {
    const { chromium, moduleName } = loadChromium();
    const channel = process.env.NV_BROWSER_CHANNEL || 'chrome';
    let executable = null;

    if (channel === 'chrome') {
        executable = systemChromePath();
        if (!executable) {
            throw new RuntimeDependencyError(
                'Google Chrome runtime not found. Install Chrome, or set ' +
                'NV_BROWSER_CHANNEL=chromium after running: npx playwright install chromium'
            );
        }
    } else if (channel === 'chromium') {
        executable = chromium.executablePath();
        if (!executable || !fs.existsSync(executable)) {
            throw new RuntimeDependencyError(
                'Playwright Chromium browser not found. Install with: ' +
                'npx playwright install chromium'
            );
        }
    }

    return {
        ok: true,
        node: process.version,
        playwright_module: moduleName,
        browser_channel: channel,
        browser_executable: executable,
        cache_dir: USER_DATA_DIR,
    };
}

async function launchBrowser() {
    const info = runtimeInfo();
    const { chromium } = loadChromium();
    fs.mkdirSync(USER_DATA_DIR, { recursive: true });

    const options = {
        headless: process.env.NV_BROWSER_HEADLESS === '1',
        viewport: { width: 1440, height: 1000 },
        locale: 'en-US',
        timezoneId: 'America/Los_Angeles',
        userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ' +
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        args: [
            '--disable-blink-features=AutomationControlled',
            '--no-first-run',
            '--no-default-browser-check',
        ],
        ignoreDefaultArgs: ['--enable-automation'],
    };
    if (info.browser_channel !== 'chromium') {
        options.channel = info.browser_channel;
    }

    let context;
    try {
        context = await chromium.launchPersistentContext(USER_DATA_DIR, options);
    } catch (error) {
        throw new RuntimeDependencyError(
            `Could not launch ${info.browser_channel}: ${error.message}. ` +
            'Run the runtime-check command for dependency details.'
        );
    }
    await context.addInitScript(STEALTH_SCRIPT);
    const page = context.pages()[0] || await context.newPage();
    page.setDefaultTimeout(30000);
    page.setDefaultNavigationTimeout(45000);
    return { context, page };
}

async function waitForSearchPage(page, timeoutMs = 120000) {
    const started = Date.now();
    let prompted = false;

    while (Date.now() - started < timeoutMs) {
        const ready = await page.locator('#BusinessSearch_Index_txtEntityName')
            .count().catch(() => 0);
        if (ready) return true;

        const body = await page.locator('body').innerText().catch(() => '');
        if (!prompted && (body.includes('Request unsuccessful') ||
            body.includes('Incapsula incident ID') || Date.now() - started > 8000)) {
            process.stderr.write('\n  *** SilverFlume Incapsula challenge detected ***\n');
            process.stderr.write('  Complete any challenge in the Chrome window.\n');
            process.stderr.write('  Clearance cookies are retained for later requests.\n\n');
            prompted = true;
        }
        await page.waitForTimeout(2000);
    }
    return false;
}

async function openSearchPage(page) {
    await page.goto(SEARCH_URL, { waitUntil: 'domcontentloaded' });
    if (!await waitForSearchPage(page)) {
        throw new Error(
            'SilverFlume search form did not load within 120 seconds. ' +
            'Run `query_nevada.py warmup` and complete the browser challenge.'
        );
    }
}

async function parseSearchPage(page) {
    return page.evaluate(() => {
        const clean = value => (value || '').replace(/\s+/g, ' ').trim();
        const tables = Array.from(document.querySelectorAll('table'));
        const resultTable = tables.find(table => {
            const headers = Array.from(table.querySelectorAll('th'))
                .map(cell => clean(cell.textContent));
            return headers.includes('Name') && headers.includes('Entity Number') &&
                headers.includes('NV Business ID');
        });

        if (!resultTable) {
            const noRecords = /no records|no result/i.test(document.body.innerText);
            return { count: 0, page: 1, pages: 1, results: [], no_records: noRecords };
        }

        const headers = Array.from(resultTable.querySelectorAll('th'))
            .map(cell => clean(cell.textContent));
        const index = label => headers.indexOf(label);
        const keys = {
            entity_name: index('Name'),
            prior_name_match: index('Prior Name Match'),
            status: index('Status'),
            compliance_hold: index('Compliance Hold'),
            filing_date: index('Filing Date'),
            entity_type: index('Type'),
            nv_business_id: index('NV Business ID'),
            entity_number: index('Entity Number'),
            mark_number: index('Mark Number'),
        };

        const results = [];
        for (const row of resultTable.querySelectorAll('tbody tr')) {
            const cells = Array.from(row.querySelectorAll('td'));
            if (!cells.length) continue;
            const item = {};
            for (const [key, position] of Object.entries(keys)) {
                item[key] = position >= 0 && cells[position]
                    ? clean(cells[position].textContent) : '';
            }
            if (!item.entity_name || item.entity_name === 'No records to view.') continue;
            results.push(item);
        }

        const body = document.body.innerText;
        const pagination = body.match(
            /Page\s+(\d+)\s+of\s+(\d+),\s*records\s+[\d,]+\s+to\s+[\d,]+\s+of\s+([\d,]+)/i
        );
        return {
            count: pagination ? Number(pagination[3].replace(/,/g, '')) : results.length,
            page: pagination ? Number(pagination[1]) : 1,
            pages: pagination ? Number(pagination[2]) : 1,
            results,
        };
    });
}

async function searchByName(page, query, mode, requestedLimit) {
    await openSearchPage(page);
    const labels = {
        starts: 'Starts With',
        contains: 'Contains',
        exact: 'Exact Match',
        all: 'All Words',
    };
    const label = labels[mode];
    if (!label) throw new Error(`Unsupported search mode: ${mode}`);

    await page.getByRole('radio', { name: label, exact: true }).check();
    await page.locator('#BusinessSearch_Index_txtEntityName').fill(query);
    await page.getByRole('button', { name: 'Search', exact: true }).click();
    await page.waitForURL(/OnlineBusinessAndMarkSearchResult/, { timeout: 45000 });
    await page.locator('table').first().waitFor({ state: 'visible' });

    const limit = Math.max(1, Math.min(requestedLimit || DEFAULT_LIMIT, MAX_RESULTS));
    let parsed = await parseSearchPage(page);
    const results = [...parsed.results];

    while (results.length < limit && parsed.page < parsed.pages) {
        const nextPage = parsed.page + 1;
        const link = page.locator(
            `a[href="javascript:businessSearchGrid.paging(${nextPage})"]`
        ).first();
        if (!await link.count()) break;

        const firstEntity = results.length ? results[results.length - parsed.results.length].entity_name : '';
        await link.click();
        if (firstEntity) {
            await page.waitForFunction(
                previous => {
                    const first = document.querySelector('table tbody tr td');
                    return first && first.textContent.trim() !== previous;
                },
                firstEntity,
                { timeout: 30000 }
            ).catch(() => {});
        } else {
            await page.waitForTimeout(750);
        }
        parsed = await parseSearchPage(page);
        results.push(...parsed.results);
        await page.waitForTimeout(500);
    }

    const selected = results.slice(0, limit);
    return {
        query,
        mode,
        count: parsed.count,
        returned: selected.length,
        truncated: selected.length < parsed.count,
        results: selected,
        source: 'silverflume_browser_dom',
        url: page.url(),
    };
}

async function openEntity(page, entityNumber) {
    await openSearchPage(page);
    await page.locator('#BusinessSearch_Index_txtEntityNumber').fill(entityNumber);
    await page.getByRole('button', { name: 'Search', exact: true }).click();
    await page.waitForURL(/OnlineBusinessAndMarkSearchResult/, { timeout: 45000 });
    await page.locator('table').first().waitFor({ state: 'visible' });

    const parsed = await parseSearchPage(page);
    const match = parsed.results.find(row =>
        row.entity_number.toLowerCase() === entityNumber.toLowerCase()
    ) || parsed.results[0];
    if (!match) throw new Error(`No Nevada entity found for ${entityNumber}`);

    const row = page.locator('table tr').filter({ hasText: match.entity_number }).first();
    const link = row.getByRole('link', { name: match.entity_name, exact: true });
    if (!await link.count()) {
        throw new Error(`Entity result for ${entityNumber} did not contain a detail link`);
    }
    await link.click();
    await page.waitForURL(/\/EntitySearch\/BusinessInformation/, { timeout: 45000 });
    await page.getByText('Entity Information', { exact: true }).first()
        .waitFor({ state: 'visible' });
}

async function parseEntityDetail(page) {
    const data = await page.evaluate(() => {
        const clean = value => (value || '').replace(/\s+/g, ' ').trim();
        const labelValues = label => Array.from(document.querySelectorAll('div.label-side'))
            .filter(element => clean(element.textContent) === label)
            .map(element => clean(element.nextElementSibling && element.nextElementSibling.textContent));
        const first = label => labelValues(label)[0] || '';
        const nth = (label, index) => labelValues(label)[index] || '';

        const tables = Array.from(document.querySelectorAll('table'));
        const officerTable = tables.find(table => {
            const headers = Array.from(table.querySelectorAll('th'))
                .map(cell => clean(cell.textContent));
            return headers.includes('Title') && headers.includes('Name') &&
                headers.includes('Address') && headers.includes('Last Updated');
        });
        const officers = [];
        if (officerTable) {
            const headers = Array.from(officerTable.querySelectorAll('th'))
                .map(cell => clean(cell.textContent));
            const index = label => headers.indexOf(label);
            for (const row of officerTable.querySelectorAll('tbody tr')) {
                const cells = Array.from(row.querySelectorAll('td'));
                if (!cells.length) continue;
                const name = index('Name') >= 0 ? clean(cells[index('Name')].textContent) : '';
                if (!name || name === 'No records to view.') continue;
                officers.push({
                    title: index('Title') >= 0 ? clean(cells[index('Title')].textContent) : '',
                    name,
                    address: index('Address') >= 0 ? clean(cells[index('Address')].textContent) : '',
                    last_updated: index('Last Updated') >= 0
                        ? clean(cells[index('Last Updated')].textContent) : '',
                    status: index('Status') >= 0 ? clean(cells[index('Status')].textContent) : '',
                });
            }
        }

        return {
            entity_name: first('Entity Name:'),
            entity_number: first('Entity Number:'),
            entity_type: first('Entity Type:'),
            status: first('Entity Status:'),
            formation_date: first('Formation Date:'),
            nv_business_id: first('NV Business ID:'),
            termination_date: first('Termination Date:'),
            annual_report_due: first('Annual Report Due Date:'),
            compliance_hold: first('Compliance Hold:'),
            agent_name: first('Name of Individual or Legal Entity:'),
            agent_status: first('Status:'),
            agent_entity_type: first('CRA Agent Entity Type:'),
            agent_type: first('Registered Agent Type:'),
            agent_nv_business_id: nth('NV Business ID:', 1),
            agent_office: first('Office or Position:'),
            agent_jurisdiction: first('Jurisdiction:'),
            agent_address: first('Street Address:'),
            agent_mailing_address: first('Mailing Address:'),
            officers,
        };
    });
    data.source = 'silverflume_browser_dom';
    data.url = page.url();
    return data;
}

async function parseTable(page, requiredHeaders, mapping) {
    return page.evaluate(({ requiredHeaders, mapping }) => {
        const clean = value => (value || '').replace(/\s+/g, ' ').trim();
        const table = Array.from(document.querySelectorAll('table')).find(candidate => {
            const headers = Array.from(candidate.querySelectorAll('th'))
                .map(cell => clean(cell.textContent));
            return requiredHeaders.every(header => headers.includes(header));
        });
        if (!table) return [];
        const headers = Array.from(table.querySelectorAll('th'))
            .map(cell => clean(cell.textContent));
        const results = [];
        for (const row of table.querySelectorAll('tbody tr')) {
            const cells = Array.from(row.querySelectorAll('td'));
            if (!cells.length || /No records to view/i.test(row.textContent)) continue;
            const item = {};
            for (const [key, label] of Object.entries(mapping)) {
                const position = headers.indexOf(label);
                item[key] = position >= 0 && cells[position]
                    ? clean(cells[position].textContent) : '';
            }
            results.push(item);
        }
        return results;
    }, { requiredHeaders, mapping });
}

async function getFullEntity(page, entityNumber) {
    await openEntity(page, entityNumber);
    const data = await parseEntityDetail(page);

    const filingButton = page.getByRole('button', { name: 'Filing History', exact: true });
    if (await filingButton.count()) {
        await filingButton.click();
        await page.waitForURL(/BusinessFilingHistoryOnline/, { timeout: 45000 });
        data.filings = await parseTable(
            page,
            ['File Date', 'Filing Number', 'Document Type'],
            {
                file_date: 'File Date',
                effective_date: 'Effective Date',
                filing_number: 'Filing Number',
                document_type: 'Document Type',
                amendment_type: 'Amendment Type',
                source: 'Source',
                pages: '# of Pages',
            }
        );
        await page.getByRole('button', { name: 'Back', exact: true }).click();
        await page.waitForURL(/\/EntitySearch\/BusinessInformation/, { timeout: 45000 });
    } else {
        data.filings = [];
    }

    const nameButton = page.getByRole('button', { name: 'Name History', exact: true });
    if (await nameButton.count()) {
        await nameButton.click();
        await page.waitForURL(/BusinessNameHistory/, { timeout: 45000 });
        data.name_history = await parseTable(
            page,
            ['File Date', 'Filing Number', 'Name'],
            {
                file_date: 'File Date',
                effective_date: 'Effective Date',
                filing_number: 'Filing Number',
                consent_date: 'Consent Date',
                previous_name: 'Name',
            }
        );
    } else {
        data.name_history = [];
    }
    return data;
}

async function probe(page) {
    await openSearchPage(page);
    return page.evaluate(() => {
        const clean = value => (value || '').replace(/\s+/g, ' ').trim();
        return {
            url: window.location.href,
            title: document.title,
            meta: {
                isAngular: !!window.ng || !!document.querySelector('[ng-app]'),
                isReact: !!document.querySelector('[data-reactroot]'),
                hasViewState: !!document.querySelector('#__VIEWSTATE'),
                hasAntiForgery: !!document.querySelector('input[name="__RequestVerificationToken"]'),
                incapsulaProtected: document.cookie.includes('incap_ses_') ||
                    document.cookie.includes('visid_incap_'),
            },
            forms: Array.from(document.forms).map(form => ({
                id: form.id,
                action: form.action,
                method: form.method,
            })),
            inputs: Array.from(document.querySelectorAll('input')).map(input => ({
                id: input.id,
                name: input.name,
                type: input.type,
                label: clean(input.labels && input.labels[0] && input.labels[0].textContent),
            })),
            selects: Array.from(document.querySelectorAll('select')).map(select => ({
                id: select.id,
                name: select.name,
                label: clean(select.labels && select.labels[0] && select.labels[0].textContent),
                options: Array.from(select.options).map(option => ({
                    value: option.value,
                    text: clean(option.textContent),
                })),
            })),
            buttons: Array.from(document.querySelectorAll(
                'button,input[type="submit"],input[type="button"],input[type="reset"]'
            ))
                .map(button => ({
                    id: button.id,
                    type: button.type,
                    text: clean(button.textContent || button.value),
                })),
            scripts: Array.from(document.scripts).map(script => script.src).filter(Boolean),
        };
    });
}

function optionValue(args, option, fallback = null) {
    const index = args.indexOf(option);
    return index >= 0 && args[index + 1] ? args[index + 1] : fallback;
}

function usage() {
    process.stderr.write('Usage: node _nv_browser_helper.js <command> [args]\n');
    process.stderr.write('  runtime-check                         Verify Node/Playwright/Chrome\n');
    process.stderr.write('  warmup                               Solve/cache Incapsula challenge\n');
    process.stderr.write('  probe                                Inspect the official search form\n');
    process.stderr.write('  search <query> [--mode MODE] [--limit N]\n');
    process.stderr.write('  entity <entity_number>               Entity/officer/agent detail\n');
    process.stderr.write('  full <entity_number>                 Detail plus filing/name history\n');
}

async function warmup() {
    const { context, page } = await launchBrowser();
    try {
        process.stderr.write('Opening Nevada SilverFlume in Chrome.\n');
        process.stderr.write('Complete any challenge, then press Enter here.\n');
        await page.goto(SEARCH_URL, { waitUntil: 'domcontentloaded' });
        await waitForSearchPage(page, 300000);
        await new Promise(resolve => {
            const timer = setTimeout(resolve, 300000);
            process.stdin.once('data', () => {
                clearTimeout(timer);
                resolve();
            });
        });
        return { ok: true, url: page.url(), cache_dir: USER_DATA_DIR };
    } finally {
        await context.close();
    }
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
    if (!command) {
        usage();
        process.exit(1);
    }

    let result;
    if (command === 'runtime-check') {
        result = runtimeInfo();
    } else if (command === 'warmup') {
        result = await warmup();
    } else if (command === 'probe') {
        result = await withBrowser(page => probe(page));
    } else if (command === 'search') {
        const query = args[1];
        if (!query) throw new Error('Search query is required');
        const mode = optionValue(args, '--mode', 'starts');
        const rawLimit = Number(optionValue(args, '--limit', DEFAULT_LIMIT));
        if (!Number.isInteger(rawLimit) || rawLimit < 1) {
            throw new Error('--limit must be a positive integer');
        }
        result = await withBrowser(page => searchByName(page, query, mode, rawLimit));
    } else if (command === 'entity' || command === 'detail') {
        const entityNumber = args[1];
        if (!entityNumber) throw new Error('Entity number is required');
        result = await withBrowser(async page => {
            await openEntity(page, entityNumber);
            return parseEntityDetail(page);
        });
    } else if (command === 'full') {
        const entityNumber = args[1];
        if (!entityNumber) throw new Error('Entity number is required');
        result = await withBrowser(page => getFullEntity(page, entityNumber));
    } else {
        usage();
        throw new Error(`Unknown command: ${command}`);
    }

    process.stdout.write(JSON.stringify(result));
}

main().catch(error => {
    const prefix = error instanceof RuntimeDependencyError ? 'RUNTIME ERROR' : 'ERROR';
    process.stderr.write(`${prefix}: ${error.message}\n`);
    process.exit(1);
});
