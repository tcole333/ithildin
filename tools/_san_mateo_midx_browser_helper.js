#!/usr/bin/env node
/**
 * Anonymous browser transport for San Mateo Superior Court MIDX.
 *
 * The portal's server returns an empty result shell to non-browser HTTP
 * clients even when the same tokenized form succeeds in Chromium. This helper
 * follows the public form and emits only the native index fields.
 */

'use strict';

const LANDING_URL = 'https://web.sanmateocourt.org/midx/';
const LANDING_ORIGIN = new URL(LANDING_URL).origin;

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

function selectorContract(selection) {
    const contracts = {
        casenumber: {
            form: '#midxsearch1',
            tab: '#midx1',
            fields: ['casenumber'],
        },
        partyname: {
            form: '#midxsearch2',
            tab: '#midx2',
            fields: ['firstname', 'lastname'],
        },
        businessname: {
            form: '#midxsearch3',
            tab: '#midx3',
            fields: ['businessname'],
        },
        filedate: {
            form: '#midxsearch4',
            tab: '#midx4',
            fields: ['df', 'dt'],
        },
    };
    const contract = contracts[selection.search_type];
    if (!contract) {
        const error = new Error(
            `Unsupported MIDX search type: ${selection.search_type}`
        );
        error.code = 'search_form_missing';
        error.status = 'source_changed';
        error.category = 'source_schema';
        throw error;
    }
    return contract;
}

async function retry(operation, maxAttempts) {
    let lastError;
    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
        try {
            return await operation();
        } catch (error) {
            lastError = error;
            if (attempt < maxAttempts) {
                await new Promise(resolve => setTimeout(resolve, 250 * attempt));
            }
        }
    }
    throw lastError;
}

async function parsePage(page) {
    return page.evaluate(() => {
        const tidy = value => String(value || '').replace(/\s+/g, ' ').trim();
        const key = value => tidy(value).toLowerCase().replace(/[^a-z0-9]+/g, '');
        const bodyText = tidy(document.body?.innerText);
        if (/\bno records? found\b/i.test(bodyText)) {
            return {
                rows: [],
                totalReported: 0,
                currentPage: 1,
                totalPages: 1,
                nextUrl: null,
            };
        }
        const countMatch = bodyText.match(/\b([\d,]+)\s+records?\s+found\b/i);
        if (!countMatch) {
            const error = new Error('MIDX result page lacks its record count');
            error.code = 'result_count_missing';
            throw error;
        }
        const tables = Array.from(document.querySelectorAll('table'));
        const table = tables.find(candidate => {
            const firstRow = candidate.querySelector('tr');
            const headers = firstRow
                ? Array.from(firstRow.cells).map(cell => key(cell.innerText))
                : [];
            return headers.includes('casenumber') && headers.includes('partyname');
        });
        if (!table) {
            const error = new Error('MIDX result page lacks its index table');
            error.code = 'result_table_missing';
            throw error;
        }
        const headerRow = table.querySelector('tr');
        const headers = Array.from(headerRow.cells).map(cell => key(cell.innerText));
        const aliases = {
            casenumber: 'case_number',
            partyname: 'party_name',
            type: 'party_type',
            filingdate: 'filing_date',
            indexinfo: 'index_info',
            moreinfo: 'index_info',
        };
        const canonical = headers.map((header, index) =>
            aliases[header] || header || `column_${index}`
        );
        const rows = Array.from(table.querySelectorAll('tr'))
            .slice(1)
            .filter(row => row.cells.length > 0)
            .map(row => {
                const values = {};
                canonical.forEach((header, index) => {
                    values[header] = tidy(row.cells[index]?.innerText) || null;
                });
                const infoIndex = canonical.indexOf('index_info');
                const infoLink = infoIndex >= 0
                    ? row.cells[infoIndex]?.querySelector('a[href]')
                    : null;
                return {
                    case_number: values.case_number,
                    party_name: values.party_name,
                    party_type: values.party_type,
                    filing_date: values.filing_date,
                    index_info_url: infoLink?.href || null,
                    source_url: location.href,
                };
            });
        const pager = Array.from(document.querySelectorAll('ul'))
            .find(element => /^Page\b/i.test(tidy(element.innerText)));
        const currentPage = Number(
            tidy(pager?.querySelector('span.selected')?.innerText) || '1'
        );
        const lastText = tidy(
            pager?.querySelector('a[title="Last Page"]')?.innerText
        ) || tidy(pager?.innerText);
        const lastMatch = lastText.match(/Last\s+of\s+([\d,]+)/i);
        const totalPages = lastMatch
            ? Number(lastMatch[1].replace(/,/g, ''))
            : currentPage;
        const directNext = pager?.querySelector(
            `a[title="Page ${currentPage + 1}"]`
        );
        const nextLink = directNext || pager?.querySelector(
            'a[title="Next Page"]'
        );
        return {
            rows,
            totalReported: Number(countMatch[1].replace(/,/g, '')),
            currentPage,
            totalPages,
            nextUrl: nextLink?.href || null,
        };
    });
}

