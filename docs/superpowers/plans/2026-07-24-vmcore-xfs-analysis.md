# Vmcore XFS Analysis Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Jenkins-built JoyCode image that runs extract → classify → analyze → report against mounted kernel incident artefacts.

**Architecture:** `analyze-vmcore` orchestrates `crash`, a deterministic Python classifier, and JoyCode. The classifier consumes only crash text and writes JSON/Markdown evidence. Jenkins builds the repository image, mounts inputs read-only, and archives `output/**`.

**Tech Stack:** Bash, Python 3 standard library, crash, Docker, Jenkins Declarative Pipeline, JoyCode CLI.

---

### Task 1: All-UN task discovery and routing classifier

**Files:**
- Create: `runtime/lib/classify_evidence.py`
- Create: `runtime/tests/fixtures/un-routing-crash.txt`
- Create: `runtime/tests/fixtures/xfs-confirmed-crash.txt`
- Create: `runtime/tests/fixtures/xfs-suspected-crash.txt`
- Create: `runtime/tests/fixtures/oops-crash.txt`
- Create: `runtime/tests/test-classify-evidence.py`

- [ ] **Step 1: Write failing tests**

Use `unittest` to run the future CLI with `--crash` and `--out-dir`. First
verify that a mixed UN fixture creates `task-index.json` for every task and a
small `routing.json` that groups XFS, block-I/O, and generic-lock signatures
without selecting a root cause. Verify the confirmed XFS fixture creates
`classification.json` with `primary_class: xfs_hang` and
`xfs-lock-graph.json` with `verdict: confirmed_agf_inode_abba` and exactly
these edges:

```json
[
  {"waiter_pid": 73713, "waits_for": "AGF:d66200", "held_by": 318156},
  {"waiter_pid": 318156, "waits_for": "INODE_CLUSTER:009f80", "held_by": 73713}
]
```

Verify the suspected fixture emits `suspected_agf_inode_inversion`; verify an Oops fixture emits `oops_panic` and no XFS graph.

- [ ] **Step 2: Verify red**

Run: `python3 runtime/tests/test-classify-evidence.py`

Expected: failure because `classify_evidence.py` does not exist.

- [ ] **Step 3: Implement minimal CLI**

Implement `--crash PATH --out-dir PATH --source PATH`. Oops/Panic signatures
take priority. Parse normalized UN records into a task index with raw spans and
stack fingerprints, group by subsystem/blocking site, and write
`routing.json`. Parse XFS records for `PID`, `COMMAND`, `WAITS_FOR`,
`BUFFER_TYPE`, and `HELD_BY`; write sorted `classification.json`,
`xfs-lock-graph.json`, and `xfs-analysis.md`. Only emit confirmed when two
reciprocal typed edges exist.

- [ ] **Step 4: Verify green**

Run: `python3 runtime/tests/test-classify-evidence.py`

Expected: all tests report `OK`.

- [ ] **Step 5: Commit**

```bash
git add runtime/lib runtime/test
git commit -m "feat: classify xfs vmcore evidence"
```

### Task 2: Two-pass crash extraction

**Files:**
- Create: `runtime/lib/xfs-crash-commands.py`
- Modify: `runtime/analyze-vmcore`
- Create: `runtime/tests/test-analyze-vmcore.sh`

- [ ] **Step 1: Write failing shell contract**

Require `analyze-vmcore --help` to say `--dmesg PATH (optional)`. Require generated XFS commands to contain `foreach UN bt`, `mount`, `dev -d`, `struct xfs_buf.b_ops`, and `struct xfs_buf.b_log_item`. Require the JoyCode prompt to reference only the evidence directory, never a raw vmcore path.

- [ ] **Step 2: Verify red**

Run: `bash runtime/tests/test-analyze-vmcore.sh`

Expected: failure because dmesg is mandatory and two-pass extraction is absent.

- [ ] **Step 3: Implement**

Run baseline `crash` commands, classify the first-pass output, and generate a second `crash` command script only for an XFS candidate. Derive second-pass buffer queries only from first-pass addresses. Rerun classification over combined evidence. Persist `crash.cmds`, `crash-raw.txt`, `evidence/extraction.md`, and the classifier artefacts.

- [ ] **Step 4: Verify green**

Run: `bash runtime/tests/test-analyze-vmcore.sh`

Expected: `analyze-vmcore contracts passed`.

- [ ] **Step 5: Commit**

```bash
git add runtime/analyze-vmcore runtime/lib runtime/test
git commit -m "feat: collect xfs crash evidence in two passes"
```

### Task 3: Skill route and XFS constraints

**Files:**
- Create: `skill/crash-analysis/references/xfs-hang.md`
- Create: `skill/crash-analysis/agents/xfs-hang.agent.md`
- Modify: `skill/crash-analysis/SKILL.md`
- Modify: `skill/crash-analysis/references/flows.md`
- Create: `test/xfs-skill-contract.sh`

- [ ] **Step 1: Write failing contract**

Require XFS capability and route text, `confirmed_agf_inode_abba`, all confidence states, and the sentence that log-full or buffer waits alone do not prove a cycle.

- [ ] **Step 2: Verify red**

