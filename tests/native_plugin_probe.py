"""Use installed Hermes Python; the test creates an isolated home and makes no model calls."""
import json
import os
import tempfile
from pathlib import Path
import shutil
import sys

SOURCE = Path('/Users/xuebai/.hermes/hermes-agent')
PROJECT = Path(__file__).resolve().parents[1]
isolated = tempfile.TemporaryDirectory(prefix='dialogue-judge-native-', dir='/private/tmp')
home = Path(isolated.name).resolve()
os.environ['HERMES_HOME'] = str(home)
sys.path.insert(0, str(SOURCE))
sys.dont_write_bytecode = True
# Native config, project data, outputs and plugin files exist only in the isolated home.
fixture_project = home / 'project'
fixture_project.mkdir(parents=True)
for name in ('dialogue_tools.py', 'case_manifest.jsonl', 'wildfeedback_candidates.jsonl'):
    shutil.copy2(PROJECT / name, fixture_project / name)
shutil.copytree(PROJECT / 'drafts/dialogue-behavior-monitor', fixture_project / 'drafts/dialogue-behavior-monitor')
shutil.copytree(PROJECT / 'plugins/dialogue-judge', home / 'plugins/dialogue-judge', ignore=shutil.ignore_patterns('__pycache__'))
(home / 'config.yaml').write_text('plugins:\n  enabled: [dialogue-judge]\n  entries:\n    dialogue-judge:\n      settings:\n        project_dir: ' + json.dumps(str(fixture_project)) + '\n')
from hermes_cli.plugins import get_plugin_manager
from hermes_cli.plugins_manifest import parse_manifest_file
from tools.registry import registry
manifest = parse_manifest_file(home / 'plugins/dialogue-judge/plugin.yaml', home / 'plugins/dialogue-judge', 'user', '')
assert manifest.name == 'dialogue-judge'
manager = get_plugin_manager()
assert manager.scope_key == str(home)
manager.discover_and_load()
loaded = manager._plugins.get('dialogue-judge')
assert loaded is not None and not loaded.error, getattr(loaded, 'error', 'not discovered')
names = ['prepare_dialogue', 'get_judge_context', 'validate_judgment', 'inspect_judge_run']
for name in names:
    entry = registry.get_entry(name, scope=manager.scope_key)
    assert entry is not None, name
    assert entry.schema['parameters']['additionalProperties'] is False

from model_tools import get_tool_definitions, handle_function_call
definitions = get_tool_definitions(enabled_toolsets=['dialogue_judge'], quiet_mode=True, skip_tool_search_assembly=True)
functions = {tool['function']['name']: tool['function'] for tool in definitions}
assert set(functions) == set(names), list(functions)
for name in names:
    definition = functions[name]
    assert definition['parameters']['type'] == 'object'
    assert set(definition['parameters']['required']) == set(definition['parameters']['properties'])
    assert definition['parameters']['additionalProperties'] is False
    assert all(prop.get('description') for prop in definition['parameters']['properties'].values())
    json.loads(json.dumps(definition))

def call(name, params):
    value = handle_function_call(name, params, session_id='native-probe', task_id='native-probe',
                                tool_call_id='probe-call', enabled_tools=names, enabled_toolsets=['dialogue_judge'])
    assert isinstance(value, str), type(value)
    return json.loads(value)

bad = call('prepare_dialogue', {'case_id': True})
assert bad['ok'] is False and bad['error']['code'] in ('invalid_arguments', 'invalid_case_id')
prepared = call('prepare_dialogue', {'case_id': 'C09'})
assert prepared['ok'], prepared
run = prepared['data']
for page in range(run['page_count']):
    response = call('get_judge_context', {'run_id': run['run_id'], 'page': page})
    assert response['ok'], response
review = (PROJECT / 'tests/fixtures/c09_draft_review.json').read_text()
validation = call('validate_judgment', {'run_id': run['run_id'], 'judgment_json': review})
assert validation['ok'] and validation['data']['status'] == 'validated_pending_review', validation
audit = call('inspect_judge_run', {'run_id': run['run_id']})
assert audit['ok'] and audit['data']['missing_context_pages'] == [], audit
assert all(audit['data']['steps'][step]['state'] == 'succeeded' for step in ('prepare','context','submission','validate'))
result = {'status': 'passed', 'native_discovery': True, 'native_registration': names,
          'native_dispatch': True, 'model_tool_definitions': True, 'host_function_call_dispatch': True,
          'emitted_function_names': sorted(functions), 'tool_definitions': definitions, 'validation': validation['data']['status'],
          'audit_steps': audit['data']['steps'], 'model_calls': 0, 'profile_modified': False}
manager.unload('dialogue-judge')
assert all(registry.get_entry(name, scope=manager.scope_key) is None for name in names)
result['native_unload'] = True
print(json.dumps(result, indent=2))
isolated.cleanup()
