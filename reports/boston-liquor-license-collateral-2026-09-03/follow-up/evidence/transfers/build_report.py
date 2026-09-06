from pathlib import Path
import csv, hashlib, json, re, shutil

work = Path('/tmp/osint-boston-transfers-gxlTsf37')
base = Path('/Users/travcole/projects/osint-research/reports/boston-liquor-license-collateral-2026-09-03/evidence/board')
roster = Path('/tmp/osint-3MBlGt4u/licenses.csv')
source_dir = work/'source'
source_dir.mkdir(exist_ok=True)
sources = {
 '2026-03-26': ('voting-minutes-2026-03-26','https://www.boston.gov/sites/default/files/file/2026/03/Voting%20Minutes%203-26-26.docx.pdf',[11,12,13]),
 '2024-06-26': ('voting-minutes-2024-06-26','https://www.boston.gov/sites/default/files/file/2024/06/Voting%20Minutes%206-26-24.docx.pdf',[7]),
 '2024-07-11': ('voting-decisions-2024-07-11','https://www.boston.gov/sites/default/files/file/2024/07/Voting%20Agenda%20July%2011.docx_2.pdf',[4,5]),
}
manifest=[]
for date,(name,url,pages) in sources.items():
    for suffix in ['.pdf','.txt']:
        shutil.copy2(base/(name+suffix),source_dir/(name+suffix))
    raw=(base/(name+'.txt')).read_text()
    for page in pages:
        match=re.search(rf'^PAGE {page}\s*\n(.*?)(?=^PAGE \d+|\Z)',raw,re.M|re.S)
        assert match
        (source_dir/f'{name}-page{page}.txt').write_text(f'PDF page {page}\n'+re.sub(r'\s+',' ',match.group(1)).strip()+'\n')
    manifest.append({'vote_date':date,'url':url,'local_pdf':str(source_dir/(name+'.pdf')),'sha256':hashlib.sha256((base/(name+'.pdf')).read_bytes()).hexdigest(),'reviewed_pdf_pages':pages,'provenance':'Copied from previously downloaded official Boston evidence; no new network request.'})
shutil.copy2(base/'jana-page7.png',work/'voting-minutes-2024-06-26-page7.png')

