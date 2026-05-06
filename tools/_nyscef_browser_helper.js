#!/usr/bin/env node
/**
 * NYSCEF guest-search browser helper.
 *
 * Uses a headed Chrome/Chromium session and drives the real browser DOM because
 * NYSCEF guest search is a server-rendered form flow, not a public API.
 *
 * Usage:
 *   node tools/_nyscef_browser_helper.js search-name '{"first_name":"Jeffrey","last_name":"Epstein"}'
 *   node tools/_nyscef_browser_helper.js search-case '{"query":"156728/2019"}'
 *   node tools/_nyscef_browser_helper.js new-cases '{"court":"New York County Supreme Court","date":"2019-07-10"}'
 *   node tools/_nyscef_browser_helper.js detail '{"docket_id":"AcfkebAfF6itr8YHo86mUQ=="}'
 *   node tools/_nyscef_browser_helper.js documents '{"docket_id":"AcfkebAfF6itr8YHo86mUQ=="}'
 *   node tools/_nyscef_browser_helper.js download '{"doc_index":"f0TLN3SKZ/mR_PLUS_Xfj5Dbefw==","output_file":"/tmp/doc.pdf"}'
 */

const fs = require("fs");
const path = require("path");

const BASE_URL = "https://iapps.courts.state.ny.us/nyscef";
const DEFAULT_PAGE_SIZE = 25;

let chromium;
try {
  chromium = require("playwright").chromium;
} catch {
  try {
    chromium = require("playwright-core").chromium;
  } catch {
    process.stderr.write(
      "ERROR: playwright package not found. Install with: npm install -g playwright or run through npx.\n",
    );
    process.exit(1);
  }
}

