"""Fail-closed D1 delta publishing and transaction assertions."""

import json
import hashlib
from pathlib import Path
import random
import re
import time

if __package__:
    from . import sync_snapshot as snapshots
    from . import upload_to_d1 as legacy
else:
    import sync_snapshot as snapshots
    import upload_to_d1 as legacy


RELEASE_FIELDS = (
    'upstream_sha', 'data_hash', 'source_data_hash', 'worker_version', 'status',
    'oier_count', 'contest_count', 'school_count', 'record_count',
    'snapshot_commit', 'snapshot_sha256', 'projection_version', 'logical_data_hash', 'core_revision',
)
SNAPSHOT_FIELDS = ('snapshot_commit', 'snapshot_sha256', 'projection_version', 'logical_data_hash', 'core_revision')
COUNT_FIELDS = {'OIer': 'oier_count', 'Contest': 'contest_count', 'School': 'school_count', 'Record': 'record_count'}
INDEXES = {
    'OIer': [('gender', 'enroll_middle', 'uid'), ('initials', 'uid')],
    'Contest': [('year', 'type', 'id')],
    'School': [],
    'Record': [('oier_uid', 'contest_id', 'level', 'score', 'rank', 'province', 'school_id'),
               ('contest_id', 'level', 'oier_uid'), ('school_id', 'province', 'level', 'oier_uid')],
}
INDEX_NAMES = {
    'OIer': ('idx_oier_gender_enroll', 'idx_oier_initials_uid'),
    'Contest': ('idx_contest_year_type',),
    'School': (),
    'Record': ('idx_record_oier_covering', 'idx_record_contest_level_uid', 'idx_record_school_province_level_uid'),
}
MIGRATION = snapshots.ROOT / 'cloudflare/migrations/0004_incremental_sync.sql'
JSON_ROWS_PER_STATEMENT = 250
MAX_JSON_VALUE_BYTES = 2000000
PAYLOAD_MIGRATION = snapshots.ROOT / 'cloudflare/migrations/0005_staged_sync_payloads.sql'
# Transport packing thresholds, never row or release quotas.
STAGED_REQUEST_BYTES = 1000000
PAYLOAD_UPLOAD_BYTES = 256000


class SyncError(RuntimeError):
    def __init__(self, message, *, result=None):
        super().__init__(message)
        self.result = result


def expected_triggers():
    return dict(re.findall(r'CREATE TRIGGER (\w+) (.*?\bEND);', MIGRATION.read_text(), re.DOTALL))


def normalized_sql(sql):
    return ' '.join(sql.strip().rstrip(';').split())


