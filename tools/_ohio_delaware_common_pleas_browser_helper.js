#!/usr/bin/env node
/**
 * Browser-session helper for Delaware County, Ohio CourtView eServices.
 *
 * CourtView builds every search, paging, case, and image action as a
 * session-bound Apache Wicket link.  This helper resolves those actions from
 * the rendered page each time and emits durable record data rather than the
 * temporary Wicket URLs.
 */

'use strict';

const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');

const BASE_URL = 'https://court.co.delaware.oh.us/eservices';
const HOME_URL = `${BASE_URL}/home.page`;
const DEFAULT_TIMEOUT_MS = Number(
    process.env.OHIO_DELAWARE_COURTS_BROWSER_TIMEOUT_MS || '90000'
);
const USER_DATA_DIR = process.env.OHIO_DELAWARE_COURTS_BROWSER_PROFILE ||
    path.join(process.cwd(), '.cache', 'ohio-delaware-common-pleas-browser');
const SESSION_STATE_PATH = path.join(USER_DATA_DIR, 'wicket-session-state.json');

class RuntimeDependencyError extends Error {}
class SourceChangedError extends Error {}
class QuerySelectionError extends Error {}
class DocumentUnavailableError extends Error {}

function clean(value) {
    return String(value ?? '').replace(/\s+/g, ' ').trim();
}

function optionValue(args, name, fallback = null) {
    const index = args.indexOf(name);
    if (index === -1) return fallback;
    if (index + 1 >= args.length) {
        throw new QuerySelectionError(`Missing value for ${name}`);
    }
    return args[index + 1];
}

function optionValues(args, name) {
    const values = [];
    for (let index = 0; index < args.length; index += 1) {
        if (args[index] === name) {
            if (index + 1 >= args.length) {
                throw new QuerySelectionError(`Missing value for ${name}`);
            }
            values.push(args[index + 1]);
            index += 1;
        }
    }
    return values;
}

function nonnegativeNumber(value, label) {
    const number = Number(value);
    if (!Number.isFinite(number) || number < 0) {
        throw new QuerySelectionError(`${label} must be a non-negative number`);
    }
    return number;
}

function loadChromium() {
    const override = process.env.OHIO_DELAWARE_COURTS_PLAYWRIGHT_MODULE;
    const candidates = override ? [override] : ['playwright', 'playwright-core'];
    const failures = [];
    for (const moduleName of candidates) {
        try {
            const loaded = require(moduleName);
            if (loaded.chromium) {
                return { chromium: loaded.chromium, moduleName };
            }
            failures.push(`${moduleName}: no chromium export`);
        } catch (error) {
            failures.push(`${moduleName}: ${error.message}`);
        }
    }
    throw new RuntimeDependencyError(
        `Playwright runtime not found (${failures.join('; ')})`
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
    const channel = process.env.OHIO_DELAWARE_COURTS_BROWSER_CHANNEL || 'chrome';
    let executable = null;
    if (channel === 'chrome') {
        executable = systemChromePath();
        if (!executable) {
            throw new RuntimeDependencyError(
                'Google Chrome was not found; select an installed Playwright browser ' +
                'with OHIO_DELAWARE_COURTS_BROWSER_CHANNEL'
            );
        }
    } else if (channel === 'chromium') {
        executable = chromium.executablePath();
        if (!executable || !fs.existsSync(executable)) {
            throw new RuntimeDependencyError('Playwright Chromium was not found');
        }
    }
    return {
        ok: true,
        node: process.version,
        playwright_module: moduleName,
        browser_channel: channel,
        browser_executable: executable,
        headed: process.env.OHIO_DELAWARE_COURTS_BROWSER_HEADLESS !== '1',
        profile_dir: USER_DATA_DIR,
        source_url: HOME_URL,
        platform_family: 'equivant_courtview_wicket',
    };
}

async function launchBrowser() {
    const info = runtimeInfo();
    const { chromium } = loadChromium();
    fs.mkdirSync(USER_DATA_DIR, { recursive: true });
    const options = {
        headless: !info.headed,
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
            'Close another Delaware CourtView helper using the same profile.'
        );
    }
    if (fs.existsSync(SESSION_STATE_PATH)) {
        try {
            const state = JSON.parse(fs.readFileSync(SESSION_STATE_PATH, 'utf8'));
            if (Array.isArray(state.cookies) && state.cookies.length) {
                await context.addCookies(state.cookies);
            }
        } catch (_error) {
            // The persistent Chrome profile remains usable when a stale state
            // snapshot cannot be loaded.
        }
    }
    const page = context.pages()[0] || await context.newPage();
    page.setDefaultTimeout(DEFAULT_TIMEOUT_MS);
    page.setDefaultNavigationTimeout(DEFAULT_TIMEOUT_MS);
    return { context, page, info };
}

