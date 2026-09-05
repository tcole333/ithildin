#!/usr/bin/env node
/**
 * Broward County AcclaimWeb browser-session helper.
 *
 * The public Official Records portal uses a disclaimer, Cloudflare browser
 * state, and server-side search state.  This helper follows the public UI,
 * captures the portal's own grid JSON, and keeps ephemeral document-image
 * tokens inside the short-lived browser session that issued them.
 *
 * Usage:
 *   node tools/_broward_official_records_browser_helper.js runtime-check
 *   node tools/_broward_official_records_browser_helper.js probe
 *   node tools/_broward_official_records_browser_helper.js name \
 *       "EPSTEIN, JEFFREY" --from 01/01/1977 --to 07/30/2026
 *   node tools/_broward_official_records_browser_helper.js parcel \
 *       514223CB0580 --from 01/01/1977 --to 07/30/2026
 *   node tools/_broward_official_records_browser_helper.js instrument 114957232
 *   node tools/_broward_official_records_browser_helper.js detail 114957232
 *   node tools/_broward_official_records_browser_helper.js download \
 *       114957232 /tmp/114957232.pdf
 */

'use strict';

const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');

const BASE_URL = 'https://officialrecords.broward.org/AcclaimWeb';
const SEARCH_PATHS = {
    name: '/search/SearchTypeName',
    parcel: '/search/SearchTypeParcel',
    instrument: '/search/SearchTypeInstrumentNumber',
};
const USER_DATA_DIR = process.env.BROWARD_OR_BROWSER_CACHE_DIR ||
    path.join(process.cwd(), '.cache', 'broward-official-records-browser');
const DEFAULT_TIMEOUT = Number(
    process.env.BROWARD_OR_BROWSER_TIMEOUT_MS || '90000'
);

class RuntimeDependencyError extends Error {}
class SourceChangedError extends Error {}
class RecordNotFoundError extends Error {}
class DocumentUnavailableError extends Error {}

function clean(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
}

