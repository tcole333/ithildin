#!/usr/bin/env node
/**
 * Browser renderer for Oregon county Helion/ORCATS Property Search Online.
 *
 * The six verified tenants are Blazor Server applications. Their initial HTTP
 * response contains only an application shell; public search and detail data
 * arrive after the SignalR circuit starts. This helper renders that public
 * state and returns JSON to query_oregon_helion_property.py.
 */

'use strict';

const fs = require('fs');
const path = require('path');

const DEFAULT_TIMEOUT_MS = 45000;

class RuntimeDependencyError extends Error {
    constructor(message) {
        super(message);
        this.code = 'browser_runtime_unavailable';
    }
}

class SourceRenderError extends Error {
    constructor(code, message, details = {}) {
        super(message);
        this.code = code;
        this.details = details;
    }
}

function clean(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
}

function loadChromium() {
    const override = process.env.OR_PSO_PLAYWRIGHT_MODULE;
    const candidates = override ? [override] : ['playwright', 'playwright-core'];
    const failures = [];
    for (const moduleName of candidates) {
        try {
            const loaded = require(moduleName);
            if (loaded.chromium) return { chromium: loaded.chromium, moduleName };
            failures.push(`${moduleName}: missing chromium export`);
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
                process.env.HOME || '',
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
    const channel = process.env.OR_PSO_BROWSER_CHANNEL || 'chrome';
    let executable = null;
    if (channel === 'chrome') {
        executable = systemChromePath();
        if (!executable) {
            throw new RuntimeDependencyError(
                'Google Chrome was not found; set OR_PSO_BROWSER_CHANNEL=chromium ' +
                'to use an installed Playwright Chromium build'
            );
        }
    } else if (channel === 'chromium') {
        executable = chromium.executablePath();
        if (!executable || !fs.existsSync(executable)) {
            throw new RuntimeDependencyError(
                'Playwright Chromium was not found'
            );
        }
    }
    return {
        ok: true,
        node: process.version,
        playwright_module: moduleName,
        browser_channel: channel,
        browser_executable: executable,
    };
}

async function launchBrowser() {
    const info = runtimeInfo();
    const { chromium } = loadChromium();
    const options = {
        headless: process.env.OR_PSO_BROWSER_HEADLESS !== '0',
    };
    if (info.browser_channel === 'chromium') {
        options.executablePath = info.browser_executable;
    } else {
        options.channel = info.browser_channel;
    }
    const browser = await chromium.launch(options);
    const context = await browser.newContext({
        locale: 'en-US',
        timezoneId: 'America/Los_Angeles',
        viewport: { width: 1440, height: 1100 },
    });
    const page = await context.newPage();
    page.setDefaultTimeout(Number(process.env.OR_PSO_TIMEOUT_MS) || DEFAULT_TIMEOUT_MS);
    page.setDefaultNavigationTimeout(
        Number(process.env.OR_PSO_TIMEOUT_MS) || DEFAULT_TIMEOUT_MS
    );
    const transportEvents = [];
    page.on('console', message => {
        const text = message.text();
        if (/WebSocket connected/i.test(text)) {
            transportEvents.push('websocket_connected');
        } else if (/using the Long Polling fallback transport/i.test(text)) {
            transportEvents.push('long_polling_fallback');
        } else if (/WebSocket.*failed/i.test(text)) {
            transportEvents.push('websocket_failed');
        }
    });
    return { browser, context, page, info, transportEvents };
}

function joined(baseUrl, relative) {
    const normalized = baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`;
    return new URL(relative, normalized).toString();
}

async function openAndWait(page, url, readySelector) {
    const response = await page.goto(url, { waitUntil: 'domcontentloaded' });
    if (response && response.status() >= 400) {
        throw new SourceRenderError(
            `source_http_${response.status()}`,
            `Property Search Online returned HTTP ${response.status()}`,
            { url, status_code: response.status() }
        );
    }
    await page.locator(readySelector).first().waitFor({ state: 'attached' });
}

async function waitForSearchOutcome(page) {
    await page.waitForFunction(() => {
        const body = document.body ? document.body.innerText : '';
        const loading = /\bLoading\.\.\./i.test(body);
        const records = document.querySelectorAll('a.hel_account-link').length;
        const empty = /no (accounts|records|results)|0 results|nothing found/i.test(body);
        return !loading && (records > 0 || empty);
    });
}

async function probe(page, baseUrl, transportEvents) {
    await openAndWait(
        page,
        baseUrl,
        'select[aria-label="Search Options"]'
    );
    return page.evaluate(events => {
        const cleanText = value => String(value || '').replace(/\s+/g, ' ').trim();
        const options = Array.from(
            document.querySelectorAll('select[aria-label="Search Options"] option')
        ).map(option => ({
            label: cleanText(option.textContent),
            value: option.value,
            selected: option.selected,
        }));
        return {
            ok: true,
            operation: 'probe',
            access_outcome: 'search_form_ready',
            url: location.href,
            title: document.title,
            search_options: options,
            footer: cleanText(
                document.querySelector('[aria-label="Site Footer"]')?.textContent ||
                Array.from(document.querySelectorAll('body *'))
                    .find(node => /Helion Software All rights reserved/i.test(
                        node.textContent || ''
                    ))?.textContent
            ),
            transport_events: Array.from(new Set(events)),
        };
    }, transportEvents);
}

async function search(page, baseUrl, searchOption, query, pageNumber) {
    const url = joined(
        baseUrl,
        `search?searchOption=${encodeURIComponent(searchOption)}` +
        `&searchValue=${encodeURIComponent(query)}` +
        `&pageNumber=${encodeURIComponent(pageNumber)}`
    );
    await openAndWait(
        page,
        url,
        'select[aria-label="Search Options"]'
    );
    await waitForSearchOutcome(page);
    return page.evaluate(() => {
        const cleanText = value => String(value || '').replace(/\s+/g, ' ').trim();
        const links = Array.from(document.querySelectorAll('a.hel_account-link'));
        const records = links.map((link, index) => {
            const card = link.closest('.row.border.rounded');
            const left = card?.querySelector('.col-12.col-lg-6') ||
                card?.firstElementChild;
            const rows = left
                ? Array.from(left.children).filter(
                    node => node.classList.contains('row')
                )
                : [];
            const first = rows[0]
                ? Array.from(rows[0].querySelectorAll('p')).map(
                    node => cleanText(node.textContent)
                )
                : [];
            const second = rows[1]
                ? Array.from(rows[1].querySelectorAll('p')).map(
                    node => cleanText(node.textContent)
                )
                : [];
            const situsNode = left?.querySelector('.oi-map-marker')?.parentElement;
            const dueLabel = card
                ? Array.from(card.querySelectorAll('p')).find(
                    node => cleanText(node.textContent) === 'Amount Due'
                )
                : null;
            const href = link.getAttribute('href') || '';
            const route = href.match(/detail\/([^/]+)\/([^/?#]+)/i);
            return {
                position_on_page: index + 1,
                account_id: route ? route[1] : cleanText(link.textContent)
                    .replace(/^Account\s+/i, '').replace(/\s*\|.*$/, ''),
                roll_type: route ? route[2] : null,
                property_type: first[0] || null,
                owner_name: second[0] || null,
                map_taxlot: second[1] || null,
                situs_address: cleanText(situsNode?.textContent) || null,
                amount_due: cleanText(dueLabel?.nextElementSibling?.textContent) || null,
                detail_url: new URL(href, location.href).toString(),
                related_accounts_url: card?.querySelector(
                    'a[href*="related/"]'
                )?.href || null,
            };
        });
        const numericPages = Array.from(document.querySelectorAll('nav li'))
            .map(node => Number(cleanText(node.textContent)))
            .filter(Number.isInteger);
        const parameters = new URL(location.href).searchParams;
        const body = document.body ? document.body.innerText : '';
        return {
            ok: true,
            operation: 'search',
            source_url: location.href,
            search_option: parameters.get('searchOption'),
            search_value: parameters.get('searchValue'),
            page_number: Number(parameters.get('pageNumber') || 1),
            total_pages: numericPages.length ? Math.max(...numericPages) : 1,
            native_page_size: records.length,
            authoritative_empty: records.length === 0 &&
                /no (accounts|records|results)|0 results|nothing found/i.test(body),
            records,
            schema_shape: {
                card_fields: [
                    'account_id',
                    'roll_type',
                    'property_type',
                    'owner_name',
                    'map_taxlot',
                    'situs_address',
                    'amount_due',
                ],
            },
        };
    });
}

async function clickTaxModal(page, buttonPattern, headingPattern) {
    const taxesTab = page.locator('a[href="#taxes"]').first();
    if (await taxesTab.count()) {
        await taxesTab.click();
        await page.waitForTimeout(150);
    }
    const buttons = page.locator('#taxes button').filter({ hasText: buttonPattern });
    if (!await buttons.count()) return null;
    const button = buttons.first();
    await button.waitFor({ state: 'visible' });
    await button.click();
    const dialog = page.locator('[role="dialog"]')
        .filter({ hasText: headingPattern }).first();
    if (!await dialog.count()) return null;
    await dialog.waitFor({ state: 'visible' });
    const value = await dialog.evaluate(node => {
        const cleanText = raw => String(raw || '').replace(/\s+/g, ' ').trim();
        const tables = Array.from(node.querySelectorAll('table')).map(table => {
            const headers = Array.from(table.querySelectorAll('thead th')).map(
                cell => cleanText(cell.textContent)
            );
            const rows = Array.from(table.rows)
                .filter(row => !row.closest('thead'))
                .map(row =>
                    Array.from(row.cells).map(cell => cleanText(cell.textContent))
                );
            return { headers, rows };
        });
        return {
            title: cleanText(node.querySelector('h1,h2,h3,h4,h5')?.textContent),
            text: cleanText(node.textContent),
            tables,
        };
    });
    const close = dialog.locator(
        'button[aria-label="Close"], button:has-text("Close")'
    ).first();
    if (await close.count()) {
        await close.click();
        await dialog.waitFor({ state: 'hidden' }).catch(() => {});
    }
    return value;
}

async function detail(page, baseUrl, accountId, rollType) {
    const url = joined(
        baseUrl,
        `detail/${encodeURIComponent(accountId)}/${encodeURIComponent(rollType)}`
    );
    await openAndWait(page, url, '#account[role="tabpanel"]');

    const paymentCalculator = await clickTaxModal(
        page,
        /Payment Calculator|Payment Options Calculator/i,
        /Payment Options Calculator|Amount Due By Month/i
    );
    const paymentHistory = await clickTaxModal(
        page,
        /Payment History/i,
        /Payment History/i
    );

    return page.evaluate(({ calculator, history }) => {
        const cleanText = value => String(value || '').replace(/\s+/g, ' ').trim();
        const lines = node => node
            ? String(node.innerText || node.textContent || '')
                .split(/\n+/).map(cleanText).filter(Boolean)
            : [];
        const snake = value => cleanText(value)
            .toLowerCase()
            .replace(/\*/g, '')
            .replace(/#/g, ' number ')
            .replace(/[^a-z0-9]+/g, '_')
            .replace(/^_|_$/g, '');

        function parseTable(table) {
            const rawHeaders = Array.from(
                table.querySelectorAll('thead tr:last-child th')
            ).map(cell => (
                cleanText(cell.textContent) ||
                cleanText(cell.getAttribute('aria-label'))
            ));
            const used = new Map();
            const headers = rawHeaders.map((header, index) => {
                const base = snake(header) || `column_${index + 1}`;
                const count = (used.get(base) || 0) + 1;
                used.set(base, count);
                return count === 1 ? base : `${base}_${count}`;
            });
            const rows = Array.from(table.querySelectorAll('tbody > tr')).map(row => {
                const cells = Array.from(row.querySelectorAll(':scope > th, :scope > td'));
                const values = cells.map(cell => cleanText(cell.textContent));
                const item = {};
                values.forEach((value, index) => {
                    item[headers[index] || `column_${index + 1}`] = value || null;
                });
                const links = Array.from(row.querySelectorAll('a[href]')).map(link => ({
                    label: cleanText(link.textContent || link.title),
                    url: link.href,
                }));
                if (links.length) item.links = links;
                return item;
            });
            return { headers, rows };
        }

        function tableWithHeaders(root, required) {
            if (!root) return null;
            return Array.from(root.querySelectorAll('table')).find(table => {
                const headers = Array.from(table.querySelectorAll('thead th'))
                    .flatMap(cell => [
                        cleanText(cell.textContent).toLowerCase(),
                        cleanText(cell.getAttribute('aria-label')).toLowerCase(),
                    ]).filter(Boolean);
                return required.every(label => headers.includes(label.toLowerCase()));
            }) || null;
        }

        function labeledParagraph(root, label) {
            if (!root) return null;
            const labelNode = Array.from(
                root.querySelectorAll('span.font-weight-bold')
            ).find(node => cleanText(node.textContent) === label);
            const column = labelNode?.closest('[class*="col-"]');
            return column?.querySelector('p') || null;
        }

        function presentationFacts(root) {
            const facts = {};
            if (!root) return facts;
            for (const row of root.querySelectorAll('table[role="presentation"] tbody tr')) {
                const cells = row.querySelectorAll(':scope > td');
                if (cells.length < 2) continue;
                const key = snake(cells[0].textContent);
                if (key) facts[key] = cleanText(cells[1].textContent) || null;
            }
            return facts;
        }

        function modalTable(root, idPrefix) {
            const modal = root?.querySelector(`[id^="${idPrefix}"]`);
            const table = modal?.querySelector('table');
            return table ? parseTable(table).rows : [];
        }

        const account = document.querySelector('#account');
        const taxes = document.querySelector('#taxes');
        const sales = document.querySelector('#sales');
        const values = document.querySelector('#values');
        const files = document.querySelector('#files');
        const ledger = document.querySelector('#ledger');
        const heading = cleanText(document.querySelector('main h1')?.textContent);
        const route = location.pathname.match(/\/detail\/([^/]+)\/([^/]+)/i);
        const accountId = route ? route[1] : heading.replace(/^Account\s+/i, '');
        const rollType = route ? route[2] : null;

        const situsNode = labeledParagraph(account, 'Situs Address');
        const mailingNode = labeledParagraph(account, 'Mailing Address');
        const mapNode = labeledParagraph(account, 'Map and Taxlot');
        const owners = Array.from(
            account.querySelectorAll('[role="group"][aria-label^="Owner"]')
        ).map(group => ({
            role: cleanText(
                group.querySelector('[aria-label$=" type"]')?.textContent
            ) || null,
            raw_name: cleanText(
                group.querySelector('[aria-label$=" name"]')?.textContent
            ) || null,
        })).filter(owner => owner.raw_name);
        if (!owners.length) {
            const ownerNode = labeledParagraph(account, 'Owner');
            const ownerName = cleanText(ownerNode?.textContent);
            if (ownerName) owners.push({ role: 'OWNER', raw_name: ownerName });
        }

        const assessmentTable = tableWithHeaders(
            account,
            ['Type', 'RMV', 'MAV', 'AV']
        );
        const improvementTable = tableWithHeaders(
            account,
            ['Bldg #', 'Year Built', 'Description', 'Livable Size']
        );
        const salesTable = tableWithHeaders(
            sales,
            ['Sales Date', 'Year/Doc ID', 'Total Sales Price']
        );
        const valuesTable = tableWithHeaders(
            values,
            ['Year', 'RMV', 'MAV*', 'AV']
        );
        const ledgerTable = tableWithHeaders(
            ledger,
            ['Year', 'Operation', 'Source', 'Type', 'Doc #']
        );

        const selectedAssessment = account.querySelector(
            'select[aria-label*="Asessment Year"] option:checked'
        );
        const facts = presentationFacts(account);
        const taxCard = taxes?.querySelector('.row.border.rounded');
        const taxParagraphs = taxCard
            ? Array.from(taxCard.querySelectorAll('p')).map(
                node => cleanText(node.textContent)
            ).filter(Boolean)
            : [];
        const amountLabel = taxes
            ? Array.from(taxes.querySelectorAll('p')).find(
                node => cleanText(node.textContent) === 'Amount Due'
            )
            : null;

        const downloads = Array.from(
            document.querySelectorAll('main a[href*="download"]')
        ).map(link => ({
            label: cleanText(link.textContent || link.title),
            url: link.href,
        }));
        const fileLinks = files
            ? Array.from(files.querySelectorAll('a[href]')).map(link => ({
                label: cleanText(link.textContent || link.title),
                url: link.href,
            }))
            : [];
        const tableShapes = Array.from(document.querySelectorAll('main table'))
            .map(table => Array.from(table.querySelectorAll('thead th'))
                .map(cell => cleanText(
                    cell.getAttribute('aria-label') || cell.textContent
                )))
            .filter(headers => headers.some(Boolean));

        return {
            ok: true,
            operation: 'detail',
            source_url: location.href,
            account_id: accountId,
            roll_type: rollType,
            heading,
            property_heading: cleanText(account.querySelector('h2')?.textContent),
            situs_address: cleanText(situsNode?.childNodes[0]?.textContent) ||
                cleanText(situsNode?.textContent) || null,
            additional_situs_addresses: modalTable(account, 'situsModal-')
                .map(row => row.column_1).filter(Boolean),
            mailing_address_lines: lines(mailingNode),
            map_taxlot: cleanText(mapNode?.textContent) || null,
            owners,
            assessment_year: cleanText(selectedAssessment?.textContent) || null,
            assessment_rows: assessmentTable
                ? parseTable(assessmentTable).rows : [],
            property_facts: facts,
            notations: modalTable(account, 'notationsModal-'),
            special_assessments: modalTable(account, 'specialAssessmentsModal-'),
            improvements: improvementTable
                ? parseTable(improvementTable).rows : [],
            tax_account: {
                account_id: taxParagraphs[1] || accountId,
                roll_type: taxParagraphs[2] || rollType,
                tax_id: taxParagraphs[3] || null,
                code_area: taxParagraphs[4] || null,
                amount_due: cleanText(
                    amountLabel?.nextElementSibling?.textContent
                ) || null,
            },
            payment_calculator: calculator,
            payment_history: history,
            sales_history: salesTable ? parseTable(salesTable).rows : [],
            value_history: valuesTable ? parseTable(valuesTable).rows : [],
            account_history: ledgerTable ? parseTable(ledgerTable).rows : [],
            downloads,
            files: fileLinks,
            schema_shape: {
                tabs: Array.from(
                    document.querySelectorAll('main a[href^="#"]')
                ).map(link => cleanText(link.textContent)).filter(Boolean),
                tables: tableShapes,
            },
        };
    }, { calculator: paymentCalculator, history: paymentHistory });
}

function optionValue(args, option, fallback = null) {
    const index = args.indexOf(option);
    return index >= 0 && args[index + 1] !== undefined
        ? args[index + 1]
        : fallback;
}

async function withBrowser(action) {
    const launched = await launchBrowser();
    try {
        const result = await action(
            launched.page,
            launched.transportEvents,
            launched.info
        );
        return {
            ...result,
            transport_events: Array.from(
                new Set([
                    ...(result.transport_events || []),
                    ...launched.transportEvents,
                ])
            ),
            runtime: launched.info,
        };
    } finally {
        await launched.browser.close();
    }
}

function usage() {
    process.stderr.write(
        'Usage: _oregon_helion_property_browser_helper.js ' +
        '<runtime-check|probe|search|detail> [options]\n'
    );
}

async function main() {
    const args = process.argv.slice(2);
    const command = args[0];
    if (command === 'runtime-check') {
        return runtimeInfo();
    }
    const baseUrl = optionValue(args, '--base-url');
    if (!baseUrl) {
        throw new SourceRenderError(
            'missing_base_url',
            '--base-url is required'
        );
    }
    if (command === 'probe') {
        return withBrowser((page, events) => probe(page, baseUrl, events));
    }
    if (command === 'search') {
        const searchOption = optionValue(args, '--search-option');
        const query = optionValue(args, '--query');
        const pageNumber = Number(optionValue(args, '--page', '1'));
        if (!searchOption || query === null) {
            throw new SourceRenderError(
                'missing_search_selector',
                '--search-option and --query are required'
            );
        }
        if (!Number.isInteger(pageNumber) || pageNumber < 1) {
            throw new SourceRenderError(
                'invalid_page_number',
                '--page must be a positive integer'
            );
        }
        return withBrowser(page =>
            search(page, baseUrl, searchOption, query, pageNumber)
        );
    }
    if (command === 'detail') {
        const accountId = optionValue(args, '--account');
        const rollType = optionValue(args, '--roll-type', 'R');
        if (!accountId) {
            throw new SourceRenderError(
                'missing_account_id',
                '--account is required'
            );
        }
        return withBrowser(page =>
            detail(page, baseUrl, accountId, rollType)
        );
    }
    usage();
    throw new SourceRenderError('unsupported_command', `Unknown command: ${command}`);
}

main().then(result => {
    process.stdout.write(JSON.stringify(result));
}).catch(error => {
    const payload = {
        ok: false,
        error: {
            code: error.code || (
                error instanceof RuntimeDependencyError
                    ? 'browser_runtime_unavailable'
                    : 'browser_render_failed'
            ),
            message: error.message,
            details: error.details || {},
            name: error.name,
        },
    };
    process.stdout.write(JSON.stringify(payload));
    process.exitCode = 1;
});