class D1Client:
    def __init__(self, cfg):
        self.cfg = cfg

    def identity(self):
        return {key: self.cfg['cloudflare'][key] for key in ('account_id', 'database_id')}

    def query(self, sql, params=()):
        payload = {'sql': sql, 'params': list(params)}
        data = legacy._execute_d1_request(self.cfg, 'query', payload)
        if len(data['result']) != 1:
            raise SyncError('Unexpected D1 query response')
        return data['result'][0].get('results', [])

    def batch(self, statements):
        return legacy.execute_d1_batch(self.cfg, statements)

    def upload_payloads(self, statements):
        return self.batch(statements)

    def payloads_ready(self):
        rows = self.query("SELECT name,type,sql FROM sqlite_master WHERE (name='OierSyncPayload' AND type='table') OR (tbl_name='OierSyncPayload' AND type='trigger')")
        if not rows:
            return False
        source = PAYLOAD_MIGRATION.read_text()
        expected = {'OierSyncPayload': re.search(r'CREATE TABLE OierSyncPayload .*?;', source, re.DOTALL).group(0)}
        expected.update({name: f'CREATE TRIGGER {name} {body}' for name, body in
                         re.findall(r'CREATE TRIGGER (\w+) (.*?\bEND);', source, re.DOTALL)})
        if {row['name'] for row in rows} != expected.keys() or any(
            normalized_sql(row['sql']) != normalized_sql(expected[row['name']]) for row in rows
        ):
            raise SyncError('Staged payload schema differs from its immutable definition')
        return True

    def stage_payloads(self, release_id, payloads):
        if not self.payloads_ready():
            raise SyncError('Staged payload migration is required before publication')
        groups, group, size = [], [], 0
        for digest, body in payloads.items():
            item = statement('INSERT INTO OierSyncPayload(release_id,digest,body) VALUES(?,?,?) ON CONFLICT(release_id,digest) DO NOTHING',
                             [release_id, digest, body])
            item_size = len(legacy.encode_d1_payload(item))
            if group and (size + item_size > PAYLOAD_UPLOAD_BYTES or len(group) >= 50):
                groups.append(group)
                group, size = [], 0
            group.append(item)
            size += item_size
        if group:
            groups.append(group)
        for group in groups:
            digests = [item['params'][1] for item in group]
            for attempt in range(1, 4):
                try:
                    # Immutable INSERT-or-ignore is idempotent even after a lost
                    # upload acknowledgement. Core tables are not involved.
                    self.upload_payloads(group)
                    rows = self.query('SELECT digest,body FROM OierSyncPayload WHERE release_id=? AND digest IN (' +
                                      ','.join('?' for _ in digests) + ')', [release_id] + digests)
                except Exception as error:
                    if attempt < 3 and legacy.is_retryable_d1_error(error):
                        time.sleep(2 ** attempt + random.uniform(0, 1))
                        continue
                    raise SyncError(f'Payload staging failed before any core writes: {error}',
                        result={'status': 'blocked', 'publication_attempted': False, 'staging_attempts': attempt,
                                'error': str(error),
                                'recovery_action': 'Keep core data unchanged; retry staging after Cloudflare recovers.'}) from error
                break
            observed = {row['digest']: row['body'] for row in rows}
            if observed != {digest: payloads[digest] for digest in digests}:
                raise SyncError('Staged payload read-back differs from the validated archive')
        if not self.payloads_ready():
            raise SyncError('Staged payload schema disappeared before publication')

    def release(self):
        return legacy.get_release(self.cfg)

    def revision(self):
        rows = self.query('SELECT revision,writing FROM OierSyncState WHERE id=1')
        if len(rows) != 1 or type(rows[0]['revision']) is not int or not 0 <= rows[0]['revision'] <= 9007199254740991:
            raise SyncError('Invalid core-data revision; publishing stopped')
        if rows[0]['writing'] != 0:
            raise SyncError('Core write gate was left open outside a publishing transaction; audit required')
        return rows[0]['revision']

    def current(self, allow_legacy=False):
        release = self.release()
        validate_release(release)
        schema = self.query("SELECT name,type,sql FROM sqlite_master WHERE name IN ('OierSyncState','OierSyncGuard','OierSyncBudget') OR (type='trigger' AND tbl_name IN ('OIer','Contest','School','Record','DataRelease','OierSyncState','OierSyncGuard','OierSyncBudget'))")
        if not schema:
            if allow_legacy and not any(release.get(k) is not None for k in SNAPSHOT_FIELDS):
                return release, None
            raise SyncError('Incremental migrations are required')
        tables = {r['name'] for r in schema if r['type'] == 'table'}
        triggers = {r['name']: r['sql'] for r in schema if r['type'] == 'trigger'}
        expected = expected_triggers()
        if tables != {'OierSyncState', 'OierSyncGuard', 'OierSyncBudget'} or triggers.keys() != expected.keys():
            raise SyncError('Incomplete sync schema or revision triggers; publishing stopped')
        expected_tables = {name: f'CREATE TABLE {name} {body}' for name, body in
                           re.findall(r'CREATE TABLE (OierSync\w+) (\(.*?\));', MIGRATION.read_text(), re.DOTALL)}
        for row in schema:
            if row['type'] == 'table' and normalized_sql(row['sql']) != normalized_sql(expected_tables[row['name']]):
                raise SyncError(f'Unexpected sync table definition: {row["name"]}')
        for name, body in expected.items():
            if normalized_sql(triggers[name]) != normalized_sql(f'CREATE TRIGGER {name} {body}'):
                raise SyncError(f'Unexpected revision trigger: {name}')
        index_rows = self.query("SELECT name,tbl_name,sql FROM sqlite_master WHERE type='index' AND tbl_name IN ('OIer','Contest','School','Record')")
        expected_indexes = {name: (table, columns) for table, names in INDEX_NAMES.items()
                            for name, columns in zip(names, INDEXES[table])}
        if {row['name'] for row in index_rows} != expected_indexes.keys():
            raise SyncError('Core indexes differ from the expected schema; do not rebuild indexes automatically')
        for row in index_rows:
            table, columns = expected_indexes[row['name']]
            match = re.search(r'\bON\s+["\[]?(\w+)["\]]?\s*\(([^)]+)\)', row['sql'] or '', re.IGNORECASE)
            actual = tuple(col.strip().strip('"[]`').lower() for col in match.group(2).split(',')) if match else ()
            if not match or match.group(1).lower() != table.lower() or actual != columns:
                raise SyncError(f'Unexpected index definition: {row["name"]}')
        revision = self.revision()
        if release.get('snapshot_commit'):
            if not all(release.get(k) is not None for k in SNAPSHOT_FIELDS):
                raise SyncError('Incomplete published snapshot identity')
            if release['core_revision'] != revision:
                raise SyncError('Core data changed outside its published snapshot; an explicit audit is required')
            if not snapshots.SHA.fullmatch(release['snapshot_commit']):
                raise SyncError('Invalid published snapshot commit')
            for field in ('snapshot_sha256', 'logical_data_hash'):
                if not snapshots.HASH.fullmatch(release[field]):
                    raise SyncError(f'Invalid published {field}')
        elif any(release.get(k) is not None for k in SNAPSHOT_FIELDS):
            raise SyncError('Partial snapshot identity; publishing stopped')
        return release, revision


