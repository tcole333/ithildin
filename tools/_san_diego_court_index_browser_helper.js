#!/usr/bin/env node
/**
 * Anonymous browser transport for the San Diego Superior Court Index.
 *
 * Direct HTTP and headless Chromium currently receive Cloudflare verification,
 * while an ordinary headed Chrome session reaches the public forms
 * anonymously.  The helper follows those forms, exhausts every native result
 * page it discovers, and returns HTML to the Python parser.
 */

'use strict';

const INDEX_ORIGIN = 'https://courtindex.sdcourt.ca.gov';
const PARTY_SEARCH_URL = `${INDEX_ORIGIN}/CISPublic/namesearch`;
const CASE_SEARCH_URL = `${INDEX_ORIGIN}/CISPublic/casesearch`;

function debug(message) {
    if (process.env.SAN_DIEGO_COURT_INDEX_DEBUG === '1') {
        process.stderr.write(`[san-diego-court-index] ${message}\n`);
    }
}

function clean(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
}

function loadChromium() {
    const candidates = ['playwright', 'playwright-core'];
    const failures = [];
    for (const moduleName of candidates) {
        try {
            const loaded = require(moduleName);
            if (loaded.chromium) {
                debug(`using ${moduleName}`);
                return loaded.chromium;
            }
            failures.push(`${moduleName}: missing chromium export`);
        } catch (error) {
            failures.push(`${moduleName}: ${error.message}`);
        }
    }
    const error = new Error(
        `Playwright runtime not found (${failures.join('; ')})`
    );
    error.code = 'browser_runtime_missing';
    error.category = 'runtime';
    throw error;
}

async function retry(operation, maxAttempts) {
    let lastError;
    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
        try {
            return await operation();
        } catch (error) {
            lastError = error;
            debug(
                `attempt ${attempt}/${maxAttempts} failed: ` +
                `${error.message || String(error)}`
            );
            if (attempt < maxAttempts) {
                await new Promise(resolve => setTimeout(resolve, 350 * attempt));
            }
        }
    }
    throw lastError;
}

async function assertPublicPage(page) {
    const title = clean(await page.title());
    const bodyText = clean(await page.locator('body').innerText());
    if (
        /just a moment/i.test(title)
        || /performing security verification/i.test(bodyText)
        || /enable javascript and cookies to continue/i.test(bodyText)
    ) {
        const error = new Error(
            'San Diego Court Index requires interactive browser verification'
        );
        error.code = 'human_verification_required';
        error.status = 'human_required';
        error.category = 'access';
        throw error;
    }
}

function validateOfficialUrl(value, expectedPath) {
    const parsed = new URL(value);
    if (parsed.origin !== INDEX_ORIGIN || parsed.pathname !== expectedPath) {
        const error = new Error(
            `Unexpected San Diego Court Index URL: ${value}`
        );
        error.code = 'result_url_changed';
        error.status = 'source_changed';
        error.category = 'source_schema';
        throw error;
    }
}

async function goto(page, url, maxAttempts) {
    debug(`navigate ${url}`);
    await retry(
        () => page.goto(url, { waitUntil: 'domcontentloaded' }),
        maxAttempts
    );
    debug(`navigated ${page.url()}`);
    await assertPublicPage(page);
}

async function submitForm(page, fieldName, resultPath) {
    const field = page.locator(`[name="${fieldName}"]`).first();
    await field.waitFor({ state: 'visible' });
    const form = field.locator('xpath=ancestor::form').first();
    const submit = form.locator(
        'input[type="submit"], input[type="button"][value="Submit"], ' +
        'button[type="submit"], button:has-text("Submit")'
    ).first();
    if (await submit.count() === 0) {
        const error = new Error('Court Index form lacks its Submit control');
        error.code = 'submit_control_missing';
        error.status = 'source_changed';
        error.category = 'source_schema';
        throw error;
    }
    await Promise.all([
        page.waitForURL(url => url.pathname === resultPath),
        submit.click(),
    ]);
    await assertPublicPage(page);
}

