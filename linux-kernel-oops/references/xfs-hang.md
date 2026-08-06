# XFS Hang and Filesystem Deadlock Flow

Use this flow when `evidence.json` contains an `xfs_hang` route. Read
`focus/xfs.txt` first. Do not classify a filesystem hang from a raw vmcore or a
keyword alone; use `/usr/local/bin/crash-query --command '<crash command>'` for
all vmcore access and read `queries.log` after every query.

## Evidence sequence

1. Read the XFS candidate PIDs and raw line ranges in `evidence.json`.
2. Query `bt -f <pid>` for candidates and any newly relevant task. Use results
   to distinguish inodegc/ifree, writeback, log-space, AIL, and block-I/O
   paths.
3. Extract a waited buffer
   address only when it is directly visible in the frame arguments.
4. Use `struct xfs_buf.b_ops <buffer>` and `struct xfs_buf.b_transp <buffer>` to label AGI, AGF, inode-cluster, or
   unknown.  Record a failed query as missing evidence, not as a type.
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

Separate facts from hypotheses.  Include the candidate task table, typed
buffer table, wait-for edges, mount/device correlation, confidence, and exact
next `crash` commands for each missing edge.  Give raw evidence file ranges
instead of copying large all-UN output into the report.
