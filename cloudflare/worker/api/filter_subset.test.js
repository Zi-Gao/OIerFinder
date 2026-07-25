import assert from 'node:assert/strict';
import test from 'node:test';

import {
    isFilterSubset,
    removeRedundantFilters,
} from './filter_subset.js';

const MIN_YEAR = 2004;
const MAX_YEAR = 2026;

const subset = (filterA, filterB) =>
    isFilterSubset(filterA, filterB, MIN_YEAR, MAX_YEAR);

const dedupe = filters =>
    removeRedundantFilters(filters, MIN_YEAR, MAX_YEAR);

test('a constrained category is a subset of an unconstrained category', () => {
    const broad = { contest_type: 'NOI', year_start: 2023, year_end: 2023 };
    const strict = { ...broad, level: '金牌' };

    assert.equal(subset(strict, broad), true);
    assert.equal(subset(broad, strict), false);
});

test('categorical arrays use value-set inclusion', () => {
    const narrow = { levels: ['金牌'] };
    const wide = { levels: ['金牌', '银牌'] };

    assert.equal(subset(narrow, wide), true);
    assert.equal(subset(wide, narrow), false);
});

test('bounded numeric ranges are subsets of wider or unbounded ranges', () => {
    assert.equal(subset({ min_score: 100 }, {}), true);
    assert.equal(subset({}, { min_score: 100 }), false);
    assert.equal(
        subset(
            { min_score: 100, max_score: 200 },
            { min_score: 50, max_score: 250 },
        ),
        true,
    );
    assert.equal(
        subset(
            { min_rank: 50, max_rank: 100 },
            { min_rank: 60, max_rank: 90 },
        ),
        false,
    );
});

test('an impossible numeric range is an empty predicate', () => {
    const impossible = { min_score: 200, max_score: 100 };

    assert.equal(subset(impossible, {}), true);
    assert.equal(subset({}, impossible), false);
});

test('year lists and year ranges are compared in both directions', () => {
    const yearList = { years: [2021] };
    const yearRange = { year_start: 2020, year_end: 2022 };

    assert.equal(subset(yearList, yearRange), true);
    assert.equal(subset(yearRange, yearList), false);
    assert.equal(subset({ years: [2021, 2022] }, { years: [2020, 2021, 2022] }), true);
    assert.equal(subset({ year: 2020, years: [2021] }, { years: [2021] }), true);
});

test('years outside the known contest domain make a predicate empty', () => {
    const outsideDomain = { years: [1900] };

    assert.equal(subset(outsideDomain, { contest_type: 'NOI' }), true);
    assert.equal(subset({ contest_type: 'NOI' }, outsideDomain), false);
});

test('fall_semester participates in subset comparison', () => {
    assert.equal(subset({ fall_semester: true }, {}), true);
    assert.equal(subset({}, { fall_semester: true }), false);
    assert.equal(subset({ fall_semester: true }, { fall_semester: false }), false);
    assert.equal(subset({ fall_semester: false }, { fall_semester: true }), false);
});

test('deduplication keeps the strict filter in either input order', () => {
    const broad = { contest_type: 'NOI', year_start: 2023, year_end: 2023 };
    const strict = { ...broad, level: '金牌' };

    assert.deepEqual(dedupe([broad, strict]), [strict]);
    assert.deepEqual(dedupe([strict, broad]), [strict]);
});

test('deduplication keeps incomparable semester filters', () => {
    const fall = { contest_type: 'NOI', fall_semester: true };
    const spring = { contest_type: 'NOI', fall_semester: false };

    assert.deepEqual(dedupe([fall, spring]), [fall, spring]);
    assert.deepEqual(dedupe([spring, fall]), [spring, fall]);
});

test('deduplication keeps a specific year list over a containing range', () => {
    const yearList = { years: [2021] };
    const yearRange = { year_start: 2020, year_end: 2022 };

    assert.deepEqual(dedupe([yearList, yearRange]), [yearList]);
    assert.deepEqual(dedupe([yearRange, yearList]), [yearList]);
});

