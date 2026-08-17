# Crash Analysis

Crash Analysis 是一个面向 Linux 内核崩溃现场的 AI 辅助分析工具。它将可复现的
`vmcore` 证据采集与 Agent 推理分开：`cra` 负责执行和记录 `crash` 查询，
`crash-analysis` Skill 负责基于这些证据生成根因分析报告。

仓库分为三个部分：

| 目录 | 职责 |
|---|---|
| `cli/` | Python 包和 `cra` 命令：vmcore 采集、分类、诊断动作与 Skill 安装。 |
| `skill/crash-analysis/` | JoyCode/Agent Skill，以及分析流程、参考资料、Agent、脚本和报告模板。 |
| `runtime/` | Docker 镜像、容器入口与 Jenkins Freestyle 执行脚本。 |

## 工作流程

```text
vmcore + 匹配的 debuginfo + 内核源码 + 可选 dmesg
                         │
                         ▼
              Docker 运行环境 / cra
                         │
          collect → classify → evidence.json
                         │
                         ▼
      JoyCode 使用 $crash-analysis Skill 分析
                         │
                         ▼
analysis.md + actions/ + queries.log（可追溯证据）
```

`cra` 先生成确定性证据和候选路由；LLM 只在此基础上执行必要的补充查询并撰写
`analysis.md`。不要把原始 vmcore 直接交给 LLM。

## Examples

| 案例 | 分析报告 | 描述 |
|---|---|---|
| XFS hang / filesystem deadlock | [analysis1.md](docs/examples/analysis1.md) | 通过 vmcore、`compact-bt`、`task`、`query` 和结构化 buffer 证据，确认 `/dev/vdb2` 上 AGF 与 inode-cluster buffer 之间的 ABBA 死锁。流程见 [xfs-hang.md](skill/crash-analysis/references/xfs-hang.md)。 |
| NFS readdir 非法释放 Oops | [analysis2.md](docs/examples/analysis2.md) | 在 `kswapd0` 回收路径中，`nfs_readdir_clear_array()` 向 `kfree()` 传入非法值并触发 kernel paging request。流程见 [flows.md](skill/crash-analysis/references/flows.md)。 |

## 开始前准备

一次完整 vmcore 分析需要以下输入：

| 输入 | 用途 |
|---|---|
| `vmcore` | kdump 生成的内核内存转储。 |
| `debuginfo.rpm` | 必须与 vmcore 内核版本精确匹配，并包含 `vmlinux`。 |
| 内核源码目录 | 对应内核版本的源码，用于将符号和栈帧映射到源码。 |
| `dmesg`（可选） | vmcore-dmesg 或现场保留的 dmesg 文本。 |

运行环境要求：本地 CLI 需要 Python 3 和可用的 `crash` 工具；

## 使用方式

### 本地 CLI 开发与调试

在仓库根目录安装 CLI：

```bash
python3 -m pip install -e ./cli
cra --help
```

使用固定命令集采集现场，再生成分类和路由证据：

```bash
cra vmcore collect \
  --vmcore /data/input/vmcore \
  --debuginfo /data/input/debuginfo.rpm \
  --kernel /data/input/kernel \
  --output-dir /data/output

cra vmcore classify --collection /data/output/collection.json
```

如果有独立 dmesg 文件，在 `collect` 命令中追加 `--dmesg /data/input/dmesg`。
分类完成后可针对指定 PID 或内核对象执行受记录的诊断操作：

```bash
cra vmcore diagnose task \
  --evidence /data/output/evidence.json --pid 284533

cra vmcore diagnose query \
  --evidence /data/output/evidence.json \
  --command 'struct xfs_buf ff257b675031dc00'
```

完整的 `collect`、`classify`、`compact-bt`、`task`、`query`、`structure` 和
`symbol` 用法见 [CLI 文档](docs/cli/index.md)。

### Docker 容器运行

从仓库根目录构建包含 `crash`、JoyCode CLI、`cra` 和 Skill 的分析镜像：

```bash
docker build -f runtime/Dockerfile -t crash-analysis:latest .
```

容器约定将输入挂载到 `/data/input/`：`vmcore`、`debuginfo.rpm`、`kernel`，
可选 `dmesg`；将输出目录挂载到 `/data/output`。输入应以只读方式挂载，
分析产物仅写入输出目录。实际的容器启动、参数校验和 JoyCode 调用由
`runtime/jenkins-workflow.sh` 统一实现；手动调试时也应遵循这些路径约定。

### Jenkins 自动化分析

在 Jenkins Freestyle Job 中，将 [runtime/jenkins-workflow.sh](runtime/jenkins-workflow.sh)
的内容粘贴到 **Build Steps → Execute shell**。将 Job 配置为参数化构建，并提供：