async function saveSession(context) {
    try {
        await context.storageState({ path: SESSION_STATE_PATH });
    } catch (_error) {
        // Session persistence is an optimization; the rendered operation has
        // already supplied the authoritative result.
    }
}

async function searchFormReady(page) {
    return await page.locator(
        'form input[name="lastName"], form input[name="caseDscr"]'
    ).count().catch(() => 0) > 0;
}

async function challengePacket(page) {
    const observed = await page.evaluate(() => {
        const tidy = value => String(value || '').replace(/\s+/g, ' ').trim();
        const visible = element => {
            const box = element.getBoundingClientRect();
            const style = window.getComputedStyle(element);
            return box.width > 0 && box.height > 0 &&
                style.visibility !== 'hidden' && style.display !== 'none';
        };
        const images = [...document.images]
            .filter(visible)
            .map(image => ({
                alt: tidy(image.alt),
                src_path: (() => {
                    try { return new URL(image.src).pathname; } catch (_error) { return ''; }
                })(),
                width: image.naturalWidth || image.width,
                height: image.naturalHeight || image.height,
            }))
            .filter(image => !image.src_path.endsWith('/indicator.gif'));
        const inputs = [...document.querySelectorAll('input[type="text"]')]
            .filter(visible)
            .map(input => ({ name: input.name || null, id: input.id || null }));
        return {
            title: document.title,
            route: window.location.pathname,
            body_prefix: tidy(document.body?.innerText).slice(0, 700),
            visible_images: images,
            visible_text_inputs: inputs,
        };
    });
    return {
        operation: 'session',
        status: 'captcha_required',
        source_url: HOME_URL,
        access: {
            interactive_challenge: true,
            profile_dir: USER_DATA_DIR,
            next_action: 'Complete the visible CourtView challenge in the headed browser, then continue.',
        },
        observed,
    };
}

async function enterSearch(page, waitSeconds = 0) {
    await page.goto(HOME_URL, { waitUntil: 'domcontentloaded' });
    if (await searchFormReady(page)) return null;

    const publicLink = page.getByRole('link', { name: 'Click Here', exact: true });
    if (await publicLink.count().catch(() => 0)) {
        await publicLink.first().click().catch(() => null);
        await page.waitForLoadState('domcontentloaded').catch(() => null);
        await page.waitForTimeout(500);
    }
    if (await searchFormReady(page)) return null;

    const deadline = Date.now() + (waitSeconds * 1000);
    while (Date.now() < deadline) {
        if (await searchFormReady(page)) return null;
        await page.waitForTimeout(500);
    }
    return await challengePacket(page);
}

async function selectLargestPageSize(page) {
    const pageSize = page.locator('select[name="topSearchPanel:pageSize"]');
    if (!await pageSize.count().catch(() => 0)) return null;
    const options = await pageSize.locator('option').evaluateAll(nodes =>
        nodes.map(node => ({ text: node.textContent.trim(), value: node.value }))
    );
    const largest = options
        .map(option => ({ ...option, number: Number(option.text) }))
        .filter(option => Number.isFinite(option.number))
        .sort((left, right) => right.number - left.number)[0];
    if (!largest) return null;
    if (await pageSize.inputValue() !== largest.value) {
        const response = page.waitForResponse(candidate =>
            candidate.request().method() === 'POST' &&
            candidate.url().includes('/eservices/search.page')
        ).catch(() => null);
        await pageSize.selectOption(largest.value);
        await response;
    }
    return { selected: largest.number, options };
}

async function clickSearchTab(page, name, inputName) {
    if (await page.locator(`input[name="${inputName}"]`).count().catch(() => 0)) {
        return;
    }
    const link = page.getByRole('link', { name, exact: true });
    if (!await link.count().catch(() => 0)) {
        throw new SourceChangedError(`CourtView search tab was not found: ${name}`);
    }
    await link.first().click();
    await page.locator(`input[name="${inputName}"]`).waitFor({ state: 'visible' });
}

