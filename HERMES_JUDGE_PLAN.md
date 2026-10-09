# Hermes 反馈处理 Judge 测试规划

## Current Stage: C09 Live Run Mechanically Validated; Semantic Review Pending

Pending simplification proposal (not implemented): user requested less output and questioned fixed pagination against minimum-POC architecture. Current 3,500-character pages were conservative rather than derived from the actual session budget. Read-only installed-source checks show the generic per-result cap is 100,000 characters at the observed 272k-token context, versus C09's 18,826-character bundle and an all-12 maximum of approximately 32,502 characters (C07). Therefore no current-suite case requires paging. Oversized native results may be persisted and replaced with a 1,500-character preview; this does not prove model consumption. Proposed scope: retain the four native tools and execution ledger, deliver full context once, enforce an explicit checked size limit and fail visibly on unsupported sizes; replace output contract v0.1 with a compact contract that retains tasks, distinct correction issues, chronological events with adjustment/recurrence, sentiment changes/final observation and indexed verbatim evidence, but merges repeated explanatory fields. No fixed event cap or input truncation. No new framework or dependencies. Skill remains semantic-only. This changes interfaces/output contract and awaits explicit architecture confirmation before dependent code or profile updates. Verify C09 and the largest C07, missing-context/invalid-evidence/oversize failures and exact source coverage; then separately measure a live model trial. No latency improvement is claimed before measurement.

C09 live run and timing investigation: the user's restarted session successfully completed run `8feae1a15e234ed88903f7651b4a97a7` using `openai-codex/gpt-6.1-sol`. Logged wall time was 236.7 seconds, 11 API calls and 10 tool calls. Summed logged API latency was 233.9 seconds; summed host tool durations were 0.41 seconds (plugin ledger duration is narrower and totals 120 ms). Initial tool details/preparation took approximately 10.4 seconds, six context pages with model round trips 50.7 seconds, the judgment-producing API request 151.3 seconds, and audit/final reporting approximately 24.4 seconds. The API latency includes service/network/reasoning/generation and cannot be subdivided from current logs. The output contains 18,943 characters, 3 tasks, 2 issues, 11 correction events and 9 sentiment observations. Validation returned `validated_pending_review` with zero mechanical errors; semantic accuracy remains unreviewed. Evidence: [c09_timing_report.json](tests/c09_timing_report.json), the retained run judgment, validation and ledger. No runtime settings or contract were changed. The model-switch log records medium reasoning effort while the user's UI showed low; actual request effort remains unverified. Potential optimization targets are serial model round trips for context and verbose judgment output, subject to separate design review and measurement; Python tool runtime is not the bottleneck.

Deployment follow-up: the user's real C09 attempt reported all four tools unavailable and created no run. Profile logs show the attempt at 22:13 used session `20261009_192739_45740c` (created before deployment), while plugin discovery was last logged at 10:42. Installed source caches discovery per backend process (`PluginManager._discovered`) and snapshots tools per Agent. A fresh-process TUI-path check on the actual profile passed (exit 0): `_load_enabled_toolsets('tui')` included `dialogue_judge`, and all four function definitions were exposed. Evidence: [tui_exposure_check.json](tests/tui_exposure_check.json). No model calls or configuration changes were made during diagnosis. This supports stale backend/session catalogs as the cause; the affected live backend has not been refreshed by this check. Completely restart Hermes and create a fresh target-profile session; opening a new conversation alone may retain the backend's old discovery cache. The prior "new session" deployment guidance was insufficient. The user's live turn logged `openai-codex/gpt-6.1-sol`; this observed session identity differs from the on-disk default and was not changed by deployment.

The user requested deployment on 2026-10-09. Installed the reviewed three-file plugin in `/Users/xuebai/.hermes/profiles/data-analyst/plugins/dialogue-judge`. Backed up the target configuration before adding only `plugins.enabled` and `plugins.entries.dialogue-judge.settings.project_dir`; parsed configuration comparison confirmed all other values were preserved. The Judge Skill remains project-local and is supplied through context pages, not registered as a separate Skill command.

Actual verification: all 27 project tests passed (exit 0). The real target profile's native loader registered all four tools; the actual CLI tool selection included `dialogue_judge`; emitted function definitions included the four expected names. Native host dispatch prepared C08, returned every context page and inspected the run (exit 0). This deployment smoke test contains no model judgment: submission and validation remain `not_executed`. It is not a Hermes semantic evaluation. Model calls: 0. Existing sessions must be restarted or replaced before testing live visibility and adherence.

Evidence: [deployment_result.json](tests/deployment_result.json). Backup configuration: `/Users/xuebai/.hermes/profiles/data-analyst/backups/dialogue-judge-20261009T141035Z/config.yaml`. Two preliminary invocations failed at the YAML import before profile writes (exit 1); the installed Hermes now uses its `utils.fast_safe_load` parser, which was used successfully without installing dependencies. The deployment script used existing managed dependency activation. Live model behavior and human semantic acceptance remain unverified.

