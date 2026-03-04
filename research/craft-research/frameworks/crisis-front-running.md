---
name: Crisis Front-Running
slug: crisis-front-running
domain: financial-crime
source: "Investigation synthesis of RTX pre-strike positioning, Polymarket foreknowledge bets, and defense stock surge timing (2025-2026)"
status: candidate
created: 2026-03-03
grounding_findings: [4725, 4730, 4943]
related_models: [adversarial-simultaneity, intelligence-brokerage, convergent-policy-channeling]
detection_keywords:
  - ["framework agreement", "pre-positioned", "signed before", "days before"]
  - ["Polymarket", "prediction market", "betting", "foreknowledge", "front-running"]
  - ["stock surge", "all-time high", "insider trading", "10b5-1 plan"]
  - ["minutes before", "hours before", "days before", "weeks before"]
  - ["strike", "conflict", "crisis", "war", "escalation"]
  - ["defense stocks", "LMT", "RTX", "NOC", "PLTR"]
---

## Definition

Crisis Front-Running is the pattern of financial positioning -- through contract agreements, equity purchases, prediction market bets, or options trades -- that precedes a crisis event (military strike, policy announcement, enforcement action, sanctions) in ways that suggest foreknowledge. The mechanism requires (a) a crisis event that creates financial winners and losers, (b) financial transactions completed before the event whose profitability depends on the event occurring, and (c) a plausible information channel connecting the transactors to people with advance knowledge of the event.

This is distinct from Adversarial Simultaneity, which describes *maintaining relationships with opposing sides* of a conflict for information and leverage. Crisis Front-Running describes *financial positioning ahead of a specific event*, which may or may not involve opposing-side relationships. The broker in AS profits from the *duration* of a conflict; the front-runner in CFR profits from a *specific moment* -- the transition from peace to war, from policy discussion to policy announcement, from investigation to indictment.

It is also distinct from Intelligence Brokerage, which describes the *collection and selective distribution* of intelligence. Intelligence Brokerage is the information flow; Crisis Front-Running is the financial exploitation of that flow. The two are complementary: intelligence brokerage creates the information asymmetry, and crisis front-running monetizes it.

In this investigation: Three distinct instances document the pattern:

**RTX framework agreements**: Framework agreements between RTX and the DoD for missile and interceptor production were signed on February 4, 2026 -- 24 days before Iran strikes began on February 28 (F4730). Framework agreements pre-position a company to fill orders rapidly when demand surges. The timing raises the question: did RTX (or DoD procurement officials) have advance knowledge that a conflict requiring massive interceptor expenditure was imminent? RTX executives made stock sales in late February (Williams on Feb 23, Mitchill on Feb 19) -- the investigation has an open lead to determine whether these were pursuant to pre-existing 10b5-1 plans or discretionary sales (F4943).

**Polymarket foreknowledge bets**: On the first trading day after Iran strikes (Mar 2), defense stocks hit all-time highs: LMT +3.37%, RTX +4.7%, NOC +6%, PLTR +5.8%. But the more granular evidence is in prediction markets. Polymarket saw $529M in Iran-related bets. The "Magamyman" account made $553K betting on Khamenei removal -- first trade placed 71 minutes before news broke at 17% probability. Six wallets collectively netted $1.2M from suspicious pre-strike bets funded within 24 hours of the event (F4725). The combination of (a) specific directional bets, (b) timing immediately before non-public information became public, and (c) wallet funding patterns that suggest preparation creates a documentary trail of potential foreknowledge.

**Congressional stock holdings**: Multiple Congress members serving on defense/homeland security committees with potential inside information on strikes owned defense stocks that surged: Rep. Cisneros (LMT, PLTR), Rep. Moskowitz (LMT), Rep. Franklin (LMT), Rep. Comer (PLTR), Rep. Fields (PLTR) (F4725). While congressional stock ownership is not illegal (absent specific STOCK Act violations), the combination of committee access to classified strike planning and personal financial holdings in the companies that benefit from strikes is a structural front-running condition.

## Detection Markers

- Contract agreements, framework orders, or procurement vehicles finalized within 30 days before a crisis event that creates demand for the contracted products/services
- Prediction market bets placed within hours of a non-public event, at odds that suggest the bettor assessed the event as more probable than the market implied (Magamyman at 17% probability)
- Wallet or account funding patterns that show preparation: accounts funded within 24-48 hours before the event, suggesting foreknowledge of timing
- Stock trades (especially options) in crisis-beneficiary companies by individuals with access to classified or non-public information about the crisis
- 10b5-1 plan status of insider trades: discretionary trades by defense company executives in the days before a military action are more suspicious than trades pursuant to pre-existing automated plans
- Government officials with defense stock holdings serving on committees or in roles with access to operational planning for the crisis that would benefit those holdings
- Post-crisis supplemental spending bills whose beneficiary companies match the pre-crisis positioning

## Mechanism

1. **Information asymmetry** -- A small number of people know (or strongly suspect) that a crisis event is imminent: military commanders, White House staff, intelligence officials, congressional leadership, senior defense company executives (through framework agreement negotiations), and potentially their associates.

2. **Financial positioning** -- People with this knowledge, or people they inform, take financial positions that will profit from the event: stock purchases, options, prediction market bets, contract agreements that pre-position for surge demand.

3. **Event occurs** -- The crisis event creates the financial payoff: defense stocks surge, prediction market bets pay off, framework agreements convert to funded orders, supplemental spending is proposed.

4. **Attribution difficulty** -- The financial positions were taken before the event, but proving that the position was *because of* foreknowledge (rather than general conviction about geopolitical trends) requires demonstrating the information channel. The information channel typically runs through classified briefings, which are difficult to subpoena and whose contents are hard to verify.

5. **Structural vs. opportunistic** -- At the structural level, government officials who hold defense stocks *always* benefit from military action, whether or not they had specific foreknowledge of specific strikes. The structural conflict (owning defense stocks while having strike authorization) is the enabling condition; the opportunistic front-running (buying more stock or placing bets before a specific strike) is the exploitation.

## Limitations

- **Coincidence is the null hypothesis.** Framework agreements are signed on a regular schedule; some will inevitably precede crises by chance. Stock ownership by defense committee members is common and not illegal. Prediction markets attract speculators who make directional bets based on public information and geopolitical analysis. The framework should be applied only when the timing, specificity, and information channel evidence collectively exceed what coincidence can explain.
- **Proving foreknowledge requires proving the information channel.** Financial positioning that profits from an event is necessary but not sufficient. Without evidence that the positioner had access to non-public information about the event, the framework produces suspicion, not evidence.
- **Prediction markets are designed for speculative bets.** Some participants will always be early on correct directional calls. The diagnostic is the combination of timing (minutes before, not days), funding pattern (wallet funded immediately before), and specificity (betting on a specific event, not a general trend).
- **10b5-1 plans provide a legitimate defense.** Insider trades pursuant to pre-existing automated selling plans are legally protected. The framework's detection markers should distinguish between discretionary trades and plan-based trades before drawing conclusions.
- **This framework can fuel conspiracy theories if applied carelessly.** Every military action will have some financial positioning that preceded it. The framework must be applied with evidentiary discipline: document the timing, the financial position, and the plausible information channel. Do not infer foreknowledge from timing alone.
