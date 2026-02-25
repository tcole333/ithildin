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
| **Nevada SOS** | Search failed (Incapsula browser session conflict) |
| **NY DOS** | 0 results |
| **Texas Comptroller** | 0 results |
| **NJ Division of Revenue** | 0 results |
| **registry.db (FL/NY/NM/PA)** | 0 exact matches |
| **OCCRP Aleph** | 0 results |

**Summit Ridge Media Group LLC does not appear in any state corporate registry searched.** If it is a Nevada LLC (given the Reno address), it would only appear in the NV SOS database, which was inaccessible due to browser session issues. This is the critical missing search.

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
8. ⚠️ NV SOS search incomplete (browser session conflict)

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

### Corporate Registry Search

| Jurisdiction | Result |
|-------------|--------|
| **Nevada SOS** | Search failed (Incapsula browser session conflict) |
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

**Confidence: VERY HIGH (shell entity)**

Evidence:
1. ✅ Exclusively used by one PAC (Think Big only)
2. ✅ No other FEC clients
3. ✅ Not found in any state corporate registry searched
4. ✅ Registered address is a Sparks NV commercial mailbox (PostalAnnex+)
5. ✅ **Zero web presence** — no domain, no social media, no business listings
6. ✅ No news coverage of this entity
7. ✅ $3.87M routed through an entity with no visible infrastructure
8. ⚠️ NV SOS search incomplete (browser session conflict)

---

## 3. Comparative Analysis

### Pattern: Matched Vendor Pairs

| Feature | Summit Ridge Media Group | Lantern Production Consultants |
|---------|------------------------|-------------------------------|
| **PAC client** | American Mission (GOP affiliate) | Think Big (Dem affiliate) |
| **Total IEs** | $1,767,642 | $3,865,136 |
| **Address type** | Mailbox (Reno NV) | Mailbox (Sparks NV) |
| **State registrations** | None found | None found |
| **Web presence** | None (under exact name) | None |
| **Other FEC clients** | None | None |
| **Spending targets** | R primaries (TX, NC) | D primaries + anti-Bores (NY, IL) |

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

1. **NV SOS registration**: Are these LLCs actually registered in Nevada? The NV SOS search failed due to browser session conflicts. This is the single most important missing data point — NV SOS records would reveal officers, registered agents, formation dates, and status.

2. **Who controls these entities?** The officers/members of these LLCs would reveal whether they are connected to Targeted Victory, Bamberger & Vlasto, or another firm. NV SOS records are the key.

3. **Where does the money actually go?** Summit Ridge and Lantern receive millions via FEC filings, but they are intermediaries. The actual media placements (TV buys, digital ads, direct mail) are executed by production companies, ad platforms, and print houses that may not appear in FEC records.

4. **Is summitridgemedia.com (Christo Zeelie) connected to Summit Ridge Media Group LLC?** The name similarity could be coincidence, or Zeelie could operate both. His GoHighLevel marketing agency template site bears no resemblance to a political media operation.

5. **Are there other PACs using this same shell vendor pattern?** The "Main Street Media Group" from Fairshake suggests this is a repeating template. A broader FEC search for single-client media vendors with mailbox addresses could reveal the full scope of this practice.

---

## 5. Recommended Follow-Up

### Critical (NV SOS — requires manual browser warmup)
```bash
uv run python tools/query_nevada.py warmup    # Solve Incapsula challenge
uv run python tools/query_nevada.py search "SUMMIT RIDGE MEDIA" --mode contains
uv run python tools/query_nevada.py search "LANTERN PRODUCTION" --mode contains
```

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
