#!/usr/bin/env node
/**
 * Wisconsin Supreme Court and Court of Appeals Case Access browser helper.
 *
 * WSCCA serves public data through a browser session that acknowledges the
 * source notice and completes the site's invisible hCaptcha validation. This
 * helper follows that published flow and emits the JSON returned by WSCCA's
 * own search and exact-case APIs. It never exports browser session state.
 *
 * Usage:
 *   node tools/_wisconsin_wscca_browser_helper.js runtime-check
 *   node tools/_wisconsin_wscca_browser_helper.js probe
 *   node tools/_wisconsin_wscca_browser_helper.js search \
 *       --scope business --query "Wisconsin Voter Alliance"
 *   node tools/_wisconsin_wscca_browser_helper.js case 2025AP000699
 *   node tools/_wisconsin_wscca_browser_helper.js download \
 *       2025AP000699 994970 /tmp/brief.pdf
 */

'use strict';

const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');

const BASE_URL = 'https://wscca.wicourts.gov';
const SENTINEL_CASE = '2025AP000699';
const DEFAULT_TIMEOUT_MS = 90000;

class RuntimeDependencyError extends Error {}

class SourceResponseError extends Error {
    constructor(message, details = {}) {
        super(message);
        this.name = 'SourceResponseError';
        this.details = details;
    }
}

class SourceChallengeError extends Error {
    constructor(message, details = {}) {
        super(message);
        this.name = 'SourceChallengeError';
        this.details = details;
    }
}

class DocumentStateError extends Error {
    constructor(message, details = {}) {
        super(message);
        this.name = 'DocumentStateError';
        this.details = details;
    }
}

function sleep(milliseconds) {
    return new Promise(resolve => setTimeout(resolve, milliseconds));
}

function clean(value) {
    return String(value ?? '').replace(/\s+/g, ' ').trim();
}

function optionValue(args, name, fallback = null) {
    const index = args.indexOf(name);
    if (index === -1) return fallback;
    if (index + 1 >= args.length) {
        throw new SourceResponseError(`Missing value for ${name}`);
    }
    return args[index + 1];
}

function hasOption(args, name) {
    return args.includes(name);
}

function positiveNumber(value, label) {
    const number = Number(value);
    if (!Number.isFinite(number) || number < 0) {
        throw new SourceResponseError(`${label} must be a non-negative number`);
    }
    return number;
}

function loadChromium() {
    const override = process.env.WSCCA_PLAYWRIGHT_MODULE;
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
    const channel = process.env.WSCCA_BROWSER_CHANNEL || 'chrome';
    let executable = null;
    if (channel === 'chrome') {
        executable = systemChromePath();
        if (!executable) {
            throw new RuntimeDependencyError(
                'Google Chrome was not found; set WSCCA_BROWSER_CHANNEL=chromium ' +
                'when a Playwright Chromium runtime is installed'
            );
        }
    } else if (channel === 'chromium') {
        executable = chromium.executablePath();
        if (!executable || !fs.existsSync(executable)) {
            throw new RuntimeDependencyError(
                'Playwright Chromium was not found; install that browser runtime'
            );
        }
    }
    return {
        ok: true,
        node: process.version,
        playwright_module: moduleName,
        browser_channel: channel,
        browser_executable: executable,
        headless: process.env.WSCCA_BROWSER_HEADLESS === '1',
        base_url: BASE_URL,
    };
}

async function launchBrowser() {
    const info = runtimeInfo();
    const { chromium } = loadChromium();
    const options = {
        headless: info.headless,
        args: ['--no-first-run', '--no-default-browser-check'],
    };
    if (info.browser_channel === 'chrome') {
        options.channel = 'chrome';
    }
    const browser = await chromium.launch(options);
    const context = await browser.newContext({
        viewport: { width: 1500, height: 1100 },
        locale: 'en-US',
        timezoneId: 'America/Chicago',
    });
    const page = await context.newPage();
    const timeout = positiveNumber(
        process.env.WSCCA_BROWSER_TIMEOUT_MS || DEFAULT_TIMEOUT_MS,
        'WSCCA_BROWSER_TIMEOUT_MS'
    );
    page.setDefaultTimeout(timeout);
    page.setDefaultNavigationTimeout(timeout);
    return { browser, context, page, info, timeout };
}

async function acknowledgePublicUse(page) {
    await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded' });
    const agree = page.getByRole('button', { name: 'I agree', exact: true });
    if (await agree.isVisible().catch(() => false)) {
        await agree.click();
    }
    await page.getByRole('heading', { name: 'Case search', exact: true })
        .waitFor({ state: 'visible' });
}

