#!/usr/bin/env node
/**
 * Wyoming Secretary of State (WyoBiz) browser helper.
 *
 * Bypasses F5 Advanced WAF/CAPTCHA using Playwright persistent Chrome context.
 * The site is ASP.NET WebForms at wyobiz.wyo.gov — requires browser-based
 * form submission (ViewState + EventValidation) and TSPD bot cookies.
 *
 * On first visit, F5 may present a CAPTCHA (visual code). Once solved,
 * clearance cookies persist for the session. Run `warmup` to solve manually.
 *
 * Search results page: FilingSearch.aspx — 20 results per page, paginated.
 * Detail page: FilingDetails.aspx?eFNum=<encrypted_id>
 *
 * Usage:
 *   node tools/_wy_browser_helper.js warmup
 *   node tools/_wy_browser_helper.js search "TRUMP"
 *   node tools/_wy_browser_helper.js search "TRUMP" --contains
 *   node tools/_wy_browser_helper.js search-id "2021-001032098"
 *   node tools/_wy_browser_helper.js detail <eFNum>
 *   node tools/_wy_browser_helper.js full <filing_id>
 *
 * Outputs JSON to stdout. Errors/progress to stderr.
 */

const path = require('path');
const os = require('os');
const fs = require('fs');

const BASE_URL = 'https://wyobiz.wyo.gov/Business';
const SEARCH_URL = `${BASE_URL}/FilingSearch.aspx`;
const DETAIL_URL = `${BASE_URL}/FilingDetails.aspx`;
const USER_DATA_DIR = path.join(os.homedir(), '.cache', 'wy-sos-browser');

let chromium;
try {
    chromium = require('playwright').chromium;
} catch {
    try {
        chromium = require('playwright-core').chromium;
    } catch {
        process.stderr.write('ERROR: playwright package not found. Install with: npm i playwright\n');
        process.exit(1);
    }
}

const STEALTH_SCRIPT = `
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    if (!window.chrome) window.chrome = {};
    if (!window.chrome.runtime) window.chrome.runtime = { id: undefined };
`;

async function launchBrowser() {
    fs.mkdirSync(USER_DATA_DIR, { recursive: true });
    const context = await chromium.launchPersistentContext(USER_DATA_DIR, {
        channel: 'chrome',
        headless: false,
        viewport: { width: 1280, height: 900 },
        locale: 'en-US',
        timezoneId: 'America/Denver',
        userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        args: [
            '--disable-blink-features=AutomationControlled',
            '--no-first-run',
            '--no-default-browser-check',
        ],
        ignoreDefaultArgs: ['--enable-automation'],
    });
    await context.addInitScript(STEALTH_SCRIPT);
    return context;
}

/**
 * Wait for F5 CAPTCHA to be solved (either auto-bypass or user interaction).
 * Returns true if the actual site page loaded, false if timed out.
 */
async function waitForF5(page) {
    let prompted = false;
    for (let i = 0; i < 60; i++) {
        try {
            await page.waitForTimeout(2000);
        } catch {
            await new Promise(r => setTimeout(r, 2000));
        }

        try {
            const title = await page.title();
            const url = page.url();

            // Check if we're on the actual WyoBiz page (past F5 challenge)
            if (title.includes('Wyoming Secretary of State') ||
                title.includes('Filing Search') ||
                title.includes('Business Entity')) {
                return true;
            }

            // Check for actual form elements
            const hasForm = await page.evaluate(() =>
                !!document.getElementById('MainContent_txtFilingName') ||
                !!document.getElementById('txtFilingName')
            ).catch(() => false);
            if (hasForm) return true;

        } catch { /* page not ready */ }

        if (i === 3 && !prompted) {
            process.stderr.write('\n  *** F5 WAF challenge detected ***\n');
            process.stderr.write('  If a browser window opened with a CAPTCHA, solve it manually.\n');
            process.stderr.write('  Cookies will be cached for future requests.\n\n');
            prompted = true;
        }
        if (i % 10 === 0 && i > 0) {
            process.stderr.write(`  [${i * 2}s] still waiting for F5 challenge...\n`);
        }
    }
    return false;
}

// ══════════════════════════════════════════════════════════
// WARMUP — Open browser for manual CAPTCHA solving
// ══════════════════════════════════════════════════════════