async function selectNativeValues(page, name, requested) {
    if (!requested.length) return [];
    const select = page.locator(`select[name="${name}"]`);
    if (!await select.count().catch(() => 0)) {
        throw new SourceChangedError(`CourtView filter was not found: ${name}`);
    }
    const options = await select.locator('option').evaluateAll(nodes =>
        nodes.map(node => ({ text: clean(node.textContent), value: node.value }))
    );
    const native = requested.map(value => {
        const key = clean(value).toLowerCase();
        const match = options.find(option =>
            clean(option.value).toLowerCase() === key ||
            clean(option.text).toLowerCase() === key ||
            clean(option.text).toLowerCase().startsWith(`(${key})`)
        );
        if (!match) {
            throw new QuerySelectionError(
                `Unknown ${name} value ${value}; choose a native code or label`
            );
        }
        return match.value;
    });
    await select.selectOption(native);
    return native.map(value => clean(value));
}

async function parseSearchPage(page, pageNumber) {
    const data = await page.evaluate(({ pageNumber }) => {
        const tidy = value => String(value || '').replace(/\s+/g, ' ').trim();
        const body = tidy(document.body.innerText);
        const count = body.match(/Showing\s+([\d,]+)\s+to\s+([\d,]+)\s+of\s+([\d,]+)/i);
        const table = document.querySelector('table#grid');
        const rows = table?.tBodies?.[0]
            ? [...table.tBodies[0].rows].map((row, rowIndex) => {
                const cells = [...row.cells].map(cell => tidy(cell.innerText));
                return {
                    party_company: cells[2] || null,
                    affiliation: cells[3] || null,
                    party_type: cells[4] || null,
                    case_number: cells[5] || null,
                    file_date: cells[6] || null,
                    case_status: cells[7] || null,
                    case_type: cells[8] || null,
                    date_of_birth: cells[9] || null,
                    source_page: pageNumber,
                    source_row: rowIndex + 1,
                    detail_link_present: Boolean(row.querySelector('a')),
                };
            })
            : [];
        return {
            rows,
            showing_from: count ? Number(count[1].replace(/,/g, '')) : null,
            showing_to: count ? Number(count[2].replace(/,/g, '')) : null,
            total_reported: count ? Number(count[3].replace(/,/g, '')) : rows.length,
            no_results: /no\s+(matching\s+)?records|no\s+results/i.test(body),
            next_present: Boolean(document.querySelector('a[title="Go to next page"]')),
        };
    }, { pageNumber });
    if (!Array.isArray(data.rows)) {
        throw new SourceChangedError('CourtView search results do not contain rows');
    }
    return data;
}

async function collectAllSearchPages(page) {
    const records = [];
    let total = null;
    let pageNumber = 1;
    const visited = new Set();
    while (true) {
        const packet = await parseSearchPage(page, pageNumber);
        if (total === null) total = packet.total_reported;
        for (const row of packet.rows) records.push(row);
        if (records.length >= total || !packet.next_present) break;
        const marker = `${packet.showing_from}:${packet.showing_to}:${records.length}`;
        if (visited.has(marker)) {
            throw new SourceChangedError('CourtView paging did not advance');
        }
        visited.add(marker);
        const next = page.locator('a[title="Go to next page"]');
        const response = page.waitForResponse(candidate =>
            candidate.url().includes('/eservices/searchresults.page')
        ).catch(() => null);
        await next.click();
        await response;
        pageNumber += 1;
    }
    if (total !== records.length) {
        throw new SourceChangedError(
            `CourtView reported ${total} occurrences but rendered ${records.length}`
        );
    }
    return {
        rows: records,
        total_reported: total,
        pages_fetched: pageNumber,
    };
}

async function submitSearch(page) {
    const submit = page.locator('input[name="submitLink"]');
    if (!await submit.count().catch(() => 0)) {
        throw new SourceChangedError('CourtView search submit control was not found');
    }
    await Promise.all([
        page.waitForURL(url => url.pathname.endsWith('/searchresults.page')),
        submit.click(),
    ]);
}

