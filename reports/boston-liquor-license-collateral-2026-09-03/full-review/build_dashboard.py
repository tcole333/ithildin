#!/usr/bin/env python3
"""Build the standalone Boston review explorer from review-data.json.

Usage: uv run python path/to/build_dashboard.py [INPUT] [--output OUTPUT]
No network access, browser libraries, or external runtime assets are required.
"""

import argparse
import json
from pathlib import Path

PAGE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; base-uri 'none'; form-action 'none'">
<title>Boston liquor licenses · Review explorer</title>
<style>
:root{color-scheme:light;--ink:#192b38;--muted:#566875;--line:#d7e0e5;--paper:#f5f7f7;--blue:#225a76;--soft:#eaf2f5;--amber:#775215}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}main{max-width:1680px;margin:auto;padding:32px 32px 60px}h1,h2,h3,p{margin-top:0}h1{font-size:clamp(26px,3vw,40px);line-height:1.15;letter-spacing:-.035em;margin-bottom:12px}h2{font-size:20px;letter-spacing:-.015em;margin-bottom:6px}h3{font-size:15px}header{margin-bottom:24px}.eyebrow{text-transform:uppercase;letter-spacing:.13em;font-size:11px;font-weight:750;color:var(--blue);margin-bottom:10px}.subtitle{color:var(--muted);max-width:950px;font-size:16px;margin-bottom:10px}.fine{font-size:12px;color:var(--muted)}.boundary{border-left:4px solid var(--blue);background:var(--soft);padding:15px 18px;margin:22px 0}.boundary p{margin:0}.boundary p+p{margin-top:5px}.panel{background:#fff;border:1px solid var(--line);border-radius:10px;padding:20px;margin-bottom:18px}.section-head{display:flex;justify-content:space-between;align-items:flex-start;gap:20px}.section-head p{color:var(--muted);margin-bottom:16px;max-width:940px}.metrics{display:grid;grid-template-columns:repeat(4,minmax(130px,1fr));gap:12px;margin:14px 0 18px}.metric{padding:15px 18px;border:1px solid var(--line);border-radius:8px;background:#fff}.metric strong{display:block;font-size:28px;letter-spacing:-.03em}.metric span{font-size:12px;color:var(--muted)}.filters{display:grid;grid-template-columns:2fr repeat(3,1fr);gap:13px}label{font-size:12px;font-weight:650;display:block;color:var(--muted)}input,select,button{font:inherit}input,select{display:block;width:100%;margin-top:5px;padding:10px;border:1px solid #a9bbc5;border-radius:5px;background:white;color:var(--ink);min-height:43px}input:focus-visible,select:focus-visible,button:focus-visible,a:focus-visible,summary:focus-visible{outline:3px solid #70a7bd;outline-offset:3px}button{border:1px solid #a9bbc5;background:#fff;color:var(--blue);border-radius:5px;cursor:pointer;padding:8px 12px;font-size:13px;font-weight:650}button:hover{background:var(--soft)}button:disabled{cursor:default;opacity:.45}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:6px}table{border-collapse:collapse;width:100%;text-align:left;background:white}caption{text-align:left;padding:12px 14px;color:var(--muted);font-size:13px}th{font-size:11px;letter-spacing:.035em;text-transform:uppercase;color:var(--muted);background:#f1f5f6;position:sticky;top:0;white-space:nowrap}th,td{padding:13px 14px;border-bottom:1px solid var(--line);vertical-align:top}td{font-size:13px;max-width:250px;overflow-wrap:anywhere}tbody tr:last-child td{border-bottom:0}tbody tr:hover{background:#f9fbfc}.primary{font-weight:650}.secondary{display:block;color:var(--muted);font-size:12px;margin-top:4px}.badge{display:inline-block;padding:3px 7px;border-radius:4px;background:#edf2f4;color:#355367;font-size:11px;line-height:1.4;max-width:210px}.pending{background:#f7f0e4;color:var(--amber)}.number{text-align:right;font-variant-numeric:tabular-nums}.empty{text-align:center;padding:35px;color:var(--muted)}.pager{display:flex;justify-content:space-between;align-items:center;gap:14px;margin-top:13px}.pager-actions{display:flex;gap:7px}.coverage-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin:16px 0}.coverage-item dd{font-variant-numeric:tabular-nums}.coverage-item .coverage-number{font-size:26px;font-weight:700;letter-spacing:-.025em}.coverage-item small{display:block;font-size:11px;color:var(--muted);margin-top:5px}.coverage-detail{margin-top:16px}.coverage-detail pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.5 ui-monospace,monospace;background:#f5f7f7;border-radius:6px;padding:14px;max-height:380px;overflow:auto}.scope-note{margin:8px 0 0;font-size:13px;color:var(--blue);font-weight:650}.coverage-item{padding:12px;border:1px solid var(--line);border-radius:5px;min-width:0}.coverage-item dt{font-size:12px;color:var(--muted);margin-bottom:5px}.coverage-item dd{margin:0;font-size:16px;overflow-wrap:anywhere}.coverage-item pre{white-space:pre-wrap;overflow-wrap:anywhere;margin:0;font:12px/1.5 ui-monospace,monospace}summary{cursor:pointer;color:var(--blue);font-weight:650}details summary+p{margin-top:12px}.below{display:grid;grid-template-columns:1.25fr 1fr;gap:18px;align-items:start}.below .panel{min-width:0}.metadata{white-space:pre-wrap;font:12px/1.6 ui-monospace,monospace;overflow-wrap:anywhere}.group-table td{max-width:400px}.group-table td:first-child{min-width:145px}.group-note{font-size:12px;color:var(--muted);margin:10px 0 0}a{color:var(--blue);text-underline-offset:3px}dialog{border:1px solid var(--line);border-radius:12px;max-width:840px;width:calc(100% - 32px);max-height:90vh;padding:0;color:var(--ink);box-shadow:0 24px 80px #142e3d33}dialog::backdrop{background:#142e3d70}.dialog-head{display:flex;justify-content:space-between;align-items:start;gap:20px;padding:22px 24px 16px;border-bottom:1px solid var(--line)}.dialog-head h2{margin:0}.dialog-body{padding:20px 24px}.detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:0 0 22px}.detail-grid div{min-width:0}.detail-grid dt{font-size:11px;text-transform:uppercase;letter-spacing:.035em;color:var(--muted)}.detail-grid dd{margin:3px 0 0;font-size:14px;white-space:pre-wrap;overflow-wrap:anywhere}.note{white-space:pre-wrap;overflow-wrap:anywhere;font-size:14px}.source-list{padding-left:20px}.source-list li{margin:8px 0;overflow-wrap:anywhere}footer{font-size:12px;color:var(--muted);margin-top:25px}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}@media(max-width:1000px){main{padding:22px 18px}.filters{grid-template-columns:repeat(2,1fr)}.below{grid-template-columns:1fr}}@media(max-width:580px){main{padding:20px 12px}.panel{padding:15px}.metrics{grid-template-columns:1fr 1fr}.filters{grid-template-columns:1fr}.section-head{display:block}.section-head button{margin-bottom:12px}.detail-grid{grid-template-columns:1fr}.pager{align-items:start;flex-direction:column}}@media print{body{background:white}main{padding:0}.filters,.pager-actions,button{display:none}.table-wrap{overflow:visible}th{position:static}.panel{break-inside:avoid}dialog{display:none}.below{display:block}}
.history-summary{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}.history-chip{padding:7px 11px;background:var(--soft);border-radius:5px;font-size:12px}.pledge-insight{display:flex;gap:16px;justify-content:space-between;align-items:center;background:#f7f3eb;border-left:3px solid #b58e49;padding:13px 15px;margin:14px 0}.pledge-insight p{margin:0;font-size:13px}.pledge-insight button{flex-shrink:0}.event-card{border:1px solid var(--line);border-radius:7px;padding:14px;margin:10px 0;background:#fff}.event-head{display:flex;gap:10px;justify-content:space-between;align-items:start}.event-head h3{font-size:14px;margin:0 0 8px}.event-card p{font-size:12px;margin:6px 0;color:var(--muted)}.event-card details{margin-top:10px}.event-card pre{font:12px/1.55 system-ui,sans-serif;white-space:pre-wrap;overflow-wrap:anywhere;background:#f6f8f8;padding:12px;border-radius:5px;max-height:350px;overflow:auto}.matched-event{border-left:4px solid var(--blue)}.timeline{margin:10px 0 22px}.history-note{margin:0 0 16px;font-size:12px;color:var(--muted)}.review-summary{font-size:13px;margin:12px 0}.extra-filters{margin-top:12px}.extra-filters .filters{margin-top:13px}.event-counts{font-size:12px;color:var(--muted);margin:0 0 12px}@media(max-width:580px){.pledge-insight{display:block}.pledge-insight button{margin-top:10px}.event-head{display:block}}
[hidden]{display:none!important}.pause-note{background:#fff3dd;border:1px solid #e8c582;border-left:5px solid #a76b15;border-radius:6px;padding:14px 17px;margin:18px 0}.pause-note p{margin:5px 0 0;font-size:13px}.pause-note strong{font-size:15px}
</style>
</head>
<body>
<main>
<header><div class="eyebrow">Public records · Boston</div><h1>Liquor license review</h1><p class="subtitle">Explore the full inventory alongside ownership research, transfer evidence, and Massachusetts UCC searches.</p><p class="fine" id="snapshot"></p><p class="scope-note" id="scope-note"></p></header>
<div class="pause-note" id="ucc-pause" role="status" hidden></div>
<div class="boundary" role="note"><p><strong>An inventory is not a completed review.</strong> Coverage below shows the work recorded in this snapshot.</p><p>A completed UCC index query does not determine whether a license has a lien. An index match may concern other collateral, terminated filings, or several records for one transaction. Unassigned ownership remains unresolved; it does not establish an independent business.</p></div>
<section class="panel" aria-labelledby="coverage-heading"><h2 id="coverage-heading">Review coverage</h2><p class="fine">Reported coverage for the entire snapshot. These figures do not change with the table filters.</p><dl class="coverage-grid" id="coverage"></dl><p class="review-summary" id="ownership-coverage"></p><p class="review-summary" id="reconciliation-coverage" hidden></p><p class="review-summary" id="judgment-coverage" hidden></p><details class="coverage-detail"><summary>Detailed coverage</summary><pre id="coverage-detail"></pre></details></section>
<section class="panel" aria-labelledby="history-heading"><h2 id="history-heading">Transfer and pledge history</h2><p class="fine" id="history-scope"></p><div class="table-wrap"><table><caption>Separate finalized source windows</caption><thead><tr><th>Archive window</th><th>Unique documents / PDF pages</th><th>Transfer / pledge actions</th><th>Transfer dispositions</th><th>Pledge dispositions</th><th>Ownership applications</th><th>Separate notices / unresolved proposals</th></tr></thead><tbody id="history-window-rows"></tbody></table></div><div class="history-summary" id="history-summary"></div><div class="pledge-insight" id="pledge-insight" hidden><p id="pledge-comparison"></p><button type="button" id="show-unmarked">View unmarked histories</button></div><p class="history-note">Counts are dated Board actions, including repeated decisions. Applications, granted approvals, pledge releases, and notices of intent to revoke transfers remain separate. They do not establish completed sales or current loan balances.</p><p class="history-note" id="interest-corpus-note" hidden></p><details id="unmatched-board"><summary id="unmatched-summary">Actions not matched to a roster license</summary><p class="fine">These source actions remain outside the license table; missing identifiers are not guessed.</p><div id="unmatched-events"></div></details></section>
<section aria-labelledby="inventory-heading">
<div class="panel"><div class="section-head"><div><h2 id="inventory-heading">Find a license or operator</h2><p>Filter the inventory, then open a record to inspect its review status, notes, and sources.</p></div><button id="reset" type="button">Reset filters</button></div>
<div class="filters">
<label>Search licenses, venues, holders, addresses<input id="search" type="search" placeholder="Name, license number, group or address" autocomplete="off"></label>
<label>Record scope<select id="scope"><option value="alcohol_license" selected>Core alcohol licenses</option><option value="all">Include BYOB / unclear categories</option><option value="boundary">BYOB / unclear categories only</option><option value="byob_separate">BYOB only</option><option value="category_needs_verification">Unclear categories only</option></select></label>
<label>Operator affiliation<select id="group"></select></label>
<label>License category<select id="category"></select></label>
<label>License class<select id="class"></select></label>
<label>Restriction label<select id="restriction-label"></select></label>
<label>Capital category<select id="capital"></select></label>
<label>Current UCC index status<select id="current"></select></label>
<label>Lapsed UCC index status<select id="lapsed"></select></label>
<label>Board action<select id="board-action"></select></label>
<label>Board outcome<select id="board-outcome"></select></label>
<label>Ownership-interest history<select id="interest-history"><option value="">All records</option><option value="matched">Matched application history</option><option value="granted">Granted application</option><option value="continued">Continued application</option><option value="conversion">Explicit entity-form conversion</option><option value="notices">Separate notice / hearing</option><option value="no_history">No matched application history</option></select></label>
<label>Ownership research<select id="ownership-review"><option value="">All records</option><option value="reviewed">Reviewed</option><option value="reviewed_unresolved">Reviewed, unresolved</option><option value="not_reviewed">Not reviewed</option><option value="pe_affiliation">Documented PE group affiliation</option></select></label>
<label>Pledge history / roster notes<select id="finance-marker"><option value="">All records</option><option value="history">Granted pledge history</option><option value="without_marker">Granted pledge history, no finance keywords</option><option value="with_marker">Granted pledge history, finance keywords found</option></select></label>
<label>Rows per page<select id="page-size"><option>25</option><option selected>50</option><option>100</option><option>250</option></select></label>
</div><p class="fine" style="margin:12px 0 0">License categories and literal restriction flags describe the source roster labels only; they do not establish transferability, acquisition route or price. The original license-class filter remains separate.</p><p class="fine">Operator and capital filters use the reviewed snapshot affiliation. They do not establish that the same operator or backing existed on an earlier transfer or pledge date; historical source parties are preserved in each record.</p><p class="fine">Board action and outcome must occur in the same recorded event. Record details retain the full collected timeline, including later notices.</p><details class="extra-filters"><summary>Additional status filters</summary><div class="filters"><label>Transfer status history<select id="transfer"></select></label><label>Pledge status history<select id="pledge"></select></label></div></details></div>
<div class="metrics" id="metrics"></div>
<div class="panel"><p class="event-counts" id="filtered-event-counts" role="status" aria-live="polite"></p><p class="event-counts" id="filtered-interest-counts" role="status" aria-live="polite"></p><div class="table-wrap"><table id="licenses"><caption id="table-caption">License records in the current view</caption><thead><tr><th scope="col">License / venue</th><th scope="col">Legal holder / address</th><th scope="col">Operator / capital</th><th scope="col">Class / roster</th><th scope="col">Current UCC / collateral</th><th scope="col">Lapsed UCC</th><th scope="col">Board history</th><th scope="col">Evidence</th></tr></thead><tbody id="rows"></tbody></table></div><div class="pager"><span id="page-info" class="fine" role="status" aria-live="polite"></span><div class="pager-actions"><button type="button" id="previous">Previous</button><button type="button" id="next">Next</button></div></div></div>
</section>
<div class="below"><section class="panel" aria-labelledby="groups-heading"><h2 id="groups-heading">Reviewed affiliations in this view</h2><p class="fine">Counts reflect reviewed operator/group affiliations, including management or brand relationships where specified. They are not verified common-equity ownership shares or a citywide private-equity percentage.</p><div class="table-wrap"><table class="group-table"><caption class="sr-only">Reviewed operator affiliations represented in the current filter</caption><thead><tr><th scope="col">Group</th><th scope="col">Reported capital category</th><th scope="col" class="number">Licenses in view</th></tr></thead><tbody id="group-rows"></tbody></table></div><p class="group-note" id="group-note"></p></section>
<section class="panel" aria-labelledby="reading-heading"><h2 id="reading-heading">How to read the evidence</h2><p class="fine">A transfer application, local approval, state approval, issued license, and completed sale are different stages. Transfer and pledge counts count application dispositions only. Releases and notices of intent to revoke are separate actions; a notice does not prove revocation occurred.</p><p class="fine">UCC occurrences are index rows, not loans. Specific license collateral requires document review, and current debt balances require separate evidence. A no-match search does not establish that a business has no debt.</p><p class="fine">Private-equity backing and group size are separate characteristics. A bank loan, a national brand, or a franchise relationship alone does not establish private-equity ownership of the local license holder.</p><details><summary>Snapshot metadata</summary><pre class="metadata" id="metadata"></pre></details></section></div>
<footer>Standalone local report. All filtering happens in this page; no data is sent anywhere. Source links open public websites in a new tab.</footer>
</main>
<dialog id="detail" aria-labelledby="detail-title"><div class="dialog-head"><div><div class="eyebrow" id="detail-license"></div><h2 id="detail-title"></h2></div><button type="button" id="close-detail" autofocus>Close</button></div><div class="dialog-body"><dl class="detail-grid" id="detail-fields"></dl><h3>Transfer / pledge timeline</h3><p class="fine" id="detail-event-window"></p><div id="detail-events" class="timeline"></div><h3>Ownership-interest timeline</h3><p class="fine" id="detail-interest-window"></p><div id="detail-interest-events" class="timeline"></div><h3>Other transaction notices and unresolved proposals</h3><p class="fine">These observations stay outside the application-disposition and approval counts. An unprinted or uncertain outcome is not treated as a grant.</p><div id="detail-history-observations" class="timeline"></div><h3>Separate attachment, execution and seizure notices</h3><p class="fine">Historical source parties remain separate from roster holders. Acknowledged notices are not reviewed court or tax instruments; literal amounts are not current debt balances or sums to aggregate.</p><div id="detail-judgment-notices" class="timeline"></div><h3>Reconciled saved UCC histories</h3><p class="fine">Separate review of previously saved text and prior PDF-review evidence. This does not refresh source access, identify loan balances, or complete all collateral and identity checks.</p><div id="detail-reconciled-histories" class="timeline"></div><h3>Source-label classification</h3><p class="fine">These literal class labels do not establish legal transferability, acquisition route, purchase price or ownership. No restriction wording does not mean unrestricted.</p><details class="coverage-detail"><summary>Preserved source labels, flags and row provenance</summary><pre id="detail-source-label-evidence"></pre></details><h3>Review notes</h3><p class="note" id="detail-notes"></p><details class="coverage-detail"><summary>Operator / ownership review evidence</summary><pre id="detail-ownership-evidence"></pre></details><details class="coverage-detail"><summary>UCC query evidence</summary><pre id="detail-ucc-evidence"></pre></details><h3 style="margin-top:22px">Sources</h3><ul class="source-list" id="detail-sources"></ul></div></dialog>
<script type="application/json" id="review-data">__REVIEW_DATA__</script>
<script>
'use strict';
const data = JSON.parse(document.getElementById('review-data').textContent);
const licenses = data.licenses;
const categoryLabels=new Map((data.coverage?.source_label_cohorts?.segments||[]).map(segment=>[segment.source_label_segment,segment.label]));
const restrictionLabels={restricted_literal:'Restricted / Restrict. wording',unrestricted_literal:'Unrestricted wording',ambiguous_rest_abbreviation:'Ambiguous Rest abbreviation',none_in_class_label:'No restriction wording in class (not a legal status)'};
const $ = id => document.getElementById(id);
const text = value => value === null || value === undefined || value === '' ? 'Not supplied' : typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value);
const label = value => text(value).replace(/_/g, ' ');
const normalize = value => String(value ?? '').toLocaleLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '');
const missingGroup = value => !value || /^(unknown|unresolved|unassigned|not[ _]researched|not[ _]reviewed)$/i.test(String(value));
const groupValue = record => missingGroup(record.owner_group) ? '__unassigned__' : String(record.owner_group);
const el = (tag, content, className) => { const node = document.createElement(tag); if (content !== undefined) node.textContent = content; if (className) node.className = className; return node; };
const number = value => Number.isFinite(Number(value)) && value !== null && value !== '' ? Number(value).toLocaleString() : text(value);
const isPending = value => /pending|not[ _]searched|not[ _]reviewed|unreviewed|unknown|unresolved|not supplied/i.test(text(value));
const badge = value => el('span', label(value), 'badge' + (isPending(value) ? ' pending' : ''));
const eventsFor = record => Array.isArray(record.board_events) ? record.board_events : [];
const interestEventsFor = record => Array.isArray(record.ownership_interest_events) ? record.ownership_interest_events : [];
const interestNoticesFor = record => Array.isArray(record.ownership_interest_notices) ? record.ownership_interest_notices : [];
function interestEventMatches(event){const value=$('interest-history').value;return !value||value==='matched'||(value==='granted'&&event.disposition==='granted')||(value==='continued'&&event.disposition==='continued')||(value==='conversion'&&event.entity_conversion_explicit);}
function interestMatches(record){const value=$('interest-history').value;const events=interestEventsFor(record);return !value||(value==='notices'?interestNoticesFor(record).length>0:value==='no_history'?!events.length:events.some(interestEventMatches));}
function appendInterestEvent(parent,event){
 const card=el('article',undefined,'event-card'+($('interest-history').value&&interestEventMatches(event)?' matched-event':''));const head=el('div',undefined,'event-head');head.append(el('h3',text(event.date)+' · '+(event.event_label||(event.event_subtype==='ownership_application_disposition'?'Ownership-interest application':'Ownership-interest notice / hearing'))),badge(event.disposition||event.outcome));card.append(head);
 card.append(el('p','Subject entity: '+text(event.ownership_subject_entity||event.entity_name)));
 if(Array.isArray(event.actions)&&event.actions.length)card.append(el('p','Recorded action: '+event.actions.map(label).join('; ')));
 if(event.entity_conversion_explicit)card.append(el('p','Explicit entity-form conversion: '+text(event.entity_before)+' → '+text(event.entity_after)+'. Entity names are not shareholder names.'));
 card.append(el('p','This record alone does not identify equity control, private-equity sponsorship, or a completed ownership transaction.'));
 if(event.source_window_label)card.append(el('p','Source archive window: '+event.source_window_label));
 const source=publicLink(event.source_locator_url||event.source_url,'Official ownership-interest decision'+(event.page_start?' · page '+event.page_start:'')+(event.item_number?' · item '+event.item_number:''));if(source)card.append(source);
 if(Array.isArray(event.ambiguity_notes)&&event.ambiguity_notes.length)card.append(el('p','Review notes: '+event.ambiguity_notes.join('; ')));
 if(event.item_text){const details=el('details');details.append(el('summary','Source item text'),el('pre',event.item_text));card.append(details);}parent.append(card);
}
const actionLabels = {transfer_application_disposition:'Transfer application disposition',pledge_application_disposition:'Pledge application disposition',pledge_release_acknowledgment:'Pledge release acknowledgment',transfer_revocation_notice:'Notice of intent to revoke transfer'};
function publicLink(rawUrl,title){let url;try{url=new URL(rawUrl);}catch{return null;}if(!['http:','https:'].includes(url.protocol))return null;const link=el('a',title||url.hostname);link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';return link;}
function appendHistoryObservation(parent,event){
 const card=el('article',undefined,'event-card');card.append(el('h3',text(event.date)+' · '+text(event.event_label)),el('p','Source archive window: '+text(event.source_window_label)),el('p','Separate observation; excluded from application-disposition and approval counts. Recorded outcome: '+text(event.disposition||event.outcome)));
 const source=publicLink(event.source_locator_url||event.source_url,'Official source item'+(event.page_start?' · page '+event.page_start:''));if(source)card.append(source);
 if(event.ambiguity_notes?.length)card.append(el('p',event.ambiguity_notes.join('; ')));
 const details=el('details');details.append(el('summary','Full source observation and provenance'),el('pre',JSON.stringify(event,null,2)));card.append(details);parent.append(card);
}
function appendJudgmentNotice(parent,notice){
 const card=el('article',undefined,'event-card');card.append(el('h3',text(notice.source_date)+' · '+label(notice.notice_type)),el('p','Historical source party: '+text(notice.source_named_entity)+(notice.source_dba?' / '+notice.source_dba:'')),el('p','Board disposition: '+text(notice.board_disposition)),el('p',notice.interpretation),el('p',notice.scope_limitations));
 if(notice.amount_usd!==null&&notice.amount_usd!==undefined)card.append(el('p','Literal notice amount: USD '+text(notice.amount_usd)+' · '+label(notice.amount_role)+' · Matter ID: '+text(notice.matter_id)+' (not a current balance or loan amount).'));
 const link=publicLink(notice.source?.page_url,'Official notice · page '+text(notice.source?.page));if(link)card.append(link);
 const details=el('details');details.append(el('summary','Full notice, historical parties, exact roster joins and source hashes'),el('pre',JSON.stringify(notice,null,2)));card.append(details);parent.append(card);
}
function appendReconciledHistory(parent,review){
 const card=el('article',undefined,'event-card');card.append(el('h3','Original UCC '+text(review.original_filing_number)),el('p','Saved source: '+text(review.source_as_of)+' · Reconciled: '+text(review.reviewed_at)),el('p','History: '+label(review.history_text_review_state)+' · Collateral: '+label(review.collateral_review_state)),el('p',review.interpretation));
 for(const caveat of review.party_match?.historical_or_license_continuity_caveats||[])card.append(el('p','Identity / continuity: '+caveat));
 if(review.party_inventory_limitation)card.append(el('p','Party inventory: '+review.party_inventory_limitation));
 for(const event of review.events||[]){const parties=(event.secured_parties_as_saved||[]).map(party=>party.name).filter(Boolean);card.append(el('p',text(event.filing_number)+' · '+text(event.action_as_recorded)+' · '+text(event.filing_datetime_local_as_recorded)+(parties.length?' · Recorded secured-party text: '+parties.join('; '):'')));}
 const documents=el('ul',undefined,'source-list');for(const document of review.document_reviews||[]){const item=el('li');const title=text(document.filing_number)+' ('+text(document.role)+'): '+label(document.pdf_review_state)+(document.pending?' — pending':'');const link=publicLink(document.viewer_url,title);item.append(link||el('span',title),el('span',document.review_scope,'secondary'));documents.append(item);}card.append(documents);
 if(review.pending_actions?.length)card.append(el('p','Remaining work: '+review.pending_actions.map(label).join('; ')));
 const details=el('details');details.append(el('summary','Complete reconciliation evidence and source hashes'),el('pre',JSON.stringify(review,null,2)));card.append(details);parent.append(card);
}
function eventTitle(event){return event.event_label||((actionLabels[event.action_subtype]||label(event.action_subtype))+' '+label(event.disposition));}
function eventMatches(event){return (!$('board-action').value||event.action_subtype===$('board-action').value)&&(!$('board-outcome').value||event.disposition===$('board-outcome').value);}
function appendEvent(parent,event,showLicense=false){
 const card=el('article',undefined,'event-card'+((($('board-action').value||$('board-outcome').value)&&eventMatches(event))?' matched-event':''));
 const head=el('div',undefined,'event-head');head.append(el('h3',(showLicense?text(event.license_num)+' · ':'')+text(event.date)+' · '+eventTitle(event)),badge(event.disposition));card.append(head);
 const parts=[];if(event.transferor)parts.push('From: '+event.transferor+(event.transferor_dba?' ('+event.transferor_dba+')':''));if(event.transferee)parts.push('To: '+event.transferee+(event.transferee_dba?' ('+event.transferee_dba+')':''));if(event.licensee)parts.push('Licensee: '+event.licensee);if(event.pledge_recipient)parts.push('Pledge recipient: '+event.pledge_recipient);for(const part of parts)card.append(el('p',part));
 if(event.action_subtype==='transfer_revocation_notice')card.append(el('p','Acknowledged notice of intent; completed revocation is not established.'));
 if(event.action_subtype==='pledge_release_acknowledgment')card.append(el('p','Release acknowledgment, retained separately from pledge applications.'));
 if(event.source_window_label)card.append(el('p','Source archive window: '+event.source_window_label));
 const source=publicLink(event.source_locator_url||event.source_url,'Official decision'+(event.page_start?' · page '+event.page_start:'')+(event.item_number?' · item '+event.item_number:''));if(source)card.append(source);
 if(event.ambiguity_notes?.length)card.append(el('p','Review notes: '+event.ambiguity_notes.join('; ')));
 if(event.item_text){const detail=el('details');detail.append(el('summary','Source item text'),el('pre',text(event.item_text)));card.append(detail);}parent.append(card);
}
function historyCell(record){const td=el('td');if(!eventsFor(record).length)td.append(el('span','No transfer / pledge action matched','secondary'));else{td.append(el('span','Transfers: '+number(record.transfer_count)+' · Pledges: '+number(record.pledge_count),'primary'));td.append(el('span','Granted: '+number(record.transfer_granted_count)+' transfer / '+number(record.pledge_granted_count)+' pledge','secondary'));if(record.pledge_release_count)td.append(el('span','Release acknowledgments: '+number(record.pledge_release_count),'secondary'));if(record.transfer_revocation_notice_count)td.append(el('span','Intent-to-revoke notices: '+number(record.transfer_revocation_notice_count),'secondary'));}if(interestEventsFor(record).length)td.append(el('span','Ownership-interest applications: '+number(interestEventsFor(record).length),'secondary'));if(interestNoticesFor(record).length)td.append(el('span','Ownership-interest notices: '+number(interestNoticesFor(record).length),'secondary'));return td;}
const allBoardEvents=licenses.flatMap(eventsFor).concat(data.unmatched_board_events||[],data.board_events_matched_only_to_excluded_roster||[]);
let filtered = licenses.slice();
let page = 0;
const filterSpecs = [['group',groupValue],['category',r=>text(r.source_label_segment)],['class',r=>text(r.license_type)],['restriction-label',r=>text(r.restriction_label_state)],['capital',r=>text(r.capital_category)],['current',r=>text(r.current_ucc_status)],['lapsed',r=>text(r.lapsed_ucc_status)],['transfer',r=>text(r.transfer_status)],['pledge',r=>text(r.pledge_status)]];
for (const [id, get] of filterSpecs) {
 const select = $(id); const all = el('option','All'); all.value = ''; select.append(all);
 const values = [...new Set(licenses.map(get))].sort((a,b)=>a.localeCompare(b));
 for (const value of values) { const optionLabel=id==='category'?(categoryLabels.get(value)||label(value)):id==='restriction-label'?(restrictionLabels[value]||label(value)):value==='__unassigned__'?'Unassigned / unresolved':label(value);const option=el('option',optionLabel);option.value = value; select.append(option); }
 select.addEventListener('change', applyFilters);
}
for(const [id,key]of [['board-action','action_subtype'],['board-outcome','disposition']]){const select=$(id);const all=el('option','All');all.value='';select.append(all);for(const value of [...new Set(allBoardEvents.map(event=>event[key]).filter(Boolean))].sort()){const option=el('option',id==='board-action'?(actionLabels[value]||label(value)):label(value));option.value=value;select.append(option);}select.addEventListener('change',applyFilters);}
for(const id of ['ownership-review','finance-marker','interest-history'])$(id).addEventListener('change',applyFilters);
const indexed = licenses.map(record => ({record, haystack: normalize([record.license_num,record.legal_holder,record.dba,record.address,record.owner_group,record.license_type].filter(Boolean).join(' '))}));
$('search').addEventListener('input', applyFilters);
$('scope').addEventListener('change', applyFilters);
if(!licenses.some(r=>r.scope_class==='alcohol_license'))$('scope').value='all';
$('page-size').addEventListener('change',()=>{page=0;render();});
function resetFilters(){ $('search').value='';$('scope').value=licenses.some(r=>r.scope_class==='alcohol_license')?'alcohol_license':'all';for(const [id]of filterSpecs)$(id).value='';for(const id of ['board-action','board-outcome','ownership-review','finance-marker','interest-history'])$(id).value='';page=0;}
$('reset').addEventListener('click',()=>{resetFilters();applyFilters();$('search').focus();});
$('show-unmarked').addEventListener('click',()=>{resetFilters();$('scope').value='all';$('finance-marker').value='without_marker';applyFilters();$('inventory-heading').scrollIntoView({behavior:'smooth'});});
$('previous').addEventListener('click',()=>{page=Math.max(0,page-1);render();});
$('next').addEventListener('click',()=>{page+=1;render();});
function scopeMatches(record){const scope=$('scope').value;return scope==='all'||(scope==='boundary'?record.scope_class!=='alcohol_license':record.scope_class===scope);}
function reviewMatches(record){const value=$('ownership-review').value;return !value||(value==='reviewed'&&record.ownership_reviewed)||(value==='reviewed_unresolved'&&record.ownership_reviewed&&missingGroup(record.owner_group))||(value==='not_reviewed'&&!record.ownership_reviewed)||(value==='pe_affiliation'&&record.documented_pe_group_affiliation);}
function markerMatches(record){const value=$('finance-marker').value;return !value||(record.historical_granted_pledge_in_window&&(value==='history'||(value==='without_marker'&&!record.finance_keyword_marker_any_field)||(value==='with_marker'&&record.finance_keyword_marker_any_field)));}
function boardMatches(record){return (!$('board-action').value&&!$('board-outcome').value)||eventsFor(record).some(eventMatches);}
function applyFilters(){
 const query = normalize($('search').value).trim().split(/\s+/).filter(Boolean);
 filtered=indexed.filter(({record,haystack})=>scopeMatches(record)&&interestMatches(record)&&reviewMatches(record)&&markerMatches(record)&&boardMatches(record)&&query.every(term=>haystack.includes(term))&&filterSpecs.every(([id,get])=>!$(id).value||get(record)===$(id).value)).map(x=>x.record);
 page=0;render();
}
function metric(value, title){const node=el('div',undefined,'metric');node.append(el('strong',number(value)),el('span',title));return node;}
function compoundCell(primary,secondary){const td=el('td');td.append(el('span',text(primary),'primary'));if(secondary)td.append(el('span',String(secondary),'secondary'));return td;}
function statusCell(value,secondary){const td=el('td');td.append(badge(value));if(secondary)td.append(el('span',secondary,'secondary'));return td;}
function render(){
 const size=Number($('page-size').value);const pages=Math.max(1,Math.ceil(filtered.length/size));page=Math.min(page,pages-1);
 const start=page*size, slice=filtered.slice(start,start+size);
 const assigned=new Map();let unassigned=0;let withEvents=0;
 for(const r of filtered){if(missingGroup(r.owner_group))unassigned++;else assigned.set(r.owner_group,(assigned.get(r.owner_group)||0)+1);if(eventsFor(r).length)withEvents++;}
 $('metrics').replaceChildren(metric(filtered.length,'License records in this view'),metric(assigned.size,'Reviewed groups in this view'),metric(unassigned,'Records without a reviewed affiliation'),metric(withEvents,'Records with transfer / pledge actions'));
 const rows=document.createDocumentFragment();
 for(const r of slice){
  const row=el('tr');
  row.append(compoundCell(r.license_num,r.dba),compoundCell(r.legal_holder,r.address),compoundCell(missingGroup(r.owner_group)?'Unassigned / unresolved':r.owner_group,label(r.capital_category)),compoundCell(r.license_type,[text(r.roster_status),r.expires?'Expires '+r.expires:''].filter(Boolean).join(' · ')),statusCell(r.current_ucc_status,'Index rows: '+number(r.current_ucc_occurrences)+' · Collateral: '+label(r.collateral_status)),statusCell(r.lapsed_ucc_status),historyCell(r));
  const action=el('td');const button=el('button','View record');button.type='button';button.setAttribute('aria-label','View evidence for '+text(r.license_num)+' '+text(r.dba));button.addEventListener('click',()=>showDetail(r));action.append(button);row.append(action);rows.append(row);
 }
 if(!slice.length){const row=el('tr'),cell=el('td','No license records match these filters.','empty');cell.colSpan=8;row.append(cell);rows.append(row);}
 $('rows').replaceChildren(rows);
 const matchedEvents=filtered.flatMap(eventsFor).filter(eventMatches);const counts=new Map();for(const event of matchedEvents)counts.set(event.action_subtype,(counts.get(event.action_subtype)||0)+1);
 $('filtered-event-counts').textContent='Matching transfer / pledge events in this view: '+number(matchedEvents.length)+' · '+number(counts.get('transfer_application_disposition')||0)+' transfer dispositions · '+number(counts.get('pledge_application_disposition')||0)+' pledge dispositions · '+number(counts.get('pledge_release_acknowledgment')||0)+' release acknowledgments · '+number(counts.get('transfer_revocation_notice')||0)+' intent-to-revoke notices. Counts are actions, not distinct transactions.';
 const interestMatchesInView=filtered.flatMap(interestEventsFor).filter(interestEventMatches);const licensesWithInterest=filtered.filter(record=>interestEventsFor(record).some(interestEventMatches)).length;$('filtered-interest-counts').textContent='Separate ownership-interest history: '+number(interestMatchesInView.length)+' matching application decisions across '+number(licensesWithInterest)+' licenses in this view; '+number(filtered.flatMap(interestNoticesFor).length)+' separate notices/hearings. These are not included in the transfer / pledge counts.';
 $('table-caption').textContent=number(filtered.length)+' of '+number(licenses.length)+' inventory records match the current filters';
 $('page-info').textContent=filtered.length?'Showing '+number(start+1)+'–'+number(Math.min(start+size,filtered.length))+' of '+number(filtered.length)+' · Page '+number(page+1)+' of '+number(pages):'No matching records';
 $('previous').disabled=page===0;$('next').disabled=page>=pages-1;
 const groups=document.createDocumentFragment();const groupMeta=new Map((data.groups||[]).map(g=>[normalize(g.group_name),g]));
 for(const [name,count] of [...assigned].sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0]))){
  const group=groupMeta.get(normalize(name));const category=group?.capital_category||[...new Set(filtered.filter(r=>r.owner_group===name).map(r=>text(r.capital_category)))].join('; ');
  const row=el('tr');const nameCell=el('td');const button=el('button',name);button.type='button';button.title='Filter inventory to '+name;button.addEventListener('click',()=>{$('group').value=name;applyFilters();$('inventory-heading').scrollIntoView({behavior:'smooth'});});nameCell.append(button);row.append(nameCell,el('td',label(category)),el('td',number(count),'number'));groups.append(row);
 }
 if(!assigned.size){const row=el('tr'),cell=el('td','No reviewed affiliations in this view.','empty');cell.colSpan=3;row.append(cell);groups.append(row);}
 $('group-rows').replaceChildren(groups);$('group-note').textContent=number(unassigned)+' records in this view have no reviewed affiliation. Affiliation can mean ownership, management, or brand membership; see each record’s evidence. Unknowns are not counted as independent operators.';
}
function showDetail(r){
 $('detail-license').textContent=text(r.license_num);$('detail-title').textContent=r.dba||r.legal_holder||'License record';
 const fields=[['Legal holder',r.legal_holder],['Address',r.address],['License class',r.license_type],['Source-label category',categoryLabels.get(r.source_label_segment)||label(r.source_label_segment)],['Source-label family',label(r.source_label_family)],['All preserved source types',(r.source_license_types||[]).join('; ')],['Source categories',(r.source_license_categories||[]).join('; ')],['Restriction wording',restrictionLabels[r.restriction_label_state]||label(r.restriction_label_state)],['Literal class-label flags',r.license_type_literal_flags],['Roster status',r.roster_status],['Expires',r.expires],['Operator group',missingGroup(r.owner_group)?'Unassigned / unresolved':r.owner_group],['Capital category',label(r.capital_category)],['Affiliation review status',label(r.ownership_status)],['Relationship to group',label(r.relationship)],['Reported scale',label(r.scale_band)],['Record scope',label(r.scope_class)],['Current UCC index status',label(r.current_ucc_status)],['Current UCC index occurrences',r.current_ucc_occurrences],['Lapsed UCC index status',label(r.lapsed_ucc_status)],['Collateral review status',label(r.collateral_status)],['Transfer review status',label(r.transfer_status)],['Transfer application dispositions',r.transfer_count],['Transfer applications granted',r.transfer_granted_count],['Pledge status history',r.pledge_status],['Pledge application dispositions',r.pledge_count],['Pledge applications granted',r.pledge_granted_count],['Pledge release acknowledgments',r.pledge_release_count],['Intent-to-revoke notices',r.transfer_revocation_notice_count],['Granted pledge history in window',r.historical_granted_pledge_in_window],['Finance keywords in checked roster fields',r.finance_keyword_marker_any_field],['Ownership research reviewed',r.ownership_reviewed],['Ownership-interest history status',r.ownership_interest_status],['Separate ownership-interest application count',interestEventsFor(r).length],['Separate ownership-interest notices',interestNoticesFor(r).length]];
 const fragment=document.createDocumentFragment();for(const [name,value]of fields){const item=el('div');item.append(el('dt',name),el('dd',text(value)));fragment.append(item);} $('detail-fields').replaceChildren(fragment);
 $('detail-notes').textContent=Array.isArray(r.notes)?r.notes.map(text).join('\n\n'):text(r.notes);
 $('detail-source-label-evidence').textContent=JSON.stringify(r.source_label_evidence||{},null,2);
 $('detail-ownership-evidence').textContent=JSON.stringify({reviewed_match:r.ownership_match_evidence||null,assessment:r.ownership_assessment_evidence||null},null,2);
 $('detail-ucc-evidence').textContent=JSON.stringify(r.ucc_query_evidence||{},null,2);
 const reconciled=document.createDocumentFragment();for(const review of r.reconciled_history_reviews||[])appendReconciledHistory(reconciled,review);if(!reconciled.childElementCount)reconciled.append(el('p','No separate saved-history reconciliation recorded for this license. See other evidence and outstanding review work.','fine'));$('detail-reconciled-histories').replaceChildren(reconciled);
 const timeline=document.createDocumentFragment();const events=eventsFor(r).slice().sort((a,b)=>String(a.date).localeCompare(String(b.date))||String(a.event_id).localeCompare(String(b.event_id)));for(const event of events)appendEvent(timeline,event);if(!events.length)timeline.append(el('p','No explicit action matched this license in the collected window. This is not a complete-history determination.','fine'));$('detail-events').replaceChildren(timeline);
 const observations=document.createDocumentFragment();for(const event of (r.history_source_notices||[]).concat(r.history_proposals_or_unresolved_outcomes||[]))appendHistoryObservation(observations,event);if(!observations.childElementCount)observations.append(el('p','No other transaction notice or unresolved proposal matched this license in these archive windows.','fine'));$('detail-history-observations').replaceChildren(observations);
 $('detail-event-window').textContent=historyWindow+' · '+number(events.length)+' collected actions. Matched by license number; historical holders can differ from the current roster. Full timeline retained; matching events have a blue left border.';
 const judgmentTimeline=document.createDocumentFragment();for(const notice of r.judgment_attachment_notices||[])appendJudgmentNotice(judgmentTimeline,notice);if(!judgmentTimeline.childElementCount)judgmentTimeline.append(el('p','No supplemental notice matched this license by an explicit source license ID. This does not establish absence of attachments or debt.','fine'));$('detail-judgment-notices').replaceChildren(judgmentTimeline);
 const interestTimeline=document.createDocumentFragment();const interestEvents=interestEventsFor(r);const interestNotices=interestNoticesFor(r);const interestRecords=interestEvents.concat(interestNotices).sort((a,b)=>String(a.date).localeCompare(String(b.date)));for(const event of interestRecords)appendInterestEvent(interestTimeline,event);if(!interestRecords.length)interestTimeline.append(el('p','No ownership-interest record matched this license in the collected window. This does not establish that ownership remained unchanged.','fine'));$('detail-interest-events').replaceChildren(interestTimeline);$('detail-interest-window').textContent=historyWindow+' · '+number(interestEvents.length)+' application decisions; '+number(interestNotices.length)+' separate notices/hearings. They do not alter the researched operator or capital assignment above.';
 const sources=document.createDocumentFragment();let count=0;for(const source of (Array.isArray(r.sources)?r.sources:[])){
  if(!source||typeof source.url!=='string')continue;const link=publicLink(source.url,source.label);if(!link)continue;const item=el('li');item.append(link);sources.append(item);count++;
 }
 if(!count)sources.append(el('li','No public HTTP(S) source links supplied for this record.'));
 $('detail-sources').replaceChildren(sources);$('detail').showModal();
}
$('close-detail').addEventListener('click',()=>$('detail').close());
const coverage=data.coverage||{};const coverageNodes=document.createDocumentFragment();
const coreLicenses=licenses.filter(r=>r.scope_class==='alcohol_license').length;
const boundaryLicenses=licenses.filter(r=>r.scope_class&&r.scope_class!=='alcohol_license').length;
const queryDenominator=coverage.holder_groups??null;
const searchProgress=scope=>{const states=coverage.search_states?.[scope];return states?number(states.complete??0)+' / '+number(queryDenominator):'Not supplied';};
const affiliationCount=coverage.ownership_affiliations_mapped??licenses.filter(r=>!missingGroup(r.owner_group)).length;
const eventCount=coverage.licenses_with_collected_events??licenses.filter(r=>eventsFor(r).length).length;
const reviewedCount=coverage.ownership_reviewed_license_count??licenses.filter(r=>r.ownership_reviewed).length;
const reviewedUnresolved=coverage.ownership_reviewed_unresolved_license_count??licenses.filter(r=>r.ownership_reviewed&&missingGroup(r.owner_group)).length;
const peAffiliations=coverage.documented_pe_group_affiliation_license_count??licenses.filter(r=>r.documented_pe_group_affiliation).length;
const peGroups=coverage.documented_pe_affiliated_group_count??new Set(licenses.filter(r=>r.documented_pe_group_affiliation&&!missingGroup(r.owner_group)).map(r=>r.owner_group)).size;
const summaries=[
 ['Core alcohol licenses',coreLicenses||'Not supplied',boundaryLicenses?number(boundaryLicenses)+' BYOB / unclear records separate':'Core classification from supplied scope'],
 ['Current index queries complete',searchProgress('current'),'Holder-query coverage; not lien determinations'],
 ['Lapsed index queries complete',searchProgress('lapsed'),'Holder-query coverage; document review separate'],
 ['Ownership research reviewed',number(reviewedCount)+' / '+number(coreLicenses),number(reviewedUnresolved)+' reviewed cases remain unresolved'],
 ['Reviewed group affiliations',affiliationCount,'License records; not verified equity ownership'],
 ['Licenses with collected events',eventCount,'Collected events do not establish completed sales']
];
const specificKey=['specific_license_ucc_cases','specific_license_ucc_case_count','specific_license_collateral_cases','licenses_with_specific_license_ucc'].find(key=>coverage[key]!==undefined&&coverage[key]!==null);
if(specificKey)summaries.push(['Specific-license UCC cases',coverage[specificKey],'Documented cases; not current balance determinations']);
for(const [title,value,note]of summaries){const item=el('div',undefined,'coverage-item');const dd=el('dd',typeof value==='number'?number(value):text(value),'coverage-number');item.append(el('dt',title),dd,el('small',note));coverageNodes.append(item);}
$('coverage').replaceChildren(coverageNodes);
$('ownership-coverage').textContent='Within the reviewed affiliations, '+number(peAffiliations)+' license records link to '+number(peGroups)+' groups with documented private-equity backing. This is a reviewed lower bound, not a citywide share or a certified license-holder equity count.';
const judgment=coverage.judgment_attachment_notice_review;
if(judgment){const paragraph=$('judgment-coverage');paragraph.hidden=false;paragraph.append(el('span','Separate attachment, execution, seizure and discharge review: '+number(judgment.counts.encumbrance_or_discharge_observations)+' observations; '+number(judgment.counts.observations_joined_to_main_review)+' exact historical-license joins across '+number(judgment.counts.distinct_license_ids_joined_to_main_review)+' inventory licenses. Repeat matters remain identified; amounts are not summed or treated as current balances. '));const link=el('a','Read all notices and limitations');link.href='judgment-attachment-review/README.md';paragraph.append(link);}
const reconciliation=coverage.reconciled_history_review;
if(reconciliation?.original_histories_text_reviewed){const paragraph=$('reconciliation-coverage');paragraph.hidden=false;paragraph.append(el('span','Separate saved-history reconciliation: '+number(reconciliation.original_histories_text_reviewed)+' originals / '+number(reconciliation.saved_history_entries_reviewed)+' saved entries across '+number(reconciliation.holder_groups)+' holders. Prior complete visual review is documented for '+number(reconciliation.original_pdfs_with_prior_complete_visual_review_reconciled)+' original PDF; '+number(reconciliation.pending_original_pdfs)+' original and '+number(reconciliation.pending_amendment_pdfs)+' amendment PDFs remain pending. The base filing queue retains its separate '+number(reconciliation.base_queue_imported_prior_history_review_count_unchanged)+' imported prior-history reviews. '));const link=el('a','Read the reconciliation ledger');link.href='filing-review-reconciliation-README.md';paragraph.append(link);}
const corpus=coverage.board_corpus||{};
const historyWindow=corpus.window_label||(corpus.window_start&&corpus.window_end?corpus.window_start+' through '+corpus.window_end:'Collection window not supplied');
$('history-scope').textContent=historyWindow+' · '+number(corpus.documents)+' unique source documents / '+number(corpus.pdf_pages)+' PDF pages · '+number(corpus.event_count)+' dated transfer/pledge actions; '+number(corpus.events_joined_to_review_inventory)+' actions joined to this inventory. The collected archive windows are bounded sources, not lifetime license history.';
for(const window of corpus.source_windows||[]){const row=el('tr');const title=el('td',window.window_label);const href=window.source_coverage_relative_file;if(typeof href==='string'&&href.startsWith('transfer-corpus/')&&!href.includes('..')&&/^[A-Za-z0-9_./-]+$/.test(href)){const link=el('a','Window coverage and provenance');link.href=href;title.append(el('br'),link);}const board=window.board_counts||{};row.append(title,el('td',number(window.documents)+' / '+number(window.pdf_pages)),el('td',number(board.event_count)),el('td',number(board.transfer_count)+' ('+number(board.transfer_granted_count)+' granted)'),el('td',number(board.pledge_count)+' ('+number(board.pledge_granted_count)+' granted)'),el('td',number(window.ownership_application_counts?.application_events)+' ('+number(window.alcohol_ownership_application_counts?.application_events)+' explicitly alcohol)'),el('td',number(window.separate_source_notice_count)+' source notices; '+number(window.ownership_notice_count)+' ownership notices; '+number(window.proposal_or_unresolved_outcome_count)+' unresolved proposals'));$('history-window-rows').append(row);}
const chips=[['Transfer dispositions',corpus.transfer_application_disposition_count,corpus.transfer_granted_count],['Pledge dispositions',corpus.pledge_application_disposition_count,corpus.pledge_granted_count],['Release acknowledgments',corpus.pledge_release_count],['Intent-to-revoke notices',corpus.transfer_revocation_notice_count]];
for(const [name,count,granted]of chips)$('history-summary').append(el('span',name+': '+number(count)+(granted!==undefined?' ('+number(granted)+' granted)':''),'history-chip'));
const interestCorpus=coverage.ownership_interest_corpus;
if(interestCorpus){$('interest-corpus-note').hidden=false;const explicit=interestCorpus.application_license_scopes?.explicit_alcohol;const total=interestCorpus.application_events;const identifiers=interestCorpus.unique_alcohol_license_ids;const partyNote=interestCorpus.alcohol_items_with_named_equity_parties===0&&interestCorpus.alcohol_items_with_explicit_owner_percentages===0?'The alcohol items name no before/after equity holders or ownership percentages. ':'Equity-party and percentage disclosures require source review. ';$('interest-corpus-note').textContent='Separate ownership-interest ledger: '+number(total)+' application decisions, including '+number(explicit)+' explicitly alcohol-license decisions across '+number(identifiers)+' source license IDs. '+number(licenses.flatMap(interestEventsFor).length)+' application decisions join '+number(licenses.filter(record=>interestEventsFor(record).length).length)+' inventory license records; '+number(interestCorpus.notices_separate)+' notices/hearings remain separate. '+partyNote+'These records do not establish private-equity ownership and remain separate from the '+number(corpus.event_count)+' transfer / pledge actions.';}
const comparison=coverage.historical_pledge_roster_note_comparison;
if(comparison){$('pledge-insight').hidden=false;$('pledge-comparison').textContent=number(comparison.without_financing_keyword_marker)+' of '+number(comparison.roster_license_ids_with_granted_pledge_history)+' roster license IDs with granted pledge history have no financing keyword in the checked roster fields. Historical local approvals do not establish current debt; this is not an active-lien sensitivity estimate.';}
const unmatched=data.unmatched_board_events||[];$('unmatched-summary').textContent=number(unmatched.length)+' actions not matched to a roster license';if(!unmatched.length)$('unmatched-board').hidden=true;
$('unmatched-board').addEventListener('toggle',()=>{if($('unmatched-board').open&&!$('unmatched-events').childElementCount){const fragment=document.createDocumentFragment();for(const event of unmatched)appendEvent(fragment,event,true);$('unmatched-events').append(fragment);}});$('coverage-detail').textContent=JSON.stringify(coverage,null,2);$('metadata').textContent=JSON.stringify(data.metadata||{},null,2);
const meta=data.metadata||{};const date=meta.as_of||meta.updated_at||meta.generated_at||meta.snapshot_date||meta.roster_research_date||meta.retrieved_at||meta.date;
$('snapshot').textContent=(date?'Snapshot: '+text(date)+' · ':'')+number(licenses.length)+' inventory records · '+number(new Set(licenses.map(r=>r.license_num).filter(Boolean)).size)+' distinct supplied license numbers';
$('scope-note').textContent=coreLicenses?number(coreLicenses)+' core alcohol licenses + '+number(boundaryLicenses)+' separately flagged BYOB / unclear-category records. Table defaults to core alcohol licenses.':'License scope classifications were not supplied.';
if(meta.collection_status==='paused_pending_supported_bulk_access'){
 const status=meta.collection_status_record||{};const current=coverage.search_states?.current||{};const lapsed=coverage.search_states?.lapsed||{};const panel=$('ucc-pause');panel.hidden=false;
 panel.append(el('strong','Full-list UCC collection paused pending supported access.'),el('p',number(current.complete??status.current_queries_complete)+' current queries complete; '+number(current.pending??status.current_queries_pending)+' current and '+number(lapsed.pending??status.lapsed_queries_pending)+' lapsed queries remain pending. Completed index searches remain separate from collateral review.'),el('p','One search form load succeeded. No new debtor searches or filing-document requests were submitted; result and document access remain unverified.'),el('p','The Secretary’s published terms prohibit automated and manual scraping. Full-list collection awaits a supported export or records-delivery route. The earlier Access Denied / Error 15 observation remains preserved separately.'));
 const links=el('p');const terms=publicLink(status.terms_review?.source_url,'Secretary’s Terms of Use');if(terms)links.append(terms,' · ');
 for(const [href,title]of [['access-options.md','UCC access options'],['corporate-records-access-options.md','Corporate-records access options'],['massachusetts-bulk-data-inquiry-draft.md','Combined unsent data inquiry'],['ucc-access-inquiry-draft.md','UCC inquiry draft'],['ucc-access-block.json','Historical access denial']]){const link=el('a',title);link.href=href;links.append(link,' · ');}links.append('No inquiry has been sent, paid order placed, or bulk data received.');panel.append(links);
}else if(meta.collection_status==='blocked'||coverage.ucc_collection_blocked){const blocker=meta.collection_blocker||{};const states=coverage.search_states?.current||{};const completed=states.complete??blocker.current_queries_complete;const pending=states.pending??blocker.current_queries_pending;$('ucc-pause').hidden=false;$('ucc-pause').append(el('strong','UCC collection paused: source access denied.'),el('p',number(completed)+' current queries complete; '+number(pending)+' remain pending. Access failure is not a zero-result search. Completed index searches remain separate from collateral review.'));}
applyFilters();
</script>
</body></html>
'''


def load_review_data(input_path: Path) -> dict:
    """Reject malformed top-level inputs without silently dropping license rows."""
    with input_path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("review data must be a JSON object")
    if not isinstance(data.get("licenses"), list):
        raise ValueError("review data requires a licenses array")
    for index, record in enumerate(data["licenses"]):
        if not isinstance(record, dict):
            raise ValueError(f"licenses[{index}] must be an object")
        for field in ("license_num", "owner_group"):
            if record.get(field) is not None and not isinstance(record[field], str):
                raise ValueError(f"licenses[{index}].{field} must be a string or null")
    for field in ("metadata", "coverage"):
        if field in data and not isinstance(data[field], dict):
            raise ValueError(f"{field} must be an object")
    if "groups" in data and (
        not isinstance(data["groups"], list)
        or any(not isinstance(group, dict) for group in data["groups"])
    ):
        raise ValueError("groups must be an array of objects")
    return data


def build(input_path: Path, output_path: Path) -> None:
    data = load_review_data(input_path)
    # Prevent markup/script termination even when source fields contain hostile HTML.
    payload = json.dumps(data, ensure_ascii=False, allow_nan=False)
    for character, escaped in (
        ("&", "\\u0026"),
        ("<", "\\u003c"),
        (">", "\\u003e"),
        ("\u2028", "\\u2028"),
        ("\u2029", "\\u2029"),
    ):
        payload = payload.replace(character, escaped)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(PAGE.replace("__REVIEW_DATA__", payload), encoding="utf-8")


def main() -> None:
    folder = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path, default=folder / "review-data.json")
    parser.add_argument("--output", type=Path, default=folder / "dashboard.html")
    args = parser.parse_args()
    try:
        build(args.input, args.output)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Cannot build dashboard: {error}\n")
    print(f"Built {args.output.resolve()}")


if __name__ == "__main__":
    main()
