'use strict';
// No browser/runtime launch: exercise serial form reset and challenge handling.
const assert = require('node:assert/strict');
const {perform, validateRequest, closeOwnedBrowser, isChallenge} = require('../tools/_ma_ucc_browser_helper.js');

function fakeSession(challenge = false) {
    const values = new Map();
    const checks = new Map([['#MainContent_chkSecuredParty', true], ['#MainContent_chkAssignee', true]]);
    const calls = [];
    let result = false;
    const page = {
        locator(selector) {
            return {
                async count() {
                    if (selector === '#MainContent_btnNewSearch') return result ? 1 : 0;
                    if (selector === '#MainContent_grdSearchResults') return result ? 1 : 0;
                    if (selector === '#MainContent_lblMessage') return 0;
                    return 1;
                },
                async waitFor() {},
                async inputValue() { return values.get(selector) || ''; },
                async isChecked() { return checks.get(selector) || false; },
                async fill(value) { calls.push(['fill', selector, value]); values.set(selector, value); },
                async selectOption(value) { values.set(selector, typeof value === 'string' ? value : ''); },
                async evaluate() { return values.get(selector) ? 1 : 0; },
                async click() { result = selector === '#MainContent_btnSearch'; calls.push(['click', selector]); },
            };
        },
        async goto(url) { calls.push(['goto', url]); result = false; return {status: () => challenge ? 500 : 200}; },
        async content() { return challenge ? '<h1>Access Denied</h1>Error 15 automated traffic' : '<h2>UCC Search Results</h2>'; },
        url() { return 'https://corp.sec.state.ma.us/CorpWeb/UCCSearch/UCCSearchResults.aspx'; },
    };
    return {
        page, values, checks, calls, requests: 0, metadata: {}, lastScope: null,
        navigate: operation => operation(), postback: operation => operation(),
        async check(selector, value) { checks.set(selector, value); },
        async select(selector, value) { values.set(selector, value); },
    };
}

(async () => {
    const session = fakeSession();
    const base = {command: 'search-org', query: 'FIRST', limit: 25, role: 'secured', search_type: 'begins', lapsed: false};
    await perform(validateRequest({...base, city: 'BOSTON', state: 'MA', since: '01/01/2020'}), session);
    const second = await perform(validateRequest({...base, query: 'SECOND', role: 'debtor', city: null, state: null, since: null}), session);
    assert.equal(second.submitted.query, 'SECOND');
    assert.equal(second.runtime.session_request, 2);
    assert.equal(session.values.get('#MainContent_txtOCity'), '');
    assert.equal(session.values.get('#MainContent_cboOState'), '');
    assert.equal(session.values.get('#MainContent_txtStartDate'), '');
    assert.equal(session.checks.get('#MainContent_chkSecuredParty'), false);
    assert.equal(session.checks.get('#MainContent_chkAssignee'), false);
    assert.equal(session.checks.get('#MainContent_chkDebtor'), true);
    assert.equal(session.calls.filter(c => c[0] === 'goto').length, 1);
    assert.equal(session.calls.filter(c => c[1] === '#MainContent_btnNewSearch').length, 1);
    await perform(validateRequest({...base, query: 'THIRD', lapsed: true}), session);
    assert.equal(session.calls.filter(c => c[0] === 'goto').at(-1)[1].endsWith('?SearchLapsed=True'), true);

    const individual = {command: 'search-individual', query: 'SMITH', role: 'debtor', limit: 25, search_type: 'begins'};
    await perform(validateRequest({...individual, first: 'JOHN', middle: 'X', suffix: 'JR'}), session);
    await perform(validateRequest({...individual, first: '', middle: '', suffix: ''}), session);
    for (const field of ['FirstName', 'MiddleName', 'Suffix']) assert.equal(session.values.get(`#MainContent_txt${field}`), '');

    const challenged = fakeSession(true);
    await assert.rejects(perform(validateRequest({...base}), challenged), /challenge detected.*not retried/);
    assert.equal(challenged.calls.filter(c => c[0] === 'goto').length, 1);
    assert.equal(isChallenge('AccessDenied Error15'), true);
    assert.throws(() => validateRequest({...base, since: '02/30/2026'}), /real date/);
    let closed = 0;
    const lifecycle = {browser: {async close() { closed += 1; }}, closing: null};
    await closeOwnedBrowser(lifecycle);
    await closeOwnedBrowser(lifecycle);
    assert.equal(closed, 1);
    process.stdout.write('Offline helper state-reset, archive separation, no-challenge-retry and owned-cleanup checks passed.\n');
})().catch(error => { process.stderr.write(`${error.stack}\n`); process.exit(1); });