async function resultPageUrls(page, resultPath) {
    return page.locator(`a[href*="${resultPath}"]`).evaluateAll(
        (links, expectedPath) => {
            const urls = new Map();
            for (const link of links) {
                const parsed = new URL(link.href, location.href);
                if (
                    parsed.origin !== location.origin
                    || parsed.pathname !== expectedPath
                ) {
                    continue;
                }
                const rawPage = parsed.searchParams.get('page');
                if (!rawPage || !/^\d+$/.test(rawPage)) {
                    continue;
                }
                urls.set(Number(rawPage), parsed.href);
            }
            return Array.from(urls.entries())
                .sort((left, right) => left[0] - right[0])
                .map(([, url]) => url);
        },
        resultPath
    );
}

function pageNumber(value) {
    const parsed = new URL(value);
    const raw = parsed.searchParams.get('page');
    return raw && /^\d+$/.test(raw) ? Number(raw) : 1;
}

async function currentPageNumber(page) {
    const bodyText = clean(await page.locator('body').innerText());
    const match = bodyText.match(/Search\s+Result\s+Page:\s*(\d+)/i);
    return match ? Number(match[1]) : pageNumber(page.url());
}

async function collectResultPages(
    page,
    resultPath,
    minimumInterval,
    maxAttempts
) {
    validateOfficialUrl(page.url(), resultPath);
    const pages = [];
    const queue = [];
    const queuedPageNumbers = new Set();
    const seenPageNumbers = new Set();
    let useCurrentPage = true;
    while (useCurrentPage || queue.length > 0) {
        if (!useCurrentPage) {
            const target = queue.shift();
            if (minimumInterval > 0) {
                await page.waitForTimeout(minimumInterval * 1000);
            }
            await goto(page, target.url, maxAttempts);
            validateOfficialUrl(page.url(), resultPath);
        }
        useCurrentPage = false;
        const currentUrl = page.url();
        const currentPage = await currentPageNumber(page);
        if (seenPageNumbers.has(currentPage)) {
            continue;
        }
        seenPageNumbers.add(currentPage);
        pages.push({
            url: currentUrl,
            html: await page.content(),
        });
        for (const discovered of await resultPageUrls(page, resultPath)) {
            validateOfficialUrl(discovered, resultPath);
            const discoveredPage = pageNumber(discovered);
            if (
                !queuedPageNumbers.has(discoveredPage)
                && !seenPageNumbers.has(discoveredPage)
            ) {
                queuedPageNumbers.add(discoveredPage);
                queue.push({
                    url: discovered,
                    page: discoveredPage,
                });
            }
        }
        queue.sort((left, right) => left.page - right.page);
    }
    pages.sort((left, right) => {
        const difference = pageNumber(left.url) - pageNumber(right.url);
        return difference || left.url.localeCompare(right.url);
    });
    return { ok: true, pages };
}

async function partySearch(
    page,
    selection,
    minimumInterval,
    maxAttempts
) {
    await goto(page, PARTY_SEARCH_URL, maxAttempts);
    const required = [
        'caseType',
        'site',
        'partyType',
        'fileDateBegin',
        'fileDateEnd',
        'lastname',
        'firstname',
    ];
    for (const field of required) {
        if (await page.locator(`[name="${field}"]`).count() === 0) {
            const error = new Error(
                `Court Index party form lacks ${field}`
            );
            error.code = 'party_form_changed';
            error.status = 'source_changed';
            error.category = 'source_schema';
            throw error;
        }
    }
    await page.locator('[name="caseType"]').selectOption(
        String(selection.case_type)
    );
    await page.locator('[name="site"]').selectOption(String(selection.site));
    await page.locator('[name="partyType"]').selectOption(
        String(selection.party_type)
    );
    await page.locator('[name="fileDateBegin"]').fill(
        String(selection.begin_year)
    );
    await page.locator('[name="fileDateEnd"]').fill(
        String(selection.end_year)
    );
    await page.locator('[name="lastname"]').fill(
        String(selection.last_name)
    );
    await page.locator('[name="firstname"]').fill(
        String(selection.first_name || '')
    );
    const birthDate = page.locator('[name="dateOfBirth"]');
    if (selection.date_of_birth && await birthDate.count() > 0) {
        await birthDate.fill(String(selection.date_of_birth));
    }
    await submitForm(page, 'lastname', '/CISPublic/viewname');
    return collectResultPages(
        page,
        '/CISPublic/viewname',
        minimumInterval,
        maxAttempts
    );
}