test('identical filters are collapsed', () => {
    const filter = {
        contest_types: ['NOI', 'NOI'],
        levels: ['金牌'],
        year_start: 2023,
        year_end: 2023,
    };

    assert.deepEqual(dedupe([filter, { ...filter }]), [{ ...filter }]);
});

test('subset decisions agree with an exhaustive finite-domain oracle', () => {
    const dimensions = {
        year: [2020, 2021, 2022],
        level: ['金牌', '银牌', '铜牌'],
        province: ['北京', '上海'],
        school_id: [1, 2],
        contest_id: [10, 20, 30],
        contest_type: ['NOI', 'NOIP'],
        fall_semester: [true, false],
        score: [null, 0, 50, 100, 150],
        rank: [null, 1, 50, 100],
    };
    const records = [];

    for (const year of dimensions.year)
    for (const level of dimensions.level)
    for (const province of dimensions.province)
    for (const school_id of dimensions.school_id)
    for (const contest_id of dimensions.contest_id)
    for (const contest_type of dimensions.contest_type)
    for (const fall_semester of dimensions.fall_semester)
    for (const score of dimensions.score)
    for (const rank of dimensions.rank) {
        records.push({
            year,
            level,
            province,
            school_id,
            contest_id,
            contest_type,
            fall_semester,
            score,
            rank,
        });
    }

    const values = (filter, singular, plural) => {
        const raw = filter[singular] ?? filter[plural];
        if (raw === undefined || raw === null) return [];
        return Array.isArray(raw) ? raw : [raw];
    };
    const matches = (record, filter) => {
        for (const [singular, plural, recordKey] of [
            ['level', 'levels', 'level'],
            ['province', 'provinces', 'province'],
            ['school_id', 'school_ids', 'school_id'],
            ['contest_id', 'contest_ids', 'contest_id'],
            ['contest_type', 'contest_types', 'contest_type'],
        ]) {
            const allowed = values(filter, singular, plural);
            if (allowed.length > 0 && !allowed.includes(record[recordKey])) return false;
        }

        const years = values(filter, 'year', 'years');
        if (years.length > 0 && !years.includes(record.year)) return false;
        if (filter.year_start !== undefined && record.year < filter.year_start) return false;
        if (filter.year_end !== undefined && record.year > filter.year_end) return false;
        if (
            filter.fall_semester !== undefined &&
            record.fall_semester !== filter.fall_semester
        ) return false;

        for (const [minKey, maxKey, recordKey] of [
            ['min_score', 'max_score', 'score'],
            ['min_rank', 'max_rank', 'rank'],
        ]) {
            if (
                (filter[minKey] !== undefined || filter[maxKey] !== undefined) &&
                record[recordKey] === null
            ) return false;
            if (filter[minKey] !== undefined && record[recordKey] < filter[minKey]) return false;
            if (filter[maxKey] !== undefined && record[recordKey] > filter[maxKey]) return false;
        }
        return true;
    };

    const representativeFilters = [
        {},
        { level: '金牌' },
        { levels: ['金牌', '银牌'] },
        { province: '北京' },
        { school_ids: [1] },
        { contest_ids: [10, 20] },
        { contest_type: 'NOI' },
        { years: [2021] },
        { year_start: 2020, year_end: 2022 },
        { fall_semester: true },
        { fall_semester: false },
        { min_score: 50 },
        { max_score: 100 },
        { min_score: 50, max_score: 100 },
        { min_score: 100, max_score: 50 },
        { min_rank: 50 },
        { contest_type: 'NOI', level: '金牌', years: [2021] },
        { province: '北京', min_score: 100, fall_semester: true },
    ];
    const matchSets = representativeFilters.map(filter =>
        new Set(
            records
                .map((record, index) => matches(record, filter) ? index : null)
                .filter(index => index !== null),
        ),
    );

    for (let a = 0; a < representativeFilters.length; a += 1) {
        for (let b = 0; b < representativeFilters.length; b += 1) {
            const expected = [...matchSets[a]].every(index => matchSets[b].has(index));
            assert.equal(
                isFilterSubset(
                    representativeFilters[a],
                    representativeFilters[b],
                    2020,
                    2022,
                ),
                expected,
                `filter ${a} subset filter ${b}`,
            );
        }
    }
});
