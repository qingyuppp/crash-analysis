# XFS Hang Evidence Agent

After `evidence.json` routes to `xfs_hang`, read `focus/xfs.txt` and follow the
XFS hang flow. First batch-query `bt` for every route candidate PID using
`cra vmcore diagnose compact-bt`, then classify every direct
`xfs_buf_lock` waiter from its compact function-level summary before selecting
object-level queries. Read `queries.log` after each batch. Do not treat raw
vmcore as LLM input, sample candidates by PID, or claim a deadlock without
explicit typed wait and holder evidence.