function normalizeText(value) {
  return String(value || "")
    .replace(/\u00a0/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeMultiline(value) {
  return String(value || "")
    .replace(/\u00a0/g, " ")
    .replace(/\r/g, "")
    .trim();
}

function toAbsoluteUrl(href) {
  if (!href) return null;
  try {
    return new URL(href, `${BASE_URL}/`).toString();
  } catch {
    return null;
  }
}

function extractQueryParam(urlValue, name) {
  if (!urlValue) return null;
  try {
    return new URL(urlValue, `${BASE_URL}/`).searchParams.get(name);
  } catch {
    return null;
  }
}

function normalizeDateInput(value) {
  if (!value) return "";
  const raw = String(value).trim();
  if (!raw) return "";
  if (/^\d{2}\/\d{2}\/\d{4}$/.test(raw)) return raw;
  const iso = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (iso) return `${iso[2]}/${iso[3]}/${iso[1]}`;
  return raw;
}

function parseCaseHeader(bodyText) {
  const text = normalizeMultiline(bodyText);
  const header = {};

  const caseMatch = text.match(/\n([A-Z0-9/-]+)\s+-\s+([^\n]+)\nShort Caption:/);
  if (caseMatch) {
    header.case_number = normalizeText(caseMatch[1]);
    header.court = normalizeText(caseMatch[2]);
  }

  const shortCaptionMatch = text.match(/Short Caption:\s*(.*?)\s+Case Type:\s*(.*?)(?:\n|$)/);
  if (shortCaptionMatch) {
    header.short_caption = normalizeText(shortCaptionMatch[1]);
    header.case_type = normalizeText(shortCaptionMatch[2]);
  }

  const caseStatusMatch = text.match(/Case Status:\s*(.*?)(?:\n|$)/);
  if (caseStatusMatch) header.case_status = normalizeText(caseStatusMatch[1]);

  const efilingStatusMatch = text.match(/eFiling Status:\s*(.*?)(?:\n|$)/);
  if (efilingStatusMatch) header.efiling_status = normalizeText(efilingStatusMatch[1]);

  const assignedJudgeMatch = text.match(/Assigned Judge:\s*(.*?)(?:\n|$)/);
  if (assignedJudgeMatch) header.assigned_judge = normalizeText(assignedJudgeMatch[1]);

  const fullCaptionMatch = text.match(/Full Caption\s+([\s\S]+?)\n(?:Plaintiffs\/Petitioners|Defendants\/Respondents)/);
  if (fullCaptionMatch) header.full_caption = normalizeText(fullCaptionMatch[1]);

  return header;
}

function parseRepresentatives(rawText) {
  const text = normalizeMultiline(rawText);
  if (!text || /^none recorded$/i.test(text)) return [];
  return text
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean)
    .map((block) => {
      const lines = block.split(/\n+/).map(normalizeText).filter(Boolean);
      const firstLine = lines[0] || "";
      const match = firstLine.match(/^(.*?)\s+on\s+(\d{2}\/\d{2}\/\d{4})$/i);
      return {
        name: normalizeText(match ? match[1] : firstLine),
        appeared_on: match ? match[2] : null,
        organization: lines.slice(1).join(" ") || null,
      };
    });
}

async function launchBrowser() {
  const launchOptions = {
    headless: false,
    args: ["--disable-blink-features=AutomationControlled"],
    ignoreDefaultArgs: ["--enable-automation"],
  };

  try {
    const browser = await chromium.launch({
      channel: "chrome",
      ...launchOptions,
    });
    const context = await browser.newContext({ viewport: { width: 1440, height: 1080 } });
    return { browser, context };
  } catch (error) {
    process.stderr.write(`  Falling back to default browser engine: ${error.message}\n`);
    const browser = await chromium.launch(launchOptions);
    const context = await browser.newContext({ viewport: { width: 1440, height: 1080 } });
    return { browser, context };
  }
}

async function getPage(context) {
  const page = await context.newPage();
  page.setDefaultTimeout(120000);
  page.setDefaultNavigationTimeout(120000);
  return page;
}

async function waitForPortal(page) {
  let prompted = false;
  for (let attempt = 0; attempt < 60; attempt += 1) {
    await page.waitForTimeout(1000);
    const title = await page.title().catch(() => "");
    const body = await page.locator("body").innerText().catch(() => "");
    const signal = `${title}\n${body.slice(0, 500)}`;

    if (
      !/Just a moment/i.test(title) &&
      /(Case Search|Case Search Results|Case Details|Document List|NYSCEF)/i.test(signal)
    ) {
      return true;
    }

    if (
      (/Just a moment/i.test(title) || /Enable JavaScript and cookies to continue/i.test(body)) &&
      attempt >= 5 &&
      !prompted
    ) {
      process.stderr.write(
        "\n  Cloudflare challenge detected. If a browser window opened, complete any prompt.\n\n",
      );
      prompted = true;
    }
  }
  return false;
}

async function gotoPortal(page, url) {
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 120000 });
  const ready = await waitForPortal(page);
  if (!ready) {
    throw new Error("NYSCEF did not become ready. Cloudflare challenge may not have cleared.");
  }
}

async function selectOptionByText(page, selector, desired) {
  if (!desired) return;

  const normalizedDesired = normalizeText(desired).toLowerCase();
  const optionValue = await page.locator(`${selector} option`).evaluateAll((options, wanted) => {
    const clean = (value) =>
      String(value || "")
        .replace(/\u00a0/g, " ")
        .replace(/\s+/g, " ")
        .trim();
    const items = options.map((opt) => ({
      value: opt.value,
      text: clean(opt.textContent),
    }));
    const exact = items.find((item) => item.value === wanted || item.text.toLowerCase() === wanted);
    if (exact) return exact.value;
    const partial = items.find((item) => item.text.toLowerCase().includes(wanted));
    return partial ? partial.value : null;
  }, normalizedDesired);

  if (!optionValue) {
    throw new Error(`Could not find option '${desired}' for ${selector}`);
  }
  await page.selectOption(selector, optionValue);
}