function attachValidationObserver(page) {
    const observed = {
        attempted: false,
        status: null,
        url: `${BASE_URL}/api/captcha/validate/search`,
    };
    const listener = response => {
        if (response.url() === observed.url) {
            observed.attempted = true;
            observed.status = response.status();
        }
    };
    page.on('response', listener);
    return {
        observed,
        detach: () => page.off('response', listener),
    };
}

async function responseJson(response, label) {
    const text = await response.text();
    try {
        return JSON.parse(text);
    } catch (error) {
        throw new SourceResponseError(
            `${label} returned non-JSON content`,
            {
                status: response.status(),
                content_type: response.headers()['content-type'] || null,
                body_prefix: text.slice(0, 240),
            }
        );
    }
}

function resultCount(payload) {
    const values = payload?.result?.p;
    const count = Array.isArray(values) ? Number(values[0]) : NaN;
    return Number.isFinite(count) && count >= 0 ? count : null;
}

function resultRows(payload) {
    const values = payload?.result?.p;
    if (!Array.isArray(values)) return [];
    for (const value of values) {
        if (Array.isArray(value)) return value;
    }
    return [];
}

async function captureCase(page, caseNumber, timeout) {
    const normalized = clean(caseNumber).toUpperCase();
    if (!normalized) {
        throw new SourceResponseError('Case number cannot be blank');
    }
    const apiUrl = `${BASE_URL}/api/case/${encodeURIComponent(normalized)}`;
    const validation = attachValidationObserver(page);
    const observedResponses = [];
    const responseListener = response => {
        const url = response.url();
        if (
            url.startsWith(`${BASE_URL}/api/`) ||
            url.includes('hcaptcha.com/getcaptcha')
        ) {
            observedResponses.push({
                method: response.request().method(),
                status: response.status(),
                url,
            });
        }
    };
    page.on('response', responseListener);
    try {
        const responsePromise = page.waitForResponse(
            response => (
                response.url() === apiUrl &&
                response.request().method() === 'GET' &&
                response.status() !== 403
            ),
            { timeout }
        );
        await page.goto(
            `${BASE_URL}/case/${encodeURIComponent(normalized)}`,
            { waitUntil: 'domcontentloaded' }
        );
        let response;
        try {
            response = await responsePromise;
        } catch (error) {
            const bodyText = clean(
                await page.locator('body').innerText().catch(() => '')
            );
            throw new SourceChallengeError(
                'WSCCA did not complete its public validation for the exact case',
                {
                    case_number: normalized,
                    source_url: page.url(),
                    validation: validation.observed,
                    observed_responses: observedResponses,
                    page_title: await page.title().catch(() => null),
                    page_text_prefix: bodyText.slice(0, 500),
                    captcha_frame_count: page.frames().filter(
                        frame => frame.url().includes('hcaptcha.com')
                    ).length,
                    cause: error.message,
                }
            );
        }
        const status = response.status();
        if (status === 404) {
            return {
                ok: true,
                operation: 'case',
                found: false,
                requested_case_number: normalized,
                source_url: page.url(),
                api_url: apiUrl,
                validation: validation.observed,
                source_status: status,
                result: null,
            };
        }
        if (status !== 200) {
            throw new SourceResponseError(
                `WSCCA exact-case API returned HTTP ${status}`,
                {
                    case_number: normalized,
                    api_url: apiUrl,
                    source_status: status,
                    validation: validation.observed,
                }
            );
        }
        const payload = await responseJson(response, 'WSCCA exact-case API');
        return {
            ok: true,
            operation: 'case',
            found: Boolean(payload?.result),
            requested_case_number: normalized,
            source_url: page.url(),
            api_url: apiUrl,
            validation: validation.observed,
            source_status: status,
            result: payload?.result ?? null,
            source_envelope: payload,
        };
    } finally {
        page.off('response', responseListener);
        validation.detach();
    }
}

async function fillSearchForm(page, selectors) {
    const scope = selectors.scope;
    if (scope === 'case-number') {
        await page.getByRole('textbox', { name: 'Case number', exact: true })
            .fill(selectors.query);
    } else if (scope === 'business') {
        await page.getByRole('textbox', { name: 'Business name', exact: true })
            .fill(selectors.query);
    } else if (scope === 'party') {
        await page.getByRole('textbox', { name: 'Last name', exact: true })
            .fill(selectors.query);
        if (selectors.first_name) {
            await page.getByRole('textbox', { name: 'First name', exact: true })
                .fill(selectors.first_name);
        }
        if (selectors.middle_name) {
            await page.getByRole('textbox', { name: 'Middle name', exact: true })
                .fill(selectors.middle_name);
        }
        if (selectors.exclude_missing_middle) {
            const includeMissing = page.getByRole(
                'checkbox',
                {
                    name: (
                        'When searching using a middle name, also show parties ' +
                        'without a middle name.'
                    ),
                    exact: true,
                }
            );
            if (await includeMissing.isChecked()) {
                await includeMissing.uncheck();
            }
        }
    } else {
        throw new SourceResponseError(`Unsupported search scope: ${scope}`);
    }

    if (selectors.similar_names) {
        const similar = page.getByRole(
            'checkbox',
            { name: 'Search similar names', exact: true }
        );
        if (!(await similar.isChecked())) {
            await similar.check();
        }
    }
    if (selectors.county) {
        const county = page.getByRole('combobox', { name: 'County', exact: true });
        try {
            await county.selectOption({ label: selectors.county });
        } catch (_) {
            await county.selectOption(selectors.county);
        }
    }
}

