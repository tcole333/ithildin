# Christine Freeman / Glynn officer-network lead

The user's director lead is supported. **OpenCorporates lists Christine M. Freeman as president and director of The Glynn Hospitality Group, Inc.**, Massachusetts company **043043012**, in a registry-derived snapshot retrieved on **31 August 2026**. It also lists Christine Freeman as agent. The company record reports incorporation on 13 March 1989 and active company status; that does not establish appointment dates, equity percentages or the current status of every related officer record. [OpenCorporates company record](https://opencorporates.com/companies/us_ma/043043012)

The initial user claim is preserved separately as `user_provided_lead` in [officer-network.json](officer-network.json). A historical primary source independently supports Freeman's Glynn roles: the **11 February 2016 ABCC decision**, printed pages 11–12, identifies her as president and sole director of Glynn and records roles at Coogan's corporate holder, A.T.G. and Black Rose. Its differing state-registry and ABCC officer lists remain qualified in the structured evidence. These are historical observations. [State Library primary PDF](https://archives.lib.state.ma.us/server/api/core/bitstreams/5a733d6b-970a-4421-8319-cb941abdb3d2/content)

## What the three API calls returned

Exactly **three OpenCorporates API requests** were used: one Massachusetts company search, one exact-company detail request, and one Massachusetts officer-name search. Search logs were checked first. The final search returned **78 role records across 41 company IDs**, all on one page. Those are **41 name-search candidate companies**, not 41 verified companies owned or controlled by one person. No additional API or account-status call was made; remaining account credits and backend billing consumption were not independently queried.

The role search contains 24 records marked inactive and 54 with `inactive: null`. Null is not proof of a current appointment. No records supplied start dates; only three supplied end dates. All carry the same 31 August retrieval date, which is a source observation date, not a corporate appointment date. The [API ledger](api-call-ledger.json) preserves endpoints, non-secret selectors, call numbers and outcomes.

## Six existing license-holder candidates

Legal-name normalization and existing official Glynn venue/address evidence connect six returned corporate names to the six previously reviewed alcohol-license holders. This adds corporate-number and officer evidence without adding licenses or upgrading equity conclusions.

| Existing venue / license | Massachusetts company ID | Returned Freeman role labels |
|---|---|---|
| Black Rose — LB-99225 | 042588695 | Agent, president, director |
| Central Wharf / K.M.F. Hospitality — LB-99100 | 043172724 | Agent, president, director |
| Granary Tavern / 170 LLC — LB-99227 | 001057624 | Manager |
| Clerys / A.T.G. — LB-98998 | 042739497 | Agent, president, director |
| Coogan's / One Hundred Seventy-Three Milk Street — LB-99156 | 043299591 | Agent, president |
| Dillon's / 955 LLC — LB-98953 | 000840651 | SOC signatory, under **Christine Marie Freeman** |

[Candidate crosswalk JSON](candidate-crosswalk.json) and [CSV](candidate-crosswalk.csv) retain company URLs, exact names, normalized-match rules, licensed-premise addresses, current portfolio URLs and all role observations. The officer-search response does not supply each company's registered address, so these are qualified corporate-number crosswalks, not certified registry-to-license joins. Existing operator affiliations remain supported by their prior portfolio evidence. The source roster separately names Christine M. Freeman as Central Wharf's licensing manager; that is distinct from her corporate offices.

## Identity and control limits

The results use Christine Freeman, Christine M Freeman, Christine M. Freeman, Christine Marie Freeman and Christine A. Freeman. Three records use **A rather than M**; they remain unresolved even though they use the same business office. Marie is compatible with M but is not independently resolved as the same person in this pass. The graph therefore preserves separate officer-record nodes and does not collapse the whole search into a single owner.

Forty-nine role records show the confirmed corporate office at **83 Central Street, Boston**. A common business contact can help identify candidates, but it does not prove shared equity, current operator control, or a commercial nominee-service relationship. Agent, signatory, manager, director and raw `real property` labels remain distinct. No reviewed source establishes that Freeman is acting as a professional nominee, and no role label is converted into an ownership percentage. Unneeded officer address and birth information are omitted from durable API artifacts.

The 2016 management-company list and contemporary officer search are separate time layers. Historical restaurant associations do not become current licenses, and unmatched company names do not prove the absence of past licenses, affiliates or property interests. The 35 companies without a legal-name match in this roster remain candidates only. No new PE classification follows from this work.

## Provenance and next resolution steps

[Source manifest](source-manifest.json) records response checksums, redactions and primary-PDF visual quality checks. Root visually verified the original PDF's pages 11–12 and relevant footnotes. The government document is used only for historical roles and management relationships; unrelated enforcement issues are outside this lead.

No live Massachusetts Secretary/Corporations portal request was made; its current access block was respected. The primary PDF came from the independently accessible State Library archive. No contact with subjects occurred. Owner-mappings now contains officer/source annotations on the same six Glynn rows, with counts and equity classifications unchanged.

Further resolution should use company-number-specific annual reports and role histories when the original registry becomes normally accessible or supplied documents are available, prioritize the A/M and Marie identity differences, and distinguish registered offices from licensed premises. The exact IDs and unresolved fields are saved, so the next pass need not repeat the three OpenCorporates searches. The wrapper's pre-existing search-log argument mismatch was fixed and papercut **#2660** resolved after 17 mocked tests and Ruff passed. Canonical search-log entries for these three saved responses were verified in an offline backfill, with **zero additional API calls**; see [the sync record](canonical-search-log-sync.json).
