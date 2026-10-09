# Hermes Dialogue Monitoring Harness Draft v0.1

This document preserves the historical outer-runner design, now superseded by [HERMES_WORKFLOW.md](../HERMES_WORKFLOW.md) and [dialogue_tools.py](../dialogue_tools.py). The earlier runner is archived at [harness.py](../archive/outer-runner/harness.py). Current status and verification are in the [project plan](../HERMES_JUDGE_PLAN.md). The user requires project-local preparation and review before any Hermes-directory changes. No Skill has been installed, profile modified, Hermes model called, or live logging integrated.

Companion artifacts: [Skill](dialogue-behavior-monitor/SKILL.md) and [output contract](dialogue-behavior-monitor/references/output-contract.md). Project facts and approval history remain in the [project plan](../HERMES_JUDGE_PLAN.md).

## Objective and Minimum End-to-End Workflow

Read a complete User/Agent conversation, run the specified Hermes profile, preserve the analysis and source evidence, and review user activity, correction points, adjustment/recurrence, and sentiment case by case. Phase one uses the existing 12 real English conversations, one case per distinct source conversation.

Normal corrections and correction-free conversations are valid observations. This phase does not automatically classify anomalies, send alerts, improve the observed Agent, write memory, or deploy continuous monitoring. New-log ingestion, cross-conversation tracking, live triggers, and alert thresholds require later design after initial validation.

## Responsibilities and Interfaces

### Simplification Proposal: Keep Judgment in the Skill, Put Mechanics in Code

The user requested a much simpler Skill and a review of which work belongs in code. This revision is a proposed responsibility split, not implementation authorization. The short Skill retains the four semantic questions. The output contract remains unchanged; a short entrypoint alone does not reduce the schema the model must understand.

| Work | Proposed owner | Boundary |
|---|---|---|
| Select source conversations; preserve text, roles, order, IDs, and provenance | Code: input adapter | Completeness needs verified source boundaries; do not infer it from the final role. English-only eligibility remains reviewed, rather than certified by an ASCII check |
| Supply the versioned output contract and conversation in the query file | Code: prompt assembly | Generate consistent prompts; the model still needs field meanings. Moving instructions into generated text does not by itself reduce tokens |
| Start one Hermes process per case; save events, stderr, exit codes, hashes, and metadata | Code: existing CLI adapter | Reuse Hermes execution; do not implement another Agent loop |
| Parse JSON; validate fields, enums, IDs, references, roles, chronology, and exact quote substrings | Code: mechanical validator | Valid quotations can still be irrelevant evidence; preserve failed raw output |
| Locate the last User message and whether feedback follows the last Agent | Code: chronology calculation | Compare model fields with calculated values; never infer satisfaction from message position |
| Check label-to-negative-emotion mapping; count validated events/issues if requested | Code: deterministic derivation | Counts depend on model grouping; they do not establish correctness or dissatisfaction. No new count fields are proposed here |
| Identify goals, requirement scope, corrections, and distinct versus repeated correction points | Model guided by Skill | Do not replace these judgments with keyword matching or string similarity |
| Assess actual adjustment, continuing failure, relapse, and sentiment | Model guided by Skill | Compare behavior in context and retain uncertainty; code cannot establish these from apologies or repetition counts |
| Decide whether evidence supports each judgment | Model, followed by human review | Mechanical validation cannot replace semantic review |

The minimum code remains one standard-library runner with input preparation, CLI invocation, storage, and validation responsibilities. These can be functions in one file; no separate framework, service, database, or per-case scripts are needed. Implementation remains pending architecture approval. The maintained contracts are the existing input/output contract and CLI transport; changes to either require corresponding adapter/validator updates.

Acceptance of this split: the Skill contains semantic rules only; the runner handles repeatable mechanics; the 12 real cases retain full dialogue and reviewable evidence. Correctness still requires human review, particularly on C09's issue grouping and C01's changing sentiment. None of the proposed code has been run.

| Component | Input → Output | Reuse, ownership, and failure handling |
|---|---|---|
| Conversation preparation | Source IDs in the current manifest + original saved pool → complete input JSON | Necessary file adaptation only. Retrieve complete conversations, not old truncated inputs. Do not treat selection categories as answers. Missing source/content/unique indices stops that case |
| Analysis Skill | Complete input + output contract → model guidance | New domain judgment rules, maintained by this project. The model performs semantic analysis. Installation location and version of a deployed copy require confirmation |
| Hermes execution | Profile + Skill + query-file → stream events and final text | Reuse the existing CLI and agent loop. Select data-analyst; do not silently change model/provider. Preserve failures rather than fabricating replacement judgments |
| Mechanical validation | Final text + identical input → validation state | Minimal owned validation of structure, evidence, IDs, and chronology. Preserve invalid output; do not rewrite it to manufacture a pass |
| Case review | Evidence-backed model output + human reference → difference record | User-confirmed references. Mechanical validity remains pending semantic review and user acceptance |

