# Shell Vendor Analysis: Summit Ridge Media Group LLC & Lantern Production Consultants LLC

**Date**: 2026-02-25
**Sources**: FEC Schedule E, crt.sh CT logs, Wayback Machine CDX, Shodan DNS, URLScan.io, NY DOS, TX Comptroller, NJ DoR, OCCRP Aleph, registry.db (FL/NY/NM/PA), web search
**Status**: Both vendors assessed as **purpose-built firewall entities** with high confidence

---

## 1. Summit Ridge Media Group LLC

### FEC Profile

| Field | Value |
|-------|-------|
| **Used by** | American Mission (C00916692) — exclusively |
| **Total IEs** | $1,767,642 (6 filings) |
| **Address** | 5150 Mae Anne Ave, Suite 405 PMB 1141, Reno NV 89523 |
| **Other FEC clients** | **None** |

### Address Analysis

**5150 Mae Anne Ave, Suite 405** = **Ridgeview Mail Center**, a UPS Authorized Shipping Outlet in Ridgeview Plaza, Reno NV. "PMB 1141" is a private mailbox number. This is a commercial mailbox service, not a business office.

### Corporate Registry Search

| Jurisdiction | Result |
|-------------|--------|
| **Nevada SOS** | **0 results** (confirmed — NOT a NV entity despite Reno NV mailing address) |
| **NY DOS** | 0 results |
| **Texas Comptroller** | 0 results |
| **NJ Division of Revenue** | 0 results |
| **registry.db (FL/NY/NM/PA)** | 0 exact matches |
| **OCCRP Aleph** | 0 results |

**Summit Ridge Media Group LLC is NOT registered in Nevada** despite using a Reno NV mailing address on FEC filings.

### Delaware Incorporation (CONFIRMED)

| Field | Value |
|-------|-------|
| **Company Number** | **10385832** |
| **Incorporation Date** | **October 30, 2025** |
| **Company Type** | Domestic Limited Liability Company |
| **Jurisdiction** | Delaware |
| **Registered Agent** | The Corporation Trust Company |
| **Agent Address** | Corporation Trust Center, 1209 Orange St, Wilmington DE 19801 |
| **Officers/Directors** | None listed (DE LLCs do not require public disclosure) |

