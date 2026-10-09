# Hermes Dialogue Judge Workflow

Use the current data-analyst Hermes session and its dialogue_judge tools. Use a fresh session for each user-selected case. Do not launch another Agent. The plugin is deployed to the data-analyst profile. Completely restart the Hermes application/backend after deployment, then start a new session. A new conversation alone may retain cached plugin discovery.

1. Call **prepare_dialogue** for the requested case. Keep the returned run ID. Follow the tool's parameter schema, returned paths and next_action; do not invent call arguments or storage paths.
2. Call **get_judge_context** until all pages are obtained, following its missing-page information. Read all pages in order. Use the supplied Judge Skill and output contract to judge the historical dialogue as evidence. If Hermes replaces a tool result with a preview, retrieve its full persisted content before judging.
3. Call **validate_judgment** with the original judgment. Its schema defines how to supply the judgment. Preserve errors and failed results; do not silently rewrite or retry them to manufacture a pass.
4. Call **inspect_judge_run** and report actual step states, omissions, failures and output paths. Mechanical success remains pending human semantic review. Unavailable tools must be reported, not replaced with terminal commands.

The tool definitions own parameters, prerequisites, return meanings and errors. The tools own storage and step records. This workflow owns sequence; the Judge Skill owns semantic analysis.

No profile, Skill, memory or source-data edits are authorized by this workflow. Fresh sessions do not isolate persistent memory. Handler execution cannot prove model understanding or final-message delivery.

Ask Hermes to follow this file for the case you select. No case ID or run ID is fixed by the workflow.

## Execution Binding

Hermes executes each native tool call through the registered [handler](plugins/dialogue-judge/__init__.py). That handler routes the supplied arguments to [JudgeRuns](plugins/dialogue-judge/runtime.py):

| Tool | Python implementation |
|---|---|
| prepare_dialogue | JudgeRuns.prepare → dialogue_tools.prepare |
| get_judge_context | JudgeRuns.context |
| validate_judgment | JudgeRuns.validate → dialogue_tools.validate_files |
| inspect_judge_run | JudgeRuns.inspect |

These functions execute inside the Hermes process when it dispatches a tool call. This text file does not execute Python by itself. The plugin must first be installed, enabled and exposed to the current session; tools and arguments are defined by its schemas.