function loadChromium() {
    const override = process.env.BROWARD_OR_PLAYWRIGHT_MODULE;
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
    const channel = process.env.BROWARD_OR_BROWSER_CHANNEL || 'chrome';
    let executable = null;
    if (channel === 'chrome') {
        executable = systemChromePath();
        if (!executable) {
            throw new RuntimeDependencyError(
                'Google Chrome was not found. Set ' +
                'BROWARD_OR_BROWSER_CHANNEL=chromium after installing the ' +
                'Playwright Chromium runtime.'
            );
        }
    } else if (channel === 'chromium') {
        executable = chromium.executablePath();
        if (!executable || !fs.existsSync(executable)) {
            throw new RuntimeDependencyError(
                'Playwright Chromium was not found. Run: ' +
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
        headless: process.env.BROWARD_OR_BROWSER_HEADLESS === '1',
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
            'Close another Broward Official Records helper if one is running.'
        );
    }
    const page = context.pages()[0] || await context.newPage();
    page.setDefaultTimeout(DEFAULT_TIMEOUT);
    page.setDefaultNavigationTimeout(DEFAULT_TIMEOUT);
    return { context, page };
}

async function waitForPortal(page) {
    const deadline = Date.now() + DEFAULT_TIMEOUT;
    while (Date.now() < deadline) {
        const accept = page.getByRole(
            'button',
            { name: 'I accept the conditions above.', exact: true }
        );
        if (await accept.count().catch(() => 0)) {
            if (await accept.first().isVisible().catch(() => false)) {
                await accept.first().click();
            }
        }
        const officialRecords = page.getByRole(
            'heading',
            { name: 'Official Records Search', exact: true }
        );
        const release = page.getByText(/Released through Instrument Number:/i);
        if (
            await officialRecords.count().catch(() => 0) ||
            await release.count().catch(() => 0)
        ) {
            return;
        }
        await page.waitForTimeout(500);
    }
    const body = clean(
        await page.locator('body').innerText().catch(() => '')
    ).slice(0, 500);
    throw new SourceChangedError(
        `The Broward public portal did not reach its search UI: ${body}`
    );
}

async function enterPortal(page) {
    await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded' });
    await waitForPortal(page);
}

async function openSearch(page, kind) {
    const route = SEARCH_PATHS[kind];
    if (!route) throw new Error(`Unsupported search kind: ${kind}`);
    await enterPortal(page);
    await page.goto(`${BASE_URL}${route}`, { waitUntil: 'domcontentloaded' });
    await waitForPortal(page);
    await page.getByRole(
        'button',
        { name: 'Search', exact: true }
    ).first().waitFor({ state: 'visible' });
}

async function fillFirst(page, selectors, value, description) {
    for (const selector of selectors) {
        const input = page.locator(selector).first();
        if (await input.count().catch(() => 0)) {
            await input.fill(value);
            return selector;
        }
    }
    throw new SourceChangedError(
        `The ${description} input was not found (${selectors.join(', ')})`
    );
}

async function maybeFill(page, selectors, value) {
    if (!value) return null;
    for (const selector of selectors) {
        const input = page.locator(selector).first();
        if (await input.count().catch(() => 0)) {
            await input.fill(value);
            return selector;
        }
    }
    return null;
}

function isGridResponse(response) {
    return response.url().includes('/AcclaimWeb/Search/GridResults') &&
        response.request().method() === 'POST';
}

async function gridResponseFor(page, action) {
    const responsePromise = page.waitForResponse(isGridResponse);
    await action();
    const response = await responsePromise;
    if (!response.ok()) {
        throw new Error(
            `Broward grid returned HTTP ${response.status()}`
        );
    }
    const payload = await response.json();
    if (
        !payload ||
        !Array.isArray(payload.data) ||
        !Number.isFinite(Number(payload.total))
    ) {
        throw new SourceChangedError(
            'Broward grid response no longer contains data[] and total'
        );
    }
    return {
        data: payload.data,
        total: Number(payload.total),
        response_url: response.url(),
    };
}

async function releaseMetadata(page) {
    const body = clean(await page.locator('body').innerText());
    const match = body.match(
        /Released through date:\s*([^|]+)\|\s*Released through Instrument Number:\s*([^|]+)\|\s*As of\s*([0-9/]+\s+[0-9:]+\s+[AP]M)/i
    );
    return match
        ? {
            released_through_date: clean(match[1]),
            released_through_instrument: clean(match[2]),
            release_as_of: clean(match[3]),
        }
        : {};
}

async function remainingGridPages(page, initial, maxPages) {
    const batches = [initial];
    let returned = initial.data.length;
    let priorSignature = JSON.stringify(initial.data.slice(0, 2));
    while (returned < initial.total && batches.length < maxPages) {
        const next = page.getByRole(
            'link',
            { name: 'next', exact: true }
        ).last();
        if (!await next.count().catch(() => 0)) break;
        const batch = await gridResponseFor(page, () => next.click());
        const signature = JSON.stringify(batch.data.slice(0, 2));
        if (signature === priorSignature) break;
        batches.push(batch);
        returned += batch.data.length;
        priorSignature = signature;
        if (!batch.data.length) break;
    }
    return {
        data: batches.flatMap(batch => batch.data),
        total: initial.total,
        pages_retrieved: batches.length,
        truncated: returned < initial.total,
        response_url: initial.response_url,
    };
}

async function submitSearch(page, kind, options = {}) {
    await openSearch(page, kind);
    if (kind === 'name') {
        await fillFirst(
            page,
            ['input[name="SearchOnName"]', '#SearchOnName'],
            options.query,
            'party name'
        );
        await maybeFill(
            page,
            ['input[name="RecordDateFrom"]', '#RecordDateFrom'],
            options.fromDate
        );
        await maybeFill(
            page,
            ['input[name="RecordDateTo"]', '#RecordDateTo'],
            options.toDate
        );
        const radios = page.locator('input[type="radio"]');
        const directionIndex = {
            all: 0,
            grantor: 1,
            grantee: 2,
        }[options.direction || 'all'];
        if (
            directionIndex !== undefined &&
            await radios.count() > directionIndex
        ) {
            await radios.nth(directionIndex).check();
        }
    } else if (kind === 'parcel') {
        await fillFirst(
            page,
            ['input[name="ParcelNumber"]', '#ParcelNumber'],
            options.query,
            'parcel number'
        );
        await maybeFill(
            page,
            ['input[name="RecordDateFrom"]', '#RecordDateFrom',
                'input[name="DateFrom"]', '#FromDatePicker'],
            options.fromDate
        );
        await maybeFill(
            page,
            ['input[name="RecordDateTo"]', '#RecordDateTo',
                'input[name="DateTo"]', '#ToDatePicker'],
            options.toDate
        );
    } else if (kind === 'instrument') {
        await fillFirst(
            page,
            ['input[name="InstrumentNumber"]', '#InstrumentNumber'],
            options.query,
            'instrument number'
        );
    }

    const initial = await gridResponseFor(page, () =>
        page.getByRole('button', { name: 'Search', exact: true }).first().click()
    );
    const collected = await remainingGridPages(
        page,
        initial,
        Number(options.maxPages || 1)
    );
    return {
        ...collected,
        query: options.query,
        search_kind: kind,
        direction: kind === 'name' ? options.direction || 'all' : null,
        parcel_match_mode: kind === 'parcel' ? 'source_configured' : null,
        from_date: options.fromDate || null,
        to_date: options.toDate || null,
        source_url: page.url(),
        release: await releaseMetadata(page),
    };
}

function comparableInstrument(value) {
    return clean(value).replace(/\D/g, '');
}

function exactInstrumentRows(payload, instrument) {
    const expected = comparableInstrument(instrument);
    return payload.data.filter(
        row => comparableInstrument(row.InstrumentNumber) === expected
    );
}

async function instrumentSearch(page, instrument) {
    const payload = await submitSearch(page, 'instrument', {
        query: instrument,
        maxPages: 1,
    });
    const exact = exactInstrumentRows(payload, instrument);
    return {
        ...payload,
        data: exact,
        exact_match_found: exact.length > 0,
        search_window_total: payload.total,
        search_window_first_instrument: payload.data.length
            ? clean(payload.data[0].InstrumentNumber)
            : null,
        search_window_last_instrument: payload.data.length
            ? clean(payload.data[payload.data.length - 1].InstrumentNumber)
            : null,
        total: exact.length,
        truncated: false,
    };
}

async function waitForDetailPage(context, searchPage, instrument) {
    const expected = comparableInstrument(instrument);
    const cells = searchPage.locator('td');
    let exactCell = null;
    for (let index = 0; index < await cells.count(); index += 1) {
        const cell = cells.nth(index);
        if (clean(await cell.innerText()) === expected) {
            exactCell = cell;
            break;
        }
    }
    if (!exactCell) {
        throw new RecordNotFoundError(
            `Instrument ${instrument} was not found in the source window`
        );
    }

    let detailsHtml = null;
    let detailsUrl = null;
    const responseListener = async response => {
        if (!/\/details\/documentdetails\//i.test(response.url())) return;
        try {
            detailsHtml = await response.text();
            detailsUrl = response.url();
        } catch (_) {
            // The rendered page remains available as a fallback.
        }
    };
    context.on('response', responseListener);
    const popupPromise = context.waitForEvent(
        'page',
        { timeout: 15000 }
    ).catch(() => null);
    const samePagePromise = searchPage.waitForURL(
        /\/AcclaimWeb\/Details/i,
        { timeout: 15000 }
    ).then(() => searchPage).catch(() => null);
    await exactCell.locator('xpath=ancestor::tr[1]').click();
    const detailPage = await Promise.race([
        popupPromise,
        samePagePromise,
    ]) || searchPage;
    await detailPage.waitForLoadState('domcontentloaded').catch(() => {});
    await detailPage.waitForURL(/\/AcclaimWeb\/Details/i, {
        timeout: DEFAULT_TIMEOUT,
    });
    const instrumentText = detailPage.getByText(
        new RegExp(`\\b${expected}\\b`)
    ).first();
    await instrumentText.waitFor({
        state: 'visible',
        timeout: DEFAULT_TIMEOUT,
    }).catch(() => {});
    const deadline = Date.now() + 15000;
    while (!detailsHtml && Date.now() < deadline) {
        await detailPage.waitForTimeout(100);
    }
    context.off('response', responseListener);

    const rendered = await detailPage.locator('body').evaluate(element => {
        const tidy = value => String(value || '')
            .replace(/\s+/g, ' ')
            .trim();
        const lines = value => String(value || '')
            .split(/\r?\n/)
            .map(tidy)
            .filter(Boolean);
        const tableRows = [];
        for (const row of element.querySelectorAll('tr')) {
            const cells = Array.from(
                row.querySelectorAll(':scope > th, :scope > td')
            );
            if (cells.length >= 2) {
                tableRows.push(cells.map(cell => lines(cell.innerText)));
            }
        }
        const fields = {};
        for (const label of element.querySelectorAll('label')) {
            const key = tidy(label.innerText).replace(/:\s*$/, '');
            if (!key) continue;
            const row = label.closest('tr');
            let values = [];
            if (row) {
                const cells = Array.from(
                    row.querySelectorAll(':scope > th, :scope > td')
                );
                values = cells.length >= 2
                    ? lines(cells[cells.length - 1].innerText)
                    : [];
            }
            if (!values.length) {
                const parent = label.parentElement;
                const sibling = parent ? parent.nextElementSibling : null;
                values = sibling ? lines(sibling.innerText) : [];
            }
            if (values.length) fields[key] = values;
        }
        const anchors = Array.from(element.querySelectorAll('a[href]')).map(
            anchor => ({
                text: tidy(anchor.innerText),
                title: tidy(anchor.getAttribute('title')),
                href: anchor.href,
            })
        );
        const token = element.querySelector('#hdnTransactionItemId')?.value ||
            element.querySelector('input[name="hdnTransactionItemId"]')?.value ||
            null;
        return {
            body_text: tidy(element.innerText),
            fields,
            table_rows: tableRows,
            anchors,
            retrieval_token: token,
        };
    });
    return {
        page: detailPage,
        details_html: detailsHtml,
        details_url: detailsUrl,
        rendered,
        source_url: detailPage.url(),
    };
}

async function preparePdf(detailPage, retrievalToken) {
    if (!retrievalToken) {
        return {
            available: false,
            state: 'retrieval_token_missing',
            page_count: null,
            pdf_url: null,
        };
    }
    const result = await detailPage.evaluate(async token => {
        const encode = value => encodeURIComponent(value);
        const startUrl = `/AcclaimWeb/Image/StartImageRetrieval/${encode(token)}/0`;
        const startResponse = await fetch(startUrl, {
            credentials: 'same-origin',
        });
        const startText = await startResponse.text();
        if (!startResponse.ok) {
            return {
                available: false,
                state: `start_http_${startResponse.status}`,
                start_text: startText.slice(0, 200),
                page_count: null,
                pdf_url: null,
            };
        }
        const viewerUrl = `/AcclaimWeb/Image/DocumentImage1/${encode(token)}`;
        const viewerResponse = await fetch(viewerUrl, {
            credentials: 'same-origin',
        });
        const viewerHtml = await viewerResponse.text();
        const pdfMatch = viewerHtml.match(
            /["']([^"']*\/Image\/DocumentPdfAllPages\/[^"']+)["']/i
        );
        const pageMatches = Array.from(
            viewerHtml.matchAll(/(?:pageCount|numberOfPages)\D{0,8}(\d+)/gi)
        );
        const pageCount = pageMatches.length
            ? Number(pageMatches[0][1])
            : null;
        return {
            available: viewerResponse.ok && Boolean(pdfMatch),
            state: pdfMatch ? 'public_pdf' : 'pdf_route_missing',
            start_text: startText.slice(0, 200),
            viewer_status: viewerResponse.status,
            viewer_url: new URL(viewerUrl, window.location.origin).toString(),
            pdf_url: pdfMatch
                ? new URL(pdfMatch[1], window.location.origin).toString()
                : null,
            page_count: pageCount,
        };
    }, retrievalToken);
    return result;
}

async function detailBundle(context, page, instrument) {
    const search = await instrumentSearch(page, instrument);
    if (!search.exact_match_found) {
        throw new RecordNotFoundError(
            `Instrument ${instrument} was not found`
        );
    }
    const detail = await waitForDetailPage(context, page, instrument);
    const image = await preparePdf(
        detail.page,
        detail.rendered.retrieval_token
    );
    return {
        found: true,
        instrument_number: comparableInstrument(instrument),
        search,
        detail: {
            source_url: detail.source_url,
            details_url: detail.details_url,
            details_html: detail.details_html,
            rendered: detail.rendered,
        },
        image,
    };
}

async function downloadPdf(
    context,
    page,
    instrument,
    destination,
    overwrite
) {
    const target = path.resolve(destination);
    const parent = path.dirname(target);
    if (!fs.existsSync(parent) || !fs.statSync(parent).isDirectory()) {
        throw new Error(`Destination directory does not exist: ${parent}`);
    }
    if (fs.existsSync(target) && !overwrite) {
        throw new Error(`Destination already exists: ${target}`);
    }

    const bundle = await detailBundle(context, page, instrument);
    if (!bundle.image.available || !bundle.image.pdf_url) {
        throw new DocumentUnavailableError(
            `Instrument ${instrument} does not expose a public all-pages PDF`
        );
    }
    const response = bundle.detail.rendered.retrieval_token
        ? await page.request.get(bundle.image.pdf_url)
        : null;
    if (!response || !response.ok()) {
        throw new DocumentUnavailableError(
            `The public PDF route returned HTTP ${response?.status() || 'unknown'}`
        );
    }
    const bytes = await response.body();
    const contentType = clean(response.headers()['content-type']).toLowerCase();
    if (
        !bytes.subarray(0, 5).equals(Buffer.from('%PDF-')) ||
        !contentType.includes('application/pdf')
    ) {
        throw new DocumentUnavailableError(
            'The document route did not return a validated PDF'
        );
    }
    fs.writeFileSync(target, bytes);
    return {
        downloaded: true,
        instrument_number: comparableInstrument(instrument),
        destination: target,
        byte_count: bytes.length,
        sha256: crypto.createHash('sha256').update(bytes).digest('hex'),
        mime_type: 'application/pdf',
        page_count: bundle.image.page_count,
        source_url: bundle.detail.source_url,
        retrieval_url_ephemeral: true,
    };
}

function optionValue(args, option, fallback = null) {
    const index = args.indexOf(option);
    return index >= 0 && args[index + 1] ? args[index + 1] : fallback;
}

function positiveIntegerOption(args, option, fallback) {
    const raw = optionValue(args, option, String(fallback));
    const value = Number(raw);
    if (!Number.isInteger(value) || value <= 0) {
        throw new Error(`${option} must be a positive integer`);
    }
    return value;
}

async function withBrowser(action) {
    const { context, page } = await launchBrowser();
    try {
        return await action(context, page);
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
        result = await withBrowser(async (_context, page) => {
            await enterPortal(page);
            const body = clean(await page.locator('body').innerText());
            const links = await page.locator('a[href*="/search/SearchType"]')
                .evaluateAll(elements => elements.map(element => ({
                    text: (element.textContent || '').replace(/\s+/g, ' ').trim(),
                    href: element.href,
                })));
            return {
                ok: true,
                title: await page.title(),
                source_url: page.url(),
                release: await releaseMetadata(page),
                search_routes: links,
                coverage_statements: body.match(
                    /All plats and maps[^.]*\.|Other Official Records[^.]*\.|Documents recorded from 3\/9\/1972[^.]*\.|Documents recorded prior to 3\/9\/1972[^.]*\./gi
                ) || [],
            };
        });
    } else if (command === 'name') {
        const query = args[1];
        if (!query) throw new Error('Party-name query is required');
        result = await withBrowser((_context, page) =>
            submitSearch(page, 'name', {
                query,
                direction: optionValue(args, '--direction', 'all'),
                fromDate: optionValue(args, '--from'),
                toDate: optionValue(args, '--to'),
                maxPages: positiveIntegerOption(args, '--max-pages', 10),
            })
        );
    } else if (command === 'parcel') {
        const query = args[1];
        if (!query) throw new Error('Parcel-number query is required');
        result = await withBrowser((_context, page) =>
            submitSearch(page, 'parcel', {
                query,
                fromDate: optionValue(args, '--from'),
                toDate: optionValue(args, '--to'),
                maxPages: positiveIntegerOption(args, '--max-pages', 10),
            })
        );
    } else if (command === 'instrument') {
        const instrument = args[1];
        if (!instrument) throw new Error('Instrument number is required');
        result = await withBrowser((_context, page) =>
            instrumentSearch(page, instrument)
        );
    } else if (command === 'detail') {
        const instrument = args[1];
        if (!instrument) throw new Error('Instrument number is required');
        result = await withBrowser((context, page) =>
            detailBundle(context, page, instrument)
        );
    } else if (command === 'download') {
        const instrument = args[1];
        const destination = args[2];
        if (!instrument || !destination) {
            throw new Error('download requires INSTRUMENT DESTINATION');
        }
        result = await withBrowser((context, page) =>
            downloadPdf(
                context,
                page,
                instrument,
                destination,
                args.includes('--overwrite')
            )
        );
    } else {
        throw new Error(
            'Usage: _broward_official_records_browser_helper.js ' +
            '{runtime-check|probe|name|parcel|instrument|detail|download}'
        );
    }
    process.stdout.write(`${JSON.stringify(result)}\n`);
}

main().catch(error => {
    const payload = {
        error: {
            type: error.name || 'Error',
            message: error.message || String(error),
        },
    };
    process.stderr.write(`${JSON.stringify(payload)}\n`);
    process.exit(1);
});
