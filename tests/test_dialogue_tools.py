"""Mechanical tests and injected faults; fixtures are not accepted ground truth."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import dialogue_tools as h

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

    def test_saved_invalid_json_reports_failure_without_repair(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            analysis = folder / 'analysis.json'
            analysis.write_text('not JSON')
            report_path = folder / 'validation.json'
            result = h.validate_files(ROOT / 'monitoring_inputs/C10.json', analysis, report_path)
            self.assertEqual(result['status'], 'output_invalid')
            self.assertEqual(analysis.read_text(), 'not JSON')
            self.assertEqual(json.loads(report_path.read_text())['status'], 'output_invalid')
            with self.assertRaises(FileExistsError):
                h.validate_files(ROOT / 'monitoring_inputs/C10.json', analysis, report_path)
            with self.assertRaises(ValueError):
                h.validate_files(ROOT / 'monitoring_inputs/C10.json', analysis, analysis)

    def test_cli_preparation_and_validation(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            base = [sys.executable, str(ROOT / 'dialogue_tools.py')]
            prep = subprocess.run(base + ['prepare', '--cases', 'C09', 'C10', '--output', str(folder / 'input')], capture_output=True, text=True)
            self.assertEqual(prep.returncode, 0, prep.stderr)
            self.assertEqual(json.loads(prep.stdout)['case_count'], 2)
            analysis = folder / 'analysis.json'
            analysis.write_text(json.dumps(self.review))
            command = base + ['validate', '--input', str(folder / 'input/C09.json'), '--analysis', str(analysis), '--report', str(folder / 'validation.json')]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'], 'validated_pending_review')
            analysis.write_text('broken JSON')
            command[-1] = str(folder / 'invalid.json')
            failed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(failed.returncode, 1)
            self.assertEqual(json.loads(failed.stdout)['status'], 'output_invalid')
            no_run = subprocess.run(base + ['run'], capture_output=True, text=True)
            self.assertEqual(no_run.returncode, 2)  # helper cannot launch an Agent


if __name__ == '__main__':
    unittest.main()
