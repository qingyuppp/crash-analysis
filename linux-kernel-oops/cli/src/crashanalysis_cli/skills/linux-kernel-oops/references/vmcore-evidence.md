# Vmcore Evidence Acquisition

## Purpose

Convert a vmcore bundle into deterministic text evidence before any crash or
hang analysis begins. This stage validates inputs and runs `crash`; it does
not analyse the cause, identify a deadlock, or recommend a fix.

Never give raw vmcore directly to an LLM. Later agents read only the text
evidence produced by this procedure.

## Required inputs

- `vmcore` — the kernel memory dump captured while the problem was present;
- matching vmlinux — an exact matching uncompressed `vmlinux`, or debuginfo
  from which that matching vmlinux has already been extracted;
- matching kernel source tree — the source for the same vendor build or its
  documented exact commit.

## Recommended input

- vmcore dmesg text, when it was saved separately from the dump.

`crash> log` is still required even when external dmesg is unavailable because
the vmcore can contain the in-memory printk ring buffer.

## Validation

Before evidence collection, record in `evidence-manifest.md`:

1. the vmcore path and readability;
2. the matching vmlinux path and readability;
3. the source-tree path and readability;
4. the kernel release and build identifiers available from `crash> sys`;
5. whether external dmesg is present.

Do not substitute a nearby kernel release for matching vmlinux. If the exact
symbol file or source is unavailable, record that condition and stop before
root-cause analysis.

## Baseline crash commands

Run `crash` with the matching vmlinux and vmcore using this conservative
baseline command file:

```text
set scroll off
sys
log
ps -m
bt -a
foreach UN bt
mod
mount
kmem -i
exit
```

Do not run `foreach bt` by default because it can produce an excessively large
evidence file. Add it only after the focused evidence identifies a concrete
need.

## Compact outputs

Write these files to the evidence output directory:

```text
crash-raw.txt         complete deterministic crash output; skill does not read it by default
evidence.json         inputs, validation, task index, classification, routes, and raw line ranges
focus/xfs.txt         generated only for an XFS route
focus/fault.txt       generated only for an Oops/Panic/BUG/WARNING route
focus/hang.txt        generated only for a generic hang route
queries.log           initially empty; iterative crash query evidence from the skill
```

The skill reads `evidence.json` first and then the matching focus file.
`crash-raw.txt` remains an escalation artifact; use `crash-query` instead of
opening it when more evidence is needed.

## Post-evidence routing

Classify the collected text in this order:

1. A primary Oops, Panic, BUG, or WARNING signature routes to the existing
   crash-type flow. The extracted text, not raw vmcore, becomes its input.
2. No primary crash signature plus XFS lock or log signals routes to the
   XFS hang / filesystem deadlock flow. Relevant signals include
   `xfs_buf_lock`, `xlog_grant_head_wait`, `TASK_UNINTERRUPTIBLE`, and XFS
   worker stacks.
3. If neither route has sufficient evidence, stop at generic vmcore triage
   and state the exact additional crash commands that would reduce uncertainty.

Do not start the legacy Fetcher merely because a vmcore bundle was supplied
with matching vmlinux and source already available.

## Failure behavior

Stop before analysis when vmcore, matching vmlinux, or source is unavailable,
or when `crash` cannot load the vmcore. Record the exact failed validation and
the command output in `evidence-manifest.md`; do not compensate by asking an
LLM to inspect raw vmcore.
