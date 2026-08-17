# XFS 死锁（AGF ↔ inode-cluster ABBA）vmcore 分析

## 1. 概述

- **触发方式**：`sysrq triggered crash`（`Kernel panic - not syncing: sysrq triggered crash`，panic 任务 PID 143304 `bash`）
- **主分类**：`xfs_hang`
- **内核**：`5.10.0-1.oe.jd_448.x86_64`（vmlinux：`/data/output/debug/usr/lib/debug/lib/modules/5.10.0-1.oe.jd_448.x86_64/vmlinux`）
- **xfs 模块**：base `ffffffffc0b19000`，size 1855488（`xfs.ko-5.10.0-1.oe.jd_448.x86_64.debug`）
- **机器**：64 CPU，512 GB 内存，26752 任务，uptime 17 天 08:07:32，load average 4712
- **结论**：**确认的 AGF ↔ inode-cluster ABBA 死锁**（`confirmed_agf_inode_abba`），发生在挂载 `/dev/vdb2` 上。

## 2. 证据来源

- `/data/output/evidence.json`（分类 `xfs_hang`，schema_version 1）
- `/data/output/routing.json`：路由 `xfs_hang`，candidate_pids 79 个（组 6，`xfs_buf_lock` 等待者）
- `/data/output/focus/xfs.txt`（13725 行）
- 动作产物：`actions/001-compact-bt`（79 个 `bt`）、`actions/002-task`（bt -f 284533）、`actions/003-task`（bt -f 224856）、`actions/004-023-query/structure`（mod -s、struct、sym、ps）
- 每次动作均记录于 `/data/output/queries.log`

## 3. 死锁判定：confirmed_agf_inode_abba

两个不同任务在 **1 个 AGF buffer** 与 **1 个 inode-cluster buffer** 之间存在**互惠、类型化**的等待边，且**两边都有直接事务/持有者证据**（`b_transp` → `xlog_ticket.t_task` 与 `b_log_item` 均非空并回指对应 buffer）。

```
PID 284533 (kworker/43:0, inodegc/ifree)
  持有 inode-cluster buffer ff257babca53ddc0  ──────────────┐
  等待 AGF buffer ff257b675031dc00                          │
        ▲                                                   │
        │                                                   ▼
  等待 inode-cluster buffer ff257babca53ddc0         持有 AGF buffer ff257b675031dc00
PID 224856 (kworker/u128:63, writeback/delalloc)
```

## 4. 候选任务表（compact-bt 分组，直接 xfs_buf_lock 等待者 = 79）

| kind | 栈模式 | 代表 PID | 说明 |
|------|--------|---------|------|
| agi | `xfs_buf_lock→…→xfs_read_agi` | 284294 等 | create/unlink/ifree 等大量 AGI 等待者（java/dockerd/containerd/kworker） |
| agf | `xfs_buf_lock→…→xfs_read_agf→xfs_alloc_fix_freelist` | **284533**（inodegc/ifree finobt） | 另有 writeback/delalloc、blockgc、inodegc truncate 等子组 |
| inode_cluster | `xfs_buf_lock→…→xfs_imap_to_bp` | **224856**（writeback/delalloc） | 唯一 inode-cluster 组 |

按规程，AGF 与 inode-cluster 两组均存在，各选一个代表：
- **AGF 代表**：`284533`（kworker/43:0，inodegc/ifree，`xfs_difree_finobt→xfs_ifree→xfs_inactive_ifree→xfs_inodegc_worker`）
- **inode-cluster 代表**：`224856`（kworker/u128:63，writeback/delalloc，`xfs_imap_to_bp→xfs_trans_log_inode→xfs_bmap_btalloc→xfs_bmapi_convert_delalloc→…→wb_workfn`）

## 5. 类型化 buffer 表

挂载：`/dev/vdb2`（`s_id="vdb2"`，`s_dev=265289746`，`sb_magicnum=0x58465342`，`sb_blocksize=4096`，`sb_agcount=4`，`sb_dblocks=170898432`）。两个 buffer 同属一个 perag（`b_pag=0xff257b674b5ab800`，AG 0）。

| Buffer | 地址 | b_ops | b_bn | b_length | b_sema.count | b_transp | b_log_item |
|--------|------|-------|------|----------|--------------|----------|------------|
| AGF | `ff257b675031dc00` | `xfs_agf_buf_ops` (0xffffffffc0bd0880) | 1 | 1 | 0（已锁） | `0xff257b68420c0e80` | `0xff257bb15ab015a8` |
| inode-cluster | `ff257babca53ddc0` | `xfs_inode_buf_ops` (0xffffffffc0bd1360) | 19565568 (0x12A8000) | 32 | 0（已锁） | `0xff257b68c119a828` | `0xff257b9caf237ac8` |