Any new implementation is limited to conversation preparation, CLI file adaptation, result storage, and mechanical validation, using Python's standard library where adequate. No new Agent framework, database, embeddings, model API SDK, or custom model/tool loop is needed. If existing interfaces fail, report evidence before proposing a minimal change.

## Conversation Preparation

1. Match C01–C12 source IDs in `case_manifest.jsonl` to `wildfeedback_candidates.jsonl`. Transform only identity and complete original messages into the input contract; exclude researcher labels, historical references, and old categories.
2. Preserve original text, message indices, order, and available source rows. Do not stitch conversations or remove messages for language filtering. Verify 12 distinct source IDs and English throughout each full source conversation.
3. Set `input_completeness` from verified source boundaries. Ending with an Agent response alone does not establish completeness. Future logs with unknown boundaries remain unknown.
4. Record input, Skill, and contract hashes and source identity. Keep real data separate from demonstrations and fault injection.

## Proposed Execution Entry Point

Target profile: `/Users/xuebai/.hermes/profiles/data-analyst/`. Its public model configuration is `nous / opencode`; service-side model availability has not been tested. Retain the profile's default rules, memory, and tools. This evaluates the actual profile, not an isolated model.

After Skill installation or explicit resource-directory configuration and verified loading, the per-case command has this shape. It is not immediately runnable: the draft is not installed and complete monitoring inputs have not been generated.

```bash
hermes -p data-analyst chat \
  -s dialogue-behavior-monitor \
  --query-file '/absolute/path/to/full-conversation-input.txt' \
  --oneshot --format stream-json
```

Use a separate process for each case without resume. New sessions do not isolate persistent memory. The Skill requests observation without memory/rule changes; inspect actual traces. Record unexpected write-tool calls, unexpected Skills, or model routing changes as configuration deviations rather than treating the attempt as an equivalent clean trial.

Do not combine this with `--ignore-rules`: it affects Skill preloading and profile context. Do not substitute `batch_runner.py` and claim equivalence; its local default model/provider and context handling differ from the target profile.

The harness may include the output contract text explicitly in the query-file, avoiding schema guessing or extra tool calls to retrieve it. It must match the Skill's referenced version. Before running, confirm the profile can discover the Skill and record the deployed copy's hash. Stop on missing Skill or version mismatch rather than falling back to a no-Skill call.

## Execution Sequence

```text
For each selected case:
  Validate complete source/input and save input/version hashes.
  Invoke the existing Hermes CLI with explicit profile and Skill.
  Preserve stdout, stderr, and process exit code.
  Extract exactly one terminal result event from stream JSONL.
  Check process exit code, result.exit_code, and error.
  Parse result.text as a strict JSON object.
  Validate domain structure, evidence, IDs, chronology, and mechanical consistency.
  Save attempt status and retain the output for semantic review.
  Continue with the next case.
```

Distinguish missing/multiple terminal events, empty text, and non-JSON text. Do not reconstruct success from partial deltas. Hermes stream-json is a transport format, not guaranteed domain JSON.

Initially, do not automatically retry model calls or repair JSON. Preserve the failure and let the operator explicitly rerun; a rerun creates a new attempt rather than replacing earlier output. Determine an existing Hermes execution-budget value during actual trial planning. Timeout is an execution outcome, not a semantic failure judgment.

## Mechanical Validation

- Required fields, enums, value types, and matching case/conversation identity.
- Unique task, issue, and event IDs; valid references belonging to the correct issue.
- Existing message indices. Corrections and sentiment refer to User messages; adjustments refer to Agent messages. Adjustment responses follow the correction; previous events precede current events.
- Every quote is a nonempty contiguous substring of its indexed message. Reject translations or paraphrases. Relationship evidence may include User and intervening Agent messages.
- No corrections means an empty issue list. Established corrections require correction_observed=true. Ambiguous unclassified feedback retains null with reasons.
- First events have no previous_event. Confirmed repetition/relapse references a preceding event in the same issue. A User index may legitimately appear in multiple events for separate correction points.
- The final sentiment object points to the last observable User message. Compute whether a User message follows the last Agent from source chronology. Enforce mechanical label/negative_emotion consistency.

These checks cannot establish correct task segmentation, issue merges, requirement continuity, substantive adjustment, evidential support, or sentiment accuracy. Accept contract-supported uncertainty; uncertainty is not a formatting failure.

