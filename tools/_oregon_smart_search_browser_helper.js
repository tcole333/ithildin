#!/usr/bin/env node
/**
 * Render and inspect Oregon Judicial Department Smart Search.
 *
 * The source's search contract is assembled in the browser from Kendo widgets.
 * This helper reports that contract without submitting a search.
 *
 * Usage:
 *   node tools/_oregon_smart_search_browser_helper.js runtime-check
 *   node tools/_oregon_smart_search_browser_helper.js probe
 *   node tools/_oregon_smart_search_browser_helper.js options SearchBy
 */

'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');

const SOURCE_URL =
    'https://webportal.courts.oregon.gov/portal/Home/Dashboard/29';
const EXPECTED_FORM_PATH = '/portal/SmartSearch/SmartSearch/SmartSearch';
const OPTION_FIELDS = Object.freeze({
    JudicialOfficerSearchBy: 'caseCriteria_JudicialOfficerSearchBy',
    NameSuffix: 'caseCriteria_NameSuffix',
    CourtLocation: 'caseCriteria_CourtLocation',
    SearchBy: 'caseCriteria_SearchBy',
    CaseType: 'caseCriteria_CaseType',
    CaseStatus: 'caseCriteria_CaseStatus',
    JudicialOfficer: 'caseCriteria_JudicialOfficer',
    JudgmentType: 'caseCriteria_JudgmentType',
    WarrantType: 'caseCriteria_WarrantType',
    WarrantStatus: 'caseCriteria_WarrantStatus',
});

class RuntimeDependencyError extends Error {}
class SourceContractError extends Error {}

function loadChromium() {
    const override = process.env.OREGON_SMART_SEARCH_PLAYWRIGHT_MODULE;
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
    const requestedChannel =
        process.env.OREGON_SMART_SEARCH_BROWSER_CHANNEL || 'chrome';
    let executable = null;
    if (requestedChannel === 'chrome') {
        executable = systemChromePath();
        if (!executable) {
            throw new RuntimeDependencyError(
                'Google Chrome runtime not found; select an installed browser ' +
                'with OREGON_SMART_SEARCH_BROWSER_CHANNEL'
            );
        }
    } else if (requestedChannel === 'chromium') {
        executable = chromium.executablePath();
        if (!executable || !fs.existsSync(executable)) {
            throw new RuntimeDependencyError(
                'Playwright Chromium runtime not found'
            );
        }
    }
    return {
        ok: true,
        node: process.version,
        playwright_module: moduleName,
        browser_channel: requestedChannel,
        browser_executable: executable,
        source_url: SOURCE_URL,
        expected_form_path: EXPECTED_FORM_PATH,
    };
}

async function launchBrowser() {
    const info = runtimeInfo();
    const { chromium } = loadChromium();
    const options = {
        headless: process.env.OREGON_SMART_SEARCH_BROWSER_HEADED !== '1',
        viewport: { width: 1440, height: 1000 },
        locale: 'en-US',
        timezoneId: 'America/Los_Angeles',
    };
    if (info.browser_channel === 'chrome') {
        options.channel = 'chrome';
    } else if (info.browser_channel !== 'chromium') {
        options.channel = info.browser_channel;
    }
    const browser = await chromium.launch(options);
    return { browser, info };
}

function compactOptions(options) {
    const data = Array.isArray(options) ? options : [];
    return {
        count: data.length,
        first: data.slice(0, 2),
        last: data.slice(-2),
    };
}