async function search(page, args) {
    const mode = optionValue(args, '--mode');
    if (!['person', 'company'].includes(mode)) {
        throw new QuerySelectionError('search requires --mode person or --mode company');
    }
    const challenge = await enterSearch(page);
    if (challenge) return challenge;
    const pageSize = await selectLargestPageSize(page);
    await clickSearchTab(page, 'Name', 'lastName');

    const lastName = clean(optionValue(args, '--last', ''));
    const firstName = clean(optionValue(args, '--first', ''));
    const middleName = clean(optionValue(args, '--middle', ''));
    const suffix = clean(optionValue(args, '--suffix', ''));
    const companyName = clean(optionValue(args, '--company', ''));
    if (mode === 'person' && !lastName) {
        throw new QuerySelectionError('person search requires --last');
    }
    if (mode === 'company' && !companyName) {
        throw new QuerySelectionError('company search requires --company');
    }
    await page.locator('input[name="lastName"]').fill(mode === 'person' ? lastName : '');
    await page.locator('input[name="firstName"]').fill(mode === 'person' ? firstName : '');
    await page.locator('input[name="middleName"]').fill(mode === 'person' ? middleName : '');
    await page.locator('input[name="companyName"]').fill(mode === 'company' ? companyName : '');
    if (suffix) await selectNativeValues(page, 'sffxCd', [suffix]);

    const selectedFilters = {
        case_types: await selectNativeValues(page, 'caseCd', optionValues(args, '--case-type')),
        case_statuses: await selectNativeValues(page, 'statCd', optionValues(args, '--case-status')),
        party_types: await selectNativeValues(page, 'ptyCd', optionValues(args, '--party-type')),
    };
    const dateFields = [
        ['--dob-from', 'dobDateRange:dateInputBegin'],
        ['--dob-to', 'dobDateRange:dateInputEnd'],
        ['--dod-from', 'dodDateRange:dateInputBegin'],
        ['--dod-to', 'dodDateRange:dateInputEnd'],
        ['--filed-from', 'fileDateRange:dateInputBegin'],
        ['--filed-to', 'fileDateRange:dateInputEnd'],
    ];
    const selectedDates = {};
    for (const [argument, field] of dateFields) {
        const value = clean(optionValue(args, argument, ''));
        if (value) await page.locator(`input[name="${field}"]`).fill(value);
        selectedDates[field] = value || null;
    }

    await submitSearch(page);
    const collected = await collectAllSearchPages(page);
    return {
        operation: 'search',
        status: collected.rows.length ? 'ok' : 'no_results',
        source_url: HOME_URL,
        platform_family: 'equivant_courtview_wicket',
        query: {
            mode,
            last_name: mode === 'person' ? lastName : null,
            first_name: mode === 'person' ? firstName : null,
            middle_name: mode === 'person' ? middleName : null,
            suffix: mode === 'person' ? suffix || null : null,
            company_name: mode === 'company' ? companyName : null,
            filters: selectedFilters,
            dates: selectedDates,
        },
        native_page_size: pageSize?.selected || null,
        native_page_size_options: pageSize?.options || [],
        total_reported: collected.total_reported,
        pages_fetched: collected.pages_fetched,
        rows: collected.rows,
    };
}

function identityJson(value) {
    const keys = Object.keys(value).sort();
    const ordered = {};
    for (const key of keys) ordered[key] = value[key];
    return JSON.stringify(ordered);
}

function docketIdentity(caseNumber, row) {
    return {
        case_number: clean(caseNumber),
        date: clean(row.date),
        description: clean(row.description),
        docket_text: clean(row.docket_text),
        amount_owed: clean(row.amount_owed),
        amount_due: clean(row.amount_due),
        duplicate_ordinal: Number(row.duplicate_ordinal),
    };
}

function derivedId(prefix, value) {
    return `${prefix}-${crypto.createHash('sha256')
        .update(identityJson(value), 'utf8')
        .digest('hex').slice(0, 24)}`;
}

