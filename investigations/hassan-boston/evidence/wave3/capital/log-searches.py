from tools.lead_tracker import log_search


SEARCHES = [
    ('"Alana Inc" 17-12396 schedules PDF', 'web', 1),
    ('"Alana, Inc." "Summary of Assets and Liabilities"', 'web', 1),
    ('"Nader Corp" 17-12398 "Motion to Reopen"', 'web', 0),
    ('"Concepts International LLC" Zappos Amazon transaction', 'web', 0),
    ('"Concepts International LLC" 47-1956576', 'web', 1),
    ('"CONCEPTS INTERNATIONAL LLC" "Tarek Hassan" 2018', 'web', 1),
    ('878754837 statuts pdf Concepts International', 'web', 1),
    ('"17-12396" "Doc 27"', 'web', 0),
    ('"17-12396" "Doc 63"', 'web', 0),
    ('"17-12398" "Doc 28"', 'web', 0),
    ('"17-12398" "Doc 24"', 'web', 0),
    ('site:sec.gov "Concepts International LLC"', 'web', 0),
    ('site:amazon.com "Concepts International LLC"', 'web', 0),
    ('site:zappos.com "Concepts International LLC"', 'web', 0),
    ('"Kedar Deshpande" "Scott Schaefer" "Tarek Hassan" Concepts', 'web', 0),
    ('site:aboutamazon.com CNCPTS Concepts International July 2025', 'web', 0),
    ('site:zappos.com CNCPTS Concepts International 2025', 'web', 0),
    ('"CNCPTS LLC" "Concepts International LLC" 2025 transaction', 'web', 1),
    ('"Jordan Mergersub, LLC" Concepts International Amazon', 'web', 0),
    ('"Jordan Mergersub" CNCPTS Zappos', 'web', 0),
    ('site:amazon.com "Jordan Mergersub"', 'web', 0),
    ('site:zappos.com "Concepts International" acquisition', 'web', 0),
    ('Concepts International LLC exact-name ID 001148501', 'ma_corps', 1),
    ('Concepts International LLC', 'registry', 0),
    ('Concepts International LLC owner', 'trademarks', 55),
    ('trademark serial 86458475', 'official_website', 2),
    ('trademark reel/frame 9039/0339', 'official_website', 5),
    ('gov.uscourts.mab.476801 item file inventory', 'internet_archive', 5),
    ('gov.uscourts.mab.476804 item file inventory', 'internet_archive', 5),
]

for query, source, count in SEARCHES:
    log_search(query, source, count)

print(f'logged {len(SEARCHES)} searches')
