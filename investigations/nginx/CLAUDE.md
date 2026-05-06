# NGINX Investigation — Agent Guidance

## Research Priorities

Focus on **infrastructure, governance, code, and corporate control** over personality narratives. The investigation tests whether Russian entities exerted influence over nginx through:
1. Corporate control (board seats, investment leverage, hiring authority)
2. Developer governance (commit access, code review authority, maintainer selection)
3. Code-level manipulation (backdoors, weakened crypto, unnecessary complexity in security paths)

## Source Reliability

| Source | Trust Level | Notes |
|--------|------------|-------|
| Git commit history | **Primary** | Authoritative for who changed what code and when. Author attribution can be spoofed but timestamps are reliable. |
| SEC filings (F5 10-K, 8-K, proxy) | **Primary** | F5 is public (FFIV). Acquisition filings are detailed. |
| Delaware/state corporate registries | **Primary** | Officers, agents, filing dates. NGINX Inc was private so filings are thin. |
| OpenCorporates / GLEIF | **Primary** | Cross-jurisdictional corporate records. |
| OpenSanctions (default + ru_egrul) | **Primary** | Sanctions, PEP data. ru_egrul has 12.3M Russian companies — available via bulk download if needed. |
| nginx changelog / release notes | **Primary** | Official project history. |
| Investigative journalism (Reuters, Bloomberg) | **Secondary** | Verify against primary sources. Useful for leads. |
| Russian state media (RT, TASS, RIA) | **Extreme caution** | Treat as propaganda unless corroborated. May contain planted narratives about the raid. |
| Hacker News / tech forums | **Tertiary** | Lead generation only. Employee comments may reveal insider perspectives but are unverified. |
| Wikipedia | **Tertiary** | Starting point for timelines, never cite as evidence. |

## Key Analytical Heuristics

### For Code Audit (Track 3)
The key heuristic is NOT "is this code malicious" (too hard to determine in isolation). Instead ask:
- **Does this commit introduce unnecessary complexity or optionality in a security-sensitive area?**
- Does it add code paths that could be triggered by specific inputs but aren't documented?
- Does it deviate from well-established patterns (e.g., custom PRNG instead of system entropy)?
- Does error handling suppress information that would reveal anomalous behavior?

### For Timeline Correlation (Track 2)
Look for:
- Burst of commits to security-sensitive code right before F5 acquisition closes
- Commits from Moscow-based developers to TLS/auth code after the December 2019 raid
- Activity gaps that correlate with corporate events (investment rounds, acquisition)
- Timezone patterns — UTC+3 (Moscow) activity in security subsystems

### For Fork Analysis (Track 4)
- What did the Angie (Moscow team) fork change **first**? Removal of specific code paths could indicate knowledge of problems.
- What does Dounin's freenginx prioritize? He left over a security disclosure dispute — his post-fork changes reveal his security priorities.

## Data Quality Notes

- **NGINX Inc was private** — corporate filings will be thinner than a public company. Expect Delaware incorporation + annual reports but no SEC filings until F5 acquired them.
- **Git author attribution is weak** — contributors can use any name/email. Identity resolution across email changes needs manual verification. Use timezone as a secondary heuristic.
- **The Rambler raid has competing narratives** — (1) legitimate IP dispute (Sysoev wrote nginx while employed at Rambler), (2) state-orchestrated leverage operation (Sberbank bought into Rambler right before the raid). Document both interpretations, don't assume either.
- **OpenCorporates rate limits** — 500 calls/month, 200/day on basic tier. Budget carefully when mapping Runa Capital entities.

## Environment Notes

- nginx git repo: `https://github.com/nginx/nginx.git` (primary, clone first)
- Angie fork: `https://github.com/webserver-llc/angie` (add as lead, clone when needed)
- freenginx: `https://freenginx.org/` (Mercurial repo, add as lead)
- F5 CIK for EDGAR: look up via `query_edgar.py lookup "F5 Networks"`
- Russian corporate data: `query_opensanctions.py download --dataset ru_egrul` (26.78 GB, defer until needed)