async function parseCaseDetail(page, expectedCaseNumber) {
    const raw = await page.evaluate(() => {
        const tidy = value => String(value || '').replace(/\s+/g, ' ').trim();
        const paired = (root, labelSelector, valueSelector) => {
            const labels = [...root.querySelectorAll(labelSelector)];
            return labels.map(label => ({
                label: tidy(label.innerText).replace(/:$/, ''),
                value: tidy(label.nextElementSibling?.matches(valueSelector)
                    ? label.nextElementSibling.innerText
                    : ''),
            }));
        };
        const summary = {};
        const header = document.querySelector('#caseHeader');
        if (header) {
            for (const item of paired(header, '.caseHdrLabel', '.caseHdrInfo')) {
                summary[item.label] = item.value || null;
            }
        }
        const parties = [...document.querySelectorAll('#ptyContainer > .rowodd, #ptyContainer > .roweven')]
            .map(section => {
                const personal = Object.fromEntries(
                    paired(section, '.ptyPersLabel', '.ptyPersInfo')
                        .map(item => [item.label, item.value || null])
                );
                const contact = Object.fromEntries(
                    paired(section, '.ptyContactLabel', '.ptyContactInfo')
                        .map(item => [item.label, item.value || null])
                );
                const attorneys = [...section.querySelectorAll('.ptyAtty .rowodd, .ptyAtty .roweven')]
                    .map(attorney => Object.fromEntries(
                        paired(attorney, '.ptyAttyLabel', '.ptyAttyInfo')
                            .map(item => [item.label, item.value || null])
                    ));
                return {
                    name: tidy(section.querySelector('.ptyInfoLabel')?.innerText) || null,
                    party_type: tidy(section.querySelector('.ptyType')?.innerText)
                        .replace(/^[-\s]+/, '') || null,
                    personal,
                    contact,
                    aliases: [...section.querySelectorAll('.ptyAffl .displayData')]
                        .map(alias => tidy(alias.innerText)).filter(Boolean),
                    attorneys,
                };
            });
        const tables = [...document.querySelectorAll('table')].map(table => ({
            element: table,
            headers: [...table.querySelectorAll('th')].map(header => tidy(header.innerText)),
        }));
        const docketTable = tables.find(table => table.headers.includes('Docket Text'));
        const docket = docketTable?.element?.tBodies?.[0]
            ? [...docketTable.element.tBodies[0].rows].map(row => {
                const cells = [...row.cells].map(cell => tidy(cell.innerText));
                return {
                    date: cells[0] || null,
                    description: cells[1] || null,
                    docket_text: cells[2] || null,
                    amount_owed: cells[3] || null,
                    amount_due: cells[4] || null,
                    document_link_present: Boolean(row.querySelector('a.dktImage')),
                };
            }) : [];
        const eventTable = tables.find(table => table.headers.includes('Event Judge'));
        const events = eventTable?.element?.tBodies?.[0]
            ? [...eventTable.element.tBodies[0].rows].map(row => {
                const cells = [...row.cells].map(cell => tidy(cell.innerText));
                return {
                    date_time: cells[0] || null,
                    location: cells[1] || null,
                    event_type: cells[2] || null,
                    result: cells[3] || null,
                    judge: cells[4] || null,
                };
            }) : [];
        const financial = tables
            .filter(table => table !== docketTable && table !== eventTable)
            .map(table => ({
                headers: table.headers,
                rows: table.element.tBodies?.[0]
                    ? [...table.element.tBodies[0].rows].map(row =>
                        [...row.cells].map(cell => tidy(cell.innerText)))
                    : [],
            }));
        const detailPagingControls = [...document.querySelectorAll(
            '#CaseDetailPanelTabSection a[title*="page" i]'
        )].map(link => ({
            title: tidy(link.title),
            text: tidy(link.innerText),
        }));
        return {
            title: tidy(document.querySelector('h1 .caseHdrTitle, h1')?.innerText),
            summary,
            parties,
            docket,
            events,
            financial,
            detail_paging_controls: detailPagingControls,
            route: window.location.pathname,
        };
    });
    if (!raw.title || !raw.route.endsWith('/searchresults.page')) {
        throw new SourceChangedError('CourtView case detail did not render');
    }
    const duplicateCounts = new Map();
    raw.docket = raw.docket.map((row, sourceIndex) => {
        const base = [
            clean(row.date), clean(row.description), clean(row.docket_text),
            clean(row.amount_owed), clean(row.amount_due),
        ].join('\u001f');
        const duplicateOrdinal = (duplicateCounts.get(base) || 0) + 1;
        duplicateCounts.set(base, duplicateOrdinal);
        const withIdentity = {
            ...row,
            source_index: sourceIndex + 1,
            duplicate_ordinal: duplicateOrdinal,
        };
        if (row.document_link_present) {
            withIdentity.document_id = derivedId(
                'dktdoc', docketIdentity(expectedCaseNumber, withIdentity)
            );
            withIdentity.document_access_state = 'link_present';
        } else {
            withIdentity.document_id = null;
            withIdentity.document_access_state = 'not_listed';
        }
        return withIdentity;
    });
    return {
        case_number: clean(expectedCaseNumber),
        caption: raw.title,
        summary: raw.summary,
        parties: raw.parties,
        docket: raw.docket,
        events: raw.events,
        financial_tables: raw.financial,
        detail_paging_controls: raw.detail_paging_controls,
    };
}