async function parseSearchResultsPage(page) {
  return page.evaluate(() => {
    const clean = (value) =>
      String(value || "")
        .replace(/\u00a0/g, " ")
        .replace(/\s+/g, " ")
        .trim();

    const table = document.querySelector('table.NewSearchResults[summary*="cases"]');
    const bodyText = document.body.innerText || "";
    const criteriaMatch = bodyText.match(/Case Search Results([\s\S]*?)Modify Search \| New Search/);
    const criteria = criteriaMatch
      ? criteriaMatch[1]
          .split(/\n+/)
          .map(clean)
          .filter(Boolean)
      : [];

    if (!table) {
      return {
        current_page: Number(new URL(location.href).searchParams.get("PageNum") || "1"),
        total_pages: 1,
        criteria,
        results: [],
        message: /No cases? were found/i.test(bodyText) ? "No cases found" : clean(bodyText).slice(0, 500),
      };
    }

    const rows = Array.from(table.querySelectorAll("tr")).slice(1);
    const results = rows
      .map((row) => {
        const cells = Array.from(row.querySelectorAll("th,td"));
        if (!cells.length) return null;

        if (
          cells.length === 2 &&
          /NOT AVAILABLE TO THE PUBLIC ONLINE/i.test(cells[1].innerText || "")
        ) {
          return {
            public_access: false,
            case_number: "*****",
            received_date: null,
            efiling_status: null,
            case_status: null,
            caption: null,
            court: null,
            case_type: null,
            docket_id: null,
            document_list_url: null,
            access_message: clean(cells[1].innerText),
          };
        }

        if (cells.length < 4) return null;

        const link = cells[0].querySelector('a[href*="DocumentList?docketId="]');
        const href = link ? new URL(link.getAttribute("href"), `${location.origin}/nyscef/`).toString() : null;
        const caseLines = (cells[0].innerText || "").split(/\n+/).map(clean).filter(Boolean);
        const statusLines = (cells[1].innerText || "").split(/\n+/).map(clean).filter(Boolean);
        const courtLines = (cells[3].innerText || "").split(/\n+/).map(clean).filter(Boolean);

        return {
          public_access: Boolean(href),
          case_number: caseLines[0] || null,
          received_date: caseLines[1] || null,
          efiling_status: statusLines[0] || null,
          case_status: statusLines[1] || null,
          caption: clean(cells[2].innerText),
          court: courtLines[0] || null,
          case_type: courtLines.slice(1).join(" ") || null,
          docket_id: href ? new URL(href).searchParams.get("docketId") : null,
          document_list_url: href,
          court_type_param: href ? new URL(href).searchParams.get("courtType") : null,
        };
      })
      .filter(Boolean);

    const pageNumbers = Array.from(
      document.querySelectorAll('a[href*="CaseSearchResults?PageNum="]'),
    )
      .map((anchor) => Number(new URL(anchor.href, location.href).searchParams.get("PageNum")))
      .filter((value) => Number.isFinite(value));

    return {
      current_page: Number(new URL(location.href).searchParams.get("PageNum") || "1"),
      total_pages: pageNumbers.length ? Math.max(...pageNumbers) : 1,
      criteria,
      results,
    };
  });
}

async function collectSearchResults(page, limit) {
  const target = limit && Number.isFinite(limit) && limit > 0 ? limit : DEFAULT_PAGE_SIZE;
  let current = await parseSearchResultsPage(page);
  const collected = [];
  const seen = new Set();

  const addResults = (items) => {
    for (const item of items) {
      const key = item.docket_id || `${item.case_number || "unknown"}|${item.caption || item.access_message || ""}`;
      if (seen.has(key)) continue;
      seen.add(key);
      collected.push(item);
      if (collected.length >= target) break;
    }
  };

  addResults(current.results);

  while (collected.length < target && current.current_page < current.total_pages) {
    const nextPage = current.current_page + 1;
    await page.goto(`${BASE_URL}/CaseSearchResults?PageNum=${nextPage}`, {
      waitUntil: "domcontentloaded",
      timeout: 120000,
    });
    await page.waitForTimeout(1000);
    current = await parseSearchResultsPage(page);
    addResults(current.results);
  }

  return {
    current_page: current.current_page,
    total_pages: current.total_pages,
    criteria: current.criteria || [],
    results: collected.slice(0, target),
  };
}

