#!/usr/bin/env node
/**
 * Palm Beach County eCaseView browser-session helper.
 *
 * The public portal uses an invisible reCAPTCHA plus ASP.NET/F5 session state.
 * This helper follows the published guest UI in a short-lived, headed Chrome
 * context and emits only public record fields and stable record identifiers.
 *
 * Usage:
 *   node tools/_pbc_court_browser_helper.js runtime-check
 *   node tools/_pbc_court_browser_helper.js probe
 *   node tools/_pbc_court_browser_helper.js search "KRAFT" --scope party
 *   node tools/_pbc_court_browser_helper.js search \
 *       50-2019-MM-002346-AXXX-NB --scope case-number
 *   node tools/_pbc_court_browser_helper.js case 50-2019-MM-002346-AXXX-NB
 *   node tools/_pbc_court_browser_helper.js download \
 *       50-2019-MM-002346-AXXX-NB 5 /tmp/din-5.pdf
 */

'use strict';

const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');

const BASE_URL = 'https://appsgp.mypalmbeachclerk.com/ecaseview';
const SEARCH_URL = `${BASE_URL}/Search`;
const USER_DATA_DIR = process.env.PBC_COURT_BROWSER_CACHE_DIR ||
    path.join(os.homedir(), '.cache', 'palm-beach-ecaseview-browser');

class RuntimeDependencyError extends Error {}

class DocumentStateError extends Error {
    constructor(message, documentState, details = {}) {
        super(message);
        this.name = 'DocumentStateError';
        this.documentState = documentState;
        this.details = details;
    }
}