async function openExactCase(page, caseNumber) {
    const requested = clean(caseNumber);
    if (!requested) throw new QuerySelectionError('case number cannot be blank');
    const challenge = await enterSearch(page);
    if (challenge) return challenge;
    await selectLargestPageSize(page);
    await clickSearchTab(page, 'Case Number', 'caseDscr');
    await page.locator('input[name="caseDscr"]').fill(requested);
    await submitSearch(page);
    const pageData = await parseSearchPage(page, 1);
    const exact = pageData.rows.filter(row =>
        clean(row.case_number).toUpperCase() === requested.toUpperCase()
    );
    if (!exact.length) {
        return {
            operation: 'case',
            status: 'no_results',
            source_url: HOME_URL,
            requested_case_number: requested,
            occurrences: [],
            case: null,
        };
    }
    const rows = page.locator('table#grid tbody tr');
    let clicked = false;
    for (let index = 0; index < await rows.count(); index += 1) {
        const row = rows.nth(index);
        const cells = await row.locator('td').allInnerTexts();
        if (clean(cells[5]).toUpperCase() !== requested.toUpperCase()) continue;
        const link = row.locator('a').filter({ hasText: requested }).first();
        if (await link.count()) {
            await link.click();
            clicked = true;
            break;
        }
    }
    if (!clicked) {
        throw new SourceChangedError('CourtView exact case row had no detail action');
    }
    await page.locator('#caseHeader').waitFor({ state: 'visible' });
    const caseRecord = await parseCaseDetail(page, exact[0].case_number);
    return {
        operation: 'case',
        status: 'ok',
        source_url: HOME_URL,
        requested_case_number: requested,
        occurrences: exact,
        case: caseRecord,
    };
}

async function capturePdfResponse(context, action, timeoutMs) {
    return await new Promise(async (resolve, reject) => {
        let settled = false;
        const finish = (callback, value) => {
            if (settled) return;
            settled = true;
            clearTimeout(timer);
            context.off('response', listener);
            callback(value);
        };
        const listener = response => {
            const contentType = response.headers()['content-type'] || '';
            if (/application\/pdf/i.test(contentType)) finish(resolve, response);
        };
        const timer = setTimeout(() => finish(
            reject,
            new DocumentUnavailableError('CourtView did not return a PDF for this docket image')
        ), timeoutMs);
        context.on('response', listener);
        try {
            await action();
        } catch (error) {
            finish(reject, error);
        }
    });
}

async function downloadDocument(context, page, caseNumber, documentId, destination) {
    const packet = await openExactCase(page, caseNumber);
    if (packet.status !== 'ok') {
        return { ...packet, operation: 'document', requested_document_id: documentId };
    }
    const docket = packet.case.docket;
    const match = docket.find(row => row.document_id === documentId);
    if (!match) {
        throw new DocumentUnavailableError(
            `Document ${documentId} is not listed for case ${packet.case.case_number}`
        );
    }
    const docketTable = page.locator('table').filter({ has: page.locator('th', { hasText: 'Docket Text' }) }).first();
    const sourceRow = docketTable.locator('tbody tr').nth(match.source_index - 1);
    const link = sourceRow.locator('a.dktImage');
    if (!await link.count()) {
        throw new SourceChangedError('The selected docket image action disappeared');
    }
    const response = await capturePdfResponse(
        context,
        () => link.click(),
        Math.min(DEFAULT_TIMEOUT_MS, 30000)
    );
    if (!response.ok()) {
        throw new DocumentUnavailableError(
            `CourtView document response returned HTTP ${response.status()}`
        );
    }
    const bytes = await response.body();
    if (bytes.length < 5 || bytes.subarray(0, 5).toString('ascii') !== '%PDF-') {
        throw new DocumentUnavailableError('CourtView document response was not a PDF artifact');
    }
    const outputPath = path.resolve(destination);
    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    fs.writeFileSync(outputPath, bytes);
    return {
        operation: 'document',
        status: 'ok',
        source_url: HOME_URL,
        requested_case_number: clean(caseNumber),
        requested_document_id: documentId,
        case: {
            case_number: packet.case.case_number,
            caption: packet.case.caption,
        },
        document: match,
        artifact: {
            output_path: outputPath,
            content_type: response.headers()['content-type'] || null,
            byte_size: bytes.length,
            sha256: crypto.createHash('sha256').update(bytes).digest('hex'),
        },
    };
}

