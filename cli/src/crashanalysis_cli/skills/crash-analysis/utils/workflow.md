# crash-analysis 工作流基线

本文记录当前 skill 的默认 Oops 流程，以及 vmcore/XFS 扩展的入口边界。
它是后续从上至下修改 skill 的导航文档。

## 默认 Oops 流程

```text
Oops 文本 / dmesg / bug report
  ↓
入口分类：Oops / Panic / BUG / WARNING
  ↓
Fetcher（可选：准备缺失的 vmlinux、源码或发行版工件）
  ↓
Collector：只收集事实
  ↓
Analyst：What / How / Where
  ↓
Patcher（条件）与 Fact checker（必做）
  ↓
report.md / factcheck.md / report.html
```

`references/primitives.md` 位于 Collector 阶段。它从已有 Oops 文本中
提取 fundamentals、backtrace、lockdep、寄存器和源码映射数据；它不是
整个 skill 的入口，也不负责读取 raw vmcore。

## Vmcore/XFS 入口

现场 vmcore 分析的输入是：

```text
vmcore + 匹配 debuginfo/vmlinux + 精确内核源码 + 可选 dmesg
```

这类输入先进入 [Vmcore Evidence Acquisition](../references/vmcore-evidence.md)：

```text
vmcore bundle
  ↓
crash 确定性取证
  ↓
evidence-manifest.md + crash-focused.txt
  ↓
二次分类
  ├─ Oops / Panic / BUG / WARNING → 复用原有 Oops flow
  ├─ XFS lock/log evidence        → 未来 XFS hang flow
  └─ 证据不足                     → generic vmcore triage
```

raw vmcore 绝不能直接交给 LLM。后续分析默认读取 `crash-focused.txt`；
只有当该证据不足时，才按明确需要查看 `crash-raw.txt` 的指定部分。

## XFS 后续范围

当前入口阶段只定义证据获取和路由，不自动判定 XFS 根因。后续 XFS flow
需要提取并关联：

```text
D 状态任务栈
→ xfs_buf_lock / xlog_grant_head_wait
→ xfs_buf 地址及 AGI / AGF / inode cluster 类型
→ transaction item 链
→ 持有者和等待者
→ wait-for 环与上游修复核对
```

## 修改顺序

1. 完成 vmcore evidence acquisition 入口和交接契约；
2. 定义 XFS hang 分类；
3. 增加 XFS-specific primitives 和 Collector flow；
4. 复用现有 Analyst、报告与事实核查；
5. 最后接入 Jenkins 的输入挂载、证据输出与归档。