async function searchCases(page, selectors, timeout) {
    await fillSearchForm(page, selectors);

    let countPayload = null;
    let searchPayload = null;
    let countUrl = null;
    let searchUrl = null;
    const validation = attachValidationObserver(page);
    const responseTasks = new Set();
    const listener = response => {
        const url = response.url();
        if (
            response.request().method() !== 'POST' ||
            response.status() !== 200 ||
            !/^https:\/\/wscca\.wicourts\.gov\/api\/case-search\/[^/]+(?:\/count)?$/.test(url)
        ) {
            return;
        }
        const task = responseJson(response, 'WSCCA case-search API')
            .then(payload => {
                if (url.endsWith('/count')) {
                    countPayload = payload;
                    countUrl = url;
                } else {
                    searchPayload = payload;
                    searchUrl = url;
                }
            });
        responseTasks.add(task);
        task.finally(() => responseTasks.delete(task));
    };
    page.on('response', listener);
    try {
        try {
            await page.getByTitle('Save').click();
            await page.waitForURL(/\/case-search-results(?:\?|$)/, { timeout });
        } catch (error) {
            const bodyText = clean(
                await page.locator('body').innerText().catch(() => '')
            );
            throw new SourceChallengeError(
                'WSCCA did not complete its public validation for search',
                {
                    selectors,
                    source_url: page.url(),
                    validation: validation.observed,
                    page_title: await page.title().catch(() => null),
                    page_text_prefix: bodyText.slice(0, 500),
                    captcha_frame_count: page.frames().filter(
                        frame => frame.url().includes('hcaptcha.com')
                    ).length,
                    cause: error.message,
                }
            );
        }
        const deadline = Date.now() + timeout;
        while (Date.now() < deadline) {
            if (countPayload && (searchPayload || resultCount(countPayload) === 0)) {
                break;
            }
            await sleep(100);
        }
        await Promise.all(Array.from(responseTasks));
        if (!countPayload) {
            throw new SourceChallengeError(
                'WSCCA search did not return a source count',
                {
                    selectors,
                    source_url: page.url(),
                    validation: validation.observed,
                }
            );
        }
        const total = resultCount(countPayload);
        if (total === null) {
            throw new SourceResponseError(
                'WSCCA search count used an unrecognized response shape',
                { source_envelope: countPayload }
            );
        }
        if (total > 0 && !searchPayload) {
            throw new SourceResponseError(
                'WSCCA reported results but did not return a result page',
                {
                    total_reported: total,
                    source_url: page.url(),
                    validation: validation.observed,
                }
            );
        }
        const records = searchPayload ? resultRows(searchPayload) : [];
        const requestId = searchUrl
            ? searchUrl.split('/').filter(Boolean).at(-1)
            : null;
        return {
            ok: true,
            operation: 'search',
            selectors,
            source_url: page.url(),
            count_api_url: countUrl,
            search_api_url: searchUrl,
            temporary_search_id: requestId,
            validation: validation.observed,
            total_reported: total,
            records,
            source_count_envelope: countPayload,
            source_result_envelope: searchPayload,
        };
    } finally {
        page.off('response', listener);
        validation.detach();
    }
}