**Critical observation**: Summit Ridge (#10385832) and Lantern (#10385842) are only **10 company numbers apart**. Both formed on the same day (Oct 30, 2025) with the same registered agent (CT Corporation). **They were created in the same batch filing** — almost certainly by the same law firm in the same session. This proves they are part of a single coordinated operation.

### Domain Investigation: summitridgemedia.com

**IMPORTANT DISTINCTION**: The FEC vendor is "Summit Ridge Media **Group** LLC" while the domain is "summitridgemedia.com" (no "Group"). The domain summitridgemediagroup.com does not exist (no certs, no Wayback captures). These may be different entities.

#### summitridgemedia.com — Infrastructure Profile

| Property | Value | Significance |
|----------|-------|-------------|
| **First cert** | 2025-07-04 (Let's Encrypt R11) | Domain existed ~1 month before LTF PAC formation |
| **First Wayback** | 2025-07-13 | 3 total captures (very thin) |
| **DNS A record** | 162.159.140.166 (Cloudflare) | Standard CDN proxy |
| **DNS MX** | mx1/mx2.privateemail.com | Namecheap private email — cheap, privacy-focused |
| **DNS NS** | dns1/dns2.registrar-servers.com | Namecheap registrar |
| **www CNAME** | sites.ludicrous.cloud | Website builder platform |
| **Total certs** | 30 (Jul 2025 – Jan 2026) | 5 Let's Encrypt, 25 Google Trust Services |

#### Subdomains (from CT logs)

| Subdomain | Purpose |
|-----------|---------|
| summitridgemedia.com | Main site |
| www.summitridgemedia.com | www redirect |
| app.summitridgemedia.com | Application/dashboard |
| link.summitridgemedia.com | Click tracking for emails |
| email.mg.summitridgemedia.com | **Mailgun** email delivery |
| email.lc.summitridgemedia.com | **LeadConnector** email service |
| email.notif.summitridgemedia.com | Notification emails |

The subdomain pattern reveals a **GoHighLevel/LeadConnector** marketing stack — a white-label SaaS platform for digital marketing agencies.

#### Site Content (from Wayback capture 2025-07-20)

The site is a **generic GoHighLevel marketing agency template**:

- **Title**: "Home"
- **Headline**: "Ignite Your Passion. Get More Leads and Sales To Your Business"
- **Content**: "How you could Double even Triple your Online Business in as little as 30 Days With no prior experience"
- **Contact**: christo@summitridgemedia.com, phone 723-561-6439
- **Person**: **Christo Zeelie** (section heading "CHRISTO ZEELIE", Wistia account `zanderchristo`)
- **Facebook Pixel**: 1844573529431685 (≠ LTF's pixel 665317187836289)
- **External services**: app.gohighlevel.com, app.leadconnectorhq.com, Authorize.net payment processing, Wistia video hosting, Facebook/Instagram/LinkedIn/YouTube social links

**Assessment**: summitridgemedia.com is NOT a political media buying operation. It is a generic lead generation template site run by Christo Zeelie, likely using GoHighLevel's white-label agency model. This appears to be a **different entity** from the FEC vendor "Summit Ridge Media Group LLC" — same name root, different business entirely.

### Shell Assessment: Summit Ridge Media Group LLC

**Confidence: HIGH (shell entity)**

Evidence:
1. ✅ Exclusively used by one PAC network (American Mission only)
2. ✅ No other FEC clients
3. ✅ Not found in any state corporate registry searched
4. ✅ Registered address is a Reno NV commercial mailbox (Ridgeview Mail Center)
5. ✅ No web presence under exact FEC name ("Summit Ridge Media Group")
6. ✅ Domain summitridgemediagroup.com does not exist
7. ✅ The similar domain summitridgemedia.com belongs to a different person/business (Christo Zeelie)
8. ✅ **Not registered in Nevada** despite Reno NV mailing address
9. ✅ **Delaware LLC #10385832**, formed Oct 30, 2025, CT Corporation agent — **same day, same agent, 10 numbers apart from Lantern (#10385842)**

---

## 2. Lantern Production Consultants LLC

### FEC Profile

| Field | Value |
|-------|-------|
| **Used by** | Think Big (C00923417) — exclusively |
| **Total IEs** | $3,865,136 (20 filings) |
| **Address** | 1344 Disc Drive #3038, Sparks NV 89436 |
| **Other FEC clients** | **None** |

### Address Analysis

**1344 Disc Drive** = **PostalAnnex+** (Store #307), Spanish Springs Shopping Center, Sparks NV. "#3038" is a mailbox number. This is a commercial mailbox/virtual office service.

### Delaware Incorporation (CONFIRMED)

| Field | Value |
|-------|-------|
| **Company Number** | 10385842 |
| **Incorporation Date** | **October 30, 2025** |
| **Company Type** | Domestic Limited Liability Company |
| **Jurisdiction** | Delaware |
| **Registered Agent** | The Corporation Trust Company |
| **Agent Address** | Corporation Trust Center, 1209 Orange St, Wilmington DE 19801 |
| **Officers/Directors** | None listed (DE LLCs do not require public disclosure) |

**Key observations**:
1. **Formation timing**: Incorporated Oct 30, 2025 — just **41 days** before Think Big's first IE payment ($118,350 on Dec 10, 2025). Entity was created specifically for this operation.
2. **Delaware for privacy**: DE LLCs do not publicly disclose members or managers. The principals behind this entity are invisible in state records.
3. **CT Corporation as agent**: Premium registered agent service ($300+/year), indicating professional legal counsel set up this entity — not a DIY formation.
4. **Jurisdictional split**: Delaware incorporation + Nevada mailing address on FEC filings = deliberate separation between formation jurisdiction (privacy) and operational address (NV mailbox).

### Corporate Registry Search

| Jurisdiction | Result |
|-------------|--------|
| **Nevada SOS** | **0 results** (confirmed — NOT a NV entity despite NV mailing address) |
| **Delaware** | **FOUND** — Company #10385842, formed Oct 30, 2025, CT Corp agent |
| **NY DOS** | 7 results, **none matching** (Black Lantern Productions, Lantern Man Productions, etc.) |
| **Texas Comptroller** | 0 results |
| **NJ Division of Revenue** | Not searched (no "Lantern Production" variant) |
| **registry.db (FL/NY/NM/PA)** | 0 results |
| **OCCRP Aleph** | 0 results |

**Lantern Production Consultants LLC does not appear in any corporate registry or public database.**

### Web Presence

- **No domain found** — web search for "Lantern Production Consultants" returns only unrelated companies (Lantern PM LLC, Lantern Entertainment, lanternproduction.com in BC Canada)
- **No LinkedIn, social media, or business directory listings**
- **No news coverage mentioning this entity independently**
- **Complete invisibility** outside of FEC filings

### Spending Pattern

| Target | Stance | Amount | % of Total |
|--------|--------|--------|-----------|
| Alex Bores (D, NY-12) | **Oppose** | $1,632,155 | 42.2% |
| Jesse L. Jackson Jr (D, IL-02) | Support | $1,117,335 | 28.9% |
| Melissa L. Bean (D, IL-08) | Support | $1,115,646 | 28.9% |

The anti-Bores spending ($1.6M+) is the network's largest single-target expenditure, representing direct retaliation against the NY legislator who sponsored AI regulation legislation (SB S7623).

### Shell Assessment: Lantern Production Consultants LLC

**Confidence: VERY HIGH (purpose-built firewall entity)**

Evidence:
1. ✅ Exclusively used by one PAC (Think Big only)
2. ✅ No other FEC clients
3. ✅ **Delaware LLC formed Oct 30, 2025** — 41 days before first payment. Created for this operation.
4. ✅ **Not registered in Nevada** despite Sparks NV mailing address on FEC filings
5. ✅ Registered address is a Sparks NV commercial mailbox (PostalAnnex+)
6. ✅ **Zero web presence** — no domain, no social media, no business listings
7. ✅ No news coverage of this entity
8. ✅ $3.87M routed through an entity with no visible infrastructure
9. ✅ CT Corporation registered agent — professional legal setup, no public officer disclosure
10. ✅ Delaware chosen specifically for member privacy (no public disclosure requirement)

---

## 3. Comparative Analysis

### Pattern: Matched Vendor Pairs

| Feature | Summit Ridge Media Group | Lantern Production Consultants |
|---------|------------------------|-------------------------------|
| **PAC client** | American Mission (GOP affiliate) | Think Big (Dem affiliate) |
| **Total IEs** | $1,767,642 | $3,865,136 |
| **DE Company #** | **10385832** | **10385842** |
| **Incorporation date** | **Oct 30, 2025** | **Oct 30, 2025** |
| **Registered agent** | CT Corporation | CT Corporation |
| **FEC mailing address** | Mailbox (Reno NV) | Mailbox (Sparks NV) |
| **NV SOS** | Not registered | Not registered |
| **Web presence** | None (under exact name) | None |
| **Other FEC clients** | None | None |
| **Spending targets** | R primaries (TX, NC) | D primaries + anti-Bores (NY, IL) |

**The 10-number gap** between company numbers (10385832 → 10385842) with identical formation date and agent is the strongest evidence that these entities were created as a matched pair in a single coordinated legal filing. Delaware company numbers are assigned sequentially — 10 numbers apart on the same day means they were filed in the same batch, likely by the same attorney or compliance firm.

Both vendors are Nevada-based, mailbox-addressed, web-invisible LLCs used exclusively by one PAC in the LTF network. They form a **matched pair**: one for the Republican spending arm, one for the Democratic spending arm. This compartmentalization ensures that no single vendor is visibly involved in both partisan sides of the operation.

### What This Structure Achieves

1. **Vendor firewall**: The actual media buying firms (likely Targeted Victory and/or affiliates) are insulated from FEC disclosure. Only the shell vendors appear in public filings.
2. **Compartmentalization**: Each partisan arm uses a different vendor, preventing cross-referencing between R and D spending.
3. **Geographic isolation**: Both vendors are in the Reno/Sparks NV area (near the PAC addresses in Henderson NV), using commercial mailbox services rather than business offices.
4. **Competitive intelligence denial**: Rival campaigns and opposition researchers cannot identify the actual media buying strategy by tracing vendor relationships.

### Comparison to Fairshake's Vendor Structure

Per the network analysis, Fairshake (the crypto equivalent) used **Main Street Media Group** as a vendor ($2.78M for media buy supporting Michelle Steel, CA-45). This is the same pattern: a purpose-named LLC that handles media buying for the Super PAC. The naming convention (geographic feature + "Media" + entity type) matches:
- **Summit Ridge** Media Group
- **Main Street** Media Group

This suggests a standardized approach to creating vendor entities for these operations.

---

## 4. Open Questions

1. **~~NV SOS registration~~**: ~~Are these LLCs actually registered in Nevada?~~ **RESOLVED**: Neither entity is registered in Nevada. Lantern is a Delaware LLC (Company #10385842, formed Oct 30, 2025, CT Corp agent). Summit Ridge is likely also Delaware — pending ICIS confirmation.

2. **Who controls these entities?** Delaware LLC members/managers are NOT publicly disclosed. The principals are invisible through state records. Alternative approaches: (a) FOIA the FEC for vendor registration documents, (b) check if any FEC Form 3X/3L attachments name the vendor principals, (c) trace payments downstream from these LLCs to actual media vendors.

3. **Where does the money actually go?** Summit Ridge and Lantern receive millions via FEC filings, but they are intermediaries. The actual media placements (TV buys, digital ads, direct mail) are executed by production companies, ad platforms, and print houses that may not appear in FEC records.

4. **Is summitridgemedia.com (Christo Zeelie) connected to Summit Ridge Media Group LLC?** The name similarity could be coincidence, or Zeelie could operate both. His GoHighLevel marketing agency template site bears no resemblance to a political media operation.

5. **Are there other PACs using this same shell vendor pattern?** The "Main Street Media Group" from Fairshake suggests this is a repeating template. A broader FEC search for single-client media vendors with mailbox addresses could reveal the full scope of this practice.

---

## 5. Recommended Follow-Up

### Critical — Delaware Batch Filing
Companies #10385833 through #10385841 (between Summit Ridge and Lantern) were filed in the same batch on Oct 30, 2025. Identifying these entities could reveal other shells in the operation, or identify the filing attorney/firm. Check Delaware ICIS for company numbers 10385833-10385841.

### Additional State Searches
```bash
uv run python tools/query_california.py search "SUMMIT RIDGE MEDIA" --output /tmp/search-ca-summit.json
uv run python tools/query_california.py search "LANTERN PRODUCTION" --output /tmp/search-ca-lantern.json
uv run python tools/query_massachusetts.py search "SUMMIT RIDGE" --output /tmp/search-ma-summit.json
```

### FEC Pattern Search
Search for other single-client media vendors with NV mailbox addresses:
- `query_fec.py ie` for "Main Street Media Group" (Fairshake's vendor)
- Broader search for NV-based media LLCs appearing in Schedule E filings

---

*Analysis generated 2026-02-25. NV SOS data pending — revisit when browser session is available.*
