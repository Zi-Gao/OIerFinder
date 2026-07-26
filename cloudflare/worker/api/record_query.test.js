import assert from 'node:assert/strict';
import test from 'node:test';

import {
    buildRecordSubquery,
    recordMatchesFilter,
} from './record_query.js';

test('initial query combines explicit contest IDs with contest metadata constraints using AND', () => {
    const { sql, params } = buildRecordSubquery({
        contest_ids: [101, 102],
        year_start: 2023,
        year_end: 2023,
        contest_type: 'NOI',
    });

    assert.match(sql, /JOIN Contest c ON r\.contest_id = c\.id/);
    assert.match(sql, /r\.contest_id IN \(\?,\?\)/);
    assert.match(sql, /c\.year >= \?/);
    assert.match(sql, /c\.year <= \?/);
    assert.match(sql, /c\.type = \?/);
    assert.match(
        sql,
        /r\.contest_id IN \(\?,\?\).* AND c\.year >= \? AND c\.year <= \? AND c\.type = \?/,
    );
    assert.deepEqual(params, [101, 102, 2023, 2023, 'NOI']);
});

test('subsequent candidate query keeps contest IDs and metadata constraints together', () => {
    const { sql, params } = buildRecordSubquery({
        contest_id: 101,
        fall_semester: false,
        contest_types: ['CSP提高', 'NOIP'],
    }, [7, 8]);

    assert.match(sql, /cr\.contest_id = \?/);
    assert.match(sql, /c\.fall_semester = \?/);
    assert.match(sql, /c\.type IN \(\?,\?\)/);
    assert.deepEqual(params, [7, 8, 101, 0, 'CSP提高', 'NOIP']);
});

test('in-memory numeric filters reject null values like SQL does', () => {
    const record = {
        score: null,
        rank: null,
    };

    assert.equal(recordMatchesFilter(record, { min_score: 0 }), false);
    assert.equal(recordMatchesFilter(record, { max_score: 100 }), false);
    assert.equal(recordMatchesFilter(record, { min_rank: 1 }), false);
    assert.equal(recordMatchesFilter(record, { max_rank: 100 }), false);
    assert.equal(recordMatchesFilter(record, {}), true);
});
