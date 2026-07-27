# XFS Hang and Filesystem Deadlock Flow

Use this flow only after vmcore evidence acquisition and task routing selected
an `xfs_hang` route.  Do not classify a filesystem hang from a raw vmcore or a
keyword alone.

## Evidence sequence

1. Read `evidence/routing.json` and select the listed XFS candidate PIDs.
2. Read their complete ordinary stacks from the raw crash evidence.  Use them
   to distinguish inodegc/ifree, writeback, log-space, AIL, and block-I/O
   paths.
3. Run `bt -f <pid>` only for selected candidates.  Extract a waited buffer
   address only when it is directly visible in the frame arguments.
4. Use `struct xfs_buf.b_ops <buffer>` to label AGI, AGF, inode-cluster, or
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

## Report requirements

Separate facts from hypotheses.  Include the candidate task table, typed
buffer table, wait-for edges, mount/device correlation, confidence, and exact
next `crash` commands for each missing edge.  Give raw evidence file ranges
instead of copying large all-UN output into the report.
