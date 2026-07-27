# Kernel vmcore workflow handoff

## Current scope

- Added the vmcore entry route and evidence-acquisition contract.
- Raw vmcore must be processed by `crash` before downstream reasoning.
- Legacy Oops Fetcher and Collector behavior remains unchanged for text-only input.

## Current artifacts

- `references/vmcore-evidence.md` defines required inputs, baseline crash commands,
  evidence outputs, failures, and post-evidence routing.
- `agents/vmcore-evidence.agent.md` defines the evidence-only role.
- `test/vmcore-entry-contract.sh` guards the entry and raw-vmcore safety rules.

## Deferred work

- Implement XFS-specific primitives for buffer, transaction, and wait-for graph extraction.
- Add the XFS hang Collector and Analyst flow.
- Integrate the evidence-acquisition interface with Jenkins and its analysis image.
