# Analysis Flows - Diagnostic Procedures

This file contains the orchestration entry point and crash-type-specific
information gathering steps.

- Phase 2 procedure: [collection-flow.md](collection-flow.md)
- Phase 3 procedure: [analysis-flow.md](analysis-flow.md)

## Table of Contents
1. [Entry point to all flows](#entry-point-to-all-flows)
2. [XFS hang / filesystem deadlock flow](#xfs-hang--filesystem-deadlock-flow)
3. ["Unable to handle paging request" flow](#unable-to-handle-paging-request-flow)
4. [WARNING flow](#warning-flow)
5. [BUG / BUG_ON flow](#bug--bug_on-flow)
6. [Panic flow](#panic-flow)

---

## Entry point to all flows

Analysis uses sequential agents with separate identities. Do not combine
phases in a single agent — strict separation prevents premature analysis
during data collection.

### Progress tracking

Before launching any agent, create a todo list so the user can track
pipeline progress:

| id | title |
|----|-------|
| `step-1-fetcher` | Step 1 — Fetcher (pre-fetch vmlinux / git / distro packages) |
| `step-2-collector` | Step 2 — Collector (fundamentals, backtrace, source mapping) |
| `step-3-analyst` | Step 3 — Analyst (root cause, fix candidates, email) |
| `step-4-patcher` | Step 4 — Patcher (patch email) |
| `step-5-factchecker` | Step 5 — Fact checker (verify source quotes and metadata) |
| `step-6-patchreviewer` | Step 6 — Patch reviewer (correctness gate) |

Mark each todo `in_progress` when its agent is launched and `completed`
when it finishes. Skip / mark `cancelled` any step that does not apply
(e.g. Step 1 only when no distro or syzbot signals are present, Step 4/6
if no `report.patch` was produced, or Step 6 if patcher returned
`PATCH_FAILED`).

### Vmcore input routing

If the user supplied a vmcore, run `analyze-vmcore` before considering the
legacy Fetcher. The user need not classify the issue. Read `evidence.json`,
then only the matched `focus/*.txt` file; do not pass raw vmcore to the skill.

After evidence acquisition:

- Route a primary Oops, Panic, BUG, or WARNING signature to the existing
  crash-type flow, using extracted text evidence as its input.
- Route XFS lock evidence without a primary crash signature to the **XFS hang
  / filesystem deadlock** flow in [xfs-hang.md](xfs-hang.md). The flow uses
  `crash-query` for its iterative `bt -f` and object queries.
- Otherwise stop at generic vmcore triage with the evidence bundle and state
  the exact additional crash commands needed.

Do not launch the legacy Fetcher merely because a vmcore bundle was supplied
with matching vmlinux and source already available.

### Step 1 — Launch the fetcher agent (optional, recommended for syzbot and distro oops)

Launch [`agents/fetcher.agent.md`](../agents/fetcher.agent.md) using a
**small/fast model** (e.g. Claude Haiku) when **any** of the following apply:
- The oops is from **syzbot** (vmlinux URL present in the email)
- The oops is from **Ubuntu** (UNAME matches `X.Y.Z-N-generic` with `~` in
  the version header — Launchpad git checkout + ddeb download)
- The oops is from **Debian** (UNAME matches `X.Y.Z+debN-amd64` —
  pool index lookup + `-dbg` package download)
- The oops is from **Fedora** (UNAME matches `X.Y.Z-N.fcNN.x86_64` —
  Koji RPM download + CKI git checkout)
- The HEAD commit SHA is already known from any other source (git checkout
  can be pre-staged regardless of distro)

Skip the fetcher only when none of the above apply (e.g. a plain mainline
oops with no vmlinux URL and no known HEAD commit).

Launch with:
- The full oops text
- The kernel source tree path
- The report output directory path

The fetcher runs concurrently with your review of the oops. Wait for it
to complete and confirm `prefetch.md` exists before launching the collector.
If the fetcher is not launched, the collector handles all acquisition steps
itself.

### Step 2 — Launch the collection agent

Launch [`agents/collector.agent.md`](../agents/collector.agent.md) with:
- The full oops text
- The output path for report.md
- The kernel source tree path
- The vmlinux URL (if known)
- Any other pre-extracted facts (commit, MSGID, etc.)

Wait for the agent to complete and confirm report.md exists on disk before
proceeding.

### Step 3 — Launch the analysis agent

Launch [`agents/analyst.agent.md`](../agents/analyst.agent.md) with:
- The path to report.md written by the collection agent
- The path to backtrace.json in the same directory (if it exists)
- The time Phase 2 took (so the analyst knows its remaining budget)
- The MSGID (for the reply email)
- The kernel source tree path
- The external report URL base (from local.md `External URL for reports`)

Wait for the agent to complete.

### Step 4, 5, 6 — Launch the patch agent (conditional), fact checker (always), and patch reviewer (conditional)

After the analyst completes:

- **Steps 4 and 5** can run in parallel — the patcher and fact-checker do
  not touch each other's sections of report.md.
- **Step 6** (patch reviewer) must wait for the patcher to finish, since
  it reviews the formatted `patch-email.txt`.

#### Step 4 — Patch agent (conditional)

Check whether `report.patch` exists in the report archive directory. Launch
[`agents/patcher.agent.md`](../agents/patcher.agent.md) **only** if:

- `report.patch` exists (analyst identified a new fix), **and**
- The analysis confidence is high (analyst did not mark the fix as speculative)

Launch with:
- The path to `report.patch`
- The path to `report.md`
- The kernel source tree path
- The `PATCH_BASE` commit/tag noted in report.md
- The MSGID (for `In-Reply-To`)
- The external report URL base (from local.md)

#### Step 5 — Fact checker (always)

Always launch [`agents/factchecker.agent.md`](../agents/factchecker.agent.md)
using a **small/fast model** (e.g. Claude Haiku) — the task is mechanical
(file lookup, string comparison, git commands) and does not require deep
reasoning.

Launch with:
- The path to `report.md`
- The path to `analysis-email.txt` (if it exists in the same directory)
- The path to `backtrace.json` (if it exists in the same directory)
- The kernel source tree path
- The `PATCH_BASE` commit/tag noted in report.md

#### Step 6 — Patch reviewer (conditional, after Step 4)

Launch [`agents/patchreviewer.agent.md`](../agents/patchreviewer.agent.md)
**only** if Step 4 produced a `patch-email.txt` (i.e. patcher did not
return `PATCH_FAILED`). Use a **small/fast model** (e.g. Claude Haiku) —
see the model note in the agent file for when to reconsider this choice.

Launch with:
- The path to `patch-email.txt`
- The path to `report.md`
- The kernel source tree path (checked out to `PATCH_BASE`)

Wait for Steps 5 and 6 to complete, then regenerate `report.html` once:

```bash
pandoc report.md -o report.html --standalone
```

### ⚠️ Do NOT commit report output files

Never run `git add reports/` or `git add <report-dir>/`. The `reports/`
directory is listed in `.gitignore` and must stay out of the repository —
report files are local working artefacts, not part of the skill source.
If you need to record analysis progress, update the todo list or write
a summary in the session notes; do not commit files under `reports/`.

---

## XFS hang / filesystem deadlock flow

This flow applies after `evidence.json` routed the case as `xfs_hang`. Do not
enter it from a keyword match alone. Read `focus/xfs.txt`, then issue only the
needed `crash-query` commands. Detailed evidence procedure:
[xfs-hang.md](xfs-hang.md).

1. **Preserve the scene** — collect vmcore, matching vmlinux, and XFS module
   debuginfo. Export `foreach UN bt`. Retain dmesg, mount table, block-device
   in-flight counts, and I/O/CPU metrics. Do not reboot or run `df` repeatedly
   — `statfs` amplifies the hang when `inodegc` is stalled.

2. **Locate the blocking centre from all D-state stacks** — split task stacks on
   blank lines and count module tags and wait functions. Distinguish
   `xfs_buf_lock`, `xlog_grant_head_wait`, `xfs_inodegc_flush`, inode
   `i_rwsem`, and block-layer I/O waits. The `[xfs]` module tag count is a
   lead only; “many tasks stopped at the same wait point” is the primary
   evidence.

3. **Classify direct waiters** — create one `bt <pid>` command for every
   `xfs_hang` route candidate in `evidence.json`, submit it through one
   `crash-query --commands-file` invocation, and read `queries.log`. Do not
   sample candidate PIDs. For each resulting group:
   - `xfs_buf_lock`: distinguish `xfs_read_agi`, `xfs_read_agf`,
     `xfs_imap_to_bp`, directory/log buffer by the calling function.
   - `xlog_grant_head_wait`: log space exhaustion or stalled log advancement.
   - `xfs_inodegc_flush`: `df`/`statfs` waiting on background inodegc —
     typically a downstream symptom, not the root.

4. **Promote from stack suspicion to object-level proof** — load
   `xfs.ko.debug`. Use `bt -f <PID>` and `struct xfs_buf -o` to recover
   `b_sema` and the `xfs_buf` address. Verify `b_sema.count`, `wait_list`,
   `b_hold`, `b_ops`, `b_pag`, `b_mount`, and `b_transp`. Use `b_ops` to
   confirm the object type (`xfs_agf_buf_ops`, `xfs_inode_buf_ops`, etc.) —
   do not infer type from the function name alone.

5. **Reconstruct the dependency graph and classify the root cause** — correlate
   `b_transp` with transaction pointers visible in each task stack to establish
   who holds a lock and who waits. A closed cycle is required to call it a
   deadlock (e.g. T1 holds AGF, waits inode-cluster; T2 holds inode-cluster,
   waits AGF). Without a closed cycle, classify as lock contention or prolonged
   wait, not deadlock. Also check I/O in-flight, XFS shutdown flags, and I/O
   errors to rule out a stuck lower layer.

6. **Explain the cascade and map to a fix** — the typical progression is:

   ```
   root buffer lock ─→ inodegc / writeback stalled
                    ─→ AIL / journal tail cannot advance
                    ─→ xlog_grant_head_wait accumulates
                    ─→ statfs/df, container file ops, app threads cascade into D
   ```

   Compare the confirmed lock order against upstream patches. Verify that the
   running kernel contains the equivalent code change — do not rely on the
   distro version string or an unrelated backport. Final output must separate:
   confirmed facts, strongly associated inferences, items requiring further
   verification, and fix recommendations.

## "Unable to handle paging request" flow

Additional information gathering steps for paging request crashes (Phase 1, step 4).
After these steps are complete, the Entry Point Phase 2 (Deep Analysis flow) produces
the full What-How-Where report.

1. Note CR2 (the faulting address) and classify it:
   - NULL or near-NULL (< 0x1000): likely a NULL pointer dereference.
   - Valid-looking kernel address that is not mapped: use-after-free or bad pointer.
   - User-space address accessed from kernel context: missing access_ok() check.
2. Note the page fault error code bits (read/write, user/kernel, not-present vs. protection).

## WARNING flow

Additional information gathering steps for WARNING crashes (Phase 1, step 4).
After these steps are complete, the Entry Point Phase 2 (Deep Analysis flow) produces
the full What-How-Where report.

1. Note the exact warning text and the source location encoded in the WARNING header line.
2. Determine whether the warning is a developer-inserted assertion (`WARN_ON`) or a
   runtime consistency check.

## BUG / BUG_ON flow

Additional information gathering steps for BUG crashes (Phase 1, step 4).
After these steps are complete, the Entry Point Phase 2 (Deep Analysis flow) produces
the full What-How-Where report.

1. Extract the BUG condition — what assertion failed and the exact source location.
2. Note the BUG variant: `BUG()`, `BUG_ON()`, `VM_BUG_ON()`, `VM_BUG_ON_FOLIO()`, etc.,
   as this hints at which kernel subsystem considers the state impossible.

## Panic flow

Additional information gathering steps for Panic crashes (Phase 1, step 4).
After these steps are complete, the Entry Point Phase 2 (Deep Analysis flow) produces
the full What-How-Where report.

1. Identify the panic reason string (e.g. `Fatal exception in interrupt`).
2. If the panic followed an OOPS, treat the OOPS as the primary crash to analyse.
3. If it is a "soft lockup" or "hard lockup", note the CPU state and backtraces
   of all CPUs reported in the log.
