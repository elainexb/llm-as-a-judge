"""Native-plugin logic tests. Fixture output is not accepted semantic ground truth."""
import concurrent.futures
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('judge_plugin_fixture', ROOT / 'plugins/dialogue-judge/__init__.py', submodule_search_locations=[str(ROOT / 'plugins/dialogue-judge')])
plugin = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = plugin
spec.loader.exec_module(plugin)
IDENTITY = {'session_id': 'local-test', 'task_id': 'local-test'}


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.engine = plugin.JudgeRuns(ROOT, Path(self.temp.name) / 'runs')
        self.review = (ROOT / 'tests/fixtures/c09_draft_review.json').read_text()

    def prepare(self, case='C09'):
        result = self.engine.prepare(case, IDENTITY)
        self.assertNotIn('error', result)
        return result

    def pages(self, result):
        text = ''
        for page in range(result['page_count']):
            reply = self.engine.context(result['run_id'], page, IDENTITY)
            self.assertLess(len(json.dumps(reply)), 8000)
            text += reply['text']
        self.assertTrue(reply['context_complete'])
        path = self.engine.path(result['run_id'])
        self.assertEqual(text, (path / 'context.txt').read_text())
        return path

    def test_all_sources_and_large_context_complete(self):
        for case in [f'C{i:02}' for i in range(1, 13)]:
            with self.subTest(case=case):
                result = self.prepare(case)
                path = self.pages(result)
                audit = self.engine.inspect(result['run_id'], IDENTITY)
                self.assertEqual(audit['missing_context_pages'], [])
                self.assertEqual(audit['steps']['validate']['state'], 'not_executed')
                self.assertEqual(audit['status'], 'incomplete')
                original = json.loads((ROOT / f'native_inputs/{case}.json').read_text())
                self.assertEqual(json.loads((path / f'prepared/{case}.json').read_text()), original)

    def test_actual_review_and_audit(self):
        result = self.prepare()
        path = self.pages(result)
        report = self.engine.validate(result['run_id'], self.review, IDENTITY)
        self.assertEqual(report['status'], 'validated_pending_review')
        self.assertEqual((path / 'judgment.txt').read_text(), self.review)
        audit = self.engine.inspect(result['run_id'], IDENTITY)
        self.assertEqual(audit['status'], 'validated_pending_review')
        for step in ('prepare', 'context', 'submission', 'validate'):
            self.assertEqual(audit['steps'][step]['state'], 'succeeded')
        self.assertEqual(audit['model_understanding'], 'not_observable')
        self.assertTrue(all('duration_ms' in e for e in self.engine.events(path) if e['phase'] in ('succeeded','failed') and e['step'] != 'inspection'))

    def test_premature_validation_is_recorded(self):
        result = self.prepare()
        self.engine.context(result['run_id'], 0, IDENTITY)
        with self.assertRaises(plugin.WorkflowError) as error:
            self.engine.validate(result['run_id'], self.review, IDENTITY)
        self.assertEqual(error.exception.code, 'context_incomplete')
        audit = self.engine.inspect(result['run_id'], IDENTITY)
        self.assertEqual(audit['status'], 'blocked')
        self.assertEqual(audit['steps']['validate']['failures'], 1)
        self.assertTrue(audit['missing_context_pages'])
        self.assertFalse((self.engine.path(result['run_id']) / 'judgment.txt').exists())

    def test_malformed_submission_kept_and_repeat_rejected(self):
        result = self.prepare()
        path = self.pages(result)
        report = self.engine.validate(result['run_id'], 'not JSON', IDENTITY)
        self.assertEqual(report['status'], 'output_invalid')
        self.assertEqual((path / 'judgment.txt').read_text(), 'not JSON')
        with self.assertRaises(plugin.WorkflowError):
            self.engine.validate(result['run_id'], self.review, IDENTITY)
        self.assertEqual((path / 'judgment.txt').read_text(), 'not JSON')
        self.assertEqual(self.engine.inspect(result['run_id'], IDENTITY)['steps']['validate']['failures'], 2)

    def test_invalid_quote_fails(self):
        result = self.prepare()
        self.pages(result)
        d = json.loads(self.review)
        d['issues'][0]['evidence'][0]['quote'] = 'invented unsupported quotation'
        report = self.engine.validate(result['run_id'], json.dumps(d), IDENTITY)
        self.assertEqual(report['status'], 'evidence_invalid')

    def test_preparation_failure_is_inspectable(self):
        result = self.engine.prepare('C99', IDENTITY)
        self.assertIn('error', result)
        audit = self.engine.inspect(result['run_id'], IDENTITY)
        self.assertEqual(audit['steps']['prepare']['state'], 'failed')
        self.assertEqual(audit['steps']['context']['state'], 'not_executed')
        with self.assertRaises(plugin.WorkflowError):
            self.engine.context(result['run_id'], 0, IDENTITY)

    def test_invalid_page_and_cross_session(self):
        result = self.prepare()
        for page in (-1, True, result['page_count']):
            with self.assertRaises(plugin.WorkflowError):
                self.engine.context(result['run_id'], page, IDENTITY)
        with self.assertRaises(plugin.WorkflowError) as error:
            self.engine.context(result['run_id'], 0, {'session_id': 'other'})
        self.assertEqual(error.exception.code, 'session_mismatch')
        with self.assertRaises(plugin.WorkflowError):
            self.engine.path('../outside')

    def test_artifact_and_ledger_changes(self):
        result = self.prepare()
        path = self.engine.path(result['run_id'])
        (path / 'context.txt').write_text('changed')
        self.assertEqual(self.engine.inspect(result['run_id'], IDENTITY)['status'], 'integrity_failed')
        other = self.prepare()
        ledger = self.engine.path(other['run_id']) / 'events.jsonl'
        ledger.write_text(ledger.read_text() + '{invalid ledger')
        self.assertEqual(self.engine.inspect(other['run_id'], IDENTITY)['status'], 'integrity_failed')

    def test_interrupted_validation_after_submission_detected(self):
        result = self.prepare()
        path = self.pages(result)
        call = uuid.uuid4().hex
        with self.engine.locked(path):
            self.engine.append(path, call, 'validate', 'started', IDENTITY)
            self.engine.append(path, call, 'submission', 'succeeded', IDENTITY)
        audit = self.engine.inspect(result['run_id'], IDENTITY)
        self.assertEqual(audit['steps']['validate']['state'], 'incomplete')
        with self.assertRaises(plugin.WorkflowError) as error:
            self.engine.context(result['run_id'], 0, IDENTITY)
        self.assertEqual(error.exception.code, 'incomplete_operation')

    def test_parallel_submission_has_only_one_saved_judgment(self):
        result = self.prepare()
        path = self.pages(result)
        def submit(_):
            try:
                return self.engine.validate(result['run_id'], self.review, IDENTITY)['status']
            except plugin.WorkflowError as error:
                return error.code
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            statuses = list(pool.map(submit, [1, 2]))
        self.assertEqual(statuses.count('validated_pending_review'), 1)
        self.assertTrue(set(statuses) <= {'validated_pending_review', 'run_busy', 'already_submitted'})
        self.assertEqual((path / 'judgment.txt').read_text(), self.review)

    def test_changed_validation_report_is_detected(self):
        result = self.prepare()
        path = self.pages(result)
        self.engine.validate(result['run_id'], 'invalid JSON', IDENTITY)
        (path / 'validation.json').write_text('{}')
        self.assertEqual(self.engine.inspect(result['run_id'], IDENTITY)['status'], 'integrity_failed')

    def test_failed_report_write_does_not_claim_completed_validation(self):
        from unittest.mock import patch
        result = self.prepare()
        path = self.pages(result)
        with patch.object(self.engine.helper, 'validate_files', side_effect=OSError('injected write failure')):
            with self.assertRaises(OSError):
                self.engine.validate(result['run_id'], self.review, IDENTITY)
        self.assertEqual((path / 'judgment.txt').read_text(), self.review)
        audit = self.engine.inspect(result['run_id'], IDENTITY)
        self.assertEqual(audit['steps']['submission']['state'], 'succeeded')
        self.assertEqual(audit['steps']['validate']['state'], 'failed')
        self.assertNotEqual(audit['status'], 'validated_pending_review')

    def test_version_change_requires_new_loading_and_run(self):
        import shutil
        project = Path(self.temp.name) / 'project'
        project.mkdir()
        for name in ('dialogue_tools.py', 'case_manifest.jsonl', 'wildfeedback_candidates.jsonl'):
            shutil.copy2(ROOT / name, project / name)
        shutil.copytree(ROOT / 'drafts/dialogue-behavior-monitor', project / 'drafts/dialogue-behavior-monitor')
        engine = plugin.JudgeRuns(project)
        result = engine.prepare('C09', IDENTITY)
        skill = project / 'drafts/dialogue-behavior-monitor/SKILL.md'
        skill.write_text(skill.read_text() + '\nChanged rule for injected fault.\n')
        with self.assertRaises(plugin.WorkflowError) as error:
            engine.context(result['run_id'], 0, IDENTITY)
        self.assertEqual(error.exception.code, 'version_changed')
        with self.assertRaises(plugin.WorkflowError):
            engine.prepare('C09', IDENTITY)


if __name__ == '__main__':
    unittest.main()
