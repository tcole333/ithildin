# GEO federal-recipient identity map

As of 2026-07-13, the canonical map resolves **12 unique current SAM registrations**, **2 legacy award-recipient registrations absent from current SAM**, and **6 legal names/UEIs actually used as ICE prime-award recipients**. The search manifest has **75 rows**, but that is not 75 subsidiaries or current registrations: it consists of **60 exact FY2025 Exhibit 22 guarantor names** plus **15 parent, former-name, legacy-recipient, and punctuation variants**, normalizing to **62 canonical legal identities**.

## Recipient registrations

| Federal legal name | UEI | CAGE | SAM status | HigherGov key | Award-recipient usage |
|---|---|---|---|---:|---|
| B.I. INCORPORATED | PKK6L9KLMYR5 | 3CUH9 | Active | 10147020 | 166 DHS actions |
| COMMUNITY EDUCATION CENTERS, INC. | K197TCMH5UB5 | 3YET9 | Active | 10116178 | 0 DHS actions in bounded scan |
| CORNELL COMPANIES, INC. | TLDCDE29G781 | 3MTH6 | Expired legacy registration | 10106691 | 24 DHS actions |
| CORRECTIONAL SERVICES CORPORATION | LTXHRJ986LF3 | 3KGQ1 | Not in March 2026 current SAM extract | 13276025 | 3 DHS actions |
| GEO CARE SERVICES, LLC | G6XJKMJUNB91 | 7D4M5 | Active | 10125440 | 92 DHS actions |
| GEO CARE, INC | J8LEF6VCY967 | 15A51 | Active | 1331958329 | 0 DHS actions in bounded scan |
| GEO CPM INC | XHRVS1L8YE54 | 99YL8 | Active | 59927962 | 0 DHS actions in bounded scan |
| GEO MANAGEMENT SERVICES INC | ZBJYBK7M9A44 | 7T8J8 | Active | 12479589 | 0 DHS actions in bounded scan |
| GEO REENTRY INC | KDQ3R3N44ZJ1 | 7CUD5 | Active | 10108147 | 0 DHS actions in bounded scan |
| GEO REENTRY OF ALASKA, INC. | FNT5N5HMB9A7 | 7G0K5 | Active | 10114506 | 0 DHS actions in bounded scan |
| GEO REENTRY SERVICES LLC | CLKXSJLN8EN1 | 7G0N6 | Active | 12440992 | 0 DHS actions in bounded scan |
| GEO SECURE SERVICES, LLC | JLG3JBCL4CC7 | 7G0P0 | Active | 10113516 | 0 DHS actions in bounded scan |
| GEO TRANSPORT, INC. | DFEKRCYPZD84 | 6PV86 | Active | 12382356 | 3 DHS actions |
| THE GEO GROUP, INC. | JMLKZZ1NL2Z6 | 3JMR1 | Active | 10000076 | 1128 DHS actions |

Displayed action counts are DHS-wide for 2015-01-01 through 2026-07-13, not all ICE: the parent row's 1,128 actions include 54 CBP actions in the verified procurement scan.

The six ICE award-recipient identities in the durable reconstruction are The GEO Group, B.I. Incorporated, Cornell Companies, Correctional Services Corporation, GEO Care Services, and GEO Transport. The remaining eight UEIs are retained because they are verified current GEO registrations, but the bounded 2015-01-01 through 2026-07-13 DHS scan returned zero DHS actions for them. That does not exclude other-agency, indirect, IGSA, subcontract, or differently registered work.

## Coverage and lineage rules

- GEO's primary SEC Exhibit 22 states that its 60 names are subsidiary guarantors to GEO's outstanding senior notes. Forty-eight of those exact legal identities had no verified recipient registration in the bounded current SAM/14-UEI recipient sources.
- Punctuation-only variants are collapsed, but distinct registrations are not. Correctional Services Corporation (legacy UEI `LTXHRJ986LF3`, CAGE `3KGQ1`) remains separate from FY2025 guarantor **Correctional Services Corporation LLC**.
- The 2003 SEC filing supports **Wackenhut Corrections Corporation** as the same issuer's former name before **The GEO Group, Inc.**; it is not counted as a separate current registration.
- The 2026 SEC credit amendment supports **GEO Care, LLC** as the former name of **GEO Care Services, LLC**. **GEO Care, Inc.** remains a separate entity and separate UEI.
- Facility and operator trade names are not promoted into recipient registrations. Every manifest row is tagged to the legal-entity plane.

## Time-sensitive SAM reconciliation

The March 2026 local extract showed GEO Care Services and GEO Secure Services expiring in June 2026. Two live SAM calls resolved the stale dates: both were active, last updated/activated 2026-06-01, and expire 2027-05-20. No other live SAM calls were used in this pass.

## Unresolved and bounded negatives

**GEO Corrections Holdings, Inc.** remains the main federal-identity gap. It is an exact FY2025 Exhibit 22 guarantor, but exact local and previously logged live SAM checks plus exact USAspending recipient checks did not resolve a UEI or award recipient. This is a bounded current-source negative, not proof that no historical registration exists.

The other 47 SEC-only guarantor identities are marked as not identified in the March 2026 SAM extract or verified 14-UEI recipient set. They were not converted into global or historical no-award claims.

HigherGov's row for GEO Management Services treats that awardee as its own parent, while GEO's primary Exhibit 22 identifies it as a subsidiary guarantor. The map preserves the SEC parent relationship and records the secondary hierarchy divergence.

## Audit note

Findings #12403 and #12474 are excluded from Tier 2 use here: this identity-map pass did not audit their full-history award/obligation reconstructions, and none of their totals appear in these artifacts. Verified findings #12531-#12534 govern the bounded 2015-2026 DHS denominator. The full row-level manifest, canonical identity records, source quotes, dates, NAICS codes, and unresolved notes are in the JSON and CSV companions.

## Primary sources

- [GEO FY2025 Exhibit 22.1](https://www.sec.gov/Archives/edgar/data/923796/000119312526071747/geo-ex22_1.htm)
- [GEO 2003 Wackenhut-to-GEO name-change filing](https://www.sec.gov/Archives/edgar/data/923796/000095014403011842/g85438e8vk.htm)
- [GEO 2026 credit amendment naming GEO Care Services f/k/a GEO Care](https://www.sec.gov/Archives/edgar/data/923796/000119312526022602/d85667dex101.htm)
- SAM.gov entity registrations by UEI (canonical links included in JSON)
- USAspending recipient/action evidence summarized in verified findings #12531-#12534