async function downloadDocument(context, page, caseNumber, documentId, destination, timeout) {
    const caseBundle = await captureCase(page, caseNumber, timeout);
    if (!caseBundle.found) {
        return {
            ...caseBundle,
            operation: 'download',
            requested_document_id: String(documentId),
        };
    }
    const numericDocumentId = Number(documentId);
    const documents = Array.isArray(caseBundle.result?.documents)
        ? caseBundle.result.documents
        : [];
    const document = documents.find(
        item => Number(item?.docId) === numericDocumentId
    );
    if (!document) {
        throw new DocumentStateError(
            'The requested document ID is not listed as a public document for this case',
            {
                case_number: caseBundle.result?.caseData?.sccaCaseNo || caseNumber,
                requested_document_id: String(documentId),
                listed_document_ids: documents.map(item => item?.docId),
                source_url: caseBundle.source_url,
            }
        );
    }
    const canonicalCase = caseBundle.result.caseData.sccaCaseNo;
    const sourceUrl = (
        `${BASE_URL}/api/case/${encodeURIComponent(canonicalCase)}` +
        `/document/${encodeURIComponent(String(document.docId))}`
    );
    const response = await context.request.get(sourceUrl, {
        headers: { Referer: caseBundle.source_url },
        timeout,
    });
    const status = response.status();
    const headers = response.headers();
    const body = await response.body();
    const mediaType = clean(headers['content-type']).split(';', 1)[0].toLowerCase();
    if (status !== 200) {
        throw new SourceResponseError(
            `WSCCA document API returned HTTP ${status}`,
            {
                case_number: canonicalCase,
                document_id: document.docId,
                source_url: sourceUrl,
                source_status: status,
                content_type: mediaType || null,
            }
        );
    }
    if (mediaType !== 'application/pdf' || body.subarray(0, 5).toString() !== '%PDF-') {
        throw new SourceResponseError(
            'WSCCA document response was not a PDF artifact',
            {
                case_number: canonicalCase,
                document_id: document.docId,
                source_url: sourceUrl,
                source_status: status,
                content_type: mediaType || null,
                body_prefix_hex: body.subarray(0, 16).toString('hex'),
            }
        );
    }
    const outputPath = path.resolve(destination);
    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    fs.writeFileSync(outputPath, body);
    return {
        ok: true,
        operation: 'download',
        found: true,
        requested_case_number: clean(caseNumber).toUpperCase(),
        requested_document_id: String(documentId),
        case_number: canonicalCase,
        court_type: caseBundle.result.caseData.courtType || null,
        case_source_url: caseBundle.source_url,
        source_url: sourceUrl,
        validation: caseBundle.validation,
        document,
        receipt: {
            local_path: outputPath,
            media_type: mediaType,
            byte_count: body.length,
            sha256: crypto.createHash('sha256').update(body).digest('hex'),
            source_status: status,
            content_length_header: headers['content-length'] || null,
            content_disposition: headers['content-disposition'] || null,
        },
    };
}

async function execute(operation, args) {
    if (operation === 'runtime-check') {
        return runtimeInfo();
    }

    const minimumIntervalSeconds = positiveNumber(
        optionValue(args, '--minimum-interval', '0.5'),
        '--minimum-interval'
    );
    const browserState = await launchBrowser();
    const { browser, context, page, timeout } = browserState;
    try {
        await acknowledgePublicUse(page);
        if (minimumIntervalSeconds) {
            await sleep(minimumIntervalSeconds * 1000);
        }
        if (operation === 'probe') {
            const sentinel = optionValue(args, '--case', SENTINEL_CASE);
            const result = await captureCase(page, sentinel, timeout);
            return {
                ok: result.ok,
                operation,
                source_url: result.source_url,
                api_url: result.api_url,
                validation: result.validation,
                sentinel_case: sentinel,
                canonical_case_number: result.result?.caseData?.sccaCaseNo || null,
                past_event_count: result.result?.pastEvents?.length || 0,
                document_count: result.result?.documents?.length || 0,
                case_found: result.found,
                runtime: browserState.info,
            };
        }
        if (operation === 'search') {
            const scope = optionValue(args, '--scope');
            const query = clean(optionValue(args, '--query'));
            if (!scope || !query) {
                throw new SourceResponseError(
                    'search requires --scope and a non-empty --query'
                );
            }
            return await searchCases(
                page,
                {
                    scope,
                    query,
                    first_name: clean(optionValue(args, '--first-name')),
                    middle_name: clean(optionValue(args, '--middle-name')),
                    county: clean(optionValue(args, '--county')),
                    similar_names: hasOption(args, '--similar-names'),
                    exclude_missing_middle: hasOption(
                        args,
                        '--exclude-missing-middle'
                    ),
                },
                timeout
            );
        }
        if (operation === 'case') {
            if (!args[0]) {
                throw new SourceResponseError('case requires an appeal number');
            }
            return await captureCase(page, args[0], timeout);
        }
        if (operation === 'download') {
            if (!args[0] || !args[1] || !args[2]) {
                throw new SourceResponseError(
                    'download requires an appeal number, document ID, and destination'
                );
            }
            return await downloadDocument(
                context,
                page,
                args[0],
                args[1],
                args[2],
                timeout
            );
        }
        throw new SourceResponseError(`Unknown operation: ${operation}`);
    } finally {
        await browser.close();
    }
}

async function main() {
    const operation = process.argv[2];
    if (!operation) {
        throw new SourceResponseError('An operation is required');
    }
    const result = await execute(operation, process.argv.slice(3));
    process.stdout.write(`${JSON.stringify(result)}\n`);
}

main().catch(error => {
    process.stdout.write(`${JSON.stringify({
        ok: false,
        error_type: error.name || 'Error',
        error: error.message,
        details: error.details || {},
    })}\n`);
    process.exitCode = 2;
});