async function probe(page) {
    const challenge = await enterSearch(page);
    if (challenge) return { ...challenge, operation: 'probe' };
    const pageSize = await selectLargestPageSize(page);
    await clickSearchTab(page, 'Name', 'lastName');
    const contract = await page.evaluate(() => {
        const tidy = value => String(value || '').replace(/\s+/g, ' ').trim();
        const values = name => [...document.querySelectorAll(`select[name="${name}"] option`)]
            .map(option => ({ text: tidy(option.textContent), value: tidy(option.value) }));
        const footer = tidy(document.body.innerText).match(/Copyright\s+(\d{4})\s+v([\d.]+)/i);
        return {
            route: window.location.pathname,
            form_method: document.querySelector('form')?.method?.toLowerCase() || null,
            person_fields: ['lastName', 'firstName', 'middleName', 'sffxCd']
                .filter(name => document.querySelector(`[name="${name}"]`)),
            company_field: Boolean(document.querySelector('[name="companyName"]')),
            date_fields: [
                'dobDateRange:dateInputBegin', 'dobDateRange:dateInputEnd',
                'dodDateRange:dateInputBegin', 'dodDateRange:dateInputEnd',
                'fileDateRange:dateInputBegin', 'fileDateRange:dateInputEnd',
            ].filter(name => document.querySelector(`[name="${name}"]`)),
            option_sets: {
                case_type: values('caseCd'),
                case_status: values('statCd'),
                party_type: values('ptyCd'),
                suffix: values('sffxCd'),
            },
            courtview_version: footer ? footer[2] : null,
            copyright_year: footer ? Number(footer[1]) : null,
        };
    });
    if (contract.form_method !== 'post' || !contract.company_field) {
        throw new SourceChangedError('CourtView rendered search contract changed');
    }
    return {
        operation: 'probe',
        status: 'ok',
        source_url: HOME_URL,
        platform_family: 'equivant_courtview_wicket',
        native_page_size: pageSize?.selected || null,
        native_page_size_options: pageSize?.options || [],
        contract,
    };
}

async function execute(operation, args) {
    if (operation === 'runtime-check') return runtimeInfo();
    const { context, page, info } = await launchBrowser();
    try {
        let result;
        if (operation === 'warmup') {
            const waitSeconds = nonnegativeNumber(
                optionValue(args, '--wait-seconds', '0'), '--wait-seconds'
            );
            const challenge = await enterSearch(page, waitSeconds);
            result = challenge || {
                operation: 'warmup',
                status: 'ok',
                source_url: HOME_URL,
                session_ready: true,
            };
        } else if (operation === 'probe') {
            result = await probe(page);
        } else if (operation === 'search') {
            result = await search(page, args);
        } else if (operation === 'case') {
            result = await openExactCase(page, args[0]);
        } else if (operation === 'document') {
            if (args.length < 3) {
                throw new QuerySelectionError(
                    'document requires case number, document ID, and destination'
                );
            }
            result = await downloadDocument(context, page, args[0], args[1], args[2]);
        } else {
            throw new QuerySelectionError(`Unknown operation: ${operation}`);
        }
        result.runtime = {
            playwright_module: info.playwright_module,
            browser_channel: info.browser_channel,
            headed: info.headed,
            profile_dir: info.profile_dir,
        };
        return result;
    } finally {
        await saveSession(context);
        await context.close();
    }
}

function emit(payload) {
    process.stdout.write(`${JSON.stringify(payload)}\n`);
}

async function main() {
    const [operation, ...args] = process.argv.slice(2);
    if (!operation) throw new QuerySelectionError('An operation is required');
    try {
        emit(await execute(operation, args));
    } catch (error) {
        const status = error instanceof RuntimeDependencyError
            ? 'runtime_unavailable'
            : error instanceof SourceChangedError
                ? 'source_changed'
                : error instanceof QuerySelectionError
                    ? 'query_invalid'
                    : error instanceof DocumentUnavailableError
                        ? 'document_unavailable'
                        : 'unavailable';
        emit({
            status,
            error: error.message,
            error_type: error.constructor.name,
            source_url: HOME_URL,
        });
        process.exitCode = 1;
    }
}

module.exports = {
    clean,
    docketIdentity,
    derivedId,
};

if (require.main === module) {
    main();
}