# Each selected item explicitly transfers the alcoholic-beverage license to another named entity.
events = [
 {'vote_date':'2026-03-26','page':11,'item':29,'license_number':'LB-101940','transferor':'Gray’s Liquors, Inc.','transferee':'Shri Saibaba Corp','prior_dba':'Oak Square Liquors','new_dba':'Oak Square Liquors','premises_before':'610 Washington St, Brighton, MA 02135','premises_after':'610 Washington St, Brighton, MA 02135','transfer_kind':'license_transfer_same_location','license_description':'Retail Package Store All-Alcoholic Beverages','related_pledge':{'recipient':'Rockland Trust Company','assets':['license','inventory']},'other_changes':'Premises description updated.'},
 {'vote_date':'2026-03-26','page':11,'item':31,'license_number':'LB-99391','transferor':'Namaha Capital, LLC','transferee':'200 Boylston Street Restaurant, LLC','prior_dba':'Basile- Fine Italian Kitchen','new_dba':None,'premises_before':'162 Columbus Ave, Boston, MA 02116','premises_after':'200 Boylston St, Boston, MA 02116','transfer_kind':'license_and_location_transfer','license_description':'Common Victualler 7 Day All-Alcoholic Beverages','related_pledge':None,'other_changes':'Removal of two outdoor-patio conditions. Restaurant is described as inside the Four Seasons Hotel, separate from its licensed premises.'},
 {'vote_date':'2026-03-26','page':12,'item':32,'license_number':'LB-98926','transferor':'Powder Dry, Inc.','transferee':'Legends Music, LLC','prior_dba':'Leader Bank Pavilion','new_dba':'Leader Bank Pavilion','premises_before':'290 Northern Ave, Boston, MA 02210','premises_after':'290 Northern Ave, Boston, MA 02210','transfer_kind':'license_transfer_same_location','license_description':'Common Victualler 7 Day All-Alcoholic Beverages','related_pledge':None,'other_changes':'Premises description updated.'},
 {'vote_date':'2026-03-26','page':12,'item':33,'license_number':'LB-99536','transferor':'Olives, Inc.','transferee':'Picklebos Charlestown LLC','prior_dba':'Figs','new_dba':'Picklebos','premises_before':'42 Charles St, Boston, MA 02108','premises_after':'440 Rutherford Ave, Boston, MA 02129','transfer_kind':'license_and_location_transfer','license_description':'Common Victualler 7 Day Wines and Malt Beverages; classification change to Wines, Malt Beverages and Liqueurs included','related_pledge':None,'other_changes':'Classification change, removal of meal-only/no-bar conditions, and 10 AM Sunday opening also included.'},
 {'vote_date':'2026-03-26','page':13,'item':34,'license_number':'LB-99537','transferor':'AOB Corp.','transferee':'Ballers Boston Seaport LLC','prior_dba':'L Street Diner & Pizzeria','new_dba':'Ballers','premises_before':'108 L St, South Boston, MA 02127','premises_after':'25 Pier 4 Blvd, Boston, MA 02210','transfer_kind':'license_and_location_transfer','license_description':'Common Victualler 7 Day Wines and Malt Beverages','related_pledge':None,'other_changes':'Removal of meal-only/no-bar conditions; outdoor sports facility.'},
 {'vote_date':'2026-03-26','page':13,'item':35,'license_number':'LB-99739','transferor':'Regina Pizzeria at Fenway, Inc.','transferee':'AV 330 Washington, LLC','prior_dba':'Regina Pizzeria','new_dba':'All’ Antico Vinaio','premises_before':'1330 Boylston St, Boston, MA 02215','premises_after':'330 Washington St, Boston, MA 02108','transfer_kind':'license_and_location_transfer','license_description':'Common Victualler 7 Day Wines and Malt Beverages with Liqueurs','related_pledge':None,'other_changes':'Removal of meal-only/no-bar conditions.'},
 {'vote_date':'2024-06-26','page':7,'item':15,'license_number':'LB-99458','transferor':'Russian Benevolent Society','transferee':'Keryan & Co, Inc.','prior_dba':'Crystal Restaurant/Garage Room','new_dba':'Jana Grill & Bar','premises_before':'14-20 Linden St, Allston, MA 02134','premises_after':'14-20 Linden St, Allston, MA 02134','transfer_kind':'license_transfer_same_location','license_description':'Common Victualler 7 Day All-Alcoholic Beverages','related_pledge':{'recipient':'Russian Benevolent Society, Inc.','assets':['license']},'other_changes':'Premises amendment and condition removals; Board lifted transferor’s indefinite suspension for the purpose of transferring the license and noted future transfers should include disciplinary-history review.'},
 {'vote_date':'2024-07-11','page':4,'item':9,'license_number':'LB-101897','transferor':'JNT Package Corporation','transferee':'Surya Narayan Corporation','prior_dba':'ODB Liquors','new_dba':'Hyde Park Liquor','premises_before':'1253 Hyde Park Ave, Hyde Park, MA 02136','premises_after':'1253 Hyde Park Ave, Hyde Park, MA 02136','transfer_kind':'license_transfer_same_location','license_description':'Retail Package Store All-Alcoholic Beverages','related_pledge':{'recipient':'Rockland Trust Company','assets':['license','inventory']},'other_changes':None},
 {'vote_date':'2024-07-11','page':5,'item':12,'license_number':'LB-99633','transferor':'Allston Rock City, LLC','transferee':'SB 201 Brookline Ave, LLC','prior_dba':'Fields West','new_dba':'Shy Bird','premises_before':'87 Glenville Ave, Allston, MA 02134','premises_after':'201 Brookline Ave, Boston, MA 02215','transfer_kind':'license_and_location_transfer','license_description':'Common Victualler Wines and Malt Beverages with Liqueurs','related_pledge':{'recipient':'Cambridge Savings Bank','assets':['license']},'other_changes':None},
]
csv.field_size_limit(2_000_000)
with roster.open(newline='') as f:
    reader=csv.DictReader(f)
    header=reader.fieldnames
    assert {'license_num','business_name','dba_name','address','city'} <= set(header)
    rows=list(reader)
keys=['license_num','business_name','dba_name','address','city','state','zip','status','issued','expires','license_category','license_type','comments']
for e in events:
    name,url,_=sources[e['vote_date']]
    e.update(board_disposition='Granted',pdf_url=url,page_numbering='one-based PDF page',source_pdf=str(source_dir/(name+'.pdf')),source_page_text=str(source_dir/f'{name}-page{e["page"]}.txt'),page_image=str(work/f'{name}-page{e["page"]}.png'),visually_verified=True,price=None,price_status='not documented in selected decision item',sale_completion_status='not established',abcc_approval_status='not established',roster_source=str(roster))
    matches=[r for r in rows if r['license_num']==e['license_number']]
    assert len(matches)<=1
    e['roster_match_count']=len(matches)
    e['roster_matches']=[{k:r[k] for k in keys} for r in matches]
    e['roster_holder_reflects']='transferee' if matches else 'unclear_license_absent'
    e['roster_join_basis']='exact license_num; matched holder names reviewed for punctuation and capitalization differences'
    e['related_pledge_scope_note']='Local grant in the same transfer item; financing amount, funding and current debt status not established.' if e['related_pledge'] else 'No pledge stated in the selected transfer item; not evidence that no financing exists.'
    if not matches:
        e['roster_caveat']='LB-99537 is absent. A separate Common Victualler license LB-626071 is held by Brookline Lunch Inc at 108 L St with DBA L Street Diner & Pizzeria. This different license is not a match to the transferred alcoholic-beverage license.'
    assert Path(e['page_image']).is_file()

