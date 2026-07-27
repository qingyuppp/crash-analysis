# Vmcore XFS Analysis Pipeline Design

## Goal

Build a Jenkins-run container workflow that mounts kernel incident artefacts,
executes the `linux-kernel-oops` skill as a staged analysis pipeline, and
produces an auditable report.  XFS hang analysis is a classified branch of
that pipeline, not a separate top-level tool.

## Scope and boundaries

The pipeline accepts a vmcore, matching debuginfo/vmlinux, kernel source, and
an optional dmesg text file.  It must never supply the raw vmcore to JoyCode
or another LLM.  `crash` is the only component that reads the vmcore.

The first implementation targets the AGF-versus-inode-cluster-buffer ABBA
deadlock described in `linux-kernel-oops/utils/人工分析.md`.  It reports a
confirmed cycle only when the collected evidence identifies both wait edges
and identifies the buffer types.  It must distinguish a confirmed cycle from
XFS suspicion and from insufficient evidence; it must not infer a holder from
an address alone.

The workflow does not build a vmcore, repair a filesystem, upload incident
artefacts, or apply kernel patches.  Network access is not required while
analysing mounted input artefacts.

## Architecture

```text
Jenkins parameters / agent-local paths
  -> read-only Docker mounts
  -> analyze-vmcore orchestrator
       -> crash evidence collector
       -> normalized evidence bundle
       -> all-UN task discovery and routing index
       -> XFS specialist, existing Oops/Panic flow, or generic specialist
       -> JoyCode report writer using text evidence only
  -> Jenkins archives output/**
```

`analyze-vmcore` is the single command-line entry point.  It validates the
mount contract, discovers `vmlinux` from debuginfo, runs a generated `crash`
command file, and records the exact commands and raw output as artefacts.
It then passes only derived text files to the skill.  JoyCode receives the
skill installed inside the image, the normalized evidence, and the mounted
read-only source tree.

The image copies this repository's `linux-kernel-oops` directory at build
time.  It must not clone the public upstream skill during image construction;
otherwise the image can silently omit private XFS functionality.

## Inputs and mount contract

| Logical input | Container path | Required | Validation |
|---|---|---:|---|
| vmcore | `/data/input/vmcore` | yes | regular, readable file |
| debuginfo RPM | `/data/input/debuginfo.rpm` | yes | regular, readable file; contains vmlinux |
| kernel source | `/data/input/kernel` | yes | readable directory with `Makefile` |
| dmesg | `/data/input/dmesg` | no | readable regular file when present |
| output | `/data/output` | yes | writable directory |

Jenkins may obtain each input from an agent-local path or a supplied URL.
All incident inputs are mounted read-only.  The only writable bind mount is
the output directory; RPM expansion and other scratch data remain inside the
container.  A missing dmesg does not stop vmcore analysis; reports state that
the extra textual context was unavailable.

## Analysis stages and artefacts

1. **Data extraction.** The collector runs baseline `crash` commands (`sys`,
   `log`, `ps -m`, `mount`, `mod`, and memory/device summaries).  It executes
   `foreach UN bt` only for a hang candidate, keeps its full result outside
   the LLM context, and writes `crash.cmds`, `crash-raw.txt`, and
   `evidence/extraction.md`.
2. **Task discovery and classification.** A deterministic parser normalizes
   every UN task into `evidence/task-index.json` without copying full stacks:
   PID, task address, command, blocking site, subsystem tags, normalized stack
   fingerprint, and raw line span.  It emits `evidence/routing.json` with
   aggregate counts and specialist routes.  A compact
   `evidence/classification.json` selects `oops_panic`, `xfs_hang`,
   `hung_task`, or `unknown`; a primary Oops/Panic signature wins over a hang
   route.  `task-index.json` is program-only (normally 1–3 MiB for thousands
   of tasks), while `routing.json` is the small skill input (normally under
   50 KiB).
3. **Specialist analysis.** For `xfs_hang`, the XFS analyzer collects and
   normalizes each waiter as `{pid, comm, task, waited_buffer, buffer_type,
   stack_path}`.  It then attempts holder/transaction correlation and emits
   `evidence/xfs-lock-graph.json` plus `evidence/xfs-analysis.md`.
4. **Report.** JoyCode invokes the installed skill with the bounded evidence
   bundle (target: under 192 KiB of focused text),
   source tree, and explicit boundaries.  It writes `analysis.md`.  When
   JoyCode is disabled or fails, the deterministic evidence and a concise
   fallback report remain available.

## XFS AGF/inode-cluster detection rules

The collector identifies candidate waiters from `TASK_UNINTERRUPTIBLE` stacks
containing `xfs_buf_lock` / `xfs_buf_find`.  It derives the requested buffer
pointer from the `down` call frame, then uses `struct xfs_buf.b_ops` to label
it as AGI, AGF, inode cluster, or unknown.  It preserves full relevant stacks
instead of a keyword-only excerpt.

The analyzer reports `confirmed_agf_inode_abba` only if all are true:

- task A waits for an AGF buffer and its stack contains the inodegc/ifree
  allocation path;
- task B waits for an inode-cluster buffer and its stack contains writeback
  allocation/logging;
- transaction/buffer-log-item evidence, or an explicit lock holder, connects
  task A to the inode-cluster buffer and task B to the AGF buffer; and
- both buffer identities are present in the evidence bundle.

If only the first two conditions are available, the result is
`suspected_agf_inode_inversion`; the report lists the exact extra `crash`
commands required for confirmation.  If XFS lock waiters exist but do not fit
that signature, the result is `xfs_lock_wait_unknown`.  Log-space, AIL, and
block-I/O observations are retained as contributing evidence, never used as
proof of the buffer ABBA by themselves.

## Failure handling

Input-contract or vmlinux-discovery failures exit nonzero before analysis.
`crash` failures preserve its stdout/stderr and exit nonzero.  If a particular
XFS structure is unavailable because of kernel layout or missing debug data,
the analyzer continues with reduced confidence and records the failed command
and reason.  A JoyCode timeout or failure does not discard deterministic
artefacts; Jenkins still archives them and marks the report as incomplete.

## Testing and acceptance criteria

Local Mac verification is limited to unit fixtures, shell syntax, and static
Docker/Jenkins contracts.  Docker image builds, container smoke tests, real
vmcore runs, and Jenkins execution occur only on the remote development node.
Unit/fixture tests must prove that the classifier routes Oops/Panic, XFS, and
unknown evidence correctly; that the XFS parser produces confirmed, suspected,
and insufficient outcomes; and that raw vmcore paths never enter the JoyCode
prompt.  Shell contract tests must check mount paths, optional-dmesg handling,
private-skill image installation, and output archive paths.  A real vmcore is
an operational validation, never a test fixture committed to the repository.