async function cmdWarmup() {
    process.stderr.write('Opening WY SoS browser for warmup...\n');
    process.stderr.write('Solve any F5 CAPTCHA challenge in the browser window.\n');
    process.stderr.write('Press Ctrl+C when done.\n\n');

    const context = await launchBrowser();
    const page = await context.newPage();
    await page.goto(SEARCH_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });

    const ok = await waitForF5(page);
    if (ok) {
        process.stderr.write('Challenge solved! Cookies cached.\n');
    } else {
        process.stderr.write('Timed out waiting for challenge resolution.\n');
    }

    // Keep browser open for manual interaction
    await new Promise(r => setTimeout(r, 300000)); // 5 min
    await context.close();
}

// ══════════════════════════════════════════════════════════
// SEARCH — Search by entity name
// ══════════════════════════════════════════════════════════

/**
 * Parse a single search result element into structured data.
 * Each result link contains text like:
 *   "Trump Across Atlantic Investments, LLC - 2021-001032098 (LLC)
 *    Status: Active
 *    Standing - Tax: Good
 *    Standing - RA: Good
 *    Filed On: 08/31/2021"
 */
function parseSearchResult(text, href) {
    const lines = text.split('\n').map(l => l.trim()).filter(l => l);
    const result = { raw_text: text };

    // First line: "NAME - FILING_ID (TYPE)" or "NAME (Old Name) - FILING_ID (TYPE)"
    if (lines[0]) {
        const firstLine = lines[0];
        // Match: name - filing_id (type)
        const m = firstLine.match(/^(.+?)\s*-\s*([\d-]+)\s*\(([^)]+)\)\s*$/);
        if (m) {
            result.entity_name = m[1].trim();
            result.filing_id = m[2].trim();
            result.entity_type_abbrev = m[3].trim();
        } else {
            result.entity_name = firstLine;
        }
    }

    // Remaining lines: key-value pairs
    for (let i = 1; i < lines.length; i++) {
        const line = lines[i];
        const kvMatch = line.match(/^(.+?):\s*(.+)$/);
        if (kvMatch) {
            const key = kvMatch[1].trim().toLowerCase();
            const val = kvMatch[2].trim();
            if (key === 'status') result.status = val;
            else if (key === 'standing - tax') result.tax_standing = val;
            else if (key === 'standing - ra') result.ra_standing = val;
            else if (key === 'filed on') result.filed_on = val;
        }
    }

    // Extract eFNum from href for detail page access
    if (href) {
        const efMatch = href.match(/eFNum=([^&]+)/);
        if (efMatch) result.efnum = efMatch[1];
    }

    return result;
}

async function cmdSearch(query, contains = false) {
    const context = await launchBrowser();
    const page = await context.newPage();

    try {
        process.stderr.write(`Navigating to WY SoS search...\n`);
        await page.goto(SEARCH_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });

        if (!await waitForF5(page)) {
            console.log(JSON.stringify({ error: 'F5 challenge not resolved. Run warmup first.' }));
            return;
        }

        // Fill search form
        const nameInput = page.locator('#MainContent_txtFilingName');
        await nameInput.fill(query);

        // Select search mode
        if (contains) {
            await page.locator('#MainContent_chkSearchIncludes').click();
        }

        // Submit — use the actual ASP.NET form submit button ID
        process.stderr.write(`Searching for "${query}"...\n`);
        await page.locator('#MainContent_cmdSearch').click();

        // Wait for page navigation (ASP.NET full postback changes page title)
        await page.waitForFunction(() => {
            const title = document.title;
            return title.includes('Filing Search -') || title.includes('No Results');
        }, { timeout: 30000 }).catch(() => {});

        // Extra wait for results to render
        await page.waitForTimeout(2000);

        // Check for no results — the page shows "No Results Found." in a visible div
        const noResults = await page.evaluate(() => {
            // Look for the "No Results Found." text anywhere in the main content
            const mainContent = document.getElementById('main-content') || document.body;
            return mainContent.textContent.includes('No Results Found');
        });

        if (noResults) {
            console.log(JSON.stringify({ query, count: 0, results: [] }));
            return;
        }

        // Parse results and pagination info
        // The search results are <li> elements containing <a> links to FilingDetails.aspx
        const data = await page.evaluate(() => {
            const items = [];
            // Find all links that point to FilingDetails.aspx within list items
            const allLinks = document.querySelectorAll('li a[href*="FilingDetails.aspx"]');
            allLinks.forEach(link => {
                items.push({
                    text: link.textContent.trim(),
                    href: link.getAttribute('href'),
                });
            });

            // Get pagination info — look for "Results: 1-20 of 45" text
            let total = items.length;
            const allText = document.body.textContent;
            const resultMatch = allText.match(/Results:\s*\d+-\d+\s+of\s+(\d+)/);
            if (resultMatch) {
                total = parseInt(resultMatch[1]);
            }

            return { items, total };
        });

        const results = data.items.map(item => parseSearchResult(item.text, item.href));

        // If more than 1 page, collect additional pages
        let allResults = [...results];
        const totalPages = Math.ceil(data.total / 20);

        if (totalPages > 1 && totalPages <= 25) {
            for (let pg = 2; pg <= totalPages; pg++) {
                process.stderr.write(`  Fetching page ${pg}/${totalPages}...\n`);

                // Click next page — uses __doPostBack links with ">" text
                await page.evaluate(() => {
                    // The pagination links use __doPostBack with lbtnNextFooter or lbtnNextHeader
                    const nextLinks = document.querySelectorAll('a');
                    for (const a of nextLinks) {
                        const href = a.getAttribute('href') || '';
                        if (href.includes('lbtnNextFooter') || href.includes('lbtnNextHeader')) {
                            a.click();
                            break;
                        }
                    }
                });

                // Wait for page to reload (ASP.NET full postback)
                await page.waitForTimeout(5000);

                const pageData = await page.evaluate(() => {
                    const items = [];
                    const allLinks = document.querySelectorAll('li a[href*="FilingDetails.aspx"]');
                    allLinks.forEach(link => {
                        items.push({
                            text: link.textContent.trim(),
                            href: link.getAttribute('href'),
                        });
                    });
                    return items;
                });

                const pageResults = pageData.map(item => parseSearchResult(item.text, item.href));
                allResults.push(...pageResults);
            }
        }

        console.log(JSON.stringify({
            query,
            count: data.total,
            results: allResults,
        }));

    } catch (err) {
        console.log(JSON.stringify({ error: err.message }));
    } finally {
        await context.close();
    }
}

