import assert from 'node:assert/strict';
import test from 'node:test';

import {
    exceedsD1ParameterLimit,
    getFilterStrength,
} from './query_policy.js';

test('empty arrays do not contribute query strength', () => {
    const score = getFilterStrength({
        contest_ids: [],
        school_ids: [],
        provinces: [],
        levels: [],
        contest_types: [],
        year_start: 1984,
        year_end: 2025,
    });

    assert.equal(score, 3);
});

test('non-empty arrays retain their intended query strength', () => {
    const score = getFilterStrength({
        contest_ids: [101],
        school_ids: [233],
        contest_types: ['NOI'],
    });

    assert.equal(score, 23);
});

test('duplicate contest types cannot inflate query strength', () => {
    assert.equal(
        getFilterStrength({ contest_types: ['NOI', 'NOI', 'NOI', 'NOI'] }),
        5,
    );
});

test('D1 parameter limit includes reserved parameters', () => {
    assert.equal(exceedsD1ParameterLimit(100), false);
    assert.equal(exceedsD1ParameterLimit(101), true);
    assert.equal(exceedsD1ParameterLimit(99, 1), false);
    assert.equal(exceedsD1ParameterLimit(100, 1), true);
});
