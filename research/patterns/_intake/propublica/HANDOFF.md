# Handoff: ProPublica evidence-ontology project (started 2026-07-28)

Mission, state, and remaining work for continuing this in a fresh session. The canonical copy of
all working state is THIS directory (`research/patterns/_intake/propublica/`). A prior session's
scratchpad at `/private/tmp/claude-501/-Users-travcole-projects-osint-research/13891cf8-bfc3-45ac-b770-153ca90b346e/scratchpad/propublica-ontology/`
holds the same files and is where in-flight wave-2 agents write; it may vanish on reboot.

Read SYNTHESIS-PLAN.md first — it is the binding spec (deliverables, de-biasing rules).
Everything below is elaborated there and in the reports themselves.

## Remaining work
1. Collect wave-2 reports (report-11..16) from the tmp path above into this directory as they
   land; respawn any missing cluster per SYNTHESIS-PLAN wave-2 spec (census §8 seeds, free-form
   tagging, neutral schema, write file via Bash).
2. Synthesize into `research/patterns/` (README, propublica-ontology.md, detection-signatures.md,
   propublica-story-index.md) — bottom-up, ≥2 cited instances per category, retired-priors +
   emergent-categories sections, census §9 sampling-frame framing.
3. `research/patterns/adapter-gaps.md` — diff observed evidence-source usage vs
   coverage-inventory.md; rank by usage frequency + patterns unlocked; candidates only.
4. Memory update + final user summary. No commits. No investigation.db writes.
