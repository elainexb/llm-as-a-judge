# Deployment Status and Operator Guidance

Deployed to the data-analyst profile on 2026-10-09 after the user requested deployment. See `tests/deployment_result.json` and the current stage in `HERMES_JUDGE_PLAN.md` for actual evidence and backup location. Host loading and dispatch passed; live model judgment remains untested.

For a future reinstall after approval, install this directory as a user plugin in the target data-analyst profile, then explicitly enable it. Add only these plugin-specific settings, preserving the rest of the profile configuration:

```yaml
plugins:
  enabled:
    - dialogue-judge
  entries:
    dialogue-judge:
      settings:
        project_dir: "/Users/xuebai/Documents/ChatGPT/llm as a judge"
```

This is a merge fragment, not a replacement configuration. The reviewed plugin consists of `plugin.yaml`, `__init__.py` and `runtime.py`. This document is operator guidance, not a model instruction. Project data, `dialogue_tools.py`, Judge Skill and workflow stay in the project. The plugin loads the operator-configured helper and supplies the pinned Skill text through `get_judge_context`; it does not register a separate Skill slash command.

Completely restart the Hermes application/backend, open the target profile in a fresh session and verify all four tools are visible, then trial one case before running the suite. Record actual profile/model identity, tool calls, artifacts and semantic review. Local native-loader tests do not prove production visibility or model adherence.

Runs contain `run.json`, `events.jsonl`, `prepared/`, `context.txt`, and, after submission, `judgment.txt` and `validation.json`. The JSONL ledger is the authoritative execution record. Artifact writes are atomic and refuse overwrite; ledger appends are flushed to disk under a per-run lock. Hash chains detect accidental edits, not a malicious rewrite of the entire ledger. Broken artifacts or incomplete calls prevent a completed result.

Invalid schema arguments and unknown run IDs return structured errors but cannot be attributed to an existing run ledger. Calls rejected because a run is busy make no state changes. Hermes's own tool trace is the supplementary evidence for those rejected calls. Optional session/task IDs come from Hermes; missing identity is explicitly unknown.

This plugin is a trusted local extension, not a filesystem sandbox. Arbitrary Agent terminal access remains outside these tool guards. It makes no model calls and registers no hooks or overrides. Human semantic review remains necessary. This version uses standard-library `fcntl` and targets the user's macOS/local backend; Windows portability is unverified.
