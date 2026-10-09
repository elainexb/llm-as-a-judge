"""Hermes native tool adapter; public PluginContext APIs only."""
import json
from .runtime import JudgeRuns, WorkflowError

TOOLSET = 'dialogue_judge'
TOOLS = {
    'prepare_dialogue': (
        'Start a new run for the user-selected case. Extract the complete original dialogue, remove dataset labels, '
        'and pin the input, Judge Skill and output contract. Return run_id, message_count, page_count, input_path, '
        'status and next_action. Outputs are stored by the tool in the configured project; no output path is needed. '
        'A failed preparation returns its run_id and error so inspect_judge_run can diagnose it. Makes no model calls.',
        {'case_id': {'type': 'string', 'pattern': '^C[0-9]{2}$',
                     'description': 'Case ID requested by the user, from the selected suite C01 through C12. Do not invent a case.'}},
        ['case_id'], 'prepare'),
    'get_judge_context': (
        'Get one page of a successfully prepared run. The pages together contain the pinned Judge Skill, output '
        'contract and full conversation. Return text, page_count, missing_pages, context_complete and next_action. '
        'Retrieve every missing page in order before judging; a returned page is evidence of delivery, not understanding. '
        'Reject unknown runs, changed artifacts, invalid pages and another session\'s run.',
        {'run_id': {'type': 'string', 'pattern': '^[0-9a-f]{32}$',
                    'description': 'Opaque run_id returned by prepare_dialogue; reuse it for this case only.'},
         'page': {'type': 'integer', 'minimum': 0,
                  'description': 'Zero-based page index. Start at the next_action.page from preparation, then use missing_pages.'}},
        ['run_id', 'page'], 'context'),
    'validate_judgment': (
        'Submit the judgment produced by the current Hermes model and run mechanical validation. Requires successful '
        'preparation and every context page. Save the original submission and validation report without overwrite or '
        'repair. Return status, error_count, errors, artifact paths and next_action. Malformed or unsupported output is '
        'retained as a failed result. Only one submission is allowed per run. A pass means validated_pending_review, '
        'not semantic correctness; inspect the run next.',
        {'run_id': {'type': 'string', 'pattern': '^[0-9a-f]{32}$',
                    'description': 'Run ID whose complete context was obtained for this judgment.'},
         'judgment_json': {'type': 'string', 'minLength': 1, 'maxLength': 200000,
                           'description': 'Original judgment serialized as JSON text following the output contract in the context. '
                                          'This argument is a string, not a nested object or file path. Preserve its text; do not add Markdown fences.'}},
        ['run_id', 'judgment_json'], 'validate'),
    'inspect_judge_run': (
        'Read the execution audit for a run, including failed preparation or submission. Return steps with actual '
        'states/call/failure counts, missing_context_pages, recent_failures, status and artifact paths. Report these '
        'observations to the user. Integrity failures prevent a completion claim. Model understanding, final response '
        'delivery and human acceptance are not inferred from tool calls.',
        {'run_id': {'type': 'string', 'pattern': '^[0-9a-f]{32}$',
                    'description': 'Run ID returned by preparation, including a run that later failed.'}},
        ['run_id'], 'inspect'),
}


def register(ctx):
    project = ctx.get_config('project_dir', '')
    if not project:
        raise ValueError('Configure plugins.entries.dialogue-judge.settings.project_dir before enabling tools.')
    engine = JudgeRuns(project)
    for name, (description, properties, required, method) in TOOLS.items():
        def handler(params, _method=method, _properties=properties, _required=required, **kwargs):
            try:
                if not isinstance(params, dict) or set(params) != set(_required):
                    raise WorkflowError('invalid_arguments', 'Supply exactly the required tool arguments.')
                for key, spec in _properties.items():
                    expected = str if spec['type'] == 'string' else int
                    if type(params[key]) is not expected:
                        raise WorkflowError('invalid_arguments', f'{key} has an invalid type.')
                identity = {key: kwargs.get(key) or None for key in ('session_id', 'task_id')}
                data = getattr(engine, _method)(**params, identity=identity)
                return json.dumps({'ok': 'error' not in data and data.get('status') not in
                    ('failed', 'integrity_failed', 'output_invalid', 'input_invalid', 'evidence_invalid'), 'data': data}, ensure_ascii=False)
            except Exception as exc:
                return json.dumps({'ok': False, 'error': {'code': getattr(exc, 'code', 'operation_failed'), 'message': str(exc)}}, ensure_ascii=False)
        registered = ctx.register_tool(name=name, toolset=TOOLSET, schema={'name': name, 'description': description,
            'parameters': {'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False}}, handler=handler)
        if registered is None:
            raise ValueError(f'Native tool registration rejected: {name}; no overrides are permitted.')