| 参数 | 说明 |
|---|---|
| `VMCORE_URL` 或 `VMCORE_PATH` | 二选一，vmcore 的下载地址或 Jenkins 节点本地路径。 |
| `DEBUG_RPM_URL` 或 `DEBUG_RPM_PATH` | 二选一，匹配的 debuginfo RPM。 |
| `KERNEL_SRC_URL` 或 `KERNEL_SRC_PATH` | 二选一；URL 必须是 `.tar`、`.tar.gz` 或 `.tar.xz` 源码归档。 |
| `DMESG_URL` 或 `DMESG_PATH` | 可选，外部 dmesg 文件。未提供时使用 crash log。 |
| `RUN_JOYCODE` | 默认 `true`；设为 `false` 时仅生成证据，不运行 LLM 分析。 |
| `JOYCODE_MODEL`、`MODEL_CONTEXT_WINDOW`、`MODEL_AUTO_COMPACT_TOKEN_LIMIT` | 可选模型与上下文配置。 |
| `BUILD_IMAGE` | 默认 `false`；设为 `true` 时从 `REPO_ROOT` 构建 `crash-analysis:latest`。 |

当 `RUN_JOYCODE=true` 时，通过 Jenkins Credentials Binding 注入 `JOYCODE_API_KEY`；
不要将密钥写入脚本、参数默认值或仓库。脚本会准备输入、以只读方式挂载它们、
运行容器，并归档 `$WORKSPACE/output`。若 JoyCode 未生成有效报告、`analysis.md`
仍是占位文件或执行失败，构建会失败，而不会将“仅完成采集”误报为分析成功。

## 输出与证据

`--output-dir`（Jenkins 中为 `$WORKSPACE/output`）包含以下主要产物：

| 产物 | 含义 |
|---|---|
| `collection.json` | 本次采集的输入、定位到的 `vmlinux` 和原始输出索引。 |
| `classification.json` | 基础崩溃分类。 |
| `routing.json` | 建议分析路由与候选 PID。 |
| `task-index.json` | 从固定 crash 输出解析出的任务索引。 |
| `evidence.json` | 供 Skill 使用的综合证据入口。 |
| `focus/` | 按路由筛选后的重点文本证据。 |
| `actions/` | 每次 `diagnose` 操作的原始输出及 `result.json`。 |
| `queries.log` | 后续查询的审计记录。 |
| `crash-raw.txt` | 固定 `crash` 命令生成的完整原始输出，仅在重点证据不足时查看。 |
| `analysis.md` | 最终中文分析报告。 |

`classify` 创建的 `analysis.md` 只是占位文件，不能视为分析完成。最终报告应由
`$crash-analysis` Skill 根据 `evidence.json`、`focus/` 和诊断 action 的证据生成。

## Skill：`crash-analysis`

该 Skill 面向 x86 Linux 的 Oops、kernel paging request、Panic、`BUG/BUG_ON`、
`WARNING`、vmcore 与 XFS hang 等场景。它支持：

- 提取内核版本、崩溃任务、寄存器、taint、硬件信息和调用栈；
- 通过 `gdb`、`addr2line`、`crash` 与内核源码映射崩溃位置；
- 按 paging fault、WARNING、BUG、Panic、XFS hang 等流程开展证据驱动的分析；
- 将上游 patch 或社区讨论作为候选线索，并区分已验证事实和待验证假设；
- 使用 `cra vmcore diagnose` 记录补充查询，以便报告结论可以复查。

主 Skill 位于 `skill/crash-analysis/`；CLI 内置副本位于
`cli/src/crashanalysis_cli/skills/crash-analysis/`。目前两份均保留，修改其中任何一份时
都应明确是否同步另一份，避免容器中的实际 Skill 与仓库文档不一致。

## 开发与维护

- 修改 `cli/`、`skill/`、`runtime/Dockerfile` 或容器入口后，重新构建镜像：

  ```bash
  docker build -f runtime/Dockerfile -t crash-analysis:latest .
  ```

- Jenkins 默认 `BUILD_IMAGE=false`，只检查并使用已有 `crash-analysis:latest` 镜像；
  因此镜像更新后需先在开发节点构建，或明确将该参数设为 `true`。
- Jenkins Job 中粘贴的是脚本正文；修改 `runtime/jenkins-workflow.sh` 后，需要将更新后的
  内容重新粘贴到 Job 的 Execute shell。
- 分析过程中的 `actions/`、`queries.log` 和 `analysis.md` 应一并归档，它们共同构成
  可复查的结论证据链。

## `cra` CLI

`cra` 是分析流程中的确定性执行层：它负责准备 vmcore
现场、运行固定或显式指定的 `crash` 命令，并将每一步的输入与输出保存为可复查产物，同时避免 LLM 在分析过程中陷入循环取证与任务超时。

![`cra --help` 命令输出](docs/assets/cli.png)

| 命令组 | 用途 |
|---|---|
| `cra vmcore collect` | 解压 debuginfo、定位 `vmlinux`、执行固定的首轮 `crash` 采集。 |
| `cra vmcore classify` | 基于采集结果生成分类、候选路由、任务索引、重点证据和报告占位文件。 |
| `cra vmcore diagnose` | 对既有 `evidence.json` 执行 `compact-bt`、`task`、`query`、`structure` 或 `symbol` 查询，并将结果写入 `actions/` 与 `queries.log`。 |
| `cra skills` | 查看、安装或卸载 CLI 内置的分析 Skill。 |

典型调用顺序是：

```text
cra vmcore collect
→ cra vmcore classify
→ $crash-analysis Skill 调用 cra vmcore diagnose
→ $crash-analysis Skill 撰写 analysis.md
```

通过 `cra --help`、`cra vmcore --help` 和 `cra vmcore diagnose --help` 查看可用参数；
完整说明与命令示例见 [CLI 文档](docs/cli/index.md)。