Usage: open a fresh data-analyst session and ask it to follow the absolute project path to `HERMES_WORKFLOW.md` for one selected case. C01–C12 remain supported; one fresh session per case. Runs are stored under this project's `runs/judge-plugin`.

## Historical Stage: Native Four-Tool Plugin Implemented and Locally Verified

The user approved completing the four-tool design. The English candidate package now exists under [plugins/dialogue-judge](plugins/dialogue-judge/__init__.py), with a thin native adapter, a durable run recorder, and manifest. It reuses `dialogue_tools.py` for preparation/validation. Hermes itself remains the judge; the plugin does not call a model, start another Agent, patch Hermes core, register hooks, or override tools. Nothing has been deployed to the real Hermes profile. All implementation files and review artifacts stay in this project.

Latest interface audit: the user questioned function-calling format and excessive invocation details in the workflow. Every parameter now has a model-facing description and applicable JSON Schema constraints; tool descriptions explain prerequisites, returned fields, storage ownership and failure handling. Tool results supply `next_action`, missing-page information and owned artifact paths. The workflow now contains sequence only, without fixed case/run IDs or shell/function-call templates. Hermes's `get_tool_definitions` emits the actual `type=function`/`function` envelopes, and its `handle_function_call` routes arguments through the host dispatch path to the handlers. The upgraded isolated native probe verifies both interfaces, not just direct `registry.dispatch`. The emitted schemas are saved in `tests/native_probe_result.json` alongside execution evidence. All 27 local tests and the upgraded native probe passed, exit 0. This is host-side protocol/dispatch verification; no provider request, real model-generated arguments, or production profile run has occurred.

Workflow clarification: removing parameter templates had also obscured explicit tool entry points. The workflow now names the four tool calls at each step and includes an execution-binding table linking native handlers to JudgeRuns/helper functions. Parameters remain in the schemas; case IDs/run IDs remain supplied at runtime. This is a documentation clarification, with no runtime or contract change.

| Tool | Observed step and guarantee |
|---|---|
| `prepare_dialogue` | Creates a unique run and full source input; failed preparations remain inspectable |
| `get_judge_context` | Returns bounded pages of pinned Judge Skill, schema and dialogue; records which pages the handler returned |
| `validate_judgment` | Requires successful preparation and all context pages; preserves original submission and records mechanical validation |
| `inspect_judge_run` | Reports actual step states, missing pages, failures, incomplete operations, identity availability and artifact integrity |

Execution statuses distinguish `not_executed`, `started`/`incomplete`, `partial`, `succeeded`, and `failed`. Run statuses include incomplete/blocked, preparation failure, integrity failure, specific mechanical validation failures, and `validated_pending_review`. No status substitutes for human semantic acceptance. Successful handler returns are not evidence of model understanding or final-message delivery.

Run artifacts are under the operator-configured project's `runs/judge-plugin`: append-only, hash-chained `events.jsonl`; pinned `run.json`, source input and context; original `judgment.txt`; and `validation.json`. A per-run lock rejects overlapping operations; atomic create refuses artifact overwrite. Session ownership is checked when a runtime session ID exists. Changed artifacts/rules/code and incomplete prior operations prevent a completed result. A duplicate judgment is rejected; invalid submissions are kept, never automatically repaired. Unknown-run/invalid-argument/busy rejections are structured tool errors, supplemented by Hermes's host trace rather than invented run records. Hash chains detect consistency changes, not an adversarial rewrite with all permissions.

### Actual Verification

- `python3 -m unittest discover -s tests -v`: 27 tests passed, exit 0. Coverage includes all 12 actual full-source preparations/context reconstruction, C09's saved independent-review output, missing pages, premature submission, malformed JSON, unsupported quotes, version/artifact/ledger changes, cross-session requests, interrupted operations, failed report writes, duplicate/concurrent submissions, and preservation of failures. Constructed faults and control outputs are explicitly test fixtures, not new user observations.
- The installed Hermes Python ran [native_plugin_probe.py](tests/native_plugin_probe.py), exit 0, using a fresh temporary `HERMES_HOME` and copied fixture project. The actual manifest parser, plugin discovery/load/enable configuration, native registry schemas, handlers, dispatch and unload succeeded. Four tools were exposed in that isolated scope. C09 used six context pages; preparation, context, submission and validation all recorded success. Evidence is saved in [native_probe_result.json](tests/native_probe_result.json). There were zero model calls and no changes to the actual Hermes profile. An initial probe invocation used the manifest parser's wrong argument signature and exited 1; correcting the test invocation produced the passing native probe. This was a test-harness error, not hidden plugin runtime success.
- The Judge Skill still has its existing format validation; domain schema v0.1 is unchanged. Current implementation changes execution interfaces and evidence, not correction/sentiment semantics.