async function readRenderedContract(page, response) {
    const payload = await page.evaluate(({ optionFields }) => {
        const tidy = value => String(value || '').replace(/\s+/g, ' ').trim();
        const optionSets = {};
        for (const [logicalName, elementId] of Object.entries(optionFields)) {
            const element = document.getElementById(elementId);
            const widget = element
                ? window.jQuery?.(element).data('kendoComboBox')
                : null;
            const values = widget?.dataSource?.data()?.toJSON?.() || [];
            optionSets[logicalName] = values.map(value => ({
                text: tidy(value.Text),
                value: String(value.Value ?? ''),
            }));
        }
        const form = document.querySelector('#frmSS');
        const settingsNode = document.querySelector('#settingsViewModelJSON');
        let settings = {};
        try {
            settings = JSON.parse(settingsNode?.textContent || '{}');
        } catch (error) {
            settings = { parse_error: String(error) };
        }
        const namedControls = form
            ? [...form.querySelectorAll('[name]')].map(element => ({
                name: element.name,
                type: element.type || element.tagName.toLowerCase(),
                checked:
                    element.type === 'checkbox' ||
                    element.type === 'radio'
                        ? Boolean(element.checked)
                        : null,
            }))
            : [];
        return {
            title: document.title,
            final_url: window.location.href,
            form: form
                ? {
                    action: form.action,
                    method: form.method.toLowerCase(),
                    named_controls: namedControls,
                }
                : null,
            settings,
            captcha: {
                enabled:
                    document.querySelector('#Settings_CaptchaEnabled')?.value,
                disabled_for_authenticated:
                    document.querySelector(
                        '#Settings_CaptchaDisabledForAuthenticated'
                    )?.value,
                provider: 'google_recaptcha',
                frame_count: [...document.querySelectorAll('iframe')].filter(
                    frame => (frame.src || '').includes('recaptcha')
                ).length,
            },
            option_sets: optionSets,
            panels: [...document.querySelectorAll('a[href^="#"]')]
                .map(link => tidy(link.textContent))
                .filter(Boolean),
        };
    }, { optionFields: OPTION_FIELDS });
    payload.http_status = response.status();
    payload.source_url = SOURCE_URL;
    return payload;
}

function validateContract(payload) {
    if (payload.http_status !== 200) {
        throw new SourceContractError(
            `Smart Search returned HTTP ${payload.http_status}`
        );
    }
    if (!payload.form) {
        throw new SourceContractError('Smart Search form #frmSS was not found');
    }
    const action = new URL(payload.form.action);
    if (action.pathname !== EXPECTED_FORM_PATH || payload.form.method !== 'post') {
        throw new SourceContractError(
            `Smart Search form contract changed: ${payload.form.method} ` +
            `${action.pathname}`
        );
    }
    for (const required of ['CourtLocation', 'SearchBy', 'CaseType', 'CaseStatus']) {
        if (!payload.option_sets[required]?.length) {
            throw new SourceContractError(
                `Smart Search option set is empty: ${required}`
            );
        }
    }
}

async function renderedContract() {
    const { browser, info } = await launchBrowser();
    try {
        const page = await browser.newPage();
        page.setDefaultNavigationTimeout(90000);
        const response = await page.goto(SOURCE_URL, {
            waitUntil: 'networkidle',
            timeout: 90000,
        });
        if (!response) {
            throw new SourceContractError('Smart Search returned no document response');
        }
        const payload = await readRenderedContract(page, response);
        validateContract(payload);
        payload.runtime = {
            playwright_module: info.playwright_module,
            browser_channel: info.browser_channel,
        };
        return payload;
    } finally {
        await browser.close();
    }
}

async function probe() {
    const payload = await renderedContract();
    const compact = {};
    for (const [name, values] of Object.entries(payload.option_sets)) {
        compact[name] = compactOptions(values);
    }
    for (const name of [
        'CourtLocation',
        'SearchBy',
        'CaseType',
        'CaseStatus',
        'WarrantType',
        'WarrantStatus',
    ]) {
        compact[name].values = payload.option_sets[name];
    }
    payload.option_sets = compact;
    return payload;
}

async function options(fieldName) {
    if (!Object.hasOwn(OPTION_FIELDS, fieldName)) {
        throw new SourceContractError(
            `Unknown option field ${fieldName}; choose one of ` +
            Object.keys(OPTION_FIELDS).join(', ')
        );
    }
    const payload = await renderedContract();
    return {
        source_url: payload.source_url,
        final_url: payload.final_url,
        http_status: payload.http_status,
        field: fieldName,
        options: payload.option_sets[fieldName],
        option_count: payload.option_sets[fieldName].length,
        runtime: payload.runtime,
    };
}

function emit(payload) {
    process.stdout.write(`${JSON.stringify(payload)}\n`);
}

async function main() {
    const [command, fieldName] = process.argv.slice(2);
    if (command === 'runtime-check') {
        emit(runtimeInfo());
        return;
    }
    if (command === 'probe') {
        emit(await probe());
        return;
    }
    if (command === 'options') {
        emit(await options(fieldName));
        return;
    }
    throw new SourceContractError(
        'Usage: _oregon_smart_search_browser_helper.js ' +
        '{runtime-check|probe|options FIELD}'
    );
}

main().catch(error => {
    process.stderr.write(`${JSON.stringify({
        error: {
            type: error.name || error.constructor?.name || 'Error',
            message: error.message || String(error),
        },
    })}\n`);
    process.exitCode = 1;
});