// ══════════════════════════════════════════════════════════
// SEARCH BY ID — Search by filing ID
// ══════════════════════════════════════════════════════════

async function cmdSearchId(filingId) {
    const context = await launchBrowser();
    const page = await context.newPage();

    try {
        process.stderr.write(`Navigating to WY SoS search...\n`);
        await page.goto(SEARCH_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });

        if (!await waitForF5(page)) {
            console.log(JSON.stringify({ error: 'F5 challenge not resolved. Run warmup first.' }));
            return;
        }

        // Fill the Filing ID field (note: capital ID)
        const idInput = page.locator('#MainContent_txtFilingID');
        await idInput.fill(filingId);

        // Submit
        process.stderr.write(`Searching for Filing ID "${filingId}"...\n`);
        await page.locator('#MainContent_cmdSearch').click();

        // Wait for page transition
        await page.waitForTimeout(5000);

        const currentUrl = page.url();

        // If redirected to detail page, extract detail
        if (currentUrl.includes('FilingDetails.aspx')) {
            const detail = await extractDetailPage(page);
            console.log(JSON.stringify(detail));
            return;
        }

        // Otherwise parse search results
        const data = await page.evaluate(() => {
            const items = [];
            const allLinks = document.querySelectorAll('li a[href*="FilingDetails.aspx"]');
            allLinks.forEach(link => {
                items.push({
                    text: link.textContent.trim(),
                    href: link.getAttribute('href'),
                });
            });
            return items;
        });

        if (data.length === 0) {
            console.log(JSON.stringify({ query: filingId, count: 0, results: [] }));
        } else {
            const results = data.map(item => parseSearchResult(item.text, item.href));
            console.log(JSON.stringify({ query: filingId, count: results.length, results }));
        }

    } catch (err) {
        console.log(JSON.stringify({ error: err.message }));
    } finally {
        await context.close();
    }
}

// ══════════════════════════════════════════════════════════
// DETAIL — Get entity detail by encrypted eFNum
// ══════════════════════════════════════════════════════════

