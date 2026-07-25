import { toArray } from './record_query.js';

export const D1_MAX_VARS = 100;

const STRENGTH_SCORES = {
    CONTEST_ID: 10,
    SCHOOL_ID: 8,
    OIER_INITIALS: 10,
    YEAR: 3,
    PROVINCE: 2,
    HIGH_PRIORITY_CONTEST: 5,
    MID_PRIORITY_CONTEST: 3,
    LOW_PRIORITY_CONTEST: 1,
    LEVEL: 1,
    SCORE: 1,
    RANK: 1,
};

const CONTEST_PRIORITY = {
    'NOI': 1,
    'CTSC': 1,
    'APIO': 1,
    'WC': 1,
    'NOID类': 1,
    'NOIP提高': 2,
    'NOIP': 2,
    'CSP提高': 3,
    'NOIP普及': 4,
    'CSP入门': 4,
};

function hasValue(value) {
    return toArray(value).length > 0;
}

function hasBound(value) {
    return value !== undefined && value !== null;
}

export function exceedsD1ParameterLimit(parameterCount, reservedParameters = 0) {
    return parameterCount + reservedParameters > D1_MAX_VARS;
}

export function getFilterStrength(filter, isOierFilter = false) {
    let score = 0;

    if (isOierFilter) {
        if (hasValue(filter.initials)) score += STRENGTH_SCORES.OIER_INITIALS;
        if (hasBound(filter.enroll_min) || hasBound(filter.enroll_max)) score += 1;
        return score;
    }

    if (hasValue(filter.contest_id ?? filter.contest_ids)) score += STRENGTH_SCORES.CONTEST_ID;
    if (hasValue(filter.school_id ?? filter.school_ids)) score += STRENGTH_SCORES.SCHOOL_ID;
    if (
        hasValue(filter.year ?? filter.years) ||
        hasBound(filter.year_start) ||
        hasBound(filter.year_end)
    ) {
        score += STRENGTH_SCORES.YEAR;
    }
    if (hasValue(filter.province ?? filter.provinces)) score += STRENGTH_SCORES.PROVINCE;
    if (hasValue(filter.level ?? filter.levels)) score += STRENGTH_SCORES.LEVEL;
    if (hasBound(filter.min_score) || hasBound(filter.max_score)) score += STRENGTH_SCORES.SCORE;
    if (hasBound(filter.min_rank) || hasBound(filter.max_rank)) score += STRENGTH_SCORES.RANK;

    const types = new Set(toArray(filter.contest_type ?? filter.contest_types));
    for (const type of types) {
        const priority = CONTEST_PRIORITY[type];
        if (priority === 1) score += STRENGTH_SCORES.HIGH_PRIORITY_CONTEST;
        else if (priority === 2) score += STRENGTH_SCORES.MID_PRIORITY_CONTEST;
        else score += STRENGTH_SCORES.LOW_PRIORITY_CONTEST;
    }

    return score;
}