async function performNameSearch(page, payload) {
  await gotoPortal(page, `${BASE_URL}/CaseSearch?TAB=name`);
  await page.check(payload.search_type === "attorney" ? "#attorneyName" : "#partyName");

  await page.fill("#txtBusinessOrgName", payload.business_name || "");
  await page.fill("#txtPartyFirstName", payload.first_name || "");
  await page.fill("#txtPartyMiddleName", payload.middle_name || "");
  await page.fill("#txtPartyLastName", payload.last_name || "");

  await selectOptionByText(page, "#txtCounty", payload.county);
  await selectOptionByText(page, "#txtCaseType", payload.case_type);

  await page.fill("#txtFilingDateFrom", normalizeDateInput(payload.filed_from));
  await page.fill("#txtFilingDateTo", normalizeDateInput(payload.filed_to));

  const navigation = page.waitForNavigation({ waitUntil: "domcontentloaded", timeout: 30000 }).catch(
    () => null,
  );
  await page.locator('button[name="btnSubmit"]').first().click();
  await navigation;
  await page.waitForTimeout(1200);

  if (!page.url().includes("CaseSearchResults")) {
    const body = await page.locator("body").innerText().catch(() => "");
    return {
      criteria: [],
      current_page: 1,
      total_pages: 1,
      results: [],
      message: normalizeText(body).slice(0, 500),
    };
  }

  return collectSearchResults(page, payload.limit);
}

async function performCaseSearch(page, payload) {
  await gotoPortal(page, `${BASE_URL}/CaseSearch?TAB=caseIdentifier`);

  const mode = payload.mode || "index";
  const radioMap = {
    index: "#indexNumber",
    attorney_file: "#fileNumber",
    third_party: "#thirdPartyNumber",
  };
  const radioSelector = radioMap[mode];
  if (!radioSelector) {
    throw new Error(`Unsupported case search mode: ${mode}`);
  }

  await page.check(radioSelector);
  await page.fill("#txtCaseIdentifierNumber", payload.query || "");
  await selectOptionByText(page, "#txtCounty", payload.county);
  await selectOptionByText(page, "#txtCaseType", payload.case_type);
  await page.fill("#txtFilingDateFrom", normalizeDateInput(payload.filed_from));
  await page.fill("#txtFilingDateTo", normalizeDateInput(payload.filed_to));

  const navigation = page.waitForNavigation({ waitUntil: "domcontentloaded", timeout: 30000 }).catch(
    () => null,
  );
  await page.locator('button[name="btnSubmit"]').first().click();
  await navigation;
  await page.waitForTimeout(1200);

  if (!page.url().includes("CaseSearchResults")) {
    const body = await page.locator("body").innerText().catch(() => "");
    return {
      criteria: [],
      current_page: 1,
      total_pages: 1,
      results: [],
      message: normalizeText(body).slice(0, 500),
    };
  }

  return collectSearchResults(page, payload.limit);
}

async function performNewCasesSearch(page, payload) {
  await gotoPortal(page, `${BASE_URL}/CaseSearch?TAB=courtDateRange`);
  await selectOptionByText(page, "#selCountyCourt", payload.court);
  await page.fill("#txtFilingDate", normalizeDateInput(payload.date));

  const navigation = page.waitForNavigation({ waitUntil: "domcontentloaded", timeout: 30000 }).catch(
    () => null,
  );
  await page.locator('button[name="btnSubmit"]').first().click();
  await navigation;
  await page.waitForTimeout(1200);

  if (!page.url().includes("CaseSearchResults")) {
    const body = await page.locator("body").innerText().catch(() => "");
    return {
      criteria: [],
      current_page: 1,
      total_pages: 1,
      results: [],
      message: normalizeText(body).slice(0, 500),
    };
  }

  return collectSearchResults(page, payload.limit);
}

