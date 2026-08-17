---
title: CLI
description: CrashAnalysis 命令行工具，用于确定性采集、分类和诊断 Linux vmcore 证据。
---

# CrashAnalysis CLI

`cra` 是 CrashAnalysis 的命令行工具。它在 LLM 推理之前执行确定性的
vmcore 证据采集、路由分类和后续 `crash` 查询；Docker/Jenkins 负责提供运行环境、
挂载输入并归档输出。

主要工作流：

- 从 vmcore、匹配的 debuginfo 和内核源码采集固定证据；
- 根据调用栈和任务状态生成分类与候选路由；
- 对指定 PID、符号、结构或自定义 `crash` 命令保存可复查的诊断产物；
- 管理 CLI 内置的分析 skill。

## 安装

推荐在包含 `crash`、`rpm2cpio` 和 `cpio` 的分析容器中安装：

```bash
cd /path/to/crash-analysis/cli
python3 -m pip install --no-deps -e .
```

确认安装：

```bash
cra --help
cra vmcore --help
```

也可以从仓库根目录进行本地开发安装：

```bash
python3 -m pip install -e ./cli
```

## 开始前准备

一次完整采集需要以下输入：

| 输入 | 说明 |
|---|---|
| `vmcore` | kdump 生成的 ELF 内核内存转储 |
| `debuginfo.rpm` | 与 vmcore 内核版本精确匹配的 debuginfo RPM，需包含 `vmlinux` |
| `kernel` | 对应版本的内核源码目录 |
| `dmesg` | 可选的外部 dmesg 文本 |

不要将 raw vmcore 直接交给 LLM。先使用 `cra vmcore collect` 生成文本证据，
再让分析 skill 读取 `evidence.json` 和对应的 `focus/*.txt`。

## 快速开始

### 1. 采集 vmcore 证据

```bash
cra vmcore collect \
  --vmcore /data/input/vmcore \
  --debuginfo /data/input/debuginfo.rpm \
  --kernel /data/input/kernel \
  --dmesg /data/input/dmesg \
  --output-dir /data/output
```

`--dmesg` 是可选参数。采集阶段会解压 debuginfo、定位 `vmlinux`、运行固定的
`crash` 命令集，并写入 `collection.json` 和 `crash-raw.txt`。

### 2. 分类并生成路由证据

```bash
cra vmcore classify --collection /data/output/collection.json
```

输出会显示任务分组与建议路由，并生成：

```text
evidence.json
classification.json
routing.json
task-index.json
focus/
queries.log
analysis.md
```

此阶段的 `analysis.md` 是占位文件；完整报告由分析 skill 在后续阶段写入。

### 3. 使用分析 skill

将 `evidence.json` 和匹配的 `focus/*.txt` 提供给 `$crash-analysis` skill。
skill 会选择对应的 Oops、Panic、XFS hang 或通用 vmcore 分析流程，并将最终报告
写入 `/data/output/analysis.md`。

## 常用任务

### 查看可用 skill

```bash
cra skills list
cra skills show crash-analysis
```

### 安装或卸载 skill

安装到 JoyCode：

```bash
cra skills install crash-analysis --target joycode
```

默认安装位置是 `/root/.joycode/skills`；可用 `JOYCODE_SKILLS_DIR` 覆盖。

安装到 Codex：

```bash
cra skills install crash-analysis --target codex
```

安装到自定义目录时必须显式指定：

```bash
cra skills install crash-analysis \
  --target custom \
  --skills-dir /path/to/skills
```

仅卸载由 `cra` 记录过的 skill：

```bash
cra skills uninstall crash-analysis --target joycode
```

### 收集多个任务的紧凑回溯

针对路由中的候选 PID 执行：

```bash
cra vmcore diagnose compact-bt \
  --evidence /data/output/evidence.json \
  --pids 284533,224856
```

该命令会创建 `actions/<序号>-compact-bt/`，其中包含原始 `crash` 输出与
结构化 `result.json`。

### 收集单个任务的完整回溯

```bash
cra vmcore diagnose task \
  --evidence /data/output/evidence.json \
  --pid 284533
```

适用于确认等待点、调用路径和 `bt -f` 参数。

### 执行受记录的 crash 查询

```bash
cra vmcore diagnose query \
  --evidence /data/output/evidence.json \
  --command 'struct xfs_buf ff257b675031dc00'
```

每次查询都会写入独立的 action 目录，并追加到 `queries.log`，便于复查 LLM 的
证据链。

### 查看结构或符号

```bash
cra vmcore diagnose structure \
  --evidence /data/output/evidence.json \
  --type xfs_buf \
  --address ff257b675031dc00

cra vmcore diagnose symbol \
  --evidence /data/output/evidence.json \
  --name __remove_mapping
```

## 输出目录约定

```text
output/
├── collection.json       # 采集输入、vmlinux 与 crash 原始输出的位置
├── classification.json   # 主分类
├── routing.json          # 候选路由和 PID
├── task-index.json       # 从 crash 输出解析出的任务索引
├── evidence.json         # 供 skill 使用的综合证据索引
├── focus/                # 根据路由筛选的文本证据
├── actions/              # 每次 diagnose 动作的原始输出和 result.json
├── queries.log           # 后续查询记录
├── crash-raw.txt         # 原始 crash 输出，仅在必要时升级查看
└── analysis.md           # 最终分析报告
```

## Jenkins 与 Docker

生产使用方式见仓库根目录 [README](../../README.md) 以及：

```text
runtime/Dockerfile
runtime/jenkins-workflow.sh
runtime/run-vmcore-analysis
```

Jenkins 负责准备和只读挂载输入、启动已有镜像并归档 `output/**`；CLI 与 skill
负责证据和分析结果。
