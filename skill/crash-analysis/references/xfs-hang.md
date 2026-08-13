# XFS Hang and Filesystem Deadlock Flow

Use this flow when `evidence.json` contains an `xfs_hang` route. Read
`focus/xfs.txt` first. Do not classify a filesystem hang from a raw vmcore or a
keyword alone; use `cra vmcore diagnose` for all vmcore access and read
`queries.log` after every query.

## Evidence sequence

1. Read the XFS candidate PIDs in the `xfs_hang` route in `evidence.json`.
   Write one `bt <pid>` command for every candidate PID to a temporary commands
   file and run one batch query:

   ```bash
   cra vmcore diagnose compact-bt --evidence /data/output/evidence.json --pids <route candidate PIDs>
   ```

   Do not sample the candidate list or prioritize it by PID, command name,
   `xlog_grant_head_wait`, or `xfsaild`. Read the compact function-level
   summary in `queries.log`, then classify all direct `xfs_buf_lock` waiters by
   the caller above it: `xfs_read_agi` (AGI), `xfs_read_agf` (AGF),
   `xfs_imap_to_bp` (inode-cluster), or `other`.
2. If both AGF and inode-cluster groups exist, choose one representative from
   each group, preferring an inodegc/ifree AGF waiter and a writeback/
   delalloc inode-cluster waiter. Run `cra vmcore diagnose task --evidence
   /data/output/evidence.json --pid <pid>` for both representatives.
3. Derive a waited buffer
   address only when it is directly visible in the frame arguments.
4. Use `cra vmcore diagnose query` for `mod -s <matching xfs.ko.debug>`
   before any structure command when module type information is not already
   available. Use `cra vmcore diagnose structure` for `struct semaphore
   <b_sema>`, `struct xfs_buf <buffer>`, `struct xfs_buf.b_ops <buffer>`, and
   `struct xfs_buf.b_transp <buffer>` for both representatives. Use the results to label AGI,
   AGF, inode-cluster, or unknown. Record a failed query as missing evidence,
   not as a type.
5. Use `b_log_item` and transaction-item evidence only to connect a specific
   holder to a buffer.  Do not infer ownership from an address, a command name,
   or a common mount alone.

## Verdicts

- `confirmed_agf_inode_abba`: two distinct tasks have reciprocal, typed wait
  edges between one AGF and one inode-cluster buffer, with direct holder or
  transaction evidence for both edges.
- `suspected_agf_inode_inversion`: inodegc/ifree waits for AGF and writeback
  waits for inode cluster, but at least one holder edge is unproven.
- `xfs_lock_wait_unknown`: XFS waiters exist without the required typed paths.

Log-full, AIL stagnation, xlog waiters, and XFS buffer waits alone do not
prove a deadlock.  They are contributing evidence or downstream symptoms.

`struct semaphore` does not identify its owner. A holder edge requires an
explicit transaction, lockdep, or task-stack relation to the same typed buffer.

## Report requirements

Write `analysis.md` in Simplified Chinese; preserve kernel symbols, crash
commands, addresses, and other machine identifiers verbatim. Separate facts
from hypotheses. Include the candidate task table, typed
buffer table, wait-for edges, mount/device correlation, confidence, and exact
next `crash` commands for each missing edge.  Give raw evidence file ranges
instead of copying large all-UN output into the report.
