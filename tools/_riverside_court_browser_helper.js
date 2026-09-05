#!/usr/bin/env node
/**
 * Anonymous browser transport for Riverside Superior Court publications.
 *
 * The official court and eCalendar hosts currently return HTTP 403 to direct
 * clients while serving ordinary Chrome sessions.  Once loaded, eCalendar
 * exposes complete JSON arrays; its visible grid paging is client-side only.
 */

'use strict';

const CALENDAR_URL = 'https://ecourtcalendars.riverside.courts.ca.gov/';
const CALENDAR_ORIGIN = 'https://ecourtcalendars.riverside.courts.ca.gov';
const RULINGS_URL =
    'https://www.riverside.courts.ca.gov/online-services/tentative-rulings';
const COURT_ORIGIN = 'https://www.riverside.courts.ca.gov';

function debug(message) {
    if (process.env.RIVERSIDE_COURT_DEBUG === '1') {
        process.stderr.write(`[riverside-court] ${message}\n`);
    }
}

function clean(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
}

function normalizedDepartment(value) {
    return clean(value)
        .replace(/^department\s+/i, '')
        .replace(/\s+/g, '')
        .toUpperCase();
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

async function goto(page, url, maxAttempts) {
    const response = await retry(
        () => page.goto(url, { waitUntil: 'domcontentloaded' }),
        maxAttempts
    );
    const status = response ? response.status() : null;
    const title = clean(await page.title());
    const body = clean(await page.locator('body').innerText());
    if (
        (status !== null && status >= 400)
        || /\b403 forbidden\b/i.test(body)
        || /just a moment/i.test(title)
        || /performing security verification/i.test(body)
    ) {
        const error = new Error(
            `Riverside court browser transport was not admitted (${status})`
        );
        error.code = 'browser_access_unavailable';
        error.category = 'access';
        error.retryable = status === 429 || (status !== null && status >= 500);
        throw error;
    }
    return response;
}

async function sourceFetch(page, input, init = {}) {
    return page.evaluate(
        async ({ input: requestInput, init: requestInit }) => {
            const response = await fetch(requestInput, requestInit);
            const contentType = response.headers.get('content-type') || '';
            const text = await response.text();
            if (!response.ok) {
                throw new Error(
                    `source request failed ${response.status}: ${text.slice(0, 240)}`
                );
            }
            if (!/application\/json/i.test(contentType)) {
                throw new Error(
                    `source request returned ${contentType || 'unknown content type'}`
                );
            }
            return JSON.parse(text);
        },
        { input, init }
    );
}

function selectOne(candidates, rawSelection, kind, aliases = value => [value]) {
    if (!rawSelection) {
        return candidates;
    }
    const target = clean(rawSelection).toLowerCase();
    const matches = candidates.filter(candidate =>
        aliases(candidate).some(value => clean(value).toLowerCase() === target)
    );
    if (matches.length !== 1) {
        const error = new Error(
            `Riverside ${kind} selection matched ${matches.length} values: ` +
            `${rawSelection}`
        );
        error.code = matches.length === 0
            ? `unknown_${kind}`
            : `ambiguous_${kind}`;
        error.category = 'query_selection';
        error.details = {
            selection: rawSelection,
            choices: candidates.map(candidate => aliases(candidate)[0]),
        };
        throw error;
    }
    return matches;
}

async function calendar(page, selection, minimumInterval, maxAttempts) {
    await goto(page, CALENDAR_URL, maxAttempts);
    const courthouseSelect = page.getByLabel('Courthouse');
    await courthouseSelect.waitFor({ state: 'visible' });
    const locations = await courthouseSelect.evaluate(select =>
        Array.from(select.options)
            .filter(option => option.value)
            .map(option => ({
                id: String(option.value),
                name: String(option.textContent || '').trim(),
            }))
    );
    if (locations.length === 0) {
        const error = new Error(
            'Riverside eCalendar exposes no courthouse selectors'
        );
        error.code = 'calendar_locations_missing';
        error.status = 'source_changed';
        error.category = 'source_schema';
        throw error;
    }

    const businessDays = await sourceFetch(
        page,
        `/Home/GetBusinessDays?pRange=3&pStartDate=${encodeURIComponent(
            selection.anchor_date
        )}&pIncludeStartDate=true`,
        { headers: { 'x-requested-with': 'XMLHttpRequest' } }
    );
    if (
        !Array.isArray(businessDays)
        || businessDays.length === 0
        || businessDays.some(value => !/^\d{4}-\d{2}-\d{2}$/.test(String(value)))
    ) {
        const error = new Error(
            'Riverside eCalendar returned an invalid business-day window'
        );
        error.code = 'calendar_business_days_changed';
        error.status = 'source_changed';
        error.category = 'source_schema';
        throw error;
    }

    for (const location of locations) {
        location.departments = await sourceFetch(
            page,
            `/Home/GetDepartmentByLocationId?courtlocationid=${encodeURIComponent(
                location.id
            )}`,
            { headers: { 'x-requested-with': 'XMLHttpRequest' } }
        );
        if (!Array.isArray(location.departments)) {
            const error = new Error(
                `Riverside eCalendar departments changed for ${location.name}`
            );
            error.code = 'calendar_departments_changed';
            error.status = 'source_changed';
            error.category = 'source_schema';
            throw error;
        }
        for (const department of location.departments) {
            department.areas = await sourceFetch(
                page,
                '/Home/GetAreasOfLawStatusByDepartmentId',
                {
                    method: 'POST',
                    headers: {
                        'content-type':
                            'application/x-www-form-urlencoded; charset=UTF-8',
                        'x-requested-with': 'XMLHttpRequest',
                    },
                    body: `departmentId=${encodeURIComponent(department.id)}`,
                }
            );
            if (!Array.isArray(department.areas)) {
                const error = new Error(
                    `Riverside eCalendar areas changed for ` +
                    `${department.locationName}`
                );
                error.code = 'calendar_areas_changed';
                error.status = 'source_changed';
                error.category = 'source_schema';
                throw error;
            }
        }
    }

    const selectedLocations = selectOne(
        locations,
        selection.courthouse,
        'courthouse',
        item => [item.name, item.id]
    );
    const combinations = [];
    for (const location of selectedLocations) {
        const departments = selectOne(
            location.departments,
            selection.department,
            'department',
            item => [
                item.locationName,
                normalizedDepartment(item.locationName),
                String(item.id),
            ]
        );
        for (const department of departments) {
            const areas = selectOne(
                department.areas,
                selection.area_of_law,
                'area_of_law',
                item => [item.name]
            );
            for (const area of areas) {
                combinations.push({ location, department, area });
            }
        }
    }

    const requestedStart = selection.start_date || businessDays[0];
    const requestedEnd =
        selection.end_date || businessDays[businessDays.length - 1];
    const selectedDays = businessDays.filter(
        value => value >= requestedStart && value <= requestedEnd
    );
    if (
        !businessDays.includes(requestedStart)
        || !businessDays.includes(requestedEnd)
        || selectedDays.length === 0
    ) {
        const error = new Error(
            'Requested dates are outside the eCalendar business-day window'
        );
        error.code = 'date_outside_source_window';
        error.category = 'query_selection';
        error.details = {
            requested_start: requestedStart,
            requested_end: requestedEnd,
            business_days: businessDays,
        };
        throw error;
    }

    const records = [];
    const sourceRequests = [];
    for (const combination of combinations) {
        if (minimumInterval > 0 && sourceRequests.length > 0) {
            await page.waitForTimeout(minimumInterval * 1000);
        }
        const departmentName = clean(combination.department.locationName);
        const areaName = clean(combination.area.name);
        const url =
            `/Home/GetDepartmentCalendar?startdate=${encodeURIComponent(
                requestedStart
            )}&enddate=${encodeURIComponent(requestedEnd)}` +
            `&department=${encodeURIComponent(departmentName)}` +
            `&areaoflaw=${encodeURIComponent(areaName)}`;
        const payload = await sourceFetch(
            page,
            url,
            { headers: { 'x-requested-with': 'XMLHttpRequest' } }
        );
        if (!Array.isArray(payload)) {
            const error = new Error(
                `Riverside calendar payload changed for ${departmentName}`
            );
            error.code = 'calendar_payload_changed';
            error.status = 'source_changed';
            error.category = 'source_schema';
            throw error;
        }
        sourceRequests.push(new URL(url, CALENDAR_ORIGIN).href);
        for (const record of payload) {
            records.push({
                ...record,
                source_location_id: combination.location.id,
                source_courthouse: combination.location.name,
                source_department_id: combination.department.id,
                source_department: departmentName,
                source_area_of_law: areaName,
            });
        }
    }
    return {
        ok: true,
        url: page.url(),
        business_days: businessDays,
        selector_tree: locations,
        selected_date_range: {
            start: requestedStart,
            end: requestedEnd,
            days: selectedDays,
        },
        selected_combinations: combinations.length,
        source_requests: sourceRequests,
        records,
    };
}

async function rulingIndex(page, maxAttempts) {
    await goto(page, RULINGS_URL, maxAttempts);
    const heading = clean(
        await page.getByRole('heading', { name: 'Tentative Rulings', exact: true })
            .first()
            .innerText()
    );
    if (heading !== 'Tentative Rulings') {
        const error = new Error(
            'Riverside ruling directory lacks its verified heading'
        );
        error.code = 'ruling_directory_changed';
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

async function rulingPdf(page, selection, maxAttempts) {
    const index = await rulingIndex(page, maxAttempts);
    const department = normalizedDepartment(selection.department);
    const matches = await page.locator('main a[href*=".pdf"]').evaluateAll(
        (links, wanted) => links
            .map(link => ({
                label: String(link.textContent || '').replace(/\s+/g, ' ').trim(),
                url: new URL(link.href, location.href).href,
            }))
            .filter(item => {
                const match = item.label.match(/Department\s+([A-Z0-9]+)/i);
                return match && match[1].toUpperCase() === wanted;
            }),
        department
    );
    if (matches.length !== 1) {
        const error = new Error(
            `Riverside ruling department ${department} matched ` +
            `${matches.length} artifacts`
        );
        error.code = matches.length === 0
            ? 'ruling_not_published'
            : 'ruling_department_ambiguous';
        error.category = 'query_selection';
        throw error;
    }
    const artifact = matches[0];
    const parsed = new URL(artifact.url);
    if (
        parsed.origin !== COURT_ORIGIN
        || !parsed.pathname.startsWith('/system/files/')
        || !parsed.pathname.toLowerCase().endsWith('.pdf')
    ) {
        const error = new Error(
            `Unexpected Riverside ruling artifact URL: ${artifact.url}`
        );
        error.code = 'ruling_artifact_url_changed';
        error.status = 'source_changed';
        error.category = 'source_schema';
        throw error;
    }
    const fetched = await page.evaluate(async url => {
        const response = await fetch(url);
        const bytes = new Uint8Array(await response.arrayBuffer());
        let binary = '';
        const chunkSize = 0x8000;
        for (let offset = 0; offset < bytes.length; offset += chunkSize) {
            binary += String.fromCharCode(
                ...bytes.subarray(offset, offset + chunkSize)
            );
        }
        return {
            status: response.status,
            ok: response.ok,
            content_type: response.headers.get('content-type'),
            etag: response.headers.get('etag'),
            last_modified: response.headers.get('last-modified'),
            base64: btoa(binary),
        };
    }, artifact.url);
    if (!fetched.ok) {
        const error = new Error(
            `Riverside ruling artifact returned ${fetched.status}`
        );
        error.code = 'ruling_artifact_unavailable';
        error.category = 'transport';
        error.retryable = fetched.status === 429 || fetched.status >= 500;
        throw error;
    }
    return {
        ok: true,
        index_url: index.url,
        index_html: index.html,
        artifact: {
            ...artifact,
            ...fetched,
        },
    };
}

async function run(selection, timeout, minimumInterval, maxAttempts) {
    const chromium = loadChromium();
    const headless = process.env.RIVERSIDE_COURT_HEADLESS === '1';
    const browser = await chromium.launch({
        channel: process.env.RIVERSIDE_COURT_BROWSER_CHANNEL || 'chrome',
        headless,
        args: ['--no-first-run', '--no-default-browser-check'],
    });
    try {
        const context = await browser.newContext({
            locale: 'en-US',
            timezoneId: 'America/Los_Angeles',
        });
        const page = await context.newPage();
        page.setDefaultTimeout(timeout * 1000);
        page.setDefaultNavigationTimeout(timeout * 1000);

        if (selection.operation === 'calendar') {
            return await calendar(
                page,
                selection,
                minimumInterval,
                maxAttempts
            );
        }
        if (selection.operation === 'ruling_index') {
            return await rulingIndex(page, maxAttempts);
        }
        if (selection.operation === 'ruling_pdf') {
            return await rulingPdf(page, selection, maxAttempts);
        }
        if (selection.operation === 'probe') {
            const calendarResult = await calendar(
                page,
                {
                    ...selection,
                    courthouse: 'Historic Court House',
                    department: '8',
                    area_of_law: 'Probate',
                    start_date: null,
                    end_date: null,
                },
                minimumInterval,
                maxAttempts
            );
            const rulingResult = await rulingIndex(page, maxAttempts);
            return {
                ok: true,
                calendar: calendarResult,
                ruling_index: rulingResult,
            };
        }
        const error = new Error(
            `Unsupported Riverside court operation: ${selection.operation}`
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
            details: error.details || {},
        },
    };
    process.stdout.write(`${JSON.stringify(payload)}\n`);
    process.exitCode = 1;
});