def validate_release(release):
    if not release or release.get('status') != 'active':
        raise SyncError('An existing active production release is required; no automatic full upload is allowed')
    if not snapshots.SHA.fullmatch(release.get('upstream_sha', '')):
        raise SyncError('Invalid active source SHA')
    if not snapshots.HASH.fullmatch(release.get('source_data_hash') or ''):
        raise SyncError('An audited active source fingerprint is required')
    if any(type(release.get(field)) is not int or release[field] <= 0 for field in COUNT_FIELDS.values()):
        raise SyncError('Invalid published row counts')


def release_identity(release):
    return {field: release.get(field) for field in RELEASE_FIELDS}


def assert_manifest_matches(release, manifest):
    expected = {
        'data_hash': release['data_hash'],
        'archive_sha256': release['snapshot_sha256'],
        'logical_data_hash': release['logical_data_hash'],
        'projection_version': release['projection_version'],
        'source_data_hash': release['source_data_hash'],
        'row_counts': {table: release[field] for table, field in COUNT_FIELDS.items()},
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise SyncError('Archived snapshot does not match the active D1 release')
    # upstream_sha can advance without changing data; the manifest retains origin.


def diff_states(old, new):
    patch, summary = {}, {}
    for table, _ in legacy.TABLES:
        a, b = old[table], new[table]
        inserts = [b[k] for k in sorted(b.keys() - a.keys())]
        deletes = [a[k] for k in sorted(a.keys() - b.keys())]
        updates = []
        for key in sorted(a.keys() & b.keys()):
            changed = [col for col in b[key] if a[key][col] != b[key][col]]
            if changed:
                updates.append({'old': a[key], 'new': b[key], 'changed': changed})
        patch[table] = {'insert': inserts, 'delete': deletes, 'update': updates}
        summary[table] = {name: len(rows) for name, rows in patch[table].items()}
    return patch, summary


def estimate_writes(patch):
    # Table + revision trigger + two assertion writes, plus conservative index
    # delete/insert costs. Per-row assertion costs conservatively overestimate
    # compact batches. This is audit telemetry, never a publishing limit.
    estimate, operations = 20, 0
    for table, changes in patch.items():
        for kind, rows in changes.items():
            for row in rows:
                operations += 1
                if kind == 'update':
                    affected = sum(bool(set(index) & set(row['changed'])) for index in INDEXES[table])
                    estimate += 4 + 2 * affected
                else:
                    estimate += 4 + len(INDEXES[table]) + int(table == 'Record' and kind == 'insert')
    return operations, estimate


def statement(sql, params=()):
    return {'sql': sql, 'params': list(params)}


def assertion(predicate, params=()):
    return statement(
        'INSERT INTO OierSyncGuard(id,ok) VALUES(1,CASE WHEN (' + predicate +
        ') THEN 1 ELSE 0 END) ON CONFLICT(id) DO UPDATE SET ok=excluded.ok', params,
    )


def release_assertion(base, revision):
    conditions = ['id=1'] + [f'{field} IS ?' for field in RELEASE_FIELDS]
    return assertion(
        f'EXISTS(SELECT 1 FROM DataRelease WHERE {" AND ".join(conditions)}) '
        'AND (SELECT revision FROM OierSyncState WHERE id=1) IS ? '
        'AND (SELECT writing FROM OierSyncState WHERE id=1)=0',
        [base.get(field) for field in RELEASE_FIELDS] + [revision],
    )


def json_rows(rows, columns=None):
    if columns is not None:
        rows = [[row[col] for col in columns] for row in rows]
    return json.dumps(rows, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def mutation_chunks(kind, rows):
    """Pack parameters under D1's string limit without limiting the release."""
    chunk, before_bytes, after_bytes = [], 2, 2
    for row in rows:
        before = row['old'] if kind == 'update' else row if kind == 'delete' else None
        after = row['new'] if kind == 'update' else row if kind == 'insert' else None
        old_bytes = len(json_rows(list(before.values())).encode()) if before is not None else 0
        new_bytes = len(json_rows(list(after.values())).encode()) if after is not None else 0
        if max(old_bytes, new_bytes) + 2 > MAX_JSON_VALUE_BYTES:
            raise SyncError('A row exceeds the D1 JSON parameter size limit')
        separator = int(bool(chunk))
        if chunk and (len(chunk) >= JSON_ROWS_PER_STATEMENT or
                      max(before_bytes + old_bytes + separator, after_bytes + new_bytes + separator) > MAX_JSON_VALUE_BYTES):
            yield chunk
            chunk, before_bytes, after_bytes, separator = [], 2, 2, 0
        chunk.append(row)
        before_bytes += old_bytes + separator
        after_bytes += new_bytes + separator
    if chunk:
        yield chunk


def mutation_statements(table, kind, rows):
    """Three compact statements per group, retaining every row's assertions."""
    statements, groups = [], {}
    for row in rows:
        changed = tuple(row['changed']) if kind == 'update' else ()
        groups.setdefault(changed, []).append(row)
    def matches(columns, selected=None):
        return ' AND '.join(f"{table}.{col} IS json_extract(src.value,'$[{columns.index(col)}]')"
                            for col in (selected or columns))
    for changed, group in groups.items():
        for chunk in mutation_chunks(kind, group):
            before = [row['old'] for row in chunk] if kind == 'update' else chunk if kind == 'delete' else None
            after = [row['new'] for row in chunk] if kind == 'update' else chunk if kind == 'insert' else None
            old_columns = list(before[0]) if before is not None else None
            new_columns = list(after[0]) if after is not None else None
            before_json = json_rows(before, old_columns) if before is not None else None
            after_json = json_rows(after, new_columns) if after is not None else None
            if before is not None:
                key_where = matches(old_columns, snapshots.KEYS[table])
                old_where = matches(old_columns)
                statements.append(assertion(
                    f'NOT EXISTS(SELECT 1 FROM json_each(?) AS src WHERE '
                    f'(SELECT COUNT(*) FROM {table} WHERE {key_where})!=1 OR '
                    f'NOT EXISTS(SELECT 1 FROM {table} WHERE {old_where}))', [before_json]))
            else:
                key_where = matches(new_columns, snapshots.KEYS[table])
                statements.append(assertion(
                    f'NOT EXISTS(SELECT 1 FROM json_each(?) AS src WHERE EXISTS('
                    f'SELECT 1 FROM {table} WHERE {key_where}))', [after_json]))
            if kind == 'delete':
                id_col = 'uid' if table == 'OIer' else 'id'
                statements.append(statement(
                    f'DELETE FROM {table} WHERE {id_col} IN (SELECT {table}.{id_col} '
                    f'FROM json_each(?) AS src JOIN {table} ON {key_where})', [before_json]))
                statements.append(assertion(
                    f'changes()=? AND NOT EXISTS(SELECT 1 FROM json_each(?) AS src '
                    f'WHERE EXISTS(SELECT 1 FROM {table} WHERE {key_where}))', [len(chunk), before_json]))
            else:
                key_where = matches(new_columns, snapshots.KEYS[table])
                if kind == 'insert':
                    values = ','.join(f"json_extract(src.value,'$[{index}]')" for index in range(len(new_columns)))
                    sql = f'INSERT INTO {table} ({",".join(new_columns)}) SELECT {values} FROM json_each(?) AS src'
                else:
                    updates = ','.join(f"{col}=json_extract(src.value,'$[{new_columns.index(col)}]')" for col in changed)
                    sql = f'UPDATE {table} SET {updates} FROM json_each(?) AS src WHERE {key_where}'
                statements.append(statement(sql, [after_json]))
                new_where = matches(new_columns)
                statements.append(assertion(
                    f'changes()=? AND NOT EXISTS(SELECT 1 FROM json_each(?) AS src WHERE '
                    f'(SELECT COUNT(*) FROM {table} WHERE {key_where})!=1 OR '
                    f'NOT EXISTS(SELECT 1 FROM {table} WHERE {new_where}))', [len(chunk), after_json]))
    return statements


def publication_values(manifest, commit, *, source_sha, source_hash, worker_version, run_url, revision):
    if not snapshots.SHA.fullmatch(commit or '') or not snapshots.SHA.fullmatch(source_sha or ''):
        raise SyncError('Invalid publication commit identity')
    if source_hash != manifest['source_data_hash'] or not snapshots.HASH.fullmatch(source_hash or ''):
        raise SyncError('Publication source fingerprint differs from its archive')
    if type(revision) is not int or revision < 0:
        raise SyncError('Invalid publication core revision')
    return {
        'upstream_sha': source_sha,
        'data_hash': manifest['data_hash'],
        'source_data_hash': source_hash,
        'worker_version': worker_version,
        'status': 'active',
        **{field: manifest['row_counts'][table] for table, field in COUNT_FIELDS.items()},
        'snapshot_commit': commit,
        'snapshot_sha256': manifest['archive_sha256'],
        'projection_version': manifest['projection_version'],
        'logical_data_hash': manifest['logical_data_hash'],
        'core_revision': revision,
        'github_run_url': run_url,
    }


def release_update(values, activate):
    keys = list(values)
    return statement('UPDATE DataRelease SET ' + ', '.join(key + '=?' for key in keys) +
                     ', updated_at=CURRENT_TIMESTAMP' +
                     (', activated_at=CURRENT_TIMESTAMP' if activate else '') + ' WHERE id=1', list(values.values()))


def validate_packet(statements):
    for item in statements:
        if len(item['sql'].encode('utf-8')) > 100000 or len(item['params']) > 100:
            raise SyncError('Delta exceeds a D1 statement limit; publishing stopped')


def build_transaction(base, base_revision, patch, target):
    if set(target) != set(RELEASE_FIELDS) | {'github_run_url'}:
        raise SyncError('Unexpected publication metadata fields')
    operations, estimate = estimate_writes(patch)
    if target['core_revision'] != base_revision + operations:
        raise SyncError('Incorrect target core revision')
    commands = [release_assertion(base, base_revision),
        statement('UPDATE OierSyncState SET writing=1 WHERE id=1 AND writing=0'),
        assertion('changes()=1 AND (SELECT writing FROM OierSyncState WHERE id=1)=1')]
    for table in ('School', 'Contest', 'OIer'):
        for kind in ('insert', 'update'):
            commands.extend(mutation_statements(table, kind, patch[table][kind]))
    for kind in ('delete', 'update', 'insert'):
        commands.extend(mutation_statements('Record', kind, patch['Record'][kind]))
    for table in ('OIer', 'Contest', 'School'):
        commands.extend(mutation_statements(table, 'delete', patch[table]['delete']))
    commands += [
        assertion('(SELECT revision FROM OierSyncState WHERE id=1) IS ?', [target['core_revision']]),
        statement('UPDATE OierSyncState SET writing=0 WHERE id=1 AND writing=1'),
        assertion('changes()=1 AND (SELECT writing FROM OierSyncState WHERE id=1)=0'),
        statement("INSERT INTO OierSyncBudget(day,estimated_writes) VALUES(date('now'),?) ON CONFLICT(day) DO UPDATE SET estimated_writes=estimated_writes+excluded.estimated_writes", [estimate]),
        release_update(target, activate=operations > 0),
        release_assertion(target, target['core_revision']),
    ]
    validate_packet(commands)
    return commands


def prepare_transport(base, revision, target, commands):
    if len(legacy.encode_d1_payload({'batch': commands})) <= STAGED_REQUEST_BYTES:
        return commands, {}, None
    release_id = hashlib.sha256(f"{base['snapshot_commit']}:{revision}:{target['snapshot_commit']}".encode()).hexdigest()
    rewritten, payloads = [], {}
    for item in commands:
        sql, params = item['sql'], list(item['params'])
        if 'json_each(?)' in sql:
            bindings = [index for index, value in enumerate(params) if isinstance(value, str) and value.startswith('[')]
            if len(bindings) != 1:
                raise SyncError('Unexpected compact payload bindings')
            index = bindings[0]
            body = params[index]
            digest = hashlib.sha256(body.encode()).hexdigest()
            payloads[digest] = body
            position = [match.start() for match in re.finditer(r'\?', sql)][index]
            sql = sql[:position] + '(SELECT body FROM OierSyncPayload WHERE release_id=? AND digest=?)' + sql[position + 1:]
            params[index:index + 1] = [release_id, digest]
        rewritten.append(statement(sql, params))
    closing = next(index for index, item in enumerate(rewritten) if item['sql'].startswith('UPDATE OierSyncState SET writing=0'))
    rewritten.insert(closing, statement("DELETE FROM OierSyncPayload WHERE release_id=? OR created_at<datetime('now','-7 days')", [release_id]))
    validate_packet(rewritten)
    return rewritten, payloads, release_id


def publish(client, base, base_revision, patch, target):
    # Retry only a known transient error after read-back proved no commit.
    # The transaction's base/revision guard also protects against a late commit.
    for attempt in range(1, 4):
        try:
            result = _publish_once(client, base, base_revision, patch, target)
        except Exception as error:
            outcome = getattr(error, 'result', None)
            if outcome:
                outcome['attempts'] = attempt
                if attempt > 1:
                    outcome['publication_attempted'] = True
            elif attempt > 1:
                raise SyncError(
                    'Cannot verify the release before retrying; no further writes were attempted.',
                    result={'status': 'outcome_unknown', 'publication_attempted': True,
                            'attempts': attempt - 1, 'error': str(error),
                            'recovery_action': 'Verify the active D1 release before another publication.'},
                ) from error
            cause = error.__cause__
            if (attempt == 3 or not outcome or outcome['status'] != 'not_committed'
                    or not legacy.is_retryable_d1_error(cause)):
                raise
            time.sleep(2 ** attempt + random.uniform(0, 1))
        else:
            result['attempts'] = attempt
            return result


def _publish_once(client, base, base_revision, patch, target):
    if target.get('snapshot_commit') == '0' * 40:
        raise SyncError('Unarchived candidate cannot be published')
    current, revision = client.current()
    if release_identity(current) == release_identity(target):
        return {'status': 'already_applied', 'core_revision': revision}
    if release_identity(current) != release_identity(base) or revision != base_revision:
        raise SyncError('Active release changed after planning; refusing a stale delta',
            result={'status': 'conflict', 'publication_attempted': False,
                    'core_revision': revision, 'active_snapshot_commit': current['snapshot_commit'],
                    'error': 'The planned base release is stale.',
                    'recovery_action': 'Rerun inspection and planning from the active release.'})
    commands = build_transaction(base, base_revision, patch, target)
    commands, payloads, release_id = prepare_transport(base, base_revision, target, commands)
    if payloads:
        client.stage_payloads(release_id, payloads)
    batch_error = None
    try:
        response = client.batch(commands)
    except Exception as error:
        batch_error = error
    # Read after either success or failure. A missing acknowledgement is never
    # grounds to resend the write, and a failed verification is not a rollback.
    try:
        actual, revision = client.current()
    except Exception as verification_error:
        raise SyncError(
            'Publish outcome is unknown. Re-read DataRelease before any retry; no further writes were attempted.',
            result={'status': 'outcome_unknown', 'publication_attempted': True,
                    'error': str(batch_error or verification_error),
                    'verification_error': str(verification_error),
                    'recovery_action': 'Verify the active D1 release before another publication.'},
        ) from (batch_error or verification_error)
    if release_identity(actual) == release_identity(base) and revision == base_revision:
        raise SyncError(
            'Publish did not commit; the previous release and snapshot remain active',
            result={'status': 'not_committed', 'publication_attempted': True,
                    'core_revision': revision, 'active_snapshot_commit': actual['snapshot_commit'],
                    'error': str(batch_error) if batch_error else 'D1 did not activate the target release.',
                    'recovery_action': 'Keep the current release; the next run will inspect and plan again.'},
        ) from batch_error
    if release_identity(actual) != release_identity(target):
        raise SyncError(
            'Unexpected release after publication; stop and audit before retrying',
            result={'status': 'conflict', 'publication_attempted': True,
                    'core_revision': revision, 'active_snapshot_commit': actual['snapshot_commit'],
                    'error': str(batch_error) if batch_error else 'D1 release differs from both base and target.',
                    'recovery_action': 'Audit the active release before another publication.'},
        ) from batch_error
    if batch_error is not None:
        return {'status': 'committed_response_lost', 'core_revision': revision}
    results = response.get('result', []) if isinstance(response, dict) else []
    if not isinstance(results, list) or len(results) != len(commands) or any(
        not isinstance(r, dict) or not r.get('success') for r in results
    ):
        # The committed marker is authoritative even if response telemetry is absent.
        return {'status': 'committed_telemetry_incomplete', 'core_revision': revision}
    try:
        rows_read = sum(r.get('meta', {}).get('rows_read', 0) for r in results)
        rows_written = sum(r.get('meta', {}).get('rows_written', 0) for r in results)
    except (AttributeError, TypeError):
        return {'status': 'committed_telemetry_incomplete', 'core_revision': revision}
    return {'status': 'committed', 'core_revision': revision,
            'rows_read': rows_read, 'rows_written': rows_written}


def bootstrap(client, archive_store, workspace, stats_generator):
    """Read the existing live data once, archive it, and atomically attach its identity."""
    base, revision = client.current()
    if base.get('snapshot_commit'):
        return base
    rows = {}
    for table, columns in legacy.TABLES:
        primary_key = 'uid' if table == 'OIer' else 'id'
        cursor = None
        rows[table] = []
        while True:
            where = f'WHERE {primary_key}>?' if cursor is not None else ''
            params = [cursor, 5000] if cursor is not None else [5000]
            page = client.query(f'SELECT {", ".join(columns)} FROM {table} {where} ORDER BY {primary_key} LIMIT ?', params)
            if not page:
                break
            if cursor is not None and page[-1][primary_key] <= cursor:
                raise SyncError('Non-progressing bootstrap pagination')
            rows[table].extend(page)
            cursor = page[-1][primary_key]
            if len(rows[table]) > base[COUNT_FIELDS[table]]:
                raise SyncError('Production row count changed during bootstrap')
    actual, after_revision = client.current()
    if release_identity(actual) != release_identity(base) or after_revision != revision:
        raise SyncError('Production changed while reading the bootstrap snapshot')
    workspace = Path(workspace)
    database = workspace / 'bootstrap.db'
    database.unlink(missing_ok=True)
    state = snapshots.write_core_database(database, rows)
    if snapshots.row_counts(state) != {table: base[field] for table, field in COUNT_FIELDS.items()}:
        raise SyncError('Bootstrap row counts differ from the published release')
    stats = workspace / 'bootstrap-stats.json'
    stats_generator(database, stats)
    directory = workspace / 'bootstrap-archive'
    manifest = snapshots.create_archive(database, stats, directory, source_sha=base['upstream_sha'],
        source_hash=base['source_data_hash'], projection='legacy-audited-v1', worker_version=base.get('worker_version'))
    commit = archive_store(directory)
    target = publication_values(manifest, commit, source_sha=base['upstream_sha'], source_hash=base['source_data_hash'],
        worker_version=base.get('worker_version'), run_url=base.get('github_run_url'), revision=revision)
    empty_patch = {table: {'insert': [], 'update': [], 'delete': []} for table, _ in legacy.TABLES}
    publish(client, base, revision, empty_patch, target)
    return client.current()[0]
