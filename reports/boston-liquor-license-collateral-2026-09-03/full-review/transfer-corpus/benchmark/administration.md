# Pilot administration

Recorded before either response run on 2026-09-04 UTC.

Both fresh agents receive the same instructions and frozen input. One filesystem read is allowed only to deliver input.json; one filesystem write is allowed only to preserve the raw JSON answer. No other files, reference answers, browsing, or research tools are allowed. This artifact-delivery exception to the pack's no-tools instruction applies equally to both models and does not permit tools during analysis.

Both runs use high reasoning effort. A single run per model on these deliberately selected cases is an accuracy pilot, not an equivalence test, a reliability estimate, or a price/performance study. Timing includes artifact I/O and tool scheduling. Per-run token usage is unavailable unless the runtime provides it; it must not be guessed from account-wide usage.

Input SHA256: d4952abfa65904484d3ae835d0a8a6e1dc1cc0f2d41e177a81a10196950b5258

Reference SHA256: f9c6a218afc9b91cb49e31cb7fbadcc4852c4c87162e46a2210e58598a25448e

The existing rubric and reference remain frozen. Reference corrections, if source-supported, must be recorded separately and applied equally. Scoring uses anonymized response filenames.
