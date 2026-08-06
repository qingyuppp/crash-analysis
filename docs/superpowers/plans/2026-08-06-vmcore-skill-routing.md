# Vmcore Skill Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `analyze-vmcore` produce compact, deterministic routing evidence and let the packaged JoyCode skill perform iterative `crash` analysis in the same Jenkins container.

**Architecture:** `analyze-vmcore` will validate artifacts, run baseline `crash` commands, and write `crash-raw.txt`, one `evidence.json`, and only the matching route filter files. A new `crash-query` helper will append arbitrary `crash` queries to `queries.log`; the skill reads the evidence, selects a flow, and uses that helper for XFS object-level verification.

**Tech Stack:** Bash, Python 3 standard library, `crash`, Docker, Jenkins Pipeline, JoyCode CLI.

---

### Task 1: Define the compact evidence contract

**Files:**
- Modify: `vmcore-workflow/test/analyze-vmcore-contract.sh`
- Modify: `vmcore-workflow/test/test-task-routing.py`
- Modify: `vmcore-workflow/lib/classify_evidence.py`

- [ ] **Step 1: Make the contract test require the compact files and forbid removed automation**

Require `evidence.json`, `focus/xfs.txt`, `focus/fault.txt`, `focus/hang.txt`, and `queries.log` support. Forbid JoyCode invocation, automatic `bt -f`, and XFS buffer/lock-graph output in `analyze-vmcore`.

- [ ] **Step 2: Run the contract test and confirm it fails**

Run: `bash vmcore-workflow/test/analyze-vmcore-contract.sh`

Expected: failure because the current script still contains XFS second-pass and JoyCode logic.

- [ ] **Step 3: Implement evidence serialization and route filter generation**

Make the classifier emit task and route data consumable by `analyze-vmcore`; make `analyze-vmcore` combine manifest, classification, routing, and task index into `evidence.json` and create only matched route text files.

- [ ] **Step 4: Re-run the focused tests**

Run: `bash vmcore-workflow/test/analyze-vmcore-contract.sh && python3 vmcore-workflow/test/test-task-routing.py`

Expected: both pass.

### Task 2: Add iterative crash queries

**Files:**
- Create: `vmcore-workflow/crash-query`
- Modify: `vmcore-workflow/joycode-kernel-oops-openeuler.Dockerfile`
- Create: `vmcore-workflow/test/crash-query-contract.sh`

- [ ] **Step 1: Write a contract test for query logging**

Require the helper to accept vmcore and vmlinux paths plus a crash command, invoke `crash`, and append a query header, command, and result to `queries.log` without restricting PID or address values.

- [ ] **Step 2: Run the test and confirm it fails**

Run: `bash vmcore-workflow/test/crash-query-contract.sh`

Expected: failure because `crash-query` does not exist.

- [ ] **Step 3: Implement the helper and package it**

Implement a Bash wrapper that validates readable artifact paths and a non-empty command, runs `crash -i`, and appends the result even when the query fails. Copy and mark it executable in the image.

- [ ] **Step 4: Re-run the query and Docker contract tests**

Run: `bash vmcore-workflow/test/crash-query-contract.sh && bash vmcore-workflow/test/dockerfile-contract.sh`

Expected: both pass.

### Task 3: Preserve Jenkins orchestration while removing manual focus selection

**Files:**
- Modify: `vmcore-workflow/Jenkinsfile`
- Modify: `vmcore-workflow/jenkins-freestyle.sh`
- Modify: `vmcore-workflow/test/jenkinsfile-contract.sh`
- Modify: `vmcore-workflow/test/freestyle-contract.sh`

- [ ] **Step 1: Update Jenkins contract tests**

Require `RUN_JOYCODE` and credential injection to remain, require automatic evidence routing, and forbid the `FOCUS` parameter and `--focus` command line use.

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `bash vmcore-workflow/test/jenkinsfile-contract.sh && bash vmcore-workflow/test/freestyle-contract.sh`

Expected: failure because both launchers still expose `FOCUS`.

- [ ] **Step 3: Update both launchers**

Remove manual focus selection, retain the evidence-only `RUN_JOYCODE=false` mode and API key validation only when JoyCode runs, and invoke the packaged analysis sequence.

- [ ] **Step 4: Re-run the launcher tests**

Run: `bash vmcore-workflow/test/jenkinsfile-contract.sh && bash vmcore-workflow/test/freestyle-contract.sh`

Expected: both pass.

### Task 4: Route the packaged skill through compact evidence

**Files:**
- Modify: `linux-kernel-oops/SKILL.md`
- Modify: `linux-kernel-oops/references/flows.md`
- Modify: `linux-kernel-oops/references/vmcore-evidence.md`
- Modify: `linux-kernel-oops/references/xfs-hang.md`
- Modify: `linux-kernel-oops/agents/vmcore-evidence.agent.md`
- Modify: `linux-kernel-oops/agents/xfs-hang.agent.md`

- [ ] **Step 1: Update the evidence contract and routing instructions**

Document the three compact output categories, automatic route selection, and the rule that the skill reads `evidence.json` before a matching focus file.

- [ ] **Step 2: Update the XFS iterative query flow**

Document that the skill invokes `crash-query` for arbitrary PIDs and objects, records results in `queries.log`, and only confirms a deadlock from explicit holder and reciprocal wait evidence.

- [ ] **Step 3: Verify internal references and stale terminology**

Run: `rg -n 'future XFS|joycode-prompt|xfs-buffer-summary|xfs-lock-graph|--focus' linux-kernel-oops vmcore-workflow`

Expected: no stale references except intentional historical tests removed during implementation.

### Task 5: Remove superseded automatic XFS inference and verify the full suite

**Files:**
- Delete: `vmcore-workflow/lib/xfs_buffer_evidence.py`
- Delete: `vmcore-workflow/test/test-xfs-buffer-evidence.py`
- Delete: `vmcore-workflow/test/test-xfs-lock-graph.py`
- Delete: `vmcore-workflow/test/fixtures/xfs-confirmed-crash.txt`
- Delete: `vmcore-workflow/test/fixtures/xfs-suspected-crash.txt`

- [ ] **Step 1: Remove files only after callers and tests no longer reference them**

Run: `rg -n 'xfs_buffer_evidence|xfs-buffer-summary|xfs-lock-graph|xfs-confirmed-crash|xfs-suspected-crash' vmcore-workflow`

Expected: no production caller remains before deletion.

- [ ] **Step 2: Run all workflow tests**

Run: `for test in vmcore-workflow/test/*.sh; do bash "$test"; done && python3 vmcore-workflow/test/test-task-routing.py`

Expected: every command exits zero.

- [ ] **Step 3: Inspect the final diff**

Run: `git diff --check && git diff -- vmcore-workflow linux-kernel-oops`

Expected: no whitespace errors; `.gitignore` and `docs/analysis-flow.drawio` remain untouched.