function loadChromium() {
    const override = process.env.PBC_COURT_PLAYWRIGHT_MODULE;
    const candidates = override ? [override] : ['playwright', 'playwright-core'];
    const failures = [];
    for (const moduleName of candidates) {
        try {
            const loaded = require(moduleName);
            if (loaded.chromium) {
                return { chromium: loaded.chromium, moduleName };
            }
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
            path.join(
                os.homedir(),
                'Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
            ),
        ]
        : process.platform === 'win32'
            ? [
                path.join(
                    process.env.PROGRAMFILES || '',
                    'Google/Chrome/Application/chrome.exe'
                ),
                path.join(
                    process.env['PROGRAMFILES(X86)'] || '',
                    'Google/Chrome/Application/chrome.exe'
                ),
                path.join(
                    process.env.LOCALAPPDATA || '',
                    'Google/Chrome/Application/chrome.exe'
                ),
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
    const channel = process.env.PBC_COURT_BROWSER_CHANNEL || 'chrome';
    let executable = null;
    if (channel === 'chrome') {
        executable = systemChromePath();
        if (!executable) {
            throw new RuntimeDependencyError(
                'Google Chrome runtime not found. Install Chrome, or set ' +
                'PBC_COURT_BROWSER_CHANNEL=chromium after running: ' +
                'npx playwright install chromium'
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
        headless: process.env.PBC_COURT_BROWSER_HEADLESS === '1',
        base_url: BASE_URL,
    };
}

async function launchBrowser() {
    const info = runtimeInfo();
    const { chromium } = loadChromium();
    fs.mkdirSync(USER_DATA_DIR, { recursive: true });
    const options = {
        headless: info.headless,
        viewport: { width: 1500, height: 1100 },
        locale: 'en-US',
        timezoneId: 'America/New_York',
        args: ['--no-first-run', '--no-default-browser-check'],
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
            'Close another Palm Beach eCaseView helper if one is running, then retry.'
        );
    }
    const page = context.pages()[0] || await context.newPage();
    page.setDefaultTimeout(45000);
    page.setDefaultNavigationTimeout(90000);
    return { context, page };
}

async function waitForGuestSearch(page) {
    const caseBox = page.getByRole('textbox', { name: 'Case Number', exact: true });
    const nameBox = page.getByRole(
        'textbox',
        { name: 'Last Name / Company Name', exact: true }
    );
    await caseBox.waitFor({ state: 'visible', timeout: 90000 });
    await nameBox.waitFor({ state: 'visible', timeout: 90000 });
}

async function enterGuestSearch(page) {
    await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded' });
    const alreadyGuest = await page.getByText('Hello Guest!', { exact: true })
        .count().catch(() => 0);
    if (alreadyGuest) {
        await page.goto(SEARCH_URL, { waitUntil: 'domcontentloaded' });
        await waitForGuestSearch(page);
        return;
    }
    const guestButton = page.getByRole(
        'button',
        { name: 'Login as Guest User.', exact: true }
    );
    await guestButton.waitFor({ state: 'visible', timeout: 60000 });
    await guestButton.click();
    await page.waitForURL(
        /\/ecaseview\/Search(?:\?|$)/i,
        { timeout: 90000, waitUntil: 'commit' }
    );
    await waitForGuestSearch(page);
}

function clean(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
}

async function selectAllEntries(page) {
    const selectors = page.getByRole('combobox', { name: 'entries per page' });
    const count = await selectors.count();
    for (let index = 0; index < count; index += 1) {
        const selector = selectors.nth(index);
        const options = await selector.locator('option').allTextContents();
        if (options.map(clean).includes('All')) {
            await selector.selectOption({ label: 'All' });
        }
    }
    if (count) {
        await page.waitForTimeout(250);
    }
}

async function extractTable(table) {
    return table.evaluate(element => {
        const tidy = value => (value || '').replace(/\s+/g, ' ').trim();
        const caption = tidy(element.querySelector('caption')?.textContent);
        const headerRow = Array.from(element.querySelectorAll('thead tr, tr'))
            .find(row => row.querySelectorAll('th').length > 0);
        const headers = headerRow
            ? Array.from(headerRow.querySelectorAll('th')).map(cell =>
                tidy(cell.textContent)
                    .replace(/:\s*Activate.*$/i, '')
                    .replace(/^View or request image$/i, 'Document State')
                    .replace(/^Add to cart$/i, 'Certified Copy')
            )
            : [];
        const rows = [];
        for (const row of element.querySelectorAll('tbody tr')) {
            const cells = Array.from(row.querySelectorAll(':scope > td'));
            if (!cells.length) continue;
            const values = cells.map(cell => tidy(cell.textContent));
            if (values.every(value => !value)) continue;
            const record = {};
            for (let index = 0; index < cells.length; index += 1) {
                const key = headers[index] || `Column ${index + 1}`;
                record[key] = values[index];
            }
            const isDocketTable = headers.includes('DIN');
            const viewButton = isDocketTable
                ? cells[0]?.querySelector('button')
                : null;
            if (viewButton) {
                const label = tidy(
                    viewButton.getAttribute('aria-label') ||
                    viewButton.querySelector('img')?.getAttribute('alt')
                );
                const formAction = viewButton.getAttribute('formaction') || '';
                record['Document State'] = label;
                record.view_form_action = formAction;
                try {
                    const url = new URL(formAction, window.location.origin);
                    record.source_docket_id = url.searchParams.get('DocketId');
                    record.source_din = url.searchParams.get('Din');
                    record.view_handler = url.searchParams.get('handler');
                } catch (_) {
                    // Keep the raw form action when it is not URL-shaped.
                }
            }
            if (isDocketTable) {
                const certifiedButton = cells[1]?.querySelector('button');
                record.certified_copy_available = Boolean(certifiedButton);
            }
            rows.push(record);
        }
        return { caption, headers, rows };
    });
}

async function extractTables(page) {
    await selectAllEntries(page);
    const tables = page.locator('main table');
    const count = await tables.count();
    const output = [];
    for (let index = 0; index < count; index += 1) {
        output.push(await extractTable(tables.nth(index)));
    }
    return output;
}

async function extractKeyValues(page) {
    return page.locator('main').evaluate(element => {
        const tidy = value => (value || '').replace(/\s+/g, ' ').trim();
        const output = {};
        for (const row of element.querySelectorAll('table tr')) {
            const cells = Array.from(row.children)
                .filter(cell => ['TH', 'TD'].includes(cell.tagName));
            for (let index = 0; index < cells.length - 1; index += 1) {
                if (cells[index].tagName !== 'TH') continue;
                const label = tidy(cells[index].textContent).replace(/:$/, '');
                const valueCell = cells[index + 1];
                if (!label || valueCell.tagName !== 'TD') continue;
                output[label] = tidy(valueCell.textContent);
                index += 1;
            }
        }
        return output;
    });
}

function tableWithHeaders(tables, required) {
    return tables.find(table =>
        required.every(label => table.headers.includes(label))
    ) || null;
}

async function parseCaseBanner(page) {
    const text = await page.locator('main').innerText();
    const caseNumber = text.match(/CASE NUMBER:\s*([^\n]+)/i);
    const caseStyle = text.match(/CASE STYLE:\s*([^\n]+)/i);
    const accessLevel = text.match(/ACCESS LEVEL:\s*([^\n]+)/i);
    return {
        case_number: clean(caseNumber && caseNumber[1]),
        case_style: clean(caseStyle && caseStyle[1]),
        access_level: clean(accessLevel && accessLevel[1]),
    };
}

async function parseSearchResults(page) {
    await selectAllEntries(page);
    const tables = await extractTables(page);
    const table = tableWithHeaders(
        tables,
        ['Case Number', 'Court Type', 'Case Type', 'Case Style', 'Status']
    );
    const body = await page.locator('main').innerText();
    const totalMatch = body.match(/([\d,]+)\s+record\(s\)\s+returned/i);
    const total = totalMatch
        ? Number(totalMatch[1].replace(/,/g, ''))
        : (table ? table.rows.length : 0);
    const buttons = page.locator('button[data-href*="caseNumber="]');
    const hrefs = [];
    for (let index = 0; index < await buttons.count(); index += 1) {
        hrefs.push(await buttons.nth(index).getAttribute('data-href'));
    }
    const rows = table ? table.rows : [];
    rows.forEach((row, index) => {
        row.case_href = hrefs[index] || null;
    });
    return {
        total_reported: total,
        source_ceiling_reached: total >= 200,
        records: rows,
        source_url: page.url(),
    };
}

async function submitSearch(page, query, scope, mode, firstName = '') {
    await enterGuestSearch(page);
    if (scope === 'case-number') {
        await page.getByRole('textbox', { name: 'Case Number', exact: true })
            .fill(query);
    } else if (scope === 'party') {
        const label = mode === 'starts-with'
            ? 'Starts With Name Search'
            : 'Exact Name Search';
        await page.getByRole('combobox', { name: 'Name Search', exact: true })
            .selectOption({ label });
        await page.getByRole(
            'textbox',
            { name: 'Last Name / Company Name', exact: true }
        ).fill(query);
        if (firstName) {
            await page.getByRole('textbox', { name: 'First Name', exact: true })
                .fill(firstName);
        }
    } else {
        throw new Error(`Unsupported search scope: ${scope}`);
    }
    await page.getByRole('button', { name: 'Start Search', exact: true }).click();
    await page.waitForURL(
        /\/ecaseview\/SearchResults/i,
        { timeout: 90000, waitUntil: 'commit' }
    );
    await page.getByText(
        /[\d,]+\s+record\(s\)\s+returned/i
    ).first().waitFor({ state: 'visible', timeout: 90000 });
    return parseSearchResults(page);
}

function comparableCaseNumber(value) {
    return clean(value).toUpperCase().replace(/[^A-Z0-9]/g, '');
}

async function openCase(page, caseNumber) {
    const search = await submitSearch(
        page,
        caseNumber,
        'case-number',
        'exact'
    );
    if (!search.records.length) {
        return null;
    }
    const expected = comparableCaseNumber(caseNumber);
    const rows = page.locator('table tbody tr');
    let selected = null;
    for (let index = 0; index < await rows.count(); index += 1) {
        const row = rows.nth(index);
        const button = row.locator('button[data-href*="caseNumber="]').first();
        if (!await button.count()) continue;
        const text = clean(await button.innerText());
        if (comparableCaseNumber(text) === expected || search.records.length === 1) {
            selected = button;
            break;
        }
    }
    if (!selected) {
        throw new Error(
            `Case-number search returned ${search.records.length} records but no exact match`
        );
    }
    await selected.click();
    await page.waitForURL(
        /\/ecaseview\/CaseData\/CaseInfo/i,
        { timeout: 90000, waitUntil: 'commit' }
    );
    await page.getByText(
        /CASE NUMBER:/i
    ).first().waitFor({ state: 'visible', timeout: 90000 });
    return parseCaseBanner(page);
}

function rowsFrom(tables, requiredHeaders) {
    const table = tableWithHeaders(tables, requiredHeaders);
    return table ? table.rows : [];
}

async function loadCaseSection(page, route) {
    await page.goto(`${BASE_URL}/CaseData/${route}`, {
        waitUntil: 'domcontentloaded',
    });
    await page.locator('main').waitFor({ state: 'visible' });
    return {
        url: page.url(),
        banner: await parseCaseBanner(page),
        main_text: clean(await page.locator('main').innerText()),
        key_values: await extractKeyValues(page),
        tables: await extractTables(page),
    };
}

async function caseBundle(page, caseNumber) {
    const banner = await openCase(page, caseNumber);
    if (!banner) {
        return {
            found: false,
            query: caseNumber,
            source_url: SEARCH_URL,
        };
    }

    const info = await loadCaseSection(page, 'CaseInfo');
    const parties = await loadCaseSection(page, 'Parties');
    const dockets = await loadCaseSection(page, 'Dockets');
    const fees = await loadCaseSection(page, 'Fees');
    const charges = await loadCaseSection(page, 'Charges');
    const events = await loadCaseSection(page, 'CourtEvents');
    const warrants = await loadCaseSection(page, 'Warrants');
    const arrests = await loadCaseSection(page, 'Arrests');

    return {
        found: true,
        source_url: info.url,
        banner,
        case_info: info.key_values,
        case_info_text: info.main_text,
        parties: rowsFrom(
            parties.tables,
            ['First Name', 'Last Name', 'Party Type']
        ),
        dockets: rowsFrom(
            dockets.tables,
            ['DIN', 'Effective Date', 'Description', 'Notes']
        ),
        fees: fees.tables,
        charges: rowsFrom(
            charges.tables,
            ['Count', 'Statute', 'Description', 'Disposition']
        ),
        sentences: charges.tables
            .filter(table => /sentence/i.test(table.caption))
            .flatMap(table => table.rows),
        court_events: rowsFrom(
            events.tables,
            ['Date', 'Description', 'Location', 'Room', 'Notes']
        ),
        warrants: warrants.tables.flatMap(table => table.rows),
        arrests: arrests.tables.flatMap(table => table.rows),
        section_urls: {
            case_info: info.url,
            parties: parties.url,
            dockets: dockets.url,
            fees: fees.url,
            charges: charges.url,
            court_events: events.url,
            warrants: warrants.url,
            arrests: arrests.url,
        },
    };
}

function documentStateFromRow(row) {
    const state = clean(row['Document State']).toLowerCase();
    const handler = clean(row.view_handler).toLowerCase();
    const formAction = clean(row.view_form_action).toLowerCase();
    if (state.includes('process')) {
        return 'view_on_request_in_process';
    }
    if (
        state.includes('request') ||
        state.includes('locked') ||
        handler === 'vorimage' ||
        formAction.includes('vorstatus=')
    ) {
        return 'view_on_request';
    }
    if (
        state.includes('view image') ||
        state.includes('image available') ||
        handler === 'viewimage'
    ) {
        return 'public';
    }
    return 'not_available_online';
}

async function downloadDocument(page, caseNumber, din, destination, overwrite) {
    const banner = await openCase(page, caseNumber);
    if (!banner) {
        throw new DocumentStateError(
            `Case not found: ${caseNumber}`,
            'case_not_found',
            { case_number: caseNumber, din }
        );
    }
    await page.goto(`${BASE_URL}/CaseData/Dockets`, {
        waitUntil: 'domcontentloaded',
    });
    await selectAllEntries(page);
    const tables = await extractTables(page);
    const docketRows = rowsFrom(
        tables,
        ['DIN', 'Effective Date', 'Description', 'Notes']
    );
    const row = docketRows.find(item => clean(item.DIN) === clean(din));
    if (!row) {
        throw new DocumentStateError(
            `DIN ${din} was not found in case ${banner.case_number}`,
            'document_not_found',
            { case_number: banner.case_number, din }
        );
    }
    const state = documentStateFromRow(row);
    if (state !== 'public') {
        throw new DocumentStateError(
            `DIN ${din} is ${state.replaceAll('_', ' ')}`,
            state,
            {
                case_number: banner.case_number,
                din,
                description: row.Description || '',
            }
        );
    }

    const target = path.resolve(destination);
    const parent = path.dirname(target);
    if (!fs.existsSync(parent) || !fs.statSync(parent).isDirectory()) {
        throw new Error(`Destination directory does not exist: ${parent}`);
    }
    if (fs.existsSync(target) && !overwrite) {
        throw new Error(`Destination already exists: ${target}`);
    }

    const docketRow = page.locator('table tbody tr').filter({
        has: page.locator('td').filter({ hasText: new RegExp(`^${clean(din)}$`) }),
    }).first();
    const viewButton = docketRow.getByRole(
        'button',
        { name: 'View image', exact: true }
    );
    if (!await viewButton.count()) {
        throw new DocumentStateError(
            `DIN ${din} does not expose a public image button`,
            state,
            { case_number: banner.case_number, din }
        );
    }
    await viewButton.click();
    const downloadButton = page.getByRole(
        'button',
        { name: 'Download docket image file', exact: true }
    );
    await downloadButton.waitFor({ state: 'visible' });
    const [download] = await Promise.all([
        page.waitForEvent('download'),
        downloadButton.click(),
    ]);
    await download.saveAs(target);
    const bytes = fs.readFileSync(target);
    return {
        downloaded: true,
        case_number: banner.case_number,
        case_style: banner.case_style,
        din: clean(din),
        source_docket_id: row.source_docket_id || null,
        document_state: state,
        description: row.Description || '',
        effective_date: row['Effective Date'] || '',
        source_url: row.view_form_action
            ? new URL(row.view_form_action, BASE_URL).toString()
            : `${BASE_URL}/CaseData/Dockets`,
        suggested_filename: download.suggestedFilename(),
        destination: target,
        byte_count: bytes.length,
        sha256: crypto.createHash('sha256').update(bytes).digest('hex'),
        mime_type: 'application/pdf',
    };
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
        result = await withBrowser(async page => {
            await enterGuestSearch(page);
            return {
                ok: true,
                source_url: page.url(),
                title: await page.title(),
                case_search_box_count: await page.getByRole(
                    'textbox',
                    { name: 'Case Number', exact: true }
                ).count(),
                party_search_box_count: await page.getByRole(
                    'textbox',
                    { name: 'Last Name / Company Name', exact: true }
                ).count(),
            };
        });
    } else if (command === 'search') {
        const query = args[1];
        if (!query) throw new Error('Search query is required');
        const scope = optionValue(args, '--scope', 'party');
        const mode = optionValue(args, '--mode', 'exact');
        const firstName = optionValue(args, '--first-name', '');
        result = await withBrowser(page =>
            submitSearch(page, query, scope, mode, firstName)
        );
        result.query = query;
        result.scope = scope;
        result.mode = mode;
        result.first_name = firstName;
    } else if (command === 'case') {
        const caseNumber = args[1];
        if (!caseNumber) throw new Error('Case number is required');
        result = await withBrowser(page => caseBundle(page, caseNumber));
    } else if (command === 'download') {
        const caseNumber = args[1];
        const din = args[2];
        const destination = args[3];
        if (!caseNumber || !din || !destination) {
            throw new Error('download requires CASE_NUMBER DIN DESTINATION');
        }
        result = await withBrowser(page =>
            downloadDocument(
                page,
                caseNumber,
                din,
                destination,
                args.includes('--overwrite')
            )
        );
    } else {
        throw new Error(
            'Usage: _pbc_court_browser_helper.js ' +
            '{runtime-check|probe|search|case|download}'
        );
    }
    process.stdout.write(`${JSON.stringify(result)}\n`);
}

main().catch(error => {
    const payload = {
        error: {
            type: error.name || 'Error',
            message: error.message || String(error),
            document_state: error.documentState || null,
            details: error.details || {},
        },
    };
    process.stderr.write(`${JSON.stringify(payload)}\n`);
    process.exit(1);
});