async function extractDetailPage(page) {
    return await page.evaluate(() => {
        const getText = (id) => {
            const el = document.getElementById(id);
            return el ? el.textContent.trim() : null;
        };

        const getAddress = (id) => {
            const el = document.getElementById(id);
            if (!el) return null;
            // Use innerText (not textContent) to preserve <br> line breaks
            const lines = el.innerText.trim().split('\n').map(l => l.trim()).filter(l => l);
            return lines.join(', ');
        };

        const result = {};

        // Entity name — uses txtFilingName (span with class formInfo)
        result.entity_name = getText('txtFilingName') || getText('txtFilingName2') || '';

        // Basic info — actual IDs from the detail page DOM
        result.filing_id = getText('txtFilingNum') || '';
        result.entity_type = getText('txtFilingType') || '';
        result.status = getText('txtStatus') || '';
        result.sub_status = getText('txtSubStatus') || '';
        result.initial_filing_date = getText('txtInitialDate') || '';

        // Standings
        result.tax_standing = getText('txtStanding') || '';
        result.ra_standing = getText('txtStandingRA') || '';
        result.other_standing = getText('txtStandingOther') || '';

        // Formation info
        result.term_of_duration = getText('txtDuration') || '';
        result.formed_in = getText('txtFormation') || '';

        // Fictitious name
        result.fictitious_name = getText('txtFictitiousName') || '';

        // Addresses (note: txtOfficeAddresss has 3 s's — a typo in the WY site)
        result.principal_office = getAddress('txtOfficeAddresss');
        result.mailing_address = getAddress('txtMailAddress');

        // Registered Agent
        result.agent_name = getText('txtAgentName') || '';
        result.agent_address = getAddress('txtAgentAddress');

        // AR info
        result.latest_ar = getText('txtLatestAR') || '';
        result.ar_exempt = getText('txtARExempt') || '';
        result.license_tax = getText('txtTaxPaid') || '';

        // Filing History — in divHistorySummary > div.search-results > section.row-fluid
        result.filings = [];
        const historyDiv = document.getElementById('divHistorySummary');
        if (historyDiv) {
            // The entries are <section class="row-fluid"> inside a <div class="search-results"> wrapper
            const entries = historyDiv.querySelectorAll('.search-results > section');
            entries.forEach(entry => {
                const text = entry.textContent.trim();
                if (!text) return;

                const lines = text.split('\n').map(l => l.trim()).filter(l => l);
                const filing = {};

                if (lines[0]) {
                    filing.description = lines[0]
                        .replace(/Image\(s\)/g, '')
                        .replace(/Expand to see details/g, '')
                        .trim();
                }

                for (const line of lines) {
                    const dateMatch = line.match(/Date:\s*(.+)/);
                    if (dateMatch) {
                        filing.date = dateMatch[1]
                            .replace(/Expand to see details/g, '')
                            .trim();
                    }
                }

                if (filing.description || filing.date) {
                    result.filings.push(filing);
                }
            });
        }

        // Parties — in divParties > ol.search-results > li
        result.parties = [];
        const partiesDiv = document.getElementById('divParties');
        if (partiesDiv) {
            const partyItems = partiesDiv.querySelectorAll('li');
            partyItems.forEach(item => {
                // Use innerText to get proper line breaks between spans
                const text = item.innerText.trim();
                if (!text) return;

                const party = { raw: text };

                // Parse role in parentheses
                const roleMatch = text.match(/\(([^)]+)\)/);
                if (roleMatch) party.role = roleMatch[1].trim();

                // Parse organization (line-separated from address thanks to innerText)
                const orgMatch = text.match(/Organization:\s*(.+)/);
                if (orgMatch) party.organization = orgMatch[1].split('\n')[0].trim();

                // Parse person name
                const nameMatch = text.match(/Name:\s*(.+)/);
                if (nameMatch) party.name = nameMatch[1].split('\n')[0].trim();

                // Parse address
                const addrMatch = text.match(/Address:\s*(.+)/);
                if (addrMatch) party.address = addrMatch[1].trim();

                result.parties.push(party);
            });
        }

        // Source URL
        result.url = window.location.href;

        return result;
    });
}

async function cmdDetail(efNum) {
    const context = await launchBrowser();
    const page = await context.newPage();

    try {
        const url = `${DETAIL_URL}?eFNum=${efNum}`;
        process.stderr.write(`Fetching entity detail: ${url}\n`);
        await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });

        if (!await waitForF5(page)) {
            console.log(JSON.stringify({ error: 'F5 challenge not resolved. Run warmup first.' }));
            return;
        }

        // Wait for detail page to load
        await page.waitForFunction(() =>
            !!document.getElementById('txtFilingName') ||
            !!document.getElementById('txtFilingNum'),
            { timeout: 15000 }
        ).catch(() => {});

        await page.waitForTimeout(1500);

        // Expand all collapsible sections
        const expandLinks = ['#collapse1', '#collapse2', '#collapse3', '#collapse4'];
        for (const sel of expandLinks) {
            try {
                const link = page.locator(`a[href="${sel}"]`);
                if (await link.count() > 0) {
                    const isExpanded = await page.evaluate((selector) => {
                        const el = document.querySelector(selector);
                        return el && el.classList.contains('in');
                    }, sel);
                    if (!isExpanded) {
                        await link.click();
                        await page.waitForTimeout(500);
                    }
                }
            } catch { /* section may not exist */ }
        }

        await page.waitForTimeout(1000);
        const detail = await extractDetailPage(page);
        console.log(JSON.stringify(detail));

    } catch (err) {
        console.log(JSON.stringify({ error: err.message }));
    } finally {
        await context.close();
    }
}