The updated [workflow](HERMES_WORKFLOW.md) uses native tools exclusively, with no terminal fallback. [Deployment guidance](plugins/dialogue-judge/DEPLOYMENT.md) contains the eventual minimal settings merge; it has not been applied. Project path is operator configuration, not a model-supplied filesystem destination. The Judge Skill remains project-local and is included in pinned context; this plugin does not create an independent Skill slash command.

Limitations: real profile startup/tool visibility, provider availability, model adherence, semantic performance and actual cost remain unverified. Tool output can still be spilled/compressed by Hermes downstream; bounded pages and recorded handler returns do not prove the model saw all bytes. Existing memory/default tools remain unchanged, so this is not a sandbox or isolation guarantee. The local recorder uses `fcntl`, targeting this user's macOS backend. Next allowed step is user review; deployment and actual trials require the later reviewed action.

## Historical Native-Plugin Design Stage

The user requested native tool calling with stable output and per-step execution analysis. The current implementation still uses the terminal helper and is not presented as meeting that new requirement. Read-only inspection confirmed public `PluginContext.register_tool` support at the installed Hermes revision. Ordinary handlers receive optional session/task kwargs and must return a JSON string, not a plain dictionary. Tool outputs may spill into previews, so full-context delivery needs bounded, recorded pages.

The proposed [plugin design](PLUGIN_DESIGN.md) uses four tools: preparation, context retrieval, submission/validation, and run inspection. A numbered grilling question is pending for this extension from the previously proposed two-tool interface. The user has authorized project-local implementation of native tools, but the additional context/inspection contract and enforced dependency design are not silently treated as confirmed. No dependent plugin implementation, Hermes-directory changes, or model calls have occurred in this stage. Native registration/dispatch tests remain planned, not performed. Earlier helper tests remain evidence for the helper only.

## Historical Text-Workflow Implementation Stage

The user approved the written-workflow/helper/Judge-Skill split and authorized one implementation. The package is English and project-local. No Hermes files or folders have been changed, no profile settings changed, and no model called. Deployment remains deferred until user review.

Current entry points:

| Artifact | Responsibility |
|---|---|
| [HERMES_WORKFLOW.md](HERMES_WORKFLOW.md) | Written execution instructions for the current Hermes session: prepare one case, load Judge Skill and full input, save judgment, validate, report actual state |
| [dialogue_tools.py](dialogue_tools.py) | Standard-library helper with only `prepare` and `validate`; no subprocess, Agent loop, model API, or Hermes-directory dependency |
| [Judge Skill](drafts/dialogue-behavior-monitor/SKILL.md) | Semantic judgment only; output delivery belongs to the workflow |
| [Output contract](drafts/dialogue-behavior-monitor/references/output-contract.md) | Existing schema v0.1; unchanged |
| [Prepared case manifest](native_inputs/preparation.json) | 12 complete English cases, 126 original messages, source/input/Skill hashes; no dataset labels in judgment input |

The helper is called by Hermes through its existing terminal tool; Hermes judges in its current session using file/Skill tools. Each case uses a fresh session as previously confirmed. The workflow does not launch nested Hermes instances. Preparation preserves full source text/order and verifies retained source turn/row metadata. Validation writes a separate report and does not alter judgment JSON; reports and prepared cases cannot be silently overwritten. Invalid JSON produces a saved failure report. Exit codes: 0 for preparation/mechanical validation success, 1 for a recorded validation failure, 2 for invocation/operation errors. Mechanical validation remains pending human semantic review.

Actual verification: `python3 -m unittest discover -s tests -v` passed 14 tests, exit 0. Tests cover all 12 real-source preparations and text preservation, actual C09 draft-review references, valid multiple corrections from one User message, correction-free and uncertain controls, invented quotes, invalid roles/chronology/links/IDs, malformed JSON, duplicate sources and broken boundaries, report preservation, real CLI prepare/validate calls, and rejection of a `run` subcommand. Constructed controls are marked as mechanical tests. The C09 fixture remains an earlier independent review, not an accepted reference or a Hermes result. Preparation of all 12 cases into `native_inputs` exited 0. Skill format validation is recorded separately; none of these checks proves Hermes runtime loading or semantic accuracy.

The former outer runner and its tests are preserved in `archive/outer-runner/` for history and excluded from current commands/tests. Older prepared query files and drafts remain historical. Current scripts stay in this project; eventual deployment needs only the reviewed Judge Skill in the target profile plus the user's workflow invocation. No profile/global instruction change is proposed. Review this package before applying anything to Hermes or making live model calls.

## Historical Hermes-Native Workflow Research

The user clarified that Hermes should execute a written workflow itself, rather than be launched by a custom outer runner. The existing `harness.py` remains a project-local candidate and is not the selected deployment route. All Hermes-directory changes remain deferred until review. This clarification supersedes the earlier interpretation of implementation approval below.

