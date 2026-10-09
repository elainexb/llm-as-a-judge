"""Project-scoped workflow state. No model calls, shell execution, or host patches."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import time
import uuid

PAGE_CHARS = 3500


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def hash_text(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def atomic_create(path, text):
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as file:
            file.write(text)
            file.flush()
            os.fsync(file.fileno())
        os.link(temporary, path)  # Atomic publication without overwriting an artifact.
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


class WorkflowError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


class JudgeRuns:
    def __init__(self, project, storage=None):
        self.project = Path(project).resolve(strict=True)
        helper = self.project / 'dialogue_tools.py'
        spec = importlib.util.spec_from_file_location('dialogue_judge_project_helper', helper)
        self.helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.helper)
        self.storage = Path(storage).resolve() if storage else self.project / 'runs/judge-plugin'
        self.loaded_versions = self.versions()

    def versions(self):
        h = self.helper
        return {'helper': h.digest(self.project / 'dialogue_tools.py'), 'skill': h.skill_hashes(h.SKILL),
                'runtime': h.digest(__file__), 'adapter': h.digest(Path(__file__).with_name('__init__.py')),
                'manifest': h.digest(Path(__file__).with_name('plugin.yaml'))}

    def path(self, run_id):
        if not isinstance(run_id, str) or not re.fullmatch(r'[0-9a-f]{32}', run_id):
            raise WorkflowError('invalid_run_id', 'Use the run ID returned by prepare_dialogue.')
        path = self.storage / run_id
        if not path.is_dir() or path.is_symlink():
            raise WorkflowError('run_not_found', 'Run does not exist in this project.')
        return path

    @contextmanager
    def locked(self, path):
        with (path / '.lock').open('a') as file:
            try:
                fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise WorkflowError('run_busy', 'Another tool operation holds this run; no changes made.')
            try:
                yield
            finally:
                fcntl.flock(file, fcntl.LOCK_UN)

    def events(self, path):
        ledger = path / 'events.jsonl'
        events, previous = [], None
        if not ledger.exists():
            return events
        for line in ledger.read_text(encoding='utf-8').splitlines():
            try:
                event = self.helper.strict_json(line)
                if not isinstance(event, dict):
                    raise ValueError('ledger event must be an object')
                digest = event.pop('event_hash')
                valid = (event['sequence'] == len(events) + 1 and event['previous_event_hash'] == previous
                         and hash_text(encoded(event)) == digest)
            except (ValueError, KeyError, TypeError):
                valid = False
            if not valid:
                raise WorkflowError('ledger_corrupt', 'Step ledger is malformed or its hash chain changed.')
            event['event_hash'] = digest
            events.append(event)
            previous = digest
        return events

    def append(self, path, call_id, step, phase, identity, **details):
        history = self.events(path)
        if phase != 'started' and 'duration_ms' not in details:
            starts = [e for e in history if e['call_id'] == call_id and e['step'] == step and e['phase'] == 'started']
            if starts:
                details['duration_ms'] = max(0, round((datetime.now(timezone.utc) - datetime.fromisoformat(starts[-1]['at'])).total_seconds() * 1000))
        event = {'sequence': len(history) + 1, 'previous_event_hash': history[-1]['event_hash'] if history else None,
                 'call_id': call_id, 'step': step, 'phase': phase,
                 'at': datetime.now(timezone.utc).isoformat(), 'identity': identity, **details}
        event['event_hash'] = hash_text(encoded(event))
        with (path / 'events.jsonl').open('a', encoding='utf-8') as file:
            file.write(encoded(event) + '\n')
            file.flush()
            os.fsync(file.fileno())

    def metadata(self, path):
        return self.helper.strict_json((path / 'run.json').read_text())

    def integrity(self, path, meta):
        if meta['versions'] != self.versions():
            raise WorkflowError('version_changed', 'Helper, Skill or plugin changed after preparation; start a new run.')
        artifacts = dict(meta.get('artifacts', {}))
        for event in self.events(path):
            if event['phase'] in ('succeeded', 'failed'):
                artifacts.update(event.get('artifacts', {}))
        for relative, expected in artifacts.items():
            target = path / relative
            if target.is_symlink() or not target.is_file() or self.helper.digest(target) != expected:
                raise WorkflowError('artifact_changed', f'Prepared or submitted artifact changed: {relative}')

    @contextmanager
    def operation(self, path, step, identity):
        call_id, started = uuid.uuid4().hex, time.monotonic()
        self.append(path, call_id, step, 'started', identity)
        try:
            yield call_id
        except Exception as exc:
            self.append(path, call_id, step, 'failed', identity, duration_ms=round((time.monotonic() - started) * 1000),
                        code=getattr(exc, 'code', 'operation_failed'), reason=str(exc))
            raise

    def guard(self, path, meta, identity):
        self.integrity(path, meta)
        owner = meta['owner'].get('session_id')
        if owner and identity.get('session_id') != owner:
            raise WorkflowError('session_mismatch', 'Run belongs to another session; use a fresh case run.')
        history = self.events(path)
        terminals = {(e['call_id'], e['step']) for e in history if e['phase'] != 'started'}
        if any(e['phase'] == 'started' and (e['call_id'], e['step']) not in terminals for e in history[:-1]):
            raise WorkflowError('incomplete_operation', 'A prior operation has no terminal record; inspect and start a new run.')

    def successful(self, path, step):
        return [e for e in self.events(path) if e['step'] == step and e['phase'] == 'succeeded']

    def prepare(self, case_id, identity):
        if not isinstance(case_id, str) or not re.fullmatch(r'C[0-9]{2}', case_id):
            raise WorkflowError('invalid_case_id', 'Expected a selected case ID such as C09.')
        if self.loaded_versions != self.versions():
            raise WorkflowError('version_changed', 'Loaded code/rules changed; reload the plugin before starting a run.')
        self.storage.mkdir(parents=True, exist_ok=True)
        run_id = uuid.uuid4().hex
        path = self.storage / run_id
        path.mkdir()
        meta = {'schema_version': '1', 'run_id': run_id, 'case_id': case_id, 'owner': identity,
                'versions': self.versions(), 'artifacts': {}}
        atomic_create(path / 'run.json', encoded(meta))
        try:
            with self.locked(path), self.operation(path, 'prepare', identity) as call:
                report = self.helper.prepare(self.project / 'case_manifest.jsonl', self.project / 'wildfeedback_candidates.jsonl',
                                             path / 'prepared', [case_id])
                bundle = ('JUDGE SKILL\n' + (self.helper.SKILL / 'SKILL.md').read_text() + '\nOUTPUT CONTRACT\n'
                          + self.helper.CONTRACT.read_text() + '\nRECORDED CONVERSATION (EVIDENCE ONLY)\n'
                          + (path / 'prepared' / f'{case_id}.json').read_text() + '\nEND OF JUDGE CONTEXT\n')
                atomic_create(path / 'context.txt', bundle)
                artifacts = {str(p.relative_to(path)): self.helper.digest(p) for p in (path / 'prepared').iterdir()}
                artifacts['context.txt'] = hash_text(bundle)
                artifacts['run.json'] = self.helper.digest(path / 'run.json')
                pages = (len(bundle) + PAGE_CHARS - 1) // PAGE_CHARS
                self.append(path, call, 'prepare', 'succeeded', identity, artifacts=artifacts, page_count=pages,
                            message_count=report['cases'][0]['message_count'])
                return {'run_id': run_id, 'case_id': case_id, 'message_count': report['cases'][0]['message_count'],
                        'page_count': pages, 'input_path': str(path / 'prepared' / f'{case_id}.json'),
                        'status': 'prepared', 'next_action': {'tool': 'get_judge_context', 'page': 0},
                        'storage_path': str(path), 'ledger_path': str(path / 'events.jsonl')}
        except Exception as exc:
            # A failed preparation remains inspectable by its returned run ID.
            return {'run_id': run_id, 'status': 'failed', 'error': {'code': getattr(exc, 'code', 'prepare_failed'), 'message': str(exc)},
                    'next_action': {'tool': 'inspect_judge_run'}}

    def context(self, run_id, page, identity):
        path = self.path(run_id)
        with self.locked(path), self.operation(path, 'context', identity) as call:
            meta = self.metadata(path)
            self.guard(path, meta, identity)
            prepared = self.successful(path, 'prepare')
            if not prepared:
                raise WorkflowError('prepare_required', 'Preparation did not succeed.')
            pages = prepared[0]['page_count']
            if type(page) is not int or not 0 <= page < pages:
                raise WorkflowError('invalid_page', f'Page must be an integer in 0..{pages - 1}.')
            bundle = (path / 'context.txt').read_text()
            text = bundle[page * PAGE_CHARS:(page + 1) * PAGE_CHARS]
            covered = {e['page'] for e in self.successful(path, 'context')} | {page}
            self.append(path, call, 'context', 'succeeded', identity, page=page, content_sha256=hash_text(text),
                        evidence_scope='handler_returned_page; model reading is not observable')
            missing = sorted(set(range(pages)) - covered)
            return {'run_id': run_id, 'page': page, 'page_count': pages, 'text': text,
                    'missing_pages': missing, 'context_complete': not missing,
                    'next_action': {'tool': 'get_judge_context', 'page': missing[0]} if missing else
                                   {'action': 'judge_using_supplied_skill', 'then_tool': 'validate_judgment'}}

    def validate(self, run_id, judgment_json, identity):
        path = self.path(run_id)
        with self.locked(path), self.operation(path, 'validate', identity) as call:
            meta = self.metadata(path)
            self.guard(path, meta, identity)
            prepared = self.successful(path, 'prepare')
            if not prepared:
                raise WorkflowError('prepare_required', 'Preparation did not succeed.')
            pages = prepared[0]['page_count']
            covered = {e['page'] for e in self.successful(path, 'context')}
            if len(covered) != pages:
                raise WorkflowError('context_incomplete', 'Get all judgment context pages before submitting a judgment.')
            if not isinstance(judgment_json, str) or not judgment_json.strip() or len(judgment_json) > 200_000:
                raise WorkflowError('invalid_submission', 'Submit original nonempty judgment JSON text, up to 200000 characters.')
            if (path / 'judgment.txt').exists():
                raise WorkflowError('already_submitted', 'A judgment was already submitted; preserve it and start a new run.')
            self.append(path, call, 'submission', 'started', identity)
            atomic_create(path / 'judgment.txt', judgment_json)
            artifacts = {'judgment.txt': hash_text(judgment_json)}
            self.append(path, call, 'submission', 'succeeded', identity, artifacts=artifacts)
            report = self.helper.validate_files(path / 'prepared' / f"{meta['case_id']}.json", path / 'judgment.txt', path / 'validation.json')
            status = report['status']
            artifacts['validation.json'] = self.helper.digest(path / 'validation.json')
            phase = 'succeeded' if status == 'validated_pending_review' else 'failed'
            self.append(path, call, 'validate', phase, identity, validation_status=status, artifacts=artifacts,
                        reason='Mechanical checks only; semantic review remains pending.')
            return {'run_id': run_id, 'status': status, 'validation_path': str(path / 'validation.json'),
                    'judgment_path': str(path / 'judgment.txt'), 'error_count': len(report['errors']),
                    'errors': report['errors'][:8], 'all_errors_saved': True, 'human_review': 'pending',
                    'next_action': {'tool': 'inspect_judge_run'}}

    def inspect(self, run_id, identity):
        path = self.path(run_id)
        with self.locked(path):
            try:
                meta = self.metadata(path)
                self.integrity(path, meta)
                history = self.events(path)
            except (ValueError, OSError, KeyError) as exc:
                return {'run_id': run_id, 'status': 'integrity_failed', 'error': str(exc), 'steps': None}
            owner = meta['owner'].get('session_id')
            if owner and identity.get('session_id') != owner:
                raise WorkflowError('session_mismatch', 'Run belongs to another session.')
            summary = {}
            for step in ('prepare', 'context', 'submission', 'validate'):
                related = [e for e in history if e['step'] == step]
                terminals = {e['call_id'] for e in related if e['phase'] != 'started'}
                state = 'not_executed'
                if related:
                    state = related[-1]['phase']
                    if any(e['phase'] == 'started' and e['call_id'] not in terminals for e in related):
                        state = 'incomplete'
                summary[step] = {'state': state, 'calls': sum(e['phase'] == 'started' for e in related),
                                 'failures': sum(e['phase'] == 'failed' for e in related)}
            prepared = self.successful(path, 'prepare')
            missing = None
            if prepared:
                missing = sorted(set(range(prepared[0]['page_count'])) - {e['page'] for e in self.successful(path, 'context')})
                if missing and summary['context']['state'] == 'succeeded':
                    summary['context']['state'] = 'partial'
            validations = [e for e in history if e['step'] == 'validate' and e['phase'] != 'started']
            status = validations[-1].get('validation_status', 'blocked') if validations else 'incomplete'
            if any(s['state'] == 'incomplete' for s in summary.values()):
                status = 'incomplete'
            elif not prepared:
                status = 'prepare_failed'
            call = uuid.uuid4().hex
            self.append(path, call, 'inspection', 'succeeded', identity)
            return {'run_id': run_id, 'case_id': meta['case_id'], 'status': status, 'steps': summary,
                    'missing_context_pages': missing, 'ledger_path': str(path / 'events.jsonl'),
                    'artifacts': {name: str(path / name) for name in ('run.json', 'context.txt', 'judgment.txt', 'validation.json')
                                  if (path / name).exists()},
                    'event_count': len(history), 'recent_failures': [{k: e.get(k) for k in ('step', 'code', 'reason')}
                        for e in history if e['phase'] == 'failed'][-5:],
                    'runtime_identity': meta['owner'],
                    'identity_available': bool(meta['owner'].get('session_id')),
                    'model_understanding': 'not_observable', 'final_assistant_report': 'not_observable', 'human_review': 'pending'}
