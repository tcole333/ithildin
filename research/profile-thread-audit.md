# Profile ↔ Thread Ownership Audit

**Status:** Phase 1 (read-only analysis + tooling). No historical remap applied — this document is the proposal for human review.
**Tool:** `scripts/audit_profile_threads.py` (read-only; `--profile X`, `--json`, `--output FILE`)
**DB audited:** `investigation.db` (WAL)
**Verified:** 2026-07-04

---

## 1. The defect

`findings`, `leads`, and `connections` each carry a **global** `thread_id`
(FK → `investigation_threads.id`) *and* a `profile_id`. But investigation
profiles number their threads **locally** in `investigations/<name>/config.yaml`
(config thread id `1..N`). When a profile's config-local ids overlap the global
ids another profile already owns — classically **epstein's global threads 1–8** —
a record written with a config-local `thread_id` lands on the *wrong* profile's
thread.

Compounding it: `findings.profile_id` and `leads.profile_id` both
`DEFAULT 'epstein'`, so any record created without an explicit profile silently
inherits epstein regardless of which investigation produced it.

### Root-cause direction (the load-bearing finding)

In **every** mismatch inspected, the record's **own `profile_id` is the reliable
owner**, and the `thread_id` is the stale/colliding field. The finding was
self-tagged with the correct profile but written on a config-local thread number
that collides with epstein's global threads. Spot-checks:

| record | profile_id | thread_id | content | true owner |
|---|---|---|---|---|
| finding 11804 | `softbank-caper` | 1 | Brian Haddock / 'Geek Slop' GRP complaint | softbank-caper ✓ |
| finding 11335 | `coscoluella` | 1 | Ed Coscolluela CPA identity | coscoluella ✓ |
| finding 9793 | `nginx` | 1 | Runa Capital 11-entity network (Angie fork) | nginx ✓ |
| finding 10039 | `zampolli` | 6 | Zampolli→Epstein DOJ Vol 11 email | zampolli ✓ |
| finding 11941 | `epstein` | 76 | Benedetti v Sawiris ↔ Epstein corpus cross-ref | epstein ✓ (on a softbank thread) |