两个 `b_log_item` 均为 `li_type=4668`（XFS_LI_BUF），`li_ailp=0xff257b6747c63980`（同一 AIL），`bli_buf` 分别回指 `0xff257b675031dc00` 与 `0xff257babca53ddc0`。

## 6. 等待边与持有者边

| 任务 | 命令 | 等待的 buffer | 持有的 buffer |
|------|------|---------------|---------------|
| **284533** | kworker/43:0（inodegc/ifree） | AGF `ff257b675031dc00` | inode-cluster `ff257babca53ddc0` |
| **224856** | kworker/u128:63（writeback/delalloc） | inode-cluster `ff257babca53ddc0` | AGF `ff257b675031dc00` |

**持有者证据链**（两边均成立）：
- AGF buffer `ff257b675031dc00`：`b_transp=0xff257b68420c0e80` → `t_ticket=0xff257b6b40f3ae60` → `t_task=0xff257ba32b688000` = **PID 224856**（`ps -t` 确认 `kworker/u128:63`）
- inode-cluster buffer `ff257babca53ddc0`：`b_transp=0xff257b68c119a828` → `t_ticket=0xff257b68c12e4da8` → `t_task=0xff257b9d327f8000` = **PID 284533**（`ps -t` 确认 `kworker/43:0`）

**等待边**（来自 `bt -f` 的 `down` 帧参数，即 `xfs_buf_lock` 的 `bp`）：
- PID 284533 在 `down` 帧等待 `ff257b675031dc00`（AGF）
- PID 224856 在 `down` 帧等待 `ff257babca53ddc0`（inode-cluster）

## 7. 死锁成因（机制）

- **PID 284533**（inodegc/ifree）：在 `xfs_inactive_ifree→xfs_difree→xfs_difree_finobt` 中，为释放 inode 需要向 finobt 插入记录，触发 `__xfs_inobt_alloc_block→xfs_alloc_fix_freelist→xfs_alloc_read_agf`，等待 **AGF buffer**；同时它已在其事务中持有该 inode 的 **inode-cluster buffer**（`xfs_trans_log_inode` 已记录）。
- **PID 224856**（writeback/delalloc）：在 `xfs_bmapi_convert_delalloc→xfs_bmap_btalloc` 中，为分配块需要读取 **AGF buffer** 并已持有；随后 `xfs_trans_log_inode→xfs_imap_to_bp` 需要读取该 inode 的 **inode-cluster buffer**，等待它。
- 两者在 **AG 0** 上形成互惠等待环：284533 持 inode-cluster 等 AGF，224856 持 AGF 等 inode-cluster，构成 ABBA 死锁。

## 8. 置信度

- **高**。两边等待边（`down` 帧参数）与持有者边（`b_transp→t_ticket→t_task` + `b_log_item` 回指）均直接可见且互惠，buffer 类型由 `b_ops`（`xfs_agf_buf_ops` / `xfs_inode_buf_ops`）确认，挂载/设备一致（`/dev/vdb2`，AG 0）。
- 判定：**confirmed_agf_inode_abba**。

## 9. 促成/下游证据（非死锁本身）

- 大量 `xlog_grant_head_wait` 等待者（组 7，787 pids，`xfs_vn_update_time` 路径）——日志空间不足，为下游症状。
- `xfsaild/vdb2`（PID 1991）、`xfsaild/vdb1`（1819）、`xfsaild/dm-0`（1834）存在；AIL 停滞（两个 buffer 的 log item 均在 AIL）。
- `df` 堵在 `xfs_inodegc_flush→xfs_fs_statfs`（PID 512/982/1709/3006/3016 等）；`cat` 堵在 `xfs_ilock`（64710/89085 等）。
- 这些单独均不能证明死锁，仅作为促成证据或下游症状。

## 10. 缺失边对应的下一条 crash 命令

当前 ABBA 环已完整闭合，无缺失边。若需进一步佐证或排查其他挂载（vdb1/dm-0）：
- 对 vdb1/dm-0 的 AGF/inode-cluster 等待者重复上述流程（`cra vmcore diagnose compact-bt` + `task` + `structure`）。
- 检查 AIL 停滞根因：`struct xfs_ail` / `xfsaild` 栈，确认是否有 log item 卡在 `XFS_LI_NEED_WAIT`。
- 检查日志满：`struct xlog` 的 `l_iclog`/`l_grant_head`，确认 `xlog_grant_head_wait` 是否因 ABBA 死锁导致事务无法提交、日志无法回收。
