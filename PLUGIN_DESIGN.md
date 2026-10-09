# Dialogue Judge Plugin: Approved Design and Implementation Contract

## Scope and Approval

Build a native Hermes plugin in this project, reusing the existing preparation and validation functions. Hermes remains the judge; the plugin never calls a model or starts another Agent. No profile deployment, configuration edits, or live model trials are authorized by this design document.

The user approved completing the four-tool interface: `prepare_dialogue`, `get_judge_context`, `validate_judgment`, and `inspect_judge_run`. Project-local implementation and tests are complete; deployment and live model trials remain deferred. Current verification is recorded in [the project plan](HERMES_JUDGE_PLAN.md).

## Contracts and Ownership

| Tool | Inputs | Outputs and enforced prerequisites |
|---|---|---|
| `prepare_dialogue` | Selected case ID | New run ID, prepared artifact paths, counts, pinned input/rule versions; preparation failure remains in the run record |
| `get_judge_context` | Run ID and page index | A bounded page of the pinned Judge Skill, output contract, and complete input; only successful preparation permits context retrieval |
| `validate_judgment` | Run ID and original judgment JSON text | Saved original submission and mechanical validation report; all context pages must have been returned before submission/validation |
| `inspect_judge_run` | Run ID | Step status, missing prerequisites, failures, incomplete calls, artifact integrity, execution events, and pending human review |

The native adapter owns JSON schemas, argument validation, error envelopes, and registration through public `ctx.register_tool`. The existing helper owns data adaptation and mechanical checks. A small run recorder owns ordering, durable events and artifact identity. The written workflow owns calling sequence and reporting. The Judge Skill owns semantic decisions only.

No Hermes core patch, new model SDK, server, or new Agent loop is required. A native plugin is sufficient; MCP would add a process/protocol without a demonstrated need here. The helper stays project-local and is loaded from a pinned operator-configured project path after deployment. Model-supplied filesystem destinations are unnecessary; run IDs map to project-owned output directories.

## Reliability and Evidence

- Validate arguments in handlers as well as JSON schemas; schema exposure alone is not enforcement.
- Return JSON strings through Hermes registry; ordinary Python dictionary returns are not the installed registry's supported payload contract.
- Persist started and terminal events for preparation, context retrieval, submission and validation, with sequence, UTC timestamp, plugin-generated call identity, measured duration, status, applicable reasons and artifact hashes. Successful inspections are terminal observation records. Session/task identity comes from runtime kwargs when available, not model-supplied parameters. Missing runtime identity is explicitly unknown. Hermes does not pass a host tool-call ID on the ordinary handler path.
- Use append-only durable events, atomic artifact writes, and a lock per run. Avoid silent overwrite and automatic retry; a new judgment attempt gets a new run.
- Preserve original submitted text even if JSON parsing or validation fails. Do not repair it into a pass.
- Detect out-of-order calls, missing context pages, incomplete started calls, changed artifacts, and changed preparation/rule identity. These prevent a completed result status.
- `validated_pending_review` requires a mechanically valid submission and the observed workflow prerequisites. It does not establish correct judgment or user acceptance.
- Page-return records establish what the plugin handler returned, not what the model read or understood. Hermes may truncate, spill or compress tool output later. Bounded pages reduce this risk; the model must acknowledge and retrieve all pages through the normal workflow. A final assistant report cannot be proven merely from inspection-tool invocation.
- JSON/ID/quote/order checks do not prove task grouping, adjustment, relapse, sentiment or evidential relevance. Those remain semantic review responsibilities.
- Existing Hermes defaults and memory are retained. A fresh session per case is not persistent-memory isolation. This package is not a sandbox against arbitrary terminal writes by the Agent.

## Verification Before Deployment

Exercise real C09/C10/C07 and all 12 source preparations. Test argument errors, missing case, skipped context pages, premature validation, duplicate submission, malformed JSON, incorrect evidence, artifact changes, concurrent calls, interrupted/incomplete events, and preserved failed runs. Mark constructed submissions and injected faults separately from real judgments.

Test registration and dispatch against installed Hermes PluginContext/registry in an isolated temporary HERMES_HOME, with no model calls or edits to the actual profile. Stub-context tests alone are insufficient integration evidence. Record manifest/schema discovery, native registration, actual dispatched results, command exit codes and limitations.

Deployment remains a later reviewed change: install/enable the plugin in data-analyst, configure the project path, and verify tool visibility/loading before actual semantic trials. Availability in a local registry test does not prove the live profile exposes the tools to its model.

## Research Evidence

Inspected installed `hermes_cli/plugins.py::PluginContext.register_tool`, `tools/registry.py::dispatch` and result normalization, `model_tools.py` context propagation, and `tools/budget_config.py`. The default tool-result threshold is 100,000 characters, but per-tool/config/model-window limits can be lower; do not assume every large result remains in context.

Primary references: [Native plugin guide](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/) and [Plugin overview](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins/). Local source defines the tested interface; current web docs are not evidence that every feature exists in the installed version.
