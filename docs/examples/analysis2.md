# vmcore 崩溃分析报告：kswapd0 内存回收路径 NFS readdir 数组损坏导致 kfree 页错误

## 1. 结论摘要

- **崩溃类型**：`BUG: unable to handle kernel paging request`（Oops 0000 [#1] SMP NOPTI），属 oops_panic 流程（非 xfs_hang，`compact-bt` 显示 `direct_xfs_buf_lock_waiters: 0`）。
- **崩溃任务**：`kswapd0`（PID 499，TASK `ffff9f522884bd80`，CPU 40，STATE TASK_RUNNING）。
- **崩溃点**：`kfree+0x4f/0x160`（RIP `ffffffffb189641f`），指令 `mov 0x8(%r10),%rax`，页错误地址 `fffff4ac76000008`（CR2）。
- **根因方向**：kswapd0 在内存回收（`prune_icache_sb` → `invalidate_mapping_pages` → `__remove_mapping`）过程中，经自定义回调 `nfs_readdir_clear_array [nfs]` 遍历 NFS 目录 readdir 缓存页中的指针数组并逐个 `kfree`。数组中某一项被破坏为非法指针 `0x000060dd00000000`（RDI），`kfree` 据此推导 vmemmap 地址 `fffff4ac76000000` 并访问 `+0x8` 触发页错误。**疑似 NFS readdir 缓存数组的内存损坏 / use-after-free / 悬垂指针写**，叠加长期运行（uptime 534 天）与 livepatch（TAINTED）环境。

## 2. 环境信息

| 项目 | 值 |
|---|---|
| 内核 | `4.18.0-193.el8.jd_020.x86_64`（JD 定制内核，`[LIVEPATCH] [TAINTED]`） |
| DUMPFILE | `/data/input/vmcore`（PARTIAL DUMP） |
| CPU / 内存 | 64 CPU / 191.4 GB |
| UPTIME | 534 天 20:53:53 |
| 负载 | 21.71 / 19.83 / 19.63 |
| TASKS | 12797 |
| 主机 | `JXQ-10-240-132-86.h.abchost.local`（Inspur SA5212M5） |
| PANIC 时间 | Mon Aug 10 04:44:52 UTC 2026 |

Taint 标志：`G OE K`（`O`=out-of-tree 模块、`E`=未签名模块、`K`=live kernel patched）。已加载 4 个京东 livepatch：`livepatch_jd_020_fix_blkcg_hardlockup`、`livepatch_jd_020_fix_blkcg`、`livepatch_jd_020_icmp_hotfix`、`livepatch_jd_020_oom_pause_fix`。

## 3. 崩溃调用链（`bt -f 499` / `log` Call Trace）

```
#0  machine_kexec
#1  __crash_kexec
#2  crash_kexec
#3  oops_end
#4  no_context
#5  do_page_fault
#6  page_fault
    [exception RIP: kfree+0x4f/0x160 = ffffffffb189641f]   <-- 崩溃点
#7  nfs_readdir_clear_array+0x4d/0x70 [nfs]  (ffffffffc095b3bd)
#8  __remove_mapping+0x14e/0x210  (ffffffffb182baae)
#9  remove_mapping
#10 invalidate_mapping_pages
#11 inode_lru_isolate
#12 __list_lru_walk_one
#13 list_lru_walk_one
#14 prune_icache_sb
#15 super_cache_scan
#16 do_shrink_slab
#17 shrink_slab
#18 shrink_node
#19 balance_pgdat
#20 kswapd
#21 kthread
#22 ret_from_fork
```

即：**kswapd0 内存回收 → shrink_slab → prune_icache_sb（回收 inode icache）→ invalidate_mapping_pages → __remove_mapping → nfs_readdir_clear_array → kfree → 页错误**。

## 4. 崩溃点反汇编与寄存器归因

### 4.1 `kfree`（base `ffffffffb18963d0`）关键指令

```
kfree+32:  mov    $0x80000000,%r10d
kfree+38:  add    %rbx,%r10          ; r10 = 0x80000000 + RDI(坏指针 000060dd00000000)
kfree+54:  sub    page_offset_base,%rdi
kfree+61:  add    %rdi,%r10
kfree+64:  shr    $0xc,%r10
kfree+68:  shl    $0x6,%r10
kfree+72:  add    vmemmap_base,%r10  ; r10 = fffff4ac76000000
kfree+79:  mov    0x8(%r10),%rax     ; <-- 访问 fffff4ac76000008，页错误
```

`kfree` 用传入指针 RDI 做 `virt_to_page` 逆运算（`(ptr + 0x80000000 - page_offset_base) >> 12 << 6 + vmemmap_base`）推导 `struct page`。坏指针 `RDI=0x000060dd00000000` 使推导出的 vmemmap 地址 `R10=fffff4ac76000000` 落在 vmemmap 有效区间之外，`+0x8` 即触发不可映射的页错误。

### 4.2 异常寄存器（kfree+0x4f）

| 寄存器 | 值 | 含义 |
|---|---|---|
| RDI | `000060dd00000000` | **传给 kfree 的损坏指针**（非合法内核堆/直接映射地址） |
| R10 | `fffff4ac76000000` | 由坏指针推导的 vmemmap 地址（与 CR2 同页） |
| RBP | `ffff9f4e70c0c000` | nfs_readdir_clear_array 中算出的页虚拟地址（数组基址） |
| R15 | `ffffffffc095b370` | nfs_readdir_clear_array [nfs] |
| R12 | `ffffffffc095b3bd` | nfs_readdir_clear_array+0x4d（call kfree 返回地址） |
| R13 | `ffff9f36e479fb30` | 页 struct 相关指针 |
| CR2 | `fffff4ac76000008` | 页错误地址 |

### 4.3 `nfs_readdir_clear_array`（base `ffffffffc095b370`）关键指令

```
+23  sub vmemmap_base(%rip),%rdi   ; page struct -> pfn
+33  sar $0x6,%rbp
+37  shl $0xc,%rbp
+41  add page_offset_base(%rip),%rbp  ; -> 页虚拟地址（数组基址）
+48  mov 0x0(%rbp),%eax            ; 读数组元素个数
+53  jle 退出
循环:
+63  lea (%rax,%rax,4),%rax        ; ×5（40 字节结构）
+67  mov 0x28(%rbp,%rax,8),%rdi    ; 加载数组项指针 -> kfree 参数
+72  call kfree
+77  cmp %ebx,0x0(%rbp)
```

崩溃发生在某次迭代：`0x28(%rbp,%rax,8)` 读出的数组项即 `RDI=000060dd00000000`，为损坏的指针条目。

### 4.4 `__remove_mapping` 中的自定义回调（关键发现）

`__remove_mapping`（base `ffffffffb182b960`）在 `+0x14e`（`ffffffffb182baae`，与栈帧返回地址一致）处：

```
__remove_mapping+280: mov 0x50(%rax),%r15   ; %rax = 0x78(%rbp) = mapping->a_ops
__remove_mapping+326: mov %rbx,%rdi
__remove_mapping+329: call __x86_indirect_thunk_r15  ; 间接调用 a_ops 偏移 0x50 的回调
```

即 `__remove_mapping` 通过 `address_space_operations` 偏移 `0x50` 处的回调间接调用 `nfs_readdir_clear_array`。**这是 JD 定制内核的扩展**：标准内核 `__remove_mapping` 不会调用 NFS 模块函数。该回调用于在页回收时清理 NFS 目录 readdir 缓存数组。

## 5. 根因分析（事实 vs 假设）

### 事实（高置信度）
1. 崩溃是 `kfree` 收到非法指针 `0x000060dd00000000` 后 vmemmap 越界访问所致（反汇编 + 寄存器完全吻合）。
2. 该指针来自 `nfs_readdir_clear_array` 从页内数组偏移 `0x28` 处加载的条目，说明 **NFS readdir 缓存页中的指针数组已被破坏**。
3. 触发路径是 kswapd0 的 icache 回收（`prune_icache_sb`），说明被回收的是 **NFS 目录 inode 的 page cache 页**。
4. `mount` 输出中**未发现任何 NFS 挂载**（全部为 xfs/ext4/tmpfs 等），但 `nfsv3 nfs_acl nfs lockd grace sunrpc fscache` 模块已加载——被回收的 NFS inode 对应的挂载点可能已卸载/关闭，inode 仍残留在 icache 中。
5. 内核为 `[LIVEPATCH] [TAINTED]`，`__remove_mapping` 含自定义 NFS 回调，属定制/热补丁代码路径。

### 假设（中置信度，需进一步验证）
- **A. NFS readdir 数组 use-after-free / 悬垂指针**：NFS 目录 inode 的 readdir 缓存页在挂载卸载或 inode 释放时未正确清理，数组项指向已释放内存，后续被 kswapd 回收时读到垃圾指针。与"无 NFS 挂载但 inode 仍在 icache"现象吻合。
- **B. 内存损坏 / 越界写**：某处（驱动、livepatch、或 NFS 自身）越界写覆盖了该数组项，写入 `0x000060dd00000000` 这类非典型值。
- **C. 长期运行累积问题**：uptime 534 天、负载偏高（21.71），长时间运行下内存碎片/损坏累积，最终在回收路径暴露。

### 排除项
- **非 xfs 死锁**：`compact-bt` 的 `direct_xfs_buf_lock_waiters: 0`，且崩溃栈为页错误而非锁等待，排除 xfs_hang 流程。
- **非普通 OOM**：崩溃为内核态页错误，非 `out_of_memory` 杀进程。

## 6. 建议的下一步验证命令（crash）

1. 检查被回收页的 `struct page` 与所属 inode/mapping：
   - `struct page ffff9f36e479fb30`（或 `ffff9f36e479fb28`）
   - `page -p ffff9f4e70c0c000`（查看页标志、mapping、index）
2. 检查数组页内容，确认损坏范围：
   - `rd ffff9f4e70c0c000 0x100`（dump 数组页，观察 `0x28` 偏移处及相邻项）
3. 定位 NFS inode 与挂载状态：
   - `struct inode <mapping->host>`（从 page 的 mapping 反查）
   - `mount -f nfs`（确认是否有 NFS 挂载残留）
4. 检查 livepatch 是否涉及该路径：
   - `mod -s livepatch_jd_020_*` / `dis __remove_mapping`（确认回调注入来源）
5. 检查是否有其他内存损坏迹象：
   - `kmem -i`（内存统计）、`kmem -f`（空闲页）、`bt -a`（其他 CPU 是否有异常）

## 7. 处置建议

- 优先验证假设 A/B：确认 NFS readdir 数组的损坏来源（UAF 还是越界写），检查 NFS 挂载卸载路径与 `nfs_readdir_clear_array` 的调用时机是否缺少同步/引用计数保护。
- 关注 JD 定制内核中 `__remove_mapping` 新增的 NFS 回调（`a_ops` 偏移 0x50）是否为近期 livepatch/补丁引入，排查其与 NFS 模块版本匹配性。
- 长期运行 + 高负载 + livepatch 环境，建议评估内核/模块升级与 livepatch 清理，并关注是否复现（若复现则基本可定位为确定性 bug 而非偶发硬件问题）。
