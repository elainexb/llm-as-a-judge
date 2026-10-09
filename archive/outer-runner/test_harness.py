"""Mechanical tests and injected faults; fixtures are not accepted ground truth."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import harness as h

ROOT = h.ROOT


def control(data):
    """A deliberately constructed correction-free control, not a new judgment."""
    users = [m for m in data['messages'] if m['role'] == 'User']
    quote = lambda m: [{'message_index': m['message_index'], 'quote': m['content'][:30]}]
    final = users[-1]
    obs = {'user_message_index': final['message_index'], 'task_id': 'T1', 'label': 'neutral',
           'reason': 'Injected mechanical control only.', 'evidence': quote(final)}
    return {'schema_version': '0.1', **{k: data[k] for k in ('case_id', 'conversation_id', 'input_completeness')},
            'user_activity_summary': 'Injected mechanical control.', 'tasks': [{'task_id': 'T1',
            'user_goal': 'Injected control.', 'user_message_indices': [m['message_index'] for m in users],
            'requirements': [], 'evidence': quote(users[0])}], 'correction_observed': False, 'issues': [],
            'unclassified_feedback': [], 'sentiment_observations': [obs], 'final_user_sentiment': obs | {
            'negative_emotion': 'not_observed', 'feedback_after_last_agent': False},
            'limitations': ['Synthetic output tests transport and validation, not semantic accuracy.']}


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.c09 = json.loads((ROOT / 'monitoring_inputs/C09.json').read_text())
        self.review = json.loads((ROOT / 'tests/fixtures/c09_draft_review.json').read_text())
        self.c10 = json.loads((ROOT / 'monitoring_inputs/C10.json').read_text())

    def verdict(self, value):
        return h.validate_analysis(value, self.c09)['status']

    def test_real_review_has_valid_references(self):
        self.assertEqual(self.verdict(self.review), 'validated_pending_review')
        indices = [e['user_message_index'] for i in self.review['issues'] for e in i['events']]
        self.assertLess(len(set(indices)), len(indices))  # one User corrects multiple points

    def test_controls_with_no_correction_and_uncertainty(self):
        d = control(self.c10)
        self.assertEqual(h.validate_analysis(d, self.c10)['status'], 'validated_pending_review')
        for item in (d['sentiment_observations'][0], d['final_user_sentiment']):
            item['label'] = None
        d['final_user_sentiment']['negative_emotion'] = 'uncertain'
        self.assertEqual(h.validate_analysis(d, self.c10)['status'], 'validated_pending_review')

    def test_quote_fault(self):
        self.review['issues'][0]['evidence'][0]['quote'] = 'nonexistent fabricated quotation'
        self.assertEqual(self.verdict(self.review), 'evidence_invalid')

    def test_wrong_role_and_early_response(self):
        event = self.review['issues'][0]['events'][0]
        event['agent_response_indices'] = [0]
        self.assertEqual(self.verdict(self.review), 'evidence_invalid')

    def test_bad_same_issue_link(self):
        event = self.review['issues'][0]['events'][0]
        event['previous_event_id'] = 'E999'
        event['relation_to_previous'] = 'relapse_after_adjustment'
        self.assertEqual(self.verdict(self.review), 'evidence_invalid')

    def test_duplicates_and_boolean_indices(self):
        self.review['tasks'].append(copy.deepcopy(self.review['tasks'][0]))
        self.assertEqual(self.verdict(self.review), 'evidence_invalid')
        self.review['tasks'][0]['user_message_indices'] = [True]
        self.assertEqual(self.verdict(self.review), 'output_invalid')

    def test_final_user_and_negative_mapping(self):
        self.review['final_user_sentiment']['user_message_index'] = 0
        self.review['final_user_sentiment']['negative_emotion'] = 'observed'
        self.assertEqual(self.verdict(self.review), 'evidence_invalid')

    def test_required_field_and_enum(self):
        del self.review['issues'][0]['recurrence']
        self.assertEqual(self.verdict(self.review), 'output_invalid')

    def test_stream_errors_and_explicit_failure(self):
        result = {'type': 'result', 'exit_code': 0, 'text': '{}'}
        good = json.dumps(result)
        for stream in ('', 'not JSON', good + '\n' + good, good + '\n' + '{"type":"delta"}'):
            with self.subTest(stream=stream), self.assertRaises(ValueError):
                h.extract_result(stream, 0)
        result['exit_code'] = 1
        self.assertEqual(h.extract_result(json.dumps(result), 0)[2], 'execution_failed')

    def test_strict_json(self):
        for text in ('{"x":1,"x":2}', '{"x":NaN}', '```json\n{}\n```'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                h.strict_json(text)

    def test_real_preparation_preserves_all_messages(self):
        with tempfile.TemporaryDirectory() as td:
            report = h.prepare(ROOT / 'case_manifest.jsonl', ROOT / 'wildfeedback_candidates.jsonl', td)
            self.assertEqual(report['case_count'], 12)
            sources = {s['conversation_id']: s for s in h.read_jsonl(ROOT / 'wildfeedback_candidates.jsonl')}
            for case in report['cases']:
                data = json.loads((Path(td) / (case['case_id'] + '.json')).read_text())
                original = sources[data['conversation_id']]['messages']
                self.assertEqual([m['content'] for m in data['messages']], [m['content'] for m in original])
                self.assertNotIn('source_labels', json.dumps(data))
            with self.assertRaises(ValueError):
                h.prepare(ROOT / 'case_manifest.jsonl', ROOT / 'wildfeedback_candidates.jsonl', td)

    def test_duplicate_sources_and_broken_boundaries(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)
            manifest = h.read_jsonl(ROOT / 'case_manifest.jsonl')[:2]
            manifest[1]['source_conversation_id'] = manifest[0]['source_conversation_id']
            (path / 'manifest').write_text('\n'.join(map(json.dumps, manifest)))
            with self.assertRaises(ValueError):
                h.prepare(path / 'manifest', ROOT / 'wildfeedback_candidates.jsonl', path / 'out')
            manifest = h.read_jsonl(ROOT / 'case_manifest.jsonl')[:1]
            (path / 'manifest').write_text(json.dumps(manifest[0]))
            source = next(s for s in h.read_jsonl(ROOT / 'wildfeedback_candidates.jsonl') if s['conversation_id'] == manifest[0]['source_conversation_id'])
            source['messages'][0]['source_labels']['UtterranceId'] = 2
            (path / 'pool').write_text(json.dumps(source))
            with self.assertRaises(ValueError):
                h.prepare(path / 'manifest', path / 'pool', path / 'out')

    def test_partial_input_and_label_leak(self):
        self.c10['input_completeness'] = 'partial'
        h.validate_input(self.c10)  # unknown/partial future logs are supported, not promoted
        self.c10['messages'][0]['source_labels'] = {'Satisfaction': True}
        with self.assertRaises(ValueError):
            h.validate_input(self.c10)

    def test_skill_preflight(self):
        with tempfile.TemporaryDirectory() as td:
            profile = Path(td)
            with self.assertRaises(ValueError):
                h.preflight(profile)
            import shutil
            installed = profile / 'skills' / h.NAME
            shutil.copytree(h.SKILL, installed)
            self.assertEqual(h.preflight(profile), installed)
            (installed / 'SKILL.md').write_text('modified')
            with self.assertRaises(ValueError):
                h.preflight(profile)

    def test_subprocess_integration_and_retained_failures(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            fake = directory / 'fake-hermes'
            analysis = control(self.c10)
            stream = json.dumps({'type': 'system', 'subtype': 'init', 'model': 'test-only'}) + '\n' + json.dumps({'type': 'result', 'exit_code': 0, 'text': json.dumps(analysis)})
            def executable(body):
                fake.write_text('#!/usr/bin/env python3\n' + body)
                fake.chmod(0o700)
            executable('import sys\nprint(' + repr(stream) + ')\n')
            valid = h.execute_case(ROOT / 'monitoring_inputs/C10.json', directory / 'runs', fake, 5)
            self.assertEqual(valid['status'], 'validated_pending_review')
            self.assertTrue((Path(valid['attempt']) / 'events.jsonl').exists())
            executable('import sys\nprint("injected failure", file=sys.stderr)\nsys.exit(7)\n')
            failed = h.execute_case(ROOT / 'monitoring_inputs/C10.json', directory / 'runs', fake, 5)
            self.assertEqual(failed['status'], 'execution_failed')
            meta = json.loads((Path(failed['attempt']) / 'metadata.json').read_text())
            self.assertEqual(meta['process_exit_code'], 7)
            self.assertNotEqual(valid['attempt'], failed['attempt'])
            executable('print("not JSON")\n')
            self.assertEqual(h.execute_case(ROOT / 'monitoring_inputs/C10.json', directory / 'runs', fake, 5)['status'], 'transport_invalid')
            executable('import time\ntime.sleep(30)\n')
            timeout = h.execute_case(ROOT / 'monitoring_inputs/C10.json', directory / 'runs', fake, 0.1)
            self.assertEqual(timeout['status'], 'execution_failed')
            self.assertTrue(json.loads((Path(timeout['attempt']) / 'metadata.json').read_text())['timed_out'])
            missing = h.execute_case(directory / 'missing.json', directory / 'runs', fake, 5)
            self.assertEqual(missing['status'], 'input_invalid')


if __name__ == '__main__':
    unittest.main()