assert len(events)==9
assert len({e['license_number'] for e in events})==9
assert sum(e['vote_date']=='2026-03-26' for e in events)==6
assert sum(e['roster_match_count']==1 for e in events)==8
assert sum(bool(e['related_pledge']) for e in events)==4
(work/'transfer-events.json').write_text(json.dumps(events,indent=2,ensure_ascii=False)+'\n')
(work/'source-manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')

lines=['# Boston license transfers: bounded decision sample','',
'Nine alcoholic-beverage license transfers received local Boston Licensing Board approval in the selected decisions: six on March 26, 2026, one on June 26, 2024, and two on July 11, 2024. All nine entries explicitly transfer the license to another named entity. Their dispositions were visually checked on the saved PDF pages. This is a selected sample, not a complete transfer inventory.','',
'Eight exact license-number joins show the named transferee in the supplied roster. LB-99537 (AOB Corp. → Ballers Boston Seaport LLC) is absent. Four selected grants also include a license pledge. No selected item states a sale price. Local approval and roster holder names do not establish a completed sale, final ABCC approval, financing disbursement, or current loan balance.','',
'| Vote date | License | Transferor → transferee | DBA before → after | Premises before → after | Same-item pledge | PDF page / item | Roster holder |',
'|---|---|---|---|---|---|---|---|']
for e in events:
    dba=f"{e['prior_dba']} → {e['new_dba'] or '(not stated)'}"
    premises=e['premises_before']+' → '+('same location' if e['premises_before']==e['premises_after'] else e['premises_after'])
    pledge=(e['related_pledge']['recipient']+' ('+', '.join(e['related_pledge']['assets'])+')') if e['related_pledge'] else 'None stated in this item'
    ref=f"[p. {e['page']}, item {e['item']}]({e['pdf_url']}#page={e['page']})"
    lines.append(f"| {e['vote_date']} | {e['license_number']} | {e['transferor']} → {e['transferee']} | {dba} | {premises} | {pledge} | {ref} | {'Transferee' if e['roster_match_count'] else 'License absent'} |")
lines += ['', '## Interpretation and joins', '',
'- Each selected disposition is “Granted.” The July 11, 2024 file is titled a voting agenda but contains the grant decisions under the relevant items; those placements were visually verified.',
'- These are license transfers, including five that also change location. Stock transfers, beneficial-interest changes, location-only changes, manager changes, and new-license applications are excluded. In particular, the adjacent Four Seasons item 30 on March 26 is a premises amendment, not a transfer; item 31 is the distinct license transfer into restaurant space inside that hotel.',
'- The roster was joined only on the exact alcoholic-beverage license number. Matching holder names are consistent with the transferee, including ordinary punctuation/case differences. The roster’s 2013 issued dates are not the dates of these 2024/2026 transfers.',
'- LB-99537 is absent from the roster. A separate Common Victualler license, LB-626071, is held by Brookline Lunch Inc at 108 L St under the L Street Diner & Pizzeria DBA. That different license is not a match to the transferred alcoholic-beverage license.',
'- Jana’s June 2024 decision lifted the transferor’s indefinite suspension for the purpose of transferring the license. The supplied roster later comments that the license is pledged and temporarily closed pending documents in 2026. Neither the 2024 grant nor the generic roster status should be treated as evidence of current operation.',
'- A pledge appearing with a transfer is a financing lead. It does not state the purchase price or prove the loan was funded; for Jana, the named pledge recipient corresponds to the transferor’s name, but seller financing remains an inference until loan documents establish it.',
'', '## Saved evidence', '',
'- `transfer-events.json`: nine structured events, source URLs/pages/items, classification, related pledges, roster match fields and limitations.',
'- `source-manifest.json`: primary-source URLs and SHA-256 hashes of copied PDFs.',
'- `source/`: three official PDFs, original extracted text, and the six reviewed page extracts.',
'- Six page PNGs at this workdir root: March 2026 pages 11–13, June 2024 page 7, and July 2024 pages 4–5.',
'- Roster source: `/tmp/osint-3MBlGt4u/licenses.csv`, supplied Boston licensing export, 3,610 rows; only relevant business fields are copied into JSON. No network calls, active-profile writes, or code edits were made for this follow-up.',
'']
(work/'report-transfers.md').write_text('\n'.join(lines))
print(json.dumps({'workdir':str(work),'events':len(events),'2026_events':6,'roster_transferee_matches':8,'roster_absent':1,'same_item_pledges':4,'pages_visually_verified':6,'roster_rows':len(rows)},indent=2))