// ══════════════════════════════════════════════════════════
// FULL — Search by filing ID, navigate to detail, extract
// ══════════════════════════════════════════════════════════

async function cmdFull(filingId) {
    const context = await launchBrowser();
    const page = await context.newPage();

    try {
        process.stderr.write(`Looking up Filing ID ${filingId}...\n`);
        await page.goto(SEARCH_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });

        if (!await waitForF5(page)) {
            console.log(JSON.stringify({ error: 'F5 challenge not resolved. Run warmup first.' }));
            return;
        }

        // Search by filing ID (note: capital ID in element name)
        const idInput = page.locator('#MainContent_txtFilingID');
        await idInput.fill(filingId);
        await page.locator('#MainContent_cmdSearch').click();

        // Wait for results
        await page.waitForTimeout(5000);

        // Check if we got results
        const currentUrl = page.url();
        if (currentUrl.includes('FilingDetails.aspx')) {
            // Direct redirect to detail
            await page.waitForFunction(() =>
                !!document.getElementById('txtFilingName'),
                { timeout: 10000 }
            ).catch(() => {});
        } else {
            // Find the result link and click it
            const firstLink = page.locator('li a[href*="FilingDetails.aspx"]').first();
            if (await firstLink.count() > 0) {
                await firstLink.click();
                await page.waitForFunction(() =>
                    !!document.getElementById('txtFilingName'),
                    { timeout: 15000 }
                ).catch(() => {});
            } else {
                console.log(JSON.stringify({ error: `No entity found for Filing ID ${filingId}` }));
                return;
            }
        }

        await page.waitForTimeout(1500);

        // Expand all collapsible sections
        const expandLinks = ['#collapse1', '#collapse2', '#collapse3', '#collapse4'];
        for (const sel of expandLinks) {
            try {
                const link = page.locator(`a[href="${sel}"]`);
                if (await link.count() > 0) {
                    const isExpanded = await page.evaluate((selector) => {
                        const el = document.querySelector(selector);
                        return el && el.classList.contains('in');
                    }, sel);
                    if (!isExpanded) {
                        await link.click();
                        await page.waitForTimeout(500);
                    }
                }
            } catch { /* section may not exist */ }
        }

        await page.waitForTimeout(1000);
        const detail = await extractDetailPage(page);
        console.log(JSON.stringify(detail));

    } catch (err) {
        console.log(JSON.stringify({ error: err.message }));
    } finally {
        await context.close();
    }
}

// ══════════════════════════════════════════════════════════
// CLI DISPATCH
// ══════════════════════════════════════════════════════════

async function main() {
    const args = process.argv.slice(2);
    const command = args[0];

    if (!command) {
        process.stderr.write('Usage:\n');
        process.stderr.write('  node _wy_browser_helper.js warmup\n');
        process.stderr.write('  node _wy_browser_helper.js search "QUERY" [--contains]\n');
        process.stderr.write('  node _wy_browser_helper.js search-id "2021-001032098"\n');
        process.stderr.write('  node _wy_browser_helper.js detail <eFNum>\n');
        process.stderr.write('  node _wy_browser_helper.js full <filing_id>\n');
        process.exit(1);
    }

    switch (command) {
        case 'warmup':
            await cmdWarmup();
            break;

        case 'search': {
            const query = args[1];
            if (!query) {
                process.stderr.write('ERROR: search requires a query string\n');
                process.exit(1);
            }
            const contains = args.includes('--contains');
            await cmdSearch(query, contains);
            break;
        }

        case 'search-id': {
            const filingId = args[1];
            if (!filingId) {
                process.stderr.write('ERROR: search-id requires a filing ID\n');
                process.exit(1);
            }
            await cmdSearchId(filingId);
            break;
        }

        case 'detail': {
            const efNum = args[1];
            if (!efNum) {
                process.stderr.write('ERROR: detail requires an eFNum parameter\n');
                process.exit(1);
            }
            await cmdDetail(efNum);
            break;
        }

        case 'full': {
            const filingId = args[1];
            if (!filingId) {
                process.stderr.write('ERROR: full requires a filing ID\n');
                process.exit(1);
            }
            await cmdFull(filingId);
            break;
        }

        default:
            process.stderr.write(`ERROR: Unknown command: ${command}\n`);
            process.exit(1);
    }
}

main().catch(err => {
    process.stderr.write(`FATAL: ${err.message}\n`);
    process.exit(1);
});