Run: `bash test/xfs-skill-contract.sh`

Expected: failure because the specialist reference does not exist.

- [ ] **Step 3: Implement**

Write the skill extract → classify → analyze → report flow. The XFS agent is evidence-only and cannot claim a cycle without reciprocal typed edges. Link it from `SKILL.md` and route `xfs_hang` in `flows.md`.

- [ ] **Step 4: Verify green**

Run: `bash test/xfs-skill-contract.sh && bash test/vmcore-entry-contract.sh`

Expected: both exit 0.

- [ ] **Step 5: Commit**

```bash
git add skill/crash-analysis test
git commit -m "feat: add xfs hang analysis flow"
```

### Task 4: Private image build

**Files:**
- Modify: `runtime/Dockerfile`
- Modify: `runtime/joycode-entrypoint.sh`
- Create: `runtime/tests/dockerfile-contract.sh`

- [ ] **Step 1: Write failing Docker contract**

Require `COPY skill/crash-analysis /opt/skills/skill/crash-analysis`, a copy to `/root/.joycode/skills/skill/crash-analysis`, and `COPY runtime/analyze-vmcore`. Forbid public `git clone`.

- [ ] **Step 2: Verify red**

Run: `bash runtime/tests/dockerfile-contract.sh`

Expected: failure because the Dockerfile clones the public repository.

- [ ] **Step 3: Implement**

Remove cloning. Copy the private checkout skill and workflow from repository-root build context; install `cpio` and `rpm2cpio`; preserve read-only input paths.

- [ ] **Step 4: Verify**

Run: `bash runtime/tests/dockerfile-contract.sh`

Run locally: `bash runtime/tests/dockerfile-contract.sh`

Run on the remote development node only:
`docker build -f runtime/Dockerfile -t joycode-kernel-oops:local .`

Expected: local contract exits 0; remote image build succeeds.

- [ ] **Step 5: Commit**

```bash
git add runtime/Dockerfile runtime/joycode-entrypoint.sh runtime/tests/dockerfile-contract.sh
git commit -m "build: package private kernel analysis skill"
```

### Task 5: Jenkins execution

**Files:**
- Modify: `runtime/Jenkinsfile`
- Modify: `runtime/jenkins-workflow.sh`
- Modify: `runtime/tests/jenkinsfile-contract.sh`

- [ ] **Step 1: Extend the failing Jenkins contract**

Require a `Build Analysis Image` stage with `docker build -f runtime/Dockerfile`; require conditional optional-dmesg staging/mount; require read-only vmcore/debuginfo/source mounts, a writable output mount, `--focus auto|xfs|generic`, and `archiveArtifacts artifacts: 'output/**'`.

- [ ] **Step 2: Verify red**

Run: `bash runtime/tests/jenkinsfile-contract.sh`

Expected: failure because it assumes a prebuilt image and dmesg is mandatory.

- [ ] **Step 3: Implement**

Build from the private checkout. Make dmesg URL/path optional and omit its mount when absent. Preserve inputs read-only and pass `--focus` and the JoyCode opt-out to `analyze-vmcore`. Make the freestyle helper use the same mount contract.

- [ ] **Step 4: Verify green**

Run: `bash runtime/tests/jenkinsfile-contract.sh`

Run: `bash -n runtime/jenkins-workflow.sh runtime/analyze-vmcore`

Expected: both exit 0.

- [ ] **Step 5: Commit**

```bash
git add runtime/Jenkinsfile runtime/jenkins-workflow.sh runtime/tests/jenkinsfile-contract.sh
git commit -m "ci: run vmcore analysis pipeline in jenkins"
```

### Task 6: Fallback report and full verification

**Files:**
- Modify: `runtime/analyze-vmcore`
- Modify: `runtime/tests/test-analyze-vmcore.sh`
- Modify: `README.md`

- [ ] **Step 1: Write failing final assertion**

Require a JoyCode-disabled run to write `analysis.md` containing the verdict and both buffer IDs. Require `joycode-prompt.txt` to contain the evidence directory but no absolute vmcore input path.

- [ ] **Step 2: Verify red**

Run: `bash runtime/tests/test-analyze-vmcore.sh`

Expected: failure until fallback output is wired.

- [ ] **Step 3: Implement**

On JoyCode disabled, timeout, or failure, write `analysis.md` from deterministic evidence. Document image build, Jenkins parameters, optional dmesg, artefacts, verdict meanings, and the rule never to commit incident data.

- [ ] **Step 4: Run all checks**

```bash
python3 runtime/tests/test-classify-evidence.py
bash runtime/tests/test-analyze-vmcore.sh
bash runtime/tests/dockerfile-contract.sh
bash runtime/tests/jenkinsfile-contract.sh
bash test/vmcore-entry-contract.sh
bash test/xfs-skill-contract.sh
git diff --check origin/main...HEAD
```

Expected: every command exits 0.

- [ ] **Step 5: Commit and push**

```bash
git add README.md runtime/analyze-vmcore runtime/tests/test-analyze-vmcore.sh
git commit -m "docs: describe automated xfs vmcore analysis"
git push -u origin xfs-analysis-pipeline
```