async function caseSearch(
    page,
    selection,
    minimumInterval,
    maxAttempts
) {
    await goto(page, CASE_SEARCH_URL, maxAttempts);
    const required = ['caseType', 'site', 'casenum'];
    for (const field of required) {
        if (await page.locator(`[name="${field}"]`).count() === 0) {
            const error = new Error(`Court Index case form lacks ${field}`);
            error.code = 'case_form_changed';
            error.status = 'source_changed';
            error.category = 'source_schema';
            throw error;
        }
    }
    await page.locator('[name="caseType"]').selectOption(
        String(selection.case_type)
    );
    await page.locator('[name="site"]').selectOption(String(selection.site));
    await page.locator('[name="casenum"]').fill(
        String(selection.case_number)
    );
    await submitForm(page, 'casenum', '/CISPublic/viewcase');
    return collectResultPages(
        page,
        '/CISPublic/viewcase',
        minimumInterval,
        maxAttempts
    );
}

async function caseDetail(page, selection, maxAttempts) {
    validateOfficialUrl(selection.detail_url, '/CISPublic/casedetail');
    await goto(page, selection.detail_url, maxAttempts);
    validateOfficialUrl(page.url(), '/CISPublic/casedetail');
    const bodyText = clean(await page.locator('body').innerText());
    if (!/View Case Detail/i.test(bodyText)) {
        const error = new Error(
            'Court Index case-detail page lacks its expected heading'
        );
        error.code = 'case_detail_marker_missing';
        error.status = 'source_changed';
        error.category = 'source_schema';
        throw error;
    }
    return {
        ok: true,
        url: page.url(),
        html: await page.content(),
    };
}

async function run(selection, timeout, minimumInterval, maxAttempts) {
    const chromium = loadChromium();
    const headless = process.env.SAN_DIEGO_COURT_INDEX_HEADLESS === '1';
    const browser = await chromium.launch({
        channel: process.env.SAN_DIEGO_COURT_INDEX_BROWSER_CHANNEL || 'chrome',
        headless,
        args: ['--no-first-run', '--no-default-browser-check'],
    });
    debug(`browser launched headless=${headless}`);
    browser.on('disconnected', () => debug('browser disconnected'));
    try {
        const context = await browser.newContext({
            locale: 'en-US',
            timezoneId: 'America/Los_Angeles',
        });
        const page = await context.newPage();
        debug('page created');
        page.setDefaultTimeout(timeout * 1000);
        page.setDefaultNavigationTimeout(timeout * 1000);

        if (selection.operation === 'party_search') {
            return await partySearch(
                page,
                selection,
                minimumInterval,
                maxAttempts
            );
        }
        if (selection.operation === 'case_search') {
            return await caseSearch(
                page,
                selection,
                minimumInterval,
                maxAttempts
            );
        }
        if (selection.operation === 'case_detail') {
            return await caseDetail(page, selection, maxAttempts);
        }
        if (selection.operation === 'probe') {
            const party = await partySearch(
                page,
                selection,
                minimumInterval,
                maxAttempts
            );
            if (minimumInterval > 0) {
                await page.waitForTimeout(minimumInterval * 1000);
            }
            const caseResult = await caseSearch(
                page,
                selection,
                minimumInterval,
                maxAttempts
            );
            if (minimumInterval > 0) {
                await page.waitForTimeout(minimumInterval * 1000);
            }
            const detail = await caseDetail(page, selection, maxAttempts);
            return {
                ok: true,
                party_search: party,
                case_search: caseResult,
                case_detail: detail,
            };
        }
        const error = new Error(
            `Unsupported Court Index operation: ${selection.operation}`
        );
        error.code = 'unsupported_operation';
        error.category = 'query_selection';
        throw error;
    } finally {
        await browser.close();
    }
}

async function main() {
    const selection = JSON.parse(process.argv[2]);
    const timeout = Number(process.argv[3]);
    const minimumInterval = Number(process.argv[4]);
    const maxAttempts = Number(process.argv[5]);
    const result = await run(
        selection,
        timeout,
        minimumInterval,
        maxAttempts
    );
    process.stdout.write(`${JSON.stringify(result)}\n`);
}

main().catch(error => {
    const payload = {
        ok: false,
        error: {
            code: error.code || 'browser_helper_failed',
            message: error.message || String(error),
            status: error.status || 'unavailable',
            category: error.category || 'transport',
            retryable: Boolean(error.retryable),
        },
    };
    process.stdout.write(`${JSON.stringify(payload)}\n`);
    process.exitCode = 1;
});
