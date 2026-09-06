#!/usr/bin/env node
/**
 * Anonymous Massachusetts UCC browser transport. JSON request on stdin;
 * JSON {ok, pages: [{url, html}], runtime} on stdout, errors on stderr.
 * Uses an isolated, ordinary visible Chrome session and public form controls.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const readline = require('readline');

const SEARCH_URL = 'https://corp.sec.state.ma.us/corpweb/UCCSearch/UCCSearch.aspx';
const NAVIGATION_TIMEOUT_MS = 25000;
const DEADLINE_MS = 180000;
const MAX_PAGES = 20;
const MAX_LIMIT = 500;

function isChallenge(html) {
    return /id=["']main-iframe|Request unsuccessful|Incapsula incident|captcha|Access\s*Denied|Error\s*15|automated traffic/i.test(html);
}

function findChrome() {
    const candidates = process.platform === 'darwin'
        ? ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome']
        : process.platform === 'win32'
            ? [process.env.LOCALAPPDATA, process.env.PROGRAMFILES, process.env['PROGRAMFILES(X86)']]
                .filter(Boolean).map(root => path.join(root, 'Google', 'Chrome', 'Application', 'chrome.exe'))
            : ['/opt/google/chrome/chrome', '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable'];
    for (const candidate of candidates) {
        try {
            fs.accessSync(candidate, fs.constants.X_OK);
            return candidate;
        } catch (error) {
            if (!['ENOENT', 'EACCES'].includes(error.code)) throw error;
        }
    }
    throw new Error('Google Chrome executable not found in a standard installation location.');
}

function loadRuntime() {
    for (const name of ['playwright', 'playwright-core']) {
        try {
            const loaded = require(name);
            if (loaded.chromium) {
                return {
                    chromium: loaded.chromium,
                    metadata: {
                        node: process.version,
                        module: name,
                        module_path: require.resolve(name),
                        channel: 'chrome',
                        headless: false,
                    },
                };
            }
        } catch (error) {
            if (error.code !== 'MODULE_NOT_FOUND') throw error;
        }
    }
    throw new Error('Playwright runtime missing. Install playwright (or playwright-core) and Google Chrome.');
}

function validateRequest(request) {
    const commands = ['runtime-check', 'probe', 'search-org', 'search-individual', 'filing'];
    if (!request || !commands.includes(request.command)) {
        throw new Error(`command must be one of: ${commands.join(', ')}`);
    }
    request.limit ??= 25;
    request.search_type ??= 'begins';
    request.role ??= 'debtor';
    if (!Number.isInteger(request.limit) || request.limit < 1 || request.limit > MAX_LIMIT) {
        throw new Error(`limit must be an integer from 1 to ${MAX_LIMIT}`);
    }
    if (!['begins', 'article9', 'exact'].includes(request.search_type)) {
        throw new Error('search_type must be begins, article9, or exact');
    }
    if (!['debtor', 'secured', 'assignee'].includes(request.role)) {
        throw new Error('role must be debtor, secured, or assignee');
    }
    if (request.command === 'search-individual' && request.search_type === 'exact') {
        throw new Error('Exact search is supported only for organizations');
    }
    if (request.role !== 'debtor' && request.search_type !== 'begins') {
        throw new Error('Secured-party and assignee searches require begins search');
    }
    if (['search-org', 'search-individual', 'filing'].includes(request.command)) {
        if (typeof request.query !== 'string' || !request.query.trim()) {
            throw new Error('query must be a nonempty string');
        }
        request.query = request.query.trim();
    }
    if (request.command === 'filing' && !/^\d{12}$/.test(request.query)) {
        throw new Error('Filing number must contain exactly 12 digits');
    }
    if (request.lapsed !== undefined && typeof request.lapsed !== 'boolean') throw new Error('lapsed must be boolean');
    const nameLimit = request.command === 'search-org' ? 175 : 35;
    if (request.command.startsWith('search-') && request.query.length > nameLimit) throw new Error('Search name exceeds form length');
    for (const [field, limit] of [['city', 35], ['first', 25], ['middle', 25], ['suffix', 25]]) {
        if (request[field] != null && (typeof request[field] !== 'string' || request[field].length > limit)) throw new Error(`${field} exceeds form length or is not text`);
    }
    if (request.state && !/^[A-Z]{2}$/.test(request.state)) throw new Error('state must be an uppercase two-letter code');
    if (request.since && !/^\d{2}\/\d{2}\/\d{4}$/.test(request.since)) {
        throw new Error('since must use MM/DD/YYYY');
    }
    if (request.since) {
        const [month, day, year] = request.since.split('/').map(Number);
        const date = new Date(Date.UTC(year, month - 1, day));
        if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) throw new Error('since must be a real date');
    }
    return request;
}

async function closeOwnedBrowser(lifecycle) {
    if (!lifecycle.browser) return;
    if (!lifecycle.closing) {
        lifecycle.closing = (async () => {
            let closeTimer;
            try {
                await Promise.race([
                    lifecycle.browser.close(),
                    new Promise((_, reject) => {
                        closeTimer = setTimeout(() => reject(new Error('Browser cleanup exceeded 5 seconds')), 5000);
                    }),
                ]);
            } finally {
                clearTimeout(closeTimer);
            }
        })();
    }
    return lifecycle.closing;
}

async function createSession(lifecycle) {
    const {chromium, metadata} = loadRuntime();
    metadata.chrome_executable = findChrome();
    const browser = await chromium.launch({
        executablePath: metadata.chrome_executable, headless: false, timeout: 15000,
    });
    lifecycle.browser = browser;
    metadata.browser_version = browser.version();
    metadata.browser_launches = 1;
    const context = await browser.newContext();
    const page = await context.newPage();
    page.setDefaultTimeout(10000);
    page.setDefaultNavigationTimeout(NAVIGATION_TIMEOUT_MS);
    const session = {page, metadata, requests: 0, lastNavigation: 0, lastScope: null};
    session.navigate = async operation => {
        const remaining = 1000 - (Date.now() - session.lastNavigation);
        if (remaining > 0) await new Promise(resolve => setTimeout(resolve, remaining));
        try { await operation(); } finally { session.lastNavigation = Date.now(); }
    };
    session.postback = operation => session.navigate(() => Promise.all([
        page.waitForNavigation({waitUntil: 'domcontentloaded'}), operation(),
    ]));
    session.select = async (selector, value) => {
        if (await page.locator(selector).inputValue() !== value) {
            await session.postback(() => page.locator(selector).selectOption(value));
        }
    };
    session.check = async (selector, checked) => {
        if (await page.locator(selector).isChecked() !== checked) {
            await session.postback(() => page.locator(selector).setChecked(checked));
        }
    };
    return session;
}

async function verifySubmittedForm(page, request) {
    const org = request.command === 'search-org';
    const suffix = org ? 'O' : 'I';
    const field = request.command === 'filing' ? 'FilingNumber' : org ? 'Name' : 'LastName';
    const actual = await page.locator(`#MainContent_txt${field}`).inputValue();
    if (actual !== request.query) throw new Error('Submitted query differs from requested query');
    if (!await page.locator(`#MainContent_rdoSearch${request.command === 'filing' ? 'F' : suffix}`).isChecked()) throw new Error('Search name mode was not applied');
    if (request.command !== 'filing') {
        const type = {begins: 'B', article9: 'M', exact: 'E'}[request.search_type];
        if (await page.locator(`#MainContent_UCCSearchMethod${suffix}`).inputValue() !== type) throw new Error('Search type was not applied');
        for (const [role, selector] of Object.entries({debtor: 'chkDebtor', secured: 'chkSecuredParty', assignee: 'chkAssignee'})) {
            if (await page.locator(`#MainContent_${selector}`).isChecked() !== (role === request.role)) throw new Error('Search role was not applied');
        }
        for (const [selector, expected] of [[`#MainContent_txt${suffix}City`, request.city || ''], ['#MainContent_txtStartDate', request.since || '']]) {
            if (await page.locator(selector).inputValue() !== expected) throw new Error('Search filter was not cleared or applied');
        }
        if (request.state) {
            if (await page.locator(`#MainContent_cbo${suffix}State`).inputValue() !== request.state) throw new Error('State filter was not applied');
        } else if (await page.locator(`#MainContent_cbo${suffix}State`).evaluate(node => node.selectedIndex) !== 0) {
            throw new Error('State filter was not cleared');
        }
        if (await page.locator('#MainContent_ddRecordsPerPage').inputValue() !== '25') throw new Error('Page size differs from parser contract');
        if (!org) for (const [key, name] of Object.entries({first: 'FirstName', middle: 'MiddleName', suffix: 'Suffix'})) {
            if (await page.locator(`#MainContent_txt${name}`).inputValue() !== (request[key] || '')) throw new Error('Individual name fields were not cleared or applied');
        }
    }
    return {...request, query: actual};
}

async function perform(request, session) {
    const {page, metadata, navigate, postback, select, check} = session;
    session.requests += 1;
    const startUrl = SEARCH_URL + (request.lapsed ? '?SearchLapsed=True' : '');
    const reuseForm = session.lastScope === Boolean(request.lapsed) &&
        await page.locator('#MainContent_btnNewSearch').count() > 0;
    if (reuseForm) {
        await postback(() => page.locator('#MainContent_btnNewSearch').click());
    } else for (let attempt = 0; attempt < 2; attempt += 1) {
        try {
            await navigate(async () => {
                const response = await page.goto(startUrl, {waitUntil: 'domcontentloaded'});
                if (response && response.status() >= 500) {
                    const error = new Error(`Massachusetts UCC returned HTTP ${response.status()}`);
                    error.transient = true;
                    throw error;
                }
                if (response && response.status() >= 400) {
                    throw new Error(`Massachusetts UCC returned HTTP ${response.status()}; no search result was obtained`);
                }
            });
            break;
        } catch (error) {
            const transient = error.transient || error.name === 'TimeoutError' || /net::ERR_TIMED_OUT/.test(error.message);
            if (!transient || attempt === 1) throw error;
            const html = await page.content().catch(() => '');
            if (isChallenge(html)) {
                throw new Error('Massachusetts UCC access challenge detected; it was not retried');
            }
            process.stderr.write('Initial Massachusetts UCC navigation timed out or returned a server error; retrying once.\n');
        }
    }
    try {
        await page.locator('#MainContent_rdoSearchI').waitFor({timeout: 15000});
    } catch {
        throw new Error('Massachusetts UCC form unavailable: access challenge or changed source. No search result was obtained.');
    }
    session.lastScope = Boolean(request.lapsed);
    const pages = [];
    async function capture() {
        if (request.command !== 'probe') {
            const table = request.command === 'filing'
                ? '#MainContent_tblFilingHistory' : '#MainContent_grdSearchResults';
            const hasTable = await page.locator(table).count() > 0;
            const message = page.locator('#MainContent_lblMessage');
            const noResults = await message.count() > 0 &&
                /^\*?\s*No records found; try a new search using different criteria\s*$/i.test(await message.innerText());
            if (!hasTable && !noResults) {
                throw new Error('Massachusetts UCC response lacks the expected table or verified no-results message. Access may be challenged or the source may have changed.');
            }
        }
        pages.push({url: page.url(), html: await page.content()});
    }
    if (request.command === 'probe') {
        await capture();
        return {ok: true, pages, runtime: {...metadata, session_request: session.requests},
            submitted: request.command === 'probe' ? null : submitted,
            captured_at: new Date().toISOString()};
    }
    if (request.command === 'filing') {
        await check('#MainContent_rdoSearchF', true);
        await page.locator('#MainContent_txtFilingNumber').fill(request.query);
    } else {
        const org = request.command === 'search-org';
        const suffix = org ? 'O' : 'I';
        await check(`#MainContent_rdoSearch${suffix}`, true);
        await select(`#MainContent_UCCSearchMethod${suffix}`, {
            begins: 'B', article9: 'M', exact: 'E',
        }[request.search_type]);
        const roleSelectors = {debtor: 'chkDebtor', secured: 'chkSecuredParty', assignee: 'chkAssignee'};
        await check(`#MainContent_${roleSelectors[request.role]}`, true);
        for (const [role, selector] of Object.entries(roleSelectors)) {
            if (role !== request.role) await check(`#MainContent_${selector}`, false);
        }
        if (org) {
            await page.locator('#MainContent_txtName').fill(request.query);
        } else {
            await page.locator('#MainContent_txtLastName').fill(request.query);
            for (const [key, field] of Object.entries({first: 'FirstName', middle: 'MiddleName', suffix: 'Suffix'})) {
                await page.locator(`#MainContent_txt${field}`).fill(request[key] || '');
            }
        }
        await page.locator(`#MainContent_txt${suffix}City`).fill(request.city || '');
        // State controls do not post back on selection.
        await page.locator(`#MainContent_cbo${suffix}State`).selectOption(request.state || {index: 0});
        await page.locator('#MainContent_txtStartDate').fill(request.since || '');
        await select('#MainContent_ddRecordsPerPage', '25');
    }
    const submitted = await verifySubmittedForm(page, request);
    await postback(() => page.locator('#MainContent_btnSearch').click());
    await capture();
    if (request.command === 'filing') {
        // Python validates detail/empty markers and extracts the filing data.
        return {ok: true, pages, runtime: {...metadata, session_request: session.requests},
            submitted: request.command === 'probe' ? null : submitted,
            captured_at: new Date().toISOString()};
    }
    const maxPages = Math.min(MAX_PAGES, Math.ceil(request.limit / 25));
    for (let nextPage = 2; nextPage <= maxPages; nextPage += 1) {
        // Follow the link exposed by the live ASP.NET pager; never synthesize a postback.
        const links = page.locator('#MainContent_grdSearchResults a[href]');
        let link;
        for (let index = 0; index < await links.count(); index += 1) {
            const candidate = links.nth(index);
            const href = await candidate.getAttribute('href');
            if (href && href.includes(`Page$${nextPage}'`)) {
                link = candidate;
                break;
            }
        }
        if (!link) {
            const countLabel = page.locator('#MainContent_ltNumOfPages');
            const countText = await countLabel.count() > 0 ? await countLabel.innerText() : '';
            const countMatch = countText.match(/Number of pages:\s*([\d,]+)/);
            if (countMatch && nextPage <= Number(countMatch[1].replace(/,/g, ''))) {
                throw new Error(`Massachusetts UCC reports another page but its page ${nextPage} link is missing`);
            }
            break;
        }
        // The results grid uses an UpdatePanel: page changes replace the
        // table through an asynchronous postback without navigating.
        const previousGrid = await page.locator('#MainContent_grdSearchResults').innerHTML();
        await navigate(() => Promise.all([
            page.waitForFunction(previous => {
                const grid = document.querySelector('#MainContent_grdSearchResults');
                return grid && grid.innerHTML !== previous;
            }, previousGrid, {timeout: NAVIGATION_TIMEOUT_MS}),
            link.click(),
        ]));
        await capture();
    }
    return {ok: true, pages, runtime: {...metadata, session_request: session.requests},
            submitted: request.command === 'probe' ? null : submitted,
            captured_at: new Date().toISOString()};
}

async function bounded(operation) {
    let timer;
    try {
        return await Promise.race([operation(), new Promise((_, reject) => {
            timer = setTimeout(() => reject(new Error('Massachusetts UCC request exceeded the 180-second deadline')), DEADLINE_MS);
        })]);
    } finally { clearTimeout(timer); }
}

async function main() {
    const lifecycle = {browser: null, closing: null};
    const stop = signal => {
        const code = signal === 'SIGINT' ? 130 : 143;
        const fallback = setTimeout(() => process.exit(code), 7000);
        closeOwnedBrowser(lifecycle).catch(error => process.stderr.write(`${error.message}\n`))
            .finally(() => { clearTimeout(fallback); process.exit(code); });
    };
    process.once('SIGINT', () => stop('SIGINT'));
    process.once('SIGTERM', () => stop('SIGTERM'));
    process.stdout.on('error', () => stop('SIGTERM'));
    let operationError;
    try {
        if (process.argv[2] === '--session') {
            const maximum = Number(process.argv[3] || 20);
            if (!Number.isInteger(maximum) || maximum < 1 || maximum > 50) throw new Error('Session size must be 1–50');
            const lines = readline.createInterface({input: process.stdin, crlfDelay: Infinity});
            let session;
            let count = 0;
            for await (const line of lines) {
                let envelope;
                try {
                    if (Buffer.byteLength(line) > 65536) throw new Error('Request exceeds 64 KiB');
                    envelope = JSON.parse(line);
                    if (typeof envelope.request_id !== 'string' || envelope.request_id.length > 100) throw new Error('Missing or invalid request_id');
                    const request = validateRequest(envelope.request);
                    if (['runtime-check', 'probe'].includes(request.command)) throw new Error('Session accepts search or filing requests only');
                    if (++count > maximum) throw new Error('Bounded browser session request limit reached');
                    const result = await bounded(async () => {
                        session ||= await createSession(lifecycle);
                        return perform(request, session);
                    });
                    await new Promise((resolve, reject) => process.stdout.write(JSON.stringify({request_id: envelope.request_id, ...result}) + '\n', error => error ? reject(error) : resolve()));
                    if (count === maximum) break;
                } catch (error) {
                    process.stdout.write(JSON.stringify({request_id: envelope?.request_id, ok: false, error: error.message}) + '\n');
                    throw error;
                }
            }
            lines.close();
        } else {
            const input = fs.readFileSync(0, 'utf8');
            if (Buffer.byteLength(input) > 65536) throw new Error('Request exceeds 64 KiB');
            const request = validateRequest(JSON.parse(input));
            if (request.command === 'runtime-check') {
                const {metadata} = loadRuntime();
                metadata.chrome_executable = findChrome();
                process.stdout.write(JSON.stringify({ok: true, pages: [], runtime: metadata}));
            } else {
                const result = await bounded(async () => perform(request, await createSession(lifecycle)));
                process.stdout.write(JSON.stringify(result));
            }
        }
    } catch (error) { operationError = error; throw error; }
    finally {
        try { await closeOwnedBrowser(lifecycle); }
        catch (error) { if (!operationError) throw error; process.stderr.write(`${error.message}\n`); }
    }
}

if (require.main === module) main().catch(error => {
    process.stderr.write(`Massachusetts UCC browser error: ${error.message}\n`);
    process.exit(1);
});
module.exports = {validateRequest, verifySubmittedForm, createSession, perform, closeOwnedBrowser, isChallenge};