Research on 2026-10-09 inspected the installed Hermes Skills documentation, `agent/skill_commands.py::_build_skill_message`, file-reading tools, and profile terminal settings, plus the [official Skills guide](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/). Hermes supports natural-language and slash-command Skill activation, references, and bundled helper scripts; its activation message supplies the absolute Skill directory and supporting resource paths. Hermes already owns the model/tool execution loop. These are inspected/documented capabilities, not a live trial of this monitoring Skill.

Proposed minimal route: one short Skill owns the workflow (read complete input, apply the four semantic questions, save output, check it, report limitations); a reference owns the output contract. A short per-case user instruction supplies source/output paths. Use the existing prepared `monitoring_inputs/C01`–`C12.json`, not the old truncated inputs or label-bearing raw pool. Retain the settled separate-session-per-case requirement; running all cases in one conversation would change the test design. New sessions do not isolate persistent memory. Do not make Hermes invoke `harness.py run` and launch nested judge sessions.

Data parsing belongs to the Skill's input procedure, but parsing need not mean model-generated code. For these prepared JSON files, the initial text-only procedure can describe the schema and require complete chronological reading, stable message indices, and no dataset labels. Confirm all messages were read: file-tool output can be truncated. C07 contains 22,509 dialogue characters and C09 30 messages; neither a file's presence nor a successful read call proves full coverage. If raw JSONL filtering or repeated format conversion is later required, a narrow bundled `scripts/` helper can mechanically select/normalize data without interpreting feedback or invoking a model. That is distinct from an outer Agent loop. No helper is implemented or selected by this research.

Tradeoff: a text-only Skill is the smallest starting point using already prepared inputs; its self-check is model-driven and does not guarantee exact-quote/structure validation. A small preparation/validation helper may improve repeatable mechanics later while the same Hermes conversation remains responsible for judgment. The prior runner's passing tests do not validate this new execution route. Input preparation already succeeded on all 12 real sources, but actual Hermes loading, reading, writing, and semantic accuracy remain unverified. No new framework, profile configuration, global instructions, or default-tool changes are proposed. This section records findings and a recommendation for user review, not installation or a newly approved architecture.

## Historical Outer-Runner Implementation Stage

The user approved the minimal responsibility split and requested harness implementation, then explicitly required all files to stay in this project until review. Deployment to `/Users/xuebai/.hermes/profiles/data-analyst/` remains deferred. No Hermes files or folders have been created or changed and no model calls have been made in this implementation stage.

### Review Package

- [Archived harness.py](archive/outer-runner/harness.py): historical standard-library Python runner; superseded by the current text workflow and helper.
- [Skill](drafts/dialogue-behavior-monitor/SKILL.md) and [output contract](drafts/dialogue-behavior-monitor/references/output-contract.md): current English deployment candidates.
- [preparation.json](monitoring_inputs/preparation.json): 12 unique full English source conversations, 126 messages, input/query hashes and preparation provenance. Each `C01`–`C12` has a JSON conversation and TXT query for review. Previous truncated inputs remain historical.
- [tests](tests/test_harness.py): mechanical and subprocess tests. The C09 fixture is the earlier independent draft-review output, not an accepted reference or Hermes result. Constructed outputs/failures are explicitly test controls, not observed user behavior.

### Operation After Review and Deployment

The runner stays in this project. The only proposed Hermes addition is a copy of `drafts/dialogue-behavior-monitor` into the target profile's `skills` directory. Copying is deferred until user review; no configuration, existing rules, or existing Skills need editing. Preflight requires exactly one installed Skill with matching project hashes. A missing or changed copy stops before any Hermes process is launched.

From this project, preparation is `python3 harness.py prepare --output NEW_DIRECTORY`; existing prepared inputs are never silently replaced. An example first-case command after deployment is:

```bash
python3 harness.py run --cases C09 --timeout-seconds 300
```

The 300-second example is an explicit per-case budget, not an already approved model run. Multiple IDs run sequentially. Each attempt gets a unique directory under `runs/hermes-monitor`, retaining input, assembled query, stream events, stderr, parseable analysis, validation, and metadata. Timeout or interruption stops the child process group. Failures are retained without automatic retry or JSON repair. `validated_pending_review` means mechanical checks passed, never semantic acceptance. Exit codes: 0 for mechanical success, 1 for recorded attempt/validation failure, 2 for command or deployment preflight errors.

Saved analyses can be checked with `python3 harness.py validate --input INPUT.json --analysis ANALYSIS.json`. This makes no model calls. The runner records observed model/tool metadata for review; it retains profile defaults and does not enforce memory isolation or tool-write prevention. Hash checks verify installed files, not runtime semantic compliance.

### Implementation Evidence and Limits

Real preparation ran with exit 0 for all 12 distinct conversations; full text/order and removal of dataset labels are tested. `python3 -m unittest discover -s tests -v` passed 15 tests, exit 0, covering actual saved C09 references, multiple correction points in one User message, correction-free/uncertain controls, fake quotations, roles/order, bad links, duplicate IDs/sources, boundaries, JSON/transport failures, retained subprocess failure, and timeout. The real C09 review validates mechanically with exit 0. Test subprocesses are fake local executables; they do not establish Hermes integration or judgment accuracy. Deployment preflight on the actual profile reports zero installed copies, as expected. Skill format validation remains required separately.