async function fetchCaseDetail(page, payload) {
  await gotoPortal(page, `${BASE_URL}/CaseDetails?docketId=${encodeURIComponent(payload.docket_id)}`);

  return page.evaluate(() => {
    const clean = (value) =>
      String(value || "")
        .replace(/\u00a0/g, " ")
        .replace(/\s+/g, " ")
        .trim();

    const normalizeMultilineInner = (value) =>
      String(value || "")
        .replace(/\u00a0/g, " ")
        .replace(/\r/g, "")
        .trim();

    const parseHeader = (bodyText) => {
      const text = normalizeMultilineInner(bodyText);
      const out = {};
      const caseMatch = text.match(/\n([A-Z0-9/-]+)\s+-\s+([^\n]+)\nShort Caption:/);
      if (caseMatch) {
        out.case_number = clean(caseMatch[1]);
        out.court = clean(caseMatch[2]);
      }
      const shortCaptionMatch = text.match(/Short Caption:\s*(.*?)\s+Case Type:\s*(.*?)(?:\n|$)/);
      if (shortCaptionMatch) {
        out.short_caption = clean(shortCaptionMatch[1]);
        out.case_type = clean(shortCaptionMatch[2]);
      }
      const caseStatusMatch = text.match(/Case Status:\s*(.*?)(?:\n|$)/);
      if (caseStatusMatch) out.case_status = clean(caseStatusMatch[1]);
      const efilingStatusMatch = text.match(/eFiling Status:\s*(.*?)(?:\n|$)/);
      if (efilingStatusMatch) out.efiling_status = clean(efilingStatusMatch[1]);
      const assignedJudgeMatch = text.match(/Assigned Judge:\s*(.*?)(?:\n|$)/);
      if (assignedJudgeMatch) out.assigned_judge = clean(assignedJudgeMatch[1]);
      const fullCaptionMatch = text.match(/Full Caption\s+([\s\S]+?)\n(?:Plaintiffs\/Petitioners|Defendants\/Respondents)/);
      if (fullCaptionMatch) out.full_caption = clean(fullCaptionMatch[1]);
      return out;
    };

    const parseRepresentativesInner = (rawText) => {
      const text = normalizeMultilineInner(rawText);
      if (!text || /^none recorded$/i.test(text)) return [];
      return text
        .split(/\n{2,}/)
        .map((block) => block.trim())
        .filter(Boolean)
        .map((block) => {
          const lines = block.split(/\n+/).map(clean).filter(Boolean);
          const firstLine = lines[0] || "";
          const match = firstLine.match(/^(.*?)\s+on\s+(\d{2}\/\d{2}\/\d{4})$/i);
          return {
            name: clean(match ? match[1] : firstLine),
            appeared_on: match ? match[2] : null,
            organization: lines.slice(1).join(" ") || null,
          };
        });
    };

    const parsePartyTable = (table) =>
      Array.from(table.querySelectorAll("tr"))
        .slice(1)
        .map((row) => {
          const cells = Array.from(row.querySelectorAll("th,td"));
          if (!cells.length) return null;
          return {
            name: clean(cells[0]?.innerText),
            representatives: parseRepresentativesInner(cells[1]?.innerText || ""),
          };
        })
        .filter(Boolean);

    const bodyText = document.body.innerText || "";
    const header = parseHeader(bodyText);
    const petitionersTable = document.querySelector('table.NewSearchResults[summary*="Petitioners"]');
    const respondentsTable = document.querySelector('table.NewSearchResults[summary*="Respondents"]');
    const documentListLink = document.querySelector('a[href*="SearchDocuments?docketId="]');

    return {
      ...header,
      docket_id: new URL(location.href).searchParams.get("docketId"),
      case_detail_url: location.href,
      document_list_url: documentListLink
        ? new URL(documentListLink.getAttribute("href"), `${location.origin}/nyscef/`).toString()
        : null,
      plaintiffs_petitioners: petitionersTable ? parsePartyTable(petitionersTable) : [],
      defendants_respondents: respondentsTable ? parsePartyTable(respondentsTable) : [],
    };
  });
}

