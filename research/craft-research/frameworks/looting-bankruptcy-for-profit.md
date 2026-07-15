---
name: Looting (Bankruptcy for Profit)
slug: looting-bankruptcy-for-profit
domain: economic
source: "Akerlof & Romer, 'Looting: The Economic Underworld of Bankruptcy for Profit' (Brookings Papers, 1993); Black (2005)"
status: evaluated
created: 2026-07-11
grounding_findings: [11450, 11451, 11438, 11441, 11466, 11435, 11508, 11517, 11582, 11584, 2039, 10552, 10556]
related_models: [control-fraud, crisis-front-running, related-party-transaction-scoring, peripheral-collapse, enabler-gradient]
minimum_trigger: "Documented extraction (fees, compensation, dividends, stock-funded purchases, related-party sales) that is large relative to the firm's true economics, PLUS a structural reason the extractors don't bear the downside (limited liability + an identifiable residual loss-bearer such as a guarantor, late-round investor, or creditor)"
anti_pattern: "Failed bets by insiders who held their equity to zero (they bore the loss — that's gambling, not looting); normal market-rate compensation at a firm that later failed; venture losses where investors knowingly priced the risk"
canonical_example: "F11450 — WeWork's stock-funded 2017-19 M&A spree as an extraction vector: sellers were paid in overvalued paper at peak marks, WeWork impaired the acquisitions, SoftBank absorbed the terminal loss"
detection_keywords:
  - ["extraction", "extracted", "stripped", "looting", "siphoned", "asset stripping"]
  - ["bag-holder", "bagholder", "bore the loss", "wrote it to zero", "impaired", "write-down", "wrote down", "made whole"]
  - ["paid in stock", "preferred stock", "stock-funded", "stock as currency", "overvalued paper", "shares instead of cash"]
  - ["advisory fees", "management fees", "special dividend", "dividend recap", "fees despite", "upfront fee"]
  - ["exited before", "cashed out", "sold before", "pre-collapse", "before the bankruptcy", "got out first"]
  - ["guarantee", "backstopped", "bailout", "rescue financing", "downside protection"]
---

## Definition

Akerlof and Romer's looting model formalizes when it is *rational* for the people controlling a firm to destroy it: whenever limited liability, guarantees, or systematically mispriced funding let owners extract more value than the firm is actually worth, "bankruptcy for profit" dominates honest operation. The looter's objective function is not the firm's net present value but the extractable current flow — salaries, bonuses, fees, dividends, related-party purchases, and sales of overvalued paper — so the firm's books are steered to maximize *extractable accounting income now*, not economic value. The model's sharpest prediction is behavioral: looters and gamblers look different. A manager gambling for resurrection concentrates risk and holds on, hoping to survive (and loses their own equity when it fails); a looter extracts early, front-loads sure payouts, avoids bets that could pay off only in a future the looter doesn't expect the firm to have, and is indifferent to terminal collapse because someone else — a guarantor, a creditor, a late investor — is the residual loss-bearer. That distinction converts an unprovable intent question into an observable structure-and-timing question, which is exactly what the claim ladder requires.

In this investigation the lens is grounded most densely in the WeWork acquisition program (thread 83): a ~$1.17B, 16+-company M&A spree paid substantially in WeWork preferred stock at peak private marks (F11451), with Conductor bought for $113.6M of which only $15.8M was cash (F11438), Managed by Q generating a ~$155-162M net loss inside 11 months (F11441, F11466), sellers alleging inducement in Emamian v. Neumann (F11435), a round-trip in which a seller took stock and WeWork later repurchased at a loss (F11508), and an undisclosed founder-to-seller relationship (F11517). The residual-loss-bearer structure is explicit: connected parties exited in a tight cascade before the Chapter 11 (F11582), using the same takeout mechanics as earlier insider redemptions (F11584), leaving SoftBank the terminal bag-holder. The pattern generalizes across profiles: the Marvin Davis trust-looting litigation (F2039) is the family-trust variant, and Allbirds shows the small-cap variant — a $39M asset sale to a related affiliate weeks before a control-shifting transaction (F10552) under a death-spiral facility whose covenants hand the extractor control of future financings (F10556).

The lens differs from Control Fraud in level: Control Fraud is the *operational method* (how the controlling officer weaponizes accounting); Looting is the *economic precondition* (why value-destruction is profitable at all). Many instances satisfy both; the looting lens applies even where no accounting statement is false — extraction can be fully disclosed and still be looting if the downside is systematically borne by others.

## Detection Markers

- **Extraction-to-economics ratio**: fees, compensation, dividends, and related-party payments large relative to (or exceeding) genuine operating earnings; extraction continuing or accelerating while true economics deteriorate.
- **Residual loss-bearer identification**: name who actually absorbs the terminal loss (guarantor, sovereign fund, late-round investor, credit fund, pension). If the decision-makers are not on that list, the looting precondition is satisfied.
- **Front-loaded, sure-thing payouts**: dividend recaps, upfront advisory fees, stock sales at administered marks — payouts that do not depend on the firm's survival.
- **Paper-as-currency transactions**: acquisitions or compensation paid in the firm's own overvalued/illiquid securities at insider-set marks; watch for later impairment of exactly those deals.
- **Exit-timing cascade**: structurally-positioned insiders exiting in a tight window before collapse (event_timeline / timeline-analysis over exit dates vs. failure date).
- **Accounting latitude in the extractors' hands**: valuation marks, revenue recognition, or reserve choices controlled by the same people whose payouts key off them (bridge to Control Fraud).
- **Looter-vs-gambler discriminator**: did the controllers' own wealth ride the firm to zero (gambling) or was it withdrawn ahead of failure (looting)? Score each principal separately — the Enabler Gradient applies inside the extraction coalition too.

## Boundary Conditions

- Does NOT apply where insiders demonstrably bore the loss alongside outside investors — check Form 4s, plan-of-reorganization recoveries, and clawback litigation before asserting the pattern.
- Does NOT apply to disclosed, market-rate compensation at firms that failed for ordinary competitive reasons; the marker is extraction *mispriced relative to economics*, not extraction per se.
- Baseline comparison: venture-backed failure is common and usually not looting. The lens requires the guarantee/mispricing leg — someone lending or investing on terms that don't price the true risk (Akerlof-Romer's original S&L deposit insurance; here, sovereign-scale sponsors marking their own books).

## Limitations

- "Looting" is legally loaded vocabulary. In findings, keep it at Pattern/Mechanism rungs (synthesis, max medium) unless a court has used the word; intent-to-loot remains an Intent claim requiring direct evidence.
- The model assumes extractors correctly foresee failure; messy reality mixes looting with genuine delusion. The discriminator markers (front-loading, exit timing) mitigate but don't eliminate this ambiguity.
- Guarantees are often implicit (too-big-to-fail expectations, patron reputational stakes) — harder to document than explicit ones; label implicit-guarantee claims as inference.