The design keeps execution simple and observable: standard library, existing Hermes loop, explicit contract/budget, retained traces, separate semantic review. This follows the simplicity and transparent-interface guidance in [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) and uses the documented [Hermes CLI](https://hermes-agent.nousresearch.com/docs/user-guide/cli/); actual local transport fields were checked against installed `hermes_cli/stream_json.py` rather than assumed from current upstream features.

Next: user review of this package, followed by authorized Skill deployment and real Hermes trial. Runtime loading, provider/model availability, live tool behavior, and semantic performance remain unverified. Ambiguous issue grouping stays uncertain; no new grouping policy was silently adopted.

## Historical Draft Review Stage

The user authorized drafting a Skill and harness for review, then required all draft artifacts to be written in English. This stage delivers project-local drafts without installing a Skill, implementing/running the harness, modifying the Hermes profile, calling a model, or replacing existing test inputs.

Current review artifacts: [Skill](drafts/dialogue-behavior-monitor/SKILL.md), [output contract](drafts/dialogue-behavior-monitor/references/output-contract.md), and [harness execution design](drafts/HARNESS_DRAFT.md). These are the current proposals. Earlier single-response designs and references below are historical and do not evaluate the latest monitoring goal.

Latest revision: the user requested a simpler Skill and identification of work suitable for code. The Skill now keeps the four semantic questions and essential evidence boundaries. The harness draft maps input preparation, prompt assembly, CLI execution, storage, structural/evidence-reference validation, and deterministic chronology to proposed code responsibilities. Goal segmentation, correction grouping, adjustment/recurrence, and sentiment remain model judgments. The output contract is unchanged; its complexity and model context cost have not disappeared. This is a draft responsibility proposal, not approval to implement the runner or deploy the Skill. The earlier independent C09 review used the longer draft and does not validate the shortened Skill's behavior.

The drafts cover user tasks, multiple correction points within a task, repeated versus distinct issues, relapse versus unresolved behavior, actual Agent adjustment, sentiment changes, and final observed negative sentiment. Normal/correction-free interactions are reported truthfully; correction counts do not determine sentiment. Skill capability is language-independent; the current suite remains 12 complete English conversations with distinct source IDs.

Validation: `codex-skill-validate drafts/dialogue-behavior-monitor` ran in the dedicated validator environment before and after the English rewrite, exit 0, output `Skill is valid!`. All three draft artifacts contain no CJK prose, and relative document links resolve (exit 0). Independent forward review of real C09 (30 messages) completed using the English drafts, with output confined to a temporary directory. Direct checks (exit 0) verified 56 exact quotations, message roles, IDs, event ordering, and the final User index. Its 7-task/9-issue interpretation exposed grouping and requirement-continuity ambiguity, recorded in the harness draft. This is not an approved reference, Hermes run, or proof of semantic accuracy. The harness remains a design document, with no executable implementation.

Next: user review and requested revisions. Skill installation, complete input preparation, harness implementation, execution budget, and actual model calls remain separate implementation/execution steps. Do not reopen settled goals, the English/distinct-source 12-case scope, or the data-analyst profile choice.

## Skill 与 harness 的研究比较（建议，尚未选定实施）

用户追问多点纠正与同点复发能否用Skill或agent harness实现。技术上现有Hermes支持该工作流，但纠正点分离、跨轮关联与情绪判断准确性尚未进行模型实测，不能称已验证可行。

职责区别：模型完成语义判断；Skill提供可版本化的方法、判定边界与输出约定；Hermes已有运行循环负责加载Skill和模型调用；可选外层程序负责遍历输入、留存原始结果、运行状态、结构/引用/事件关系检查。程序能检验ID是否存在、证据是否对应原文、时间是否合理，不能仅凭这些检查证明同点合并或情绪语义正确。

候选比较：

| 候选 | 复用与新增 | 适用及缺口 |
|---|---|---|
| 固定提示词 + 现有profile CLI | 直接复用CLI与模型配置，维护一个输入规则文件 | 可快速验证分析方法；规则已复杂时Skill便于复用和版本管理；提示词本身不保证语义准确 |
| 一个分析Skill + 现有profile CLI | 新增自有业务判定规则；复用Skill预加载与运行循环 | 建议先验证12例；不需要新agent框架；Skill安装/加载和语义准确性均需真实运行验证 |
| Skill + 外层执行/校验程序 | 在上项上增加必要的文件/CLI适配、结果校验 | 自动处理新日志和稳定批处理时适用；增加运行与升级维护，不能自行证明语义正确 |
| 直接使用现有batch_runner.py | 复用批处理、轨迹与断点恢复 | 本机脚本默认OpenRouter模型路径，跳过上下文文件/记忆，未暴露目标profile与Skill预加载合同；不能直接声称等价运行data-analyst；目前不推荐未经验证采用 |

具体本机证据：58份profile Skill的名称与frontmatter未发现针对会话纠正/情绪监控的现有Skill。`hermes_cli/_parser.py`支持`-s`预加载及`--query-file`；`agent/skill_commands.py`的`build_preloaded_skills_prompt`与CLI构建调用支持加载规则。`hermes_cli/stream_json.py`提供文本、退出码、token、耗时等运行事件，不强制业务判断JSON结构，也不校验证据。`batch_runner.py`的模型/provider默认与上下文设置不等于目标profile。没有读取密钥、私有记忆或历史运行会话，没有修改profile或调用模型。

官方来源：https://hermes-agent.nousresearch.com/docs/user-guide/features/skills；https://github.com/NousResearch/hermes-agent/blob/main/batch_runner.py。建议以已安装v0.21.6为当前验证对象，不因上游文档出现新功能就假定本机可用。

建议分析步骤：先分任务并识别原始要求，再抽取纠正事件；用任务、被纠正对象、希望改变的行为与仍适用的要求关联纠正点。一个User消息可产生多个事件；措辞不同可属于同一点；同样措辞在不同任务中不自动合并。每个纠正点分配会话内issue_id，逐次连接User纠正、Agent调整和后续相同问题。新增要求、不同问题与同点未解决/已改后复发分别记录。关联有歧义时保留不确定性。情绪独立分析，不从纠正点或复发次数推算。

首轮验证覆盖：不同纠正点拆分、同点不同措辞合并、一句多点纠正、约束改变而非复发、已改后复发、正常中性纠正、未调整但用户没表达不满、没有纠正、没有结束反馈以及最后情绪与早期情绪不同。使用真实完整会话与人工参考，不只检查JSON或退出码。

成本/维护：Skill不会自动降低模型费用或提升正确率；先以一次完整会话分析调用/例验证是否足够，记录实际token、耗时和可获得费用，必要时再研究拆分或独立复核，不默认增加第二模型调用。新增Skill维护判定规则与测试样本；外层程序只维护必要CLI接口和校验，避免自建模型循环、重复存储和新数据库。技术研究建议已记录；框架选择、Skill制作、部署和新输入/输出合同尚待用户确认与适用批准。

## 最新已确认目标：用户使用过程监控

用户进一步说明目的：监控用户使用Agent主要做了什么、是否给出纠正、Agent是否依据纠正调整回答、最终用户是否表现负面情绪。正常纠正本身不是问题；没有纠正、没有不满就如实报告。本说明取代之前“全部case必须有纠正”的待选建议；当前保留无纠正的真实会话，不强行补写纠正或不满。英文、12例、来源不重复和data-analyst profile要求不变。

这里判断实际观察到的使用与调整，不从未出现的纠正推断用户不能纠正Agent，不从用户沉默推断满意，不将回复质量问题、复发或纠正次数直接等同于负面情绪。没有后续证据时明确说明观察边界。

### 可复查的执行变更提案（待批准）

现有输入只评某一次回复，8例截掉了后续消息，无法监控全过程。最小变更为使用同一12段完整英文来源会话，评审单位从单回复改为整段会话；继续复用现有Hermes CLI、逐例运行、目标profile、保存原始结果，不增加框架、Skill或新的模型。

每例输出以下事实及消息索引/原文证据：

1. **用户主要做了什么**：列出任务及必要的任务变化，不把所有请求合成单一目标。
2. **是否纠正及纠正什么**：`correction_observed`和逐次纠正事件；区分纠正、追加要求、普通追问、致谢。无纠正时列表为空。
3. **Agent是否调整**：每次纠正对应后续回复，标明已调整、部分调整、未调整或无法判断；给出具体行为差异。另记录同问题复发与新问题；没有纠正则该项不适用。仅判断文本中的调整，不声称代码已运行或外部事实已验证。
4. **用户情绪与最终负面情绪**：用positive/neutral/negative描述用户针对互动的实际表达，保留必要的阶段变化及最后可观察User消息。客观纠正不自动negative；明确的负面评价/不满可为negative，不要求必须愤怒。最后没有表达不满时报告“未观察到最终负面情绪”，不报告“确认满意”。最后Agent回复之后若无用户回复，单独说明缺乏最终回答的用户反馈。

“最终”使用最后可观察的User消息并报告其所处任务；转话题不等于原问题解决。记录此前明确负面情绪，避免以最后中性消息抹去阶段性不满。情绪证据含糊时给出不确定性，不强制猜测。保留没有纠正、正常纠正和负面情绪会话，作为正常与边界覆盖。

真实材料验证：C08的User4要求给孩子简化，Agent5明显缩短解释，未观察到该User消息不满；C11的“Write more”是扩写请求，不是纠正；C01的User2/4明显不满，但后续User10说“good”，不能称最终仍不满；C09多次纠正AI-art引导语而复发，但命令式措辞不能自动标负面情绪。

用户目标已清楚，旧的sentiment粒度/是否仅选纠正case问题不再需要回答。仅待批准上述整段输入与四项输出合同变更；批准前不覆盖现有case输入与judge规则，也不运行旧规则来冒充新目标结果。旧参考草稿只适用于历史单回复任务，不能作为本监控任务的标准答案。

## 历史目标澄清：四项行为分析

用户最新明确需要：1）用户让Agent做什么；2）用户纠正Agent的什么行为；3）纠正后是否反复出现问题；4）期间用户sentiment为positive、neutral或negative。此前的“明确纠错/含糊不满/约束调整/正向反馈/普通追问”是Agent人工归纳的选样类别，不是数据集原始标签，也不是Hermes的已运行判断。

当前输入与提示词仍针对一个指定回复，许多输入在该回复后截止；因此它们不能完整验证新目标的复发与情绪轨迹。需改为整段来源对话分析，并区分同问题复发、新问题、未观察到复发和缺乏后续证据。此前参考草稿也不等于新任务的标准答案。本节记录目标澄清；下文旧单回复评审设计是历史已批准设计，尚未实施新的输入/输出合同或运行Hermes。

当时待回答的两个问题已被上方最新用户目的澄清取代。英文原文和来源不重复要求继续适用。

## 已确认目标与范围

2026-10-09：用户确认 Hermes 当 judge，评审 WildFeedback 中历史 Agent 的反馈处理；第一轮精选 12 个真实 case，由用户确认参考判定。后续明确仅保留英文 case，移除非英文 case，并要求替换C10–C12的重复来源；当前每个case使用不同来源会话。语言范围包括整段来源会话和全部送 judge 的对话上下文；不通过翻译或删去消息将混合语言会话改成英文。逐例检查判定、证据与不确定性，不能用总分替代核查。

最小闭环：下载真实候选对话 → 精选反馈事件 → 人工确认参考判定 → Hermes 独立评审 → 对照参考并检查原文证据 → 用户验收。

本轮不让 Hermes 生成修复回答，不做模型横向排名，不把研究者标签或历史回答当标准答案。原始完整会话保留；送 judge 的上下文截止待评审回复，避免后续用户态度泄漏。

## 当前证据

- 来源目录 `/Users/xuebai/Downloads/WildFeedback_complete_dialogue_extractor` 仅含提取器、README、requirements 和测试，没有下载的对话。
- 提取器读取 `microsoft/WildFeedback / sat_dsat_annotation / train`，输出完整连续会话、原始行号、原文消息、反馈事件、反馈前后回答。按源顺序取前 N 个合格会话，不保证行为分布。
- 默认至少一次反馈。普通追问对照可以从完整会话里的非反馈 User 消息派生，必须标明是事件级派生样本，不能声称另有完整无反馈会话。
- 首条消息的反馈计数与输出事件计数存在静态不一致风险；下载后核查。尚未运行数据提取、原文核验或模型评审。
- 本机 `hermes --version`：exit 0，`v0.21.6+131.g38880bd (2026.9.24)`，upstream `38880bd2`。首次沙箱检查受安装锁写权限限制，获准后版本检查成功。
- 本机源码 `hermes_cli/main.py` 包含 `--query-file` 读取逻辑；官方 CLI 文档说明单次查询、文件输入和 Skill 预加载。文档与源码支持不等于模型调用已验证。
- 官方来源：https://hermes-agent.nousresearch.com/docs/user-guide/cli

## 已批准使用方向

用户已批准 CLI、每例新会话、固定评审提示词，逐例保存结果，保留目标 Hermes 的默认工具、记忆与规则，第一轮不封装 Skill。提示词文件路线直接复用现有入口；Skill 可在标准稳定后复用，但首轮会增加技能加载与版本管理变量；自定义评测框架目前没有已证明的必要性。

用户另明确指定 `/Users/xuebai/.hermes/profiles/data-analyst/` 为最终运行目标。使用 `hermes -p data-analyst chat --query-file ...`，不运行默认 profile，也不改写全局配置。该 profile 的公开配置为 `provider=nous`、`model.default=opencode`；不按默认 profile 的 `openai-codex/gpt-6.1-sol` 覆盖它。配置名不等于已验证的实际后端模型，需以运行记录核查。

组件职责：现有提取器下载与保存原文；case 文件保存一个事件截至待评审回复的上下文和评审规则；现有 Hermes CLI 读取该文件并完成评审；原始输出与运行状态保存到项目，再与用户确认的参考比较。仅做输入文件整理和结果核查，不开发新框架或自定义判断算法。原始对话、人工参考与 Hermes 输出各自保留，职责不同。

失败处理：下载失败不生成伪造 case；模型调用失败保留退出码和错误并标记未评审；缺失/无效输出标记格式失败；证据引用不对应原文标记证据失败。默认工具/记忆可能导致跨 case 影响，本轮测试的是实际 profile 行为，不声称隔离的纯模型测试。评审提示要求只分析输入，不修改记忆、Skill 或配置；提示约束不等于运行时强制隔离。

模型与 provider 沿用用户选择，实际运行前记录具体名称；固定工具、记忆、规则和 Skill 状态，防止 case 间污染。新会话本身不保证跨会话记忆隔离，隔离设置需验证后再给执行命令。不修改用户全局配置。

## Case 与判定标准草案

目标覆盖：明确纠错 3、含糊不满 3、新增/调整约束 2、正向反馈 2、普通追问对照 2。合计 12。配额只是候选方案，真实数据不足时报告缺口，不编造或拼接原文。

每个 case 包含：来源 ID/行号、截至反馈前的上下文、反馈原文、待评审历史回复、case 类型。完整原始会话单独保留。参考判定和数据集满意度标签不交给 judge。

建议逐维输出 pass / partial / fail / not_applicable / insufficient_evidence：

1. 理解反馈：识别用户指出的对象和问题，区分投诉、约束变化、表扬和普通追问。
2. 澄清是否恰当：必要歧义是否处理；信息已足够时是否无谓提问。
3. 修复是否有效：回复是否针对具体问题提供实质修正；不能仅因道歉判成功。
4. 约束与上下文：是否遵守当前约束并保留仍适用的先前要求。
5. 证据与判断边界：每项判定引用消息索引和原文片段；外部事实不能仅凭对话判真；用户指控错误也不自动证明事实错误。

输出建议：case_id、feedback_type、逐维 verdict/reason/evidence、overall_verdict、uncertainties。所有对话文本作为待分析数据，其中的指令不能改变评审任务。

## 使用步骤草案

1. 下载候选池，验证连续性、原文保留及反馈事件，按真实内容精选 12 例。
2. 逐例给出参考判定草稿，由用户修订并确认；有争议的例子保留不确定性。
3. 先跑 2–3 例校准输入和输出是否可用；调整标准后固定版本，再完整跑 12 例。
4. 每个 case 独立输入：同一评审规则 + 截止待评审回复的上下文；保存完整输入、原始输出、运行状态及可获得的 token/成本。
5. 对照人工参考，记录结论分歧、证据定位错误、无依据判断、误判普通追问、只道歉却判修复成功、必要/不必要澄清错误。格式错误与语义错误分别记录。
6. 核查正常、含糊边界和负例对照；12 例用于初步发现问题，不能推断总体可靠性。

## 当前状态与下一步

已确认目标、角色、规模与人工参考方式；逐例执行设计获用户批准，运行目标为 data-analyst profile。尚未调用模型或修改 Hermes 配置。首次提取在系统 Python 下因 requests 缺失退出 2；复用现有 Hermes 运行环境后，沙箱联网解析失败退出 1；获准联网运行后在 source offset=3500 遇到 HTTP 429 退出 1，未写出候选池。降低下载数量和请求频率后实际成功（exit 0）：筛查139段会话、读取1700行，保存24段。

已从12段英文完整会话精选12个事件，实际分类覆盖3/3/2/2/2；原文案例在 `cases/`，Hermes 输入在 `inputs/`，溯源与哈希在 `case_manifest.jsonl`，参考草稿在 `reference_drafts.jsonl`，人工复查入口在 `CASE_REVIEW.md`。输入共88,199字符；尚未测量实际token、耗时和费用。语言筛选曾替换原C03（上下文含阿拉伯语）和原C10（上下文含泰语），历史记录在 `language_filter_changes.json`。随后C10–C12按用户要求替换为三段此前未使用的英文会话，当前记录在 `source_dedup_changes.json`；C01–C09在本次来源去重中未改动。12个来源会话ID无重复，不代表12个独立用户。原始下载候选池保留溯源，不作为全部可运行case清单。

实际核查（exit 0）：24段会话都通过现有提取器完整性条件；12份输入与候选池原文相同、截止目标回复、排除研究者标签与参考答案。对实际会话副本进行故障注入：缺末尾配对、来源行号缺口、源文本截断标记、角色错误都被现有校验拒绝。结果在 `case_validation.json`；这些不是模型评审结果，也不替代单独从官方页面再次逐字核对。

下一步：用户确认或修订 `CASE_REVIEW.md` 中参考草稿，然后每例执行下列已检查入口（本命令尚未运行）：

```bash
hermes -p data-analyst chat --query-file '/Users/xuebai/Documents/ChatGPT/llm as a judge/inputs/C01.txt' --oneshot --format stream-json
```

依次将 C01 替换为 C02–C12，逐例保存流式原始输出、stderr、退出码和可获得的模型/用量信息。输出结构合法、引用原文匹配以及与参考判定一致，是三个独立核查项。若 Nous 不接受配置中的 `opencode` 模型名，保留错误并暂停模型相关工作，不自动切换provider或模型。