async function fetchDocuments(page, payload) {
  const display = payload.motion_only ? "motion" : "all";
  await gotoPortal(
    page,
    `${BASE_URL}/DocumentList?docketId=${encodeURIComponent(payload.docket_id)}&display=${display}`,
  );

  return page.evaluate(() => {
    const clean = (value) =>
      String(value || "")
        .replace(/\u00a0/g, " ")
        .replace(/\s+/g, " ")
        .trim();

    const normalizeMultilineInner = (value) =>
      String(value || "")
        .replace(/\u00a0/g, " ")
        .replace(/\r/g, "")
        .trim();

    const parseHeader = (bodyText) => {
      const text = normalizeMultilineInner(bodyText);
      const out = {};
      const caseMatch = text.match(/\n([A-Z0-9/-]+)\s+-\s+([^\n]+)\nShort Caption:/);
      if (caseMatch) {
        out.case_number = clean(caseMatch[1]);
        out.court = clean(caseMatch[2]);
      }
      const shortCaptionMatch = text.match(/Short Caption:\s*(.*?)\s+Case Type:\s*(.*?)(?:\n|$)/);
      if (shortCaptionMatch) {
        out.short_caption = clean(shortCaptionMatch[1]);
        out.case_type = clean(shortCaptionMatch[2]);
      }
      const caseStatusMatch = text.match(/Case Status:\s*(.*?)(?:\n|$)/);
      if (caseStatusMatch) out.case_status = clean(caseStatusMatch[1]);
      const efilingStatusMatch = text.match(/eFiling Status:\s*(.*?)(?:\n|$)/);
      if (efilingStatusMatch) out.efiling_status = clean(efilingStatusMatch[1]);
      const assignedJudgeMatch = text.match(/Assigned Judge:\s*(.*?)(?:\n|$)/);
      if (assignedJudgeMatch) out.assigned_judge = clean(assignedJudgeMatch[1]);
      return out;
    };

    const bodyText = document.body.innerText || "";
    const header = parseHeader(bodyText);
    const table = document.querySelector('table.NewSearchResults[summary*="documents"]');
    const documentListLink = document.querySelector('a[href*="SearchDocuments?docketId="]');
    const caseDetailLink = document.querySelector('a[href*="CaseDetails?docketId="]');
    const printLink = document.querySelector('a[href*="pdf=y"]');

    const documents = table
      ? Array.from(table.querySelectorAll("tr"))
          .slice(1)
          .map((row) => {
            const cells = Array.from(row.querySelectorAll("th,td"));
            if (cells.length < 4) return null;

            const docLink = row.querySelector('a[href*="ViewDocument?docIndex="]');
            const confirmationLink = row.querySelector('a[href*="ConfirmationNotice?docId="]');

            const typeLines = normalizeMultilineInner(cells[1].innerText)
              .split(/\n+/)
              .map(clean)
              .filter(Boolean);
            const typeLine = typeLines[0] || null;
            const motionMatch = typeLine ? typeLine.match(/\(Motion #([^)]+)\)/i) : null;
            const filedLines = normalizeMultilineInner(cells[2].innerText)
              .split(/\n+/)
              .map(clean)
              .filter(Boolean);
            const statusLines = normalizeMultilineInner(cells[3].innerText)
              .split(/\n+/)
              .map(clean)
              .filter(Boolean);
            const filedLine = filedLines.find((line) => /^Filed:/i.test(line));
            const receivedLine = filedLines.find((line) => /^Received:/i.test(line));
            const terminalStatus = statusLines[0] || null;
            const documentUrl = docLink
              ? new URL(docLink.getAttribute("href"), `${location.origin}/nyscef/`).toString()
              : null;
            const confirmationUrl = confirmationLink
              ? new URL(confirmationLink.getAttribute("href"), `${location.origin}/nyscef/`).toString()
              : null;

            return {
              document_number: clean(cells[0].innerText),
              document_type: typeLine ? clean(typeLine.replace(/\s*\(Motion #[^)]+\)/i, "")) : null,
              motion_number: motionMatch ? motionMatch[1] : null,
              description: typeLines.slice(1).join(" ") || null,
              filed_by:
                filedLines.find((line) => !/^Filed:/i.test(line) && !/^Received:/i.test(line)) || null,
              filed_date: filedLine ? clean(filedLine.replace(/^Filed:/i, "")) : null,
              received_date: receivedLine ? clean(receivedLine.replace(/^Received:/i, "")) : null,
              status: terminalStatus || null,
              document_url: documentUrl,
              doc_index: documentUrl ? new URL(documentUrl).searchParams.get("docIndex") : null,
              confirmation_url: confirmationUrl,
              confirmation_id: confirmationUrl ? new URL(confirmationUrl).searchParams.get("docId") : null,
            };
          })
          .filter(Boolean)
      : [];

    return {
      ...header,
      docket_id: new URL(location.href).searchParams.get("docketId"),
      document_list_url: documentListLink
        ? new URL(documentListLink.getAttribute("href"), `${location.origin}/nyscef/`).toString()
        : location.href,
      case_detail_url: caseDetailLink
        ? new URL(caseDetailLink.getAttribute("href"), `${location.origin}/nyscef/`).toString()
        : null,
      print_document_list_url: printLink
        ? new URL(printLink.getAttribute("href"), `${location.origin}/nyscef/`).toString()
        : null,
      documents,
    };
  });
}

async function downloadPdf(page, payload) {
  const targetUrl = payload.url
    ? payload.url
    : `${BASE_URL}/ViewDocument?docIndex=${encodeURIComponent(payload.doc_index)}`;

  await gotoPortal(page, `${BASE_URL}/CaseSearch`);
  const response = await page.evaluate(async (url) => {
    const resp = await fetch(url);
    const contentType = resp.headers.get("content-type") || "";
    const buffer = await resp.arrayBuffer();
    const bytes = new Uint8Array(buffer);
    let binary = "";
    const chunkSize = 0x8000;
    for (let i = 0; i < bytes.length; i += chunkSize) {
      binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
    }
    return {
      status: resp.status,
      content_type: contentType,
      body_base64: btoa(binary),
      bytes: bytes.length,
    };
  }, targetUrl);

  const contentType = response.content_type || "";
  if (response.status !== 200) {
    throw new Error(`Expected HTTP 200 but received ${response.status}`);
  }
  if (!/application\/pdf/i.test(contentType)) {
    throw new Error(`Expected PDF response but received '${contentType || "unknown"}'`);
  }

  const body = Buffer.from(response.body_base64, "base64");
  fs.mkdirSync(path.dirname(payload.output_file), { recursive: true });
  fs.writeFileSync(payload.output_file, body);

  return {
    output_file: payload.output_file,
    source_url: targetUrl,
    bytes: body.length,
    content_type: contentType,
  };
}

async function main() {
  const command = process.argv[2];
  const payloadArg = process.argv[3];
  if (!command || !payloadArg) {
    process.stderr.write("Usage: _nyscef_browser_helper.js <command> <json-payload>\n");
    process.exit(1);
  }

  let payload;
  try {
    payload = JSON.parse(payloadArg);
  } catch (error) {
    process.stderr.write(`ERROR: Invalid JSON payload: ${error.message}\n`);
    process.exit(1);
  }

  const { browser, context } = await launchBrowser();
  const page = await getPage(context);

  try {
    let result;
    if (command === "search-name") {
      result = await performNameSearch(page, payload);
    } else if (command === "search-case") {
      result = await performCaseSearch(page, payload);
    } else if (command === "new-cases") {
      result = await performNewCasesSearch(page, payload);
    } else if (command === "detail") {
      result = await fetchCaseDetail(page, payload);
    } else if (command === "documents") {
      result = await fetchDocuments(page, payload);
    } else if (command === "download") {
      result = await downloadPdf(page, payload);
    } else {
      throw new Error(`Unknown command: ${command}`);
    }

    process.stdout.write(`${JSON.stringify(result)}\n`);
  } finally {
    await context.close();
    await browser.close();
  }
}

main().catch((error) => {
  process.stderr.write(`ERROR: ${error.message}\n`);
  process.exit(1);
});