**Therefore the correct remediation is a THREAD re-map**
(config-local id → the profile's own global thread id), exactly as
`scripts/migrate_softbank_caper_threads.py` already did for softbank-caper
(1–11 → 76–86). **It is NOT a `profile_id` rewrite** — the `profile_id` is
already correct on the vast majority of records. Any tool that "fixes" this by
trusting the thread and overwriting `profile_id` would corrupt 2,000+ correctly
tagged records.

---

## 2. Verified counts

Numbers below are read directly from `investigation.db` and reconcile with the
audit tool's totals.

| Metric | Count |
|---|---|
| **findings** with `profile_id` ≠ thread's `profile_id` | **1,687** |
| **leads** with `profile_id` ≠ thread's `profile_id` (non-null) | **543** |
| **connections** whose `profile_id` ≠ their source finding's `profile_id` | **18** |
| findings with NULL `profile_id` | 1 (a `TEST_PROFILE_CHECK` artifact, id 7460) |
| **leads with NULL `profile_id`** | **5,612** — of which **5,518 have no thread** (cannot infer) and 94 sit on epstein threads |
| connections with NULL `profile_id` | 6 |

The mismatch reconciles as **2,083 safe-remap + 147 contested = 2,230** =
1,687 findings + 543 leads.

---

## 3. Per-profile classification

`SAFE-AUTO` = every drifted record is a pure config-local collision (its own
`profile_id` is corroborated; remediation is a mechanical re-thread).
`NEEDS-REVIEW` = at least one record's `profile_id` is *contested* (see §4).
"safe" / "contested" columns count individual records.

| profile | verdict | findings | leads | safe-remap | contested | config-local → DB threads |
|---|---|---:|---:|---:|---:|---|
| tech-right | NEEDS-REVIEW | 1147 | 140 | 1254 | 33 | 1–10 → **9–18** |
| zampolli | NEEDS-REVIEW | 184 | 161 | 336 | 9 | 1–6 → **46–51** |
| nginx | NEEDS-REVIEW | 197 | 61 | 188 | 70 | 1–6 → **not seeded** |
| parlatore | NEEDS-REVIEW | 67 | 17 | 81 | 3 | 1–7 → **64–70** |
| dfj-network | **SAFE-AUTO** | 40 | 28 | 68 | 0 | 1–6 → **not seeded** |
| hfia | **SAFE-AUTO** | 0 | 52 | 52 | 0 | 1–7 → **39–45** |
| manosphere | **SAFE-AUTO** | 0 | 51 | 51 | 0 | 1–7 → **32–38** |
| altman | NEEDS-REVIEW | 21 | 8 | 14 | 15 | 1–6 → **not seeded** |
| smci | NEEDS-REVIEW | 15 | 0 | 8 | 7 | 1–4 → **not seeded** |
| epstein-aetna | NEEDS-REVIEW | 4 | 11 | 12 | 3 | 1–6 → **52–57** |
| chesney | NEEDS-REVIEW | 8 | 0 | 5 | 3 | 1–2 → **not seeded** |
| mike-johnson | **SAFE-AUTO** | 0 | 7 | 7 | 0 | 1–6 → **not seeded** |
| allbirds | **SAFE-AUTO** | 0 | 7 | 7 | 0 | 1–6 → **58–63** |
| softbank-caper | NEEDS-REVIEW | 2 | 0 | 0 | 2 | 1–11 → **76–86** |
| epstein | NEEDS-REVIEW | 1 | 0 | 0 | 1 | 1–7 → 1–8 |
| coscoluella | NEEDS-REVIEW | 1 | 0 | 0 | 1 | 1–5 → **71–75** |

**SAFE-AUTO (5 profiles, mechanical re-thread):** dfj-network, hfia, manosphere,
mike-johnson, allbirds. Every drifted record is a clean config-local collision;
none of their records land on epstein's thread 1, so nothing is contested.

**NEEDS-REVIEW (11 profiles):** carry at least one contested record — but see the
crucial nuance in §4: for most of these, the *bulk* of the mismatch is still
safe-remappable, and the contested subset is concentrated entirely on one thread.

---

## 4. What "contested" actually means (the thread-1 artifact)

The audit flags a record `NEEDS-REVIEW` when its `profile_id` disagrees with a
thread that is ≥90 % owned by a *different* profile and the record is the lone
outlier. **Every one of the 147 contested records sits on epstein's global
thread 1** ("Epstein Core Network"):

```
nginx=70  tech-right=33  altman=15  zampolli=9  smci=7  chesney=3  parlatore=3  epstein-aetna=3   → ALL on thread 1
```

Thread 1 is simultaneously (a) epstein's **largest genuine thread** (2,525
profiled records) and (b) the **most-collided config-local slot** (`id: 1` in
every profile's config). Its sheer epstein volume means its 94 % epstein share
*swamps* any collision victim landing on it. So the ≥90 % heuristic cannot tell
apart two very different populations without reading content:

- **False positives (collision victims):** e.g. nginx finding 9793 *Runa Capital*
  and 9796 *Serguei Beloussov* — genuinely nginx (Angie-fork Russian-tech
  network), correctly tagged nginx, merely stranded on config-local thread 1.
  The correct fix is a re-thread; `profile_id` should NOT change.
- **True positives (genuine misfiles):** e.g. tech-right findings 4885–4891 —
  PPP loans to **Epstein-network entities** (HBRK/Richard Kahn, Island Global
  Yachting/Farkas, Nardello/Brad Karp). Content, thread, and siblings all say
  *epstein*; only `profile_id` says tech-right. Here `profile_id` itself is the
  suspect field.

**Design decision:** the tool never auto-asserts a `profile_id` flip. For every
contested record it keeps `proposed_profile_id = record.profile_id` and emits an
`AMBIGUOUS` evidence line telling a human to read the record. Deciding
victim-vs-misfile is a content judgment an automated audit must not make.

Practical consequence: even the NEEDS-REVIEW profiles are *mostly* safe. E.g.
tech-right is 1,254 clean re-thread + 33 thread-1 records to eyeball; zampolli is
336 clean + 9. Only nginx (70/258) and altman (15/29) have a materially large
contested fraction, and both are entirely the thread-1 artifact.

---

## 5. Two structural sub-cases the remediation must handle

1. **Profiles with NO threads seeded in the DB** — `chesney`, `smci`,
   `dfj-network`, `altman`, `nginx`, `mike-johnson`. Their config declares
   threads `1..N` but nobody ran `lead_tracker.py thread seed`, so **all** their
   records sit on config-local ids that collide with epstein. There is no global
   thread to remap *to* yet. Remediation for these must **first seed their
   threads** (assigning fresh global ids, as softbank got 76–86), then remap
   config-local → the new global ids. Note this includes two SAFE-AUTO profiles
   (dfj-network, mike-johnson) — "safe" refers to the record-level ambiguity, not
   to the seeding prerequisite.

2. **Reverse / cross-profile stragglers** (all NEEDS-REVIEW, tiny):
   - `softbank-caper` findings 11804, 11806 on thread 1 — missed by
     `migrate_softbank_caper_threads.py` (they were on config-local thread 1, and
     that script only remapped rows already tagged `softbank-caper` on threads
     1–11; these two qualify and should be swept in a re-run).
   - `coscoluella` finding 11335 on thread 1 — analogous straggler.
   - `epstein` finding 11941 on thread **76** (a softbank thread) — an epstein
     corpus cross-reference written while in softbank context; genuinely
     ambiguous whether to re-thread onto an epstein thread or reclassify.

---

## 6. NULL-profile records (separate problem)

The 5,612 NULL-`profile_id` leads are a *different* failure from the thread
collision and should be handled separately:

- **5,518 have no `thread_id` at all** → cannot be inferred from a thread.
  `tools/fix_null_profiles.py` assigns these to the **active profile**, which is
  only correct if the active profile at apply-time is the one that created them —
  a fragile assumption for a 5,518-row backlog accumulated across many
  investigations. These should be triaged by creation context (agent_run_id,
  created_at window, title/description content), **not** blanket-assigned.
- **94 sit on epstein threads** → can be treated like the mismatch set (trust the
  thread only if content agrees).
- The single NULL-profile **finding** (id 7460) is a `TEST_PROFILE_CHECK` test
  artifact and can be deleted.

---

## 7. Connection drift (18 + 6)

- **6 NULL-profile connections** and **6** `tech-right`-finding-derived
  connections with NULL conn.profile_id (findings 7436–7453: Anduril / Founders
  Fund / Missile Defense Agency edges) — should inherit their source finding's
  profile.
- **8 connections tagged `tech-right` but derived from `softbank-caper`
  findings** (Misra ↔ Wirecard, Neumann ↔ Agarwal, Credit Suisse ↔ Vision Fund,
  Eros ↔ Misra, etc.) — the exact **thread-9/10/11 footgun** documented in
  MEMORY.md, where softbank-caper mistakenly used threads 9–11 and its
  connections were re-homed to tech-right. These edges belong to softbank-caper.
- **4 connections tagged `dfj-network` but derived from `epstein` findings**
  (Readsboro / Oscrivia / QWave / Centice) — a genuine cross-profile boundary
  (DFJ ↔ Epstein financial network); review whether the edge is dfj-network or
  epstein.

---

## 8. Recommendation: how / whether to apply the remap

**Do the remap, but as a THREAD re-map through an audited path — never a bulk
`UPDATE profile_id`.** Concretely:

1. **SAFE-AUTO, already-seeded (hfia, manosphere, allbirds, and the safe subset
   of others):** apply a `migrate_softbank_caper_threads.py`-style script that
   remaps config-local `thread_id` → the profile's existing global thread ids.
   Structural FK-only, idempotent, dry-run by default (`--apply` to commit),
   scoped to one `profile_id`. Leaves `profile_id` untouched. This is the proven
   pattern and is low-risk.

2. **SAFE-AUTO / NEEDS-REVIEW, not-yet-seeded (dfj-network, mike-johnson;
   chesney, smci, altman, nginx):** first `lead_tracker.py thread seed` to mint
   global threads for these profiles, capture the config-local→global map, then
   run the same re-thread migration. Verify the seed did not reuse an occupied
   global id.

3. **The 147 contested (all on thread 1):** hold for a human content pass. The
   audit's `--json` output enumerates each with `record_id`, `label`, and an
   `AMBIGUOUS` evidence note. A reviewer marks each victim (re-thread, keep
   profile) vs misfile (change profile). Genuine `profile_id` changes must go
   through **`findings_tracker.py correct`** (the audited corrections path) —
   **direct `UPDATE` on `findings` is hook-blocked** by design, and re-homing a
   `profile_id` is exactly the kind of change that should leave a corrections
   audit trail.

4. **Stragglers (§5.2):** re-run the softbank migration to sweep findings 11804 /
   11806, handle coscoluella 11335 the same way, and adjudicate epstein 11941
   individually.

5. **NULL leads (§6):** separate remediation effort; triage by creation context,
   do not blanket-assign to the active profile.

6. **Prevent recurrence:** the write-time guard added to
   `findings_tracker.add_finding` (see below) warns on new drift at creation
   time. Longer-term, config-local thread numbering should be eliminated in
   favor of always seeding global thread ids per profile (as softbank and the
   post-8 profiles already do), so `id: 1` never collides again.

### Guard shipped in this phase

`tools/findings_tracker.py::add_finding` (line ~288) now performs a warn-only
check: when both `thread_id` and `profile_id` are set, it looks up the thread's
owning profile and prints a `WARNING: profile/thread drift …` to **stderr** if
they disagree. It **never raises** — modelled on the existing `VALID_SOURCES`
warning, so existing tools/tests are unaffected. Covered by
`tests/test_enforcement.py::TestProfileThreadGuard` (4 cases: drift-warns,
match-silent, no-thread-silent, null-thread-profile-silent). This is a tripwire
for *new* drift; it does not touch existing rows.

---

## 9. Reproduce

```bash
uv run python scripts/audit_profile_threads.py              # full human summary
uv run python scripts/audit_profile_threads.py --profile nginx
uv run python scripts/audit_profile_threads.py --json --output audit.json
```

The `--json` report contains `totals`, `by_profile` (with declared vs DB thread
ids), `null_records`, `connection_mismatches`, and a `proposals` array where each
entry has `record_id`, `thread_id`, `current_profile_id`, `thread_profile_id`,
`proposed_profile_id`, `changes_profile_id`, `classification`, `label`, and a
per-record `evidence` list.