## Storage and Status

Record input, Skill, contract, and harness versions per run. Each case attempt retains `input.json`, `events.jsonl`, `stderr.txt`, `analysis.json` when parseable, `validation.json`, and execution metadata. These names are proposed; implementation should fit the existing project structure.

Execution/validation states: `input_invalid`, `execution_failed`, `transport_invalid`, `output_invalid`, `evidence_invalid`, and `validated_pending_review`. The last state only means mechanical checks passed. Human review separately records `reviewed_with_differences` or `reviewed_agreed`; program status does not replace user acceptance.

Retain available actual model identity, session ID, token/cache statistics, duration, and cost. Unknown cost is null. A returned zero token count requires a note about whether valid usage data exists; it does not prove the call was free. Do not read or emit provider secrets, private historical memory, or unrelated sessions.

## Semantic Validation with Existing Real Material

These are review targets and provisional observations, not Hermes results or approved ground truth:

| Real case | Review target |
|---|---|
| C09: cat prompts | Separate one-sentence length from unwanted AI-art framing; link repeated corrections; split a message correcting both points; distinguish relapse; do not turn neutral imperatives into negative sentiment; a final topic change does not prove resolution |
| C02: C# loop and CS0120 | Do not merge the original stopping problem and a new static/instance error solely because both concern code |
| C03: EU/heat calculations | Track related arithmetic and cooling issues separately; new data is not automatically recurrence; technical correction is not automatically dissatisfaction |
| C08: simpler explanation | Observe ordinary revision and actual simplification; a child-oriented request may strengthen or change requirements rather than prove relapse |
| C01: replacement materials | Identify persistent misunderstanding and explicit earlier dissatisfaction; later “good” and neutral follow-up must not be overridden by earlier negativity |
| C05: engineering ideas | Separate an explicit boring-to-interesting shift from later interest refinement |
| C10 and C11 | New tasks, thanks, and requests for more; return no corrections when none occurred |
| C04 and C12 | Handle ambiguous “No” and sequence-context correction; preserve missing-source and missing-follow-up limitations |

After implementation, test normal, boundary, and negative cases: nonexistent/paraphrased quotes, incorrect ID links, Agent responses preceding corrections, duplicate sources, partial input, non-JSON output, model-call failure, valid multi-issue messages, valid correction-free output, and valid uncertain sentiment. Mark injected faults separately from real user behavior.

Confirm human references before the first full run. Review missed/false corrections, wrong merges/splits, unresolved-versus-relapse confusion, adjustment errors, sentiment false positives/negatives, and absent final feedback. Twelve cases establish performance on those cases, not production-wide accuracy. Consider independent review, batch automation, or continuous monitoring only after this evidence.

## Maintenance and Next Steps

### Draft Review Findings

A separate reviewing agent applied the English draft to the real C09 conversation (30 messages). Its output was parseable and contained 7 tasks, 9 issues, and 10 correction events. A subsequent direct check verified 56 verbatim quotations, message roles, ID references, event ordering, and the final User index. This is an independent draft review, not a Hermes run, approved reference, or proof of semantic accuracy. No harness implementation was used.

The review exposed interpretation boundaries to resolve before implementation:

- **Task granularity:** Does changing the requested cat outfit start a new task or continue the same art-prompt task? The reviewer split deliverables into several tasks and retained uncertainty about cross-task issue links. A provisional recommendation is to treat content variations under the same user objective as one task unless the objective changes; user review is needed before adopting this as a grouping policy.
- **Requirement continuity:** Does an earlier removal instruction persist into a new requested deliverable? Do not infer permanent applicability merely because the topic is similar. Preserve uncertainty where there is no explicit or contextual basis.
- **Correction meaning:** Does “Remove the Ai-generated artwork” prohibit semantically equivalent “Create AI art” framing, or only the literal phrase? Context may support semantic removal, but ambiguous interpretations must remain visible.
- **Correction versus reinforcement:** A repeated length request after an already short reply does not by itself prove a remaining defect. Likewise, a preferred formulation plus “Much Better” may be praise rather than a new correction event.

The draft deliberately supports uncertain links. Mechanical checks passed for the review output, but these policy boundaries must be reviewed rather than silently treated as settled.

The Skill and contract own domain semantics; the harness owns file/CLI interfaces and mechanical checks. After Hermes, profile, Skill, or contract changes, review differences using fixed real cases. Do not silently combine results from different configurations.

The current review objects are the Skill, output contract, and this execution design. After approval, implement the minimal adapters/validators, prepare complete inputs, confirm Skill installation/loading and execution budget, and run actual tests. Keep installation, model execution, production integration, and acceptance records distinct.
