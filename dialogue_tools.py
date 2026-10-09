#!/usr/bin/env python3
"""Prepare dialogue data and validate judgments; no Agent or model execution."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
SKILL = ROOT / 'drafts/dialogue-behavior-monitor'
CONTRACT = SKILL / 'references/output-contract.md'
COMPLETENESS = ('complete_from_source', 'partial', 'unknown')
LABELS = ('positive', 'neutral', 'negative', None)


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f'duplicate JSON key: {key}')
            result[key] = value
        return result
    def constant(value):
        raise ValueError(f'invalid JSON constant: {value}')
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def skill_hashes(directory):
    return {str(p.relative_to(directory)): digest(p) for p in sorted(directory.rglob('*')) if p.is_file()}


def read_jsonl(path):
    return [strict_json(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def validate_input(data):
    if not isinstance(data, dict):
        raise ValueError('input must be an object')
    if set(data) - {'case_id', 'conversation_id', 'input_completeness', 'messages'}:
        raise ValueError('input contains fields outside the observation contract')
    if any(not isinstance(data.get(k), str) or not data[k] for k in ('case_id', 'conversation_id')):
        raise ValueError('input identities must be nonempty strings')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', data['case_id']):
        raise ValueError('unsafe case_id')
    if data.get('input_completeness') not in COMPLETENESS:
        raise ValueError('invalid input_completeness')
    messages = data.get('messages')
    if not isinstance(messages, list) or not messages:
        raise ValueError('messages must be a nonempty list')
    previous = -1
    for m in messages:
        if not isinstance(m, dict) or type(m.get('message_index')) is not int or m['message_index'] <= previous:
            raise ValueError('message indices must be increasing nonnegative integers')
        previous = m['message_index']
        if set(m) - {'message_index', 'role', 'content', 'source_row_idx'}:
            raise ValueError('message contains fields outside the observation contract')
        if m.get('role') not in ('User', 'Agent') or not isinstance(m.get('content'), str):
            raise ValueError('invalid role/content')


def prepare(manifest, pool, output, selected=None):
    entries, sources = read_jsonl(manifest), read_jsonl(pool)
    by_id = {}
    for source in sources:
        key = source['conversation_id']
        if key in by_id:
            raise ValueError(f'duplicate source in pool: {key}')
        by_id[key] = source
    ids = [e['case_id'] for e in entries]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate manifest case IDs')
    if selected and set(selected) - set(ids):
        raise ValueError('requested case not in manifest')
    chosen = [e for e in entries if not selected or e['case_id'] in selected]
    source_ids = [e['source_conversation_id'] for e in chosen]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError('duplicate selected source conversation')
    prepared = []
    for entry in chosen:
        if entry.get('dialogue_language') != 'English' or entry.get('language_review_scope') != 'entire_source_conversation_and_full_judge_context':
            raise ValueError(f"{entry['case_id']}: full English review missing")
        source = by_id[entry['source_conversation_id']]
        messages = source['messages']
        start, end = source['source_row_start'], source['source_row_end_inclusive']
        if type(start) is not int or type(end) is not int or end - start + 1 != len(messages):
            raise ValueError('source row range does not match messages')
        # The saved extractor records retain TurnId/UtterranceId integrity evidence.
        if len(messages) % 2 or source.get('number_of_turns') != len(messages) // 2:
            raise ValueError('unpaired source conversation')
        for i, message in enumerate(messages):
            labels = message.get('source_labels', {})
            if (message.get('source_row_idx') != start + i or
                message.get('role') != ('User' if i % 2 == 0 else 'Agent') or
                labels.get('UtterranceId') != i or labels.get('TurnId') != i // 2 + 1):
                raise ValueError('source chronology/boundary evidence mismatch')
        data = {
            'case_id': entry['case_id'], 'conversation_id': source['conversation_id'],
            'input_completeness': 'complete_from_source',
            'messages': [{k: m[k] for k in ('role', 'content', 'source_row_idx')} | {'message_index': i}
                         for i, m in enumerate(messages)]}
        validate_input(data)
        prepared.append(data)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    # Never silently replace earlier prepared material.
    if any((output / f"{d['case_id']}.{suffix}").exists() for d in prepared for suffix in ('json',)) or (output / 'preparation.json').exists():
        raise ValueError('output already contains prepared cases; choose a new directory')
    for data in prepared:
        write_json(output / f"{data['case_id']}.json", data)
    report = {'case_count': len(prepared), 'cases': [{'case_id': d['case_id'], 'conversation_id': d['conversation_id'],
              'message_count': len(d['messages']), 'sha256': digest(output / f"{d['case_id']}.json")} for d in prepared],
              'manifest_sha256': digest(manifest), 'pool_sha256': digest(pool),
              'skill_hashes': skill_hashes(SKILL), 'contract_sha256': digest(CONTRACT),
              'completeness_basis': 'Saved complete contiguous extractor sessions, with retained source row and turn checks; no new upstream fetch.',
              'language_basis': 'Existing full-source human/agent English review in manifest; not an automatic language classifier.'}
    write_json(output / 'preparation.json', report)
    return report


# Small schema vocabulary: type, enum tuple, homogeneous list, required object.
EVIDENCE = [{'message_index': int, 'quote': str}]
SENTIMENT = {'user_message_index': int, 'task_id': (str, type(None)), 'label': LABELS, 'reason': str, 'evidence': EVIDENCE}
EVENT = {'event_id': str, 'user_message_index': int, 'correction_summary': str, 'evidence': EVIDENCE,
         'relation_to_previous': ('first_correction', 'repeated_unresolved', 'relapse_after_adjustment', 'uncertain'),
         'previous_event_id': (str, type(None)), 'relation_reason': str, 'relation_evidence': EVIDENCE,
         'agent_response_indices': [int], 'adjustment': ('adjusted', 'partially_adjusted', 'not_adjusted', 'not_observable'),
         'adjustment_reason': str, 'adjustment_evidence': EVIDENCE}
SCHEMA = {'schema_version': ('0.1',), 'case_id': str, 'conversation_id': str, 'input_completeness': COMPLETENESS,
          'user_activity_summary': str,
          'tasks': [{'task_id': str, 'user_goal': str, 'user_message_indices': [int],
                     'requirements': [{'description': str, 'introduced_at': int, 'changed_at': (int, type(None))}], 'evidence': EVIDENCE}],
          'correction_observed': (bool, type(None)),
          'issues': [{'issue_id': str, 'task_id': str, 'corrected_behavior': str, 'desired_change': str,
                      'scope_explanation': str, 'evidence': EVIDENCE, 'events': [EVENT],
                      'recurrence': {'status': ('observed', 'not_observed', 'not_observable', 'uncertain'), 'reason': str, 'evidence': EVIDENCE}}],
          'unclassified_feedback': [{'user_message_index': int, 'reason': str, 'evidence': EVIDENCE}],
          'sentiment_observations': [SENTIMENT],
          'final_user_sentiment': SENTIMENT | {'user_message_index': (int, type(None)),
              'negative_emotion': ('observed', 'not_observed', 'uncertain', 'not_observable'), 'feedback_after_last_agent': bool},
          'limitations': [str]}


def shape(value, spec, path='$'):
    errors = []
    if isinstance(spec, dict):
        if not isinstance(value, dict):
            return [f'{path}: expected object']
        for key, child in spec.items():
            if key not in value:
                errors.append(f'{path}.{key}: missing')
            else:
                errors.extend(shape(value[key], child, f'{path}.{key}'))
    elif isinstance(spec, list):
        if not isinstance(value, list):
            return [f'{path}: expected list']
        for i, child in enumerate(value):
            errors.extend(shape(child, spec[0], f'{path}[{i}]'))
    elif isinstance(spec, tuple):
        if all(isinstance(x, type) for x in spec):
            valid = type(value) in spec
        else:
            valid = any(type(value) is type(x) and value == x for x in spec)
        if not valid:
            errors.append(f'{path}: invalid value/type')
    elif type(value) is not spec:
        errors.append(f'{path}: expected {spec.__name__}')
    return errors


def validate_analysis(data, input_data):
    validate_input(input_data)
    errors = shape(data, SCHEMA)
    if errors:
        return {'status': 'output_invalid', 'errors': errors}
    messages = {m['message_index']: m for m in input_data['messages']}
    def check(ok, reason):
        if not ok:
            errors.append(reason)
    def index(idx, role, context):
        check(idx in messages and messages[idx]['role'] == role, f'{context}: invalid {role} index {idx}')
    def evidence(items, context, required=False):
        check(not required or bool(items), f'{context}: missing evidence')
        for item in items:
            idx, quote = item['message_index'], item['quote']
            check(bool(quote) and idx in messages and quote in messages[idx]['content'], f'{context}: quote not found at {idx}')
    def unique(objects, key, prefix):
        values = [o[key] for o in objects]
        check(len(values) == len(set(values)), f'duplicate {key}')
        check(all(re.fullmatch(prefix + r'[1-9][0-9]*', v) for v in values), f'invalid {key} format')
        return set(values)
    for key in ('case_id', 'conversation_id', 'input_completeness'):
        check(data[key] == input_data[key], f'{key}: differs from input')
    tasks = unique(data['tasks'], 'task_id', 'T')
    unique(data['issues'], 'issue_id', 'I')
    unique([e for issue in data['issues'] for e in issue['events']], 'event_id', 'E')
    check(bool(data['tasks']) or not any(m['role'] == 'User' for m in messages.values()), 'missing user tasks')
    for task in data['tasks']:
        for idx in task['user_message_indices']:
            index(idx, 'User', task['task_id'])
        evidence(task['evidence'], task['task_id'], True)
        for req in task['requirements']:
            index(req['introduced_at'], 'User', 'requirement')
            if req['changed_at'] is not None:
                index(req['changed_at'], 'User', 'requirement change')
                check(req['changed_at'] > req['introduced_at'], 'requirement change precedes introduction')
    if data['issues']:
        check(data['correction_observed'] is True, 'issues require correction_observed=true')
    if data['correction_observed'] is True:
        check(bool(data['issues']), 'true correction requires issues')
    if data['correction_observed'] is False:
        check(not data['issues'] and not data['unclassified_feedback'], 'false correction conflicts with issues/ambiguous feedback')
    if data['correction_observed'] is None:
        check(bool(data['unclassified_feedback']), 'null correction requires ambiguous feedback')
    for issue in data['issues']:
        check(issue['task_id'] in tasks, 'issue task does not exist')
        evidence(issue['evidence'], issue['issue_id'], True)
        check(bool(issue['events']), 'issue has no events')
        earlier = {}
        last_index = -1
        for event in issue['events']:
            eid, idx = event['event_id'], event['user_message_index']
            index(idx, 'User', eid)
            check(idx > last_index, f'{eid}: events not chronological')
            last_index = idx
            evidence(event['evidence'], eid, True)
            check(any(e['message_index'] == idx for e in event['evidence']), f'{eid}: lacks correction quote')
            previous = event['previous_event_id']
            relation = event['relation_to_previous']
            if relation == 'first_correction':
                check(previous is None and not earlier, f'{eid}: invalid first event')
            elif relation != 'uncertain':
                check(previous in earlier, f'{eid}: preceding same-issue event missing')
            if previous is not None:
                check(previous in earlier and earlier[previous] < idx, f'{eid}: invalid previous event')
            evidence(event['relation_evidence'], eid + ' relation', relation in ('repeated_unresolved', 'relapse_after_adjustment'))
            responses = event['agent_response_indices']
            check(len(responses) == len(set(responses)) and responses == sorted(responses), f'{eid}: duplicate/unordered responses')
            for response in responses:
                index(response, 'Agent', eid)
                check(response > idx, f'{eid}: response precedes correction')
            check(bool(responses) or event['adjustment'] == 'not_observable', f'{eid}: adjustment without response')
            evidence(event['adjustment_evidence'], eid + ' adjustment', event['adjustment'] != 'not_observable')
            check(all(e['message_index'] in responses for e in event['adjustment_evidence']), f'{eid}: adjustment evidence outside responses')
            earlier[eid] = idx
        recurrence = issue['recurrence']
        evidence(recurrence['evidence'], issue['issue_id'] + ' recurrence', recurrence['status'] in ('observed', 'not_observed'))
        if recurrence['status'] in ('observed', 'not_observed') and issue['events']:
            check(any(e['message_index'] in messages and messages[e['message_index']]['role'] == 'Agent'
                      and e['message_index'] > issue['events'][0]['user_message_index'] for e in recurrence['evidence']), 'recurrence lacks later Agent evidence')
    for feedback in data['unclassified_feedback']:
        index(feedback['user_message_index'], 'User', 'unclassified feedback')
        check(bool(feedback['reason'].strip()), 'ambiguous feedback requires reason')
        evidence(feedback['evidence'], 'unclassified feedback', True)
    for observation in data['sentiment_observations'] + [data['final_user_sentiment']]:
        idx = observation['user_message_index']
        if idx is not None:
            index(idx, 'User', 'sentiment')
        check(observation['task_id'] is None or observation['task_id'] in tasks, 'sentiment task missing')
        check(bool(observation['reason'].strip()), 'sentiment requires reason')
        evidence(observation['evidence'], 'sentiment', idx is not None)
        check(all(e['message_index'] == idx for e in observation['evidence']), 'sentiment evidence must quote observed User message')
    users = [i for i, m in messages.items() if m['role'] == 'User']
    agents = [i for i, m in messages.items() if m['role'] == 'Agent']
    last_user = max(users) if users else None
    final = data['final_user_sentiment']
    check(final['user_message_index'] == last_user, 'final sentiment must use last User')
    feedback = bool(users) and (not agents or max(users) > max(agents))
    check(final['feedback_after_last_agent'] == feedback, 'feedback_after_last_agent chronology mismatch')
    expected = 'not_observable' if last_user is None else ('uncertain' if final['label'] is None else ('observed' if final['label'] == 'negative' else 'not_observed'))
    check(final['negative_emotion'] == expected, 'negative_emotion mapping mismatch')
    if last_user is None:
        check(final['label'] is None, 'no User requires null sentiment')
    covered = {o['user_message_index'] for o in data['sentiment_observations']}
    required = {e['user_message_index'] for issue in data['issues'] for e in issue['events']}
    if last_user is not None:
        required.add(last_user)
    check(required <= covered, 'sentiment observations omit corrections or last User')
    return {'status': 'evidence_invalid' if errors else 'validated_pending_review', 'errors': errors,
            'semantic_review': 'pending; mechanical checks do not establish semantic accuracy'}



def validate_files(input_path, analysis_path, report_path=None):
    report = {'status': 'input_invalid', 'errors': []}
    try:
        input_data = strict_json(Path(input_path).read_text(encoding='utf-8'))
        validate_input(input_data)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        report['errors'].append(str(exc))
    else:
        report = {'status': 'output_invalid', 'errors': []}
        try:
            analysis = strict_json(Path(analysis_path).read_text(encoding='utf-8'))
        except (ValueError, OSError) as exc:
            report['errors'].append(str(exc))
        else:
            report = validate_analysis(analysis, input_data)
    report['versions'] = {'helper_sha256': digest(__file__), 'skill_hashes': skill_hashes(SKILL),
                          'contract_sha256': digest(CONTRACT)}
    report['files'] = {name: {'path': str(Path(path).resolve()),
                      'sha256': digest(path) if Path(path).is_file() else None}
                      for name, path in (('input', input_path), ('analysis', analysis_path))}
    if report_path is not None:
        target = Path(report_path)
        if target.resolve() in (Path(input_path).resolve(), Path(analysis_path).resolve()):
            raise ValueError('report cannot replace input or analysis')
        # Preserve every earlier report, including failures.
        with target.open('x', encoding='utf-8') as file:
            file.write(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare', help='extract full selected conversations; remove dataset labels')
    prep.add_argument('--manifest', type=Path, default=ROOT / 'case_manifest.jsonl')
    prep.add_argument('--pool', type=Path, default=ROOT / 'wildfeedback_candidates.jsonl')
    prep.add_argument('--output', type=Path, required=True)
    prep.add_argument('--cases', nargs='+', required=True)
    val = sub.add_parser('validate', help='check a saved judgment without changing it')
    val.add_argument('--input', type=Path, required=True)
    val.add_argument('--analysis', type=Path, required=True)
    val.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            if len(args.cases) != len(set(args.cases)):
                raise ValueError('duplicate selected case IDs')
            report = prepare(args.manifest, args.pool, args.output, args.cases)
        else:
            report = validate_files(args.input, args.analysis, args.report)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return int('status' in report and report['status'] != 'validated_pending_review')
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f'Dialogue tools error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