async function search(selection, limit, offset, timeout, minimumInterval, maxAttempts) {
    const chromium = loadChromium();
    const browser = await chromium.launch({
        channel: process.env.SAN_MATEO_MIDX_BROWSER_CHANNEL || 'chrome',
        headless: true,
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
        await retry(
            () => page.goto(LANDING_URL, { waitUntil: 'domcontentloaded' }),
            maxAttempts
        );
        const bodyText = clean(await page.locator('body').innerText());
        const currentMatch = bodyText.match(
            /information\s+provided\s+is\s+current\s+as\s+of\s+(.+?(?:AM|PM))\b/i
        );
        const currentAsOf = currentMatch ? clean(currentMatch[1]) : null;
        const contract = selectorContract(selection);
        await page.locator(contract.tab).click();
        await page.locator(contract.form).waitFor({ state: 'visible' });
        for (const field of contract.fields) {
            await page.locator(`${contract.form} [name="${field}"]`)
                .fill(String(selection[field]));
        }
        await Promise.all([
            page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
            page.locator(`${contract.form} input[type="submit"]`).click(),
        ]);
        await page.waitForFunction(() => {
            const text = document.body?.innerText || '';
            return /\b(?:[\d,]+\s+records?|no records?)\s+found\b/i.test(text);
        });

        const collected = [];
        const seen = new Set();
        let pagesFetched = 0;
        let totalReported = 0;
        let sourceTotalPages = 1;
        while (true) {
            const parsed = await parsePage(page);
            pagesFetched += 1;
            if (pagesFetched === 1) {
                totalReported = parsed.totalReported;
            }
            sourceTotalPages = Math.max(sourceTotalPages, parsed.totalPages);
            collected.push(...parsed.rows);
            if (limit !== null && collected.length >= offset + limit) {
                break;
            }
            if (!parsed.nextUrl) {
                if (parsed.currentPage < parsed.totalPages) {
                    const error = new Error(
                        'MIDX indicates another page without a continuation link'
                    );
                    error.code = 'pagination_link_missing';
                    throw error;
                }
                break;
            }
            if (new URL(parsed.nextUrl).origin !== LANDING_ORIGIN) {
                const error = new Error(
                    'MIDX pagination link points outside the official host'
                );
                error.code = 'pagination_origin_changed';
                throw error;
            }
            if (seen.has(parsed.nextUrl)) {
                const error = new Error('MIDX returned a repeated continuation link');
                error.code = 'pagination_loop';
                throw error;
            }
            seen.add(parsed.nextUrl);
            if (minimumInterval > 0) {
                await page.waitForTimeout(minimumInterval * 1000);
            }
            await retry(
                () => page.goto(parsed.nextUrl, { waitUntil: 'domcontentloaded' }),
                maxAttempts
            );
        }
        const rows = limit === null
            ? collected.slice(offset)
            : collected.slice(offset, offset + limit);
        return {
            ok: true,
            rows,
            total_reported: totalReported,
            source_total_pages: sourceTotalPages,
            pages_fetched: pagesFetched,
            current_as_of: currentAsOf,
            source_url: page.url(),
            transport: 'playwright',
        };
    } finally {
        await browser.close();
    }
}

async function main() {
    const selection = JSON.parse(process.argv[2]);
    const rawLimit = process.argv[3];
    const limit = rawLimit === 'null' ? null : Number(rawLimit);
    const offset = Number(process.argv[4]);
    const timeout = Number(process.argv[5]);
    const minimumInterval = Number(process.argv[6]);
    const maxAttempts = Number(process.argv[7]);
    const result = await search(
        selection,
        limit,
        offset,
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
