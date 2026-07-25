function toArray(value) {
    if (value === undefined || value === null) return [];
    return Array.isArray(value)
        ? value.filter(item => item !== undefined && item !== null)
        : [value];
}

function uniqueValues(filter, singularKey, pluralKey) {
    // Keep this precedence aligned with the SQL builder: when both aliases are
    // present, the singular form wins.
    return [...new Set(toArray(filter[singularKey] ?? filter[pluralKey]))];
}

function isCategoricalSubset(valuesA, valuesB) {
    // An omitted constraint means "all values", not the empty set.
    if (valuesB.length === 0) return true;
    if (valuesA.length === 0) return false;

    const allowedByB = new Set(valuesB);
    return valuesA.every(value => allowedByB.has(value));
}

function hasBound(value) {
    return value !== undefined && value !== null;
}

function isEmptyRange(minValue, maxValue) {
    return hasBound(minValue) &&
           hasBound(maxValue) &&
           Number(minValue) > Number(maxValue);
}

function isRangeSubset(minA, maxA, minB, maxB) {
    if (isEmptyRange(minA, maxA)) return true;
    if (isEmptyRange(minB, maxB)) return false;

    if (hasBound(minB) && (!hasBound(minA) || Number(minA) < Number(minB))) {
        return false;
    }
    if (hasBound(maxB) && (!hasBound(maxA) || Number(maxA) > Number(maxB))) {
        return false;
    }
    return true;
}

function allowedYears(filter, minYear, maxYear) {
    const start = Math.max(
        hasBound(filter.year_start) ? Number(filter.year_start) : minYear,
        minYear,
    );
    const end = Math.min(
        hasBound(filter.year_end) ? Number(filter.year_end) : maxYear,
        maxYear,
    );
    const yearsList = toArray(filter.years);
    // Query preprocessing gives an explicit years list precedence over the
    // singular year and over a year range.
    const explicitYears = [
        ...new Set(yearsList.length > 0 ? yearsList : toArray(filter.year)),
    ].map(Number);
    const result = new Set();

    if (start > end) return result;

    if (explicitYears.length > 0) {
        for (const year of explicitYears) {
            // Contest.year is an integer column. Non-integer values cannot
            // match a stored contest year.
            if (Number.isInteger(year) && year >= start && year <= end) {
                result.add(year);
            }
        }
        return result;
    }

    for (let year = Math.ceil(start); year <= Math.floor(end); year += 1) {
        result.add(year);
    }
    return result;
}

function isSetSubset(setA, setB) {
    for (const value of setA) {
        if (!setB.has(value)) return false;
    }
    return true;
}

function isScalarSubset(valueA, valueB) {
    // Undefined means that this dimension is unconstrained.
    if (!hasBound(valueB)) return true;
    if (!hasBound(valueA)) return false;
    return valueA === valueB;
}

function isFilterUnsatisfiable(filter, years) {
    return years.size === 0 ||
           isEmptyRange(filter.min_score, filter.max_score) ||
           isEmptyRange(filter.min_rank, filter.max_rank);
}

/**
 * Return whether every record matched by filterA is also matched by filterB.
 *
 * Missing constraints are wildcards (the universe for that dimension), so a
 * constrained value is a subset of an omitted constraint, never the reverse.
 */
export function isFilterSubset(filterA, filterB, minYear, maxYear) {
    const yearsA = allowedYears(filterA, minYear, maxYear);
    const yearsB = allowedYears(filterB, minYear, maxYear);
    const isAEmpty = isFilterUnsatisfiable(filterA, yearsA);
    const isBEmpty = isFilterUnsatisfiable(filterB, yearsB);

    // The empty predicate is a subset of every predicate. A non-empty
    // predicate cannot be a subset of an empty predicate.
    if (isAEmpty) return true;
    if (isBEmpty) return false;

    return isCategoricalSubset(
        uniqueValues(filterA, 'level', 'levels'),
        uniqueValues(filterB, 'level', 'levels'),
    ) &&
    isCategoricalSubset(
        uniqueValues(filterA, 'province', 'provinces'),
        uniqueValues(filterB, 'province', 'provinces'),
    ) &&
    isCategoricalSubset(
        uniqueValues(filterA, 'school_id', 'school_ids'),
        uniqueValues(filterB, 'school_id', 'school_ids'),
    ) &&
    isCategoricalSubset(
        uniqueValues(filterA, 'contest_id', 'contest_ids'),
        uniqueValues(filterB, 'contest_id', 'contest_ids'),
    ) &&
    isCategoricalSubset(
        uniqueValues(filterA, 'contest_type', 'contest_types'),
        uniqueValues(filterB, 'contest_type', 'contest_types'),
    ) &&
    isSetSubset(yearsA, yearsB) &&
    isScalarSubset(filterA.fall_semester, filterB.fall_semester) &&
    isRangeSubset(
        filterA.min_score,
        filterA.max_score,
        filterB.min_score,
        filterB.max_score,
    ) &&
    isRangeSubset(
        filterA.min_rank,
        filterA.max_rank,
        filterB.min_rank,
        filterB.max_rank,
    );
}

/**
 * Remove predicates made redundant by a stricter predicate.
 *
 * The returned predicates form an antichain: none is a subset of another.
 * Input order does not change which matching-record sets are retained.
 */
export function removeRedundantFilters(filters, minYear, maxYear) {
    return filters.reduce((acc, current) => {
        let currentIsRedundant = false;
        const retained = [];

        for (const existing of acc) {
            if (isFilterSubset(current, existing, minYear, maxYear)) {
                // current is stricter, so existing is redundant.
                continue;
            }
            if (isFilterSubset(existing, current, minYear, maxYear)) {
                // existing is stricter, so current is redundant.
                currentIsRedundant = true;
            }
            retained.push(existing);
        }

        if (!currentIsRedundant) retained.push(current);
        return retained;
    }, []);
}
