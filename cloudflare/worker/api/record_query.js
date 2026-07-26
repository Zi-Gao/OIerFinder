export function toArray(value) {
    if (value === undefined || value === null) return [];
    return Array.isArray(value)
        ? value.filter(item => item !== undefined && item !== null)
        : [value];
}

export function pushInClause(targetWhere, targetParams, column, values) {
    if (!values || values.length === 0) return;
    if (values.length === 1) {
        targetWhere.push(`${column} = ?`);
        targetParams.push(values[0]);
        return;
    }

    const placeholders = values.map(() => '?').join(',');
    targetWhere.push(`${column} IN (${placeholders})`);
    targetParams.push(...values);
}

export function recordMatchesFilter(record, filter) {
    const levels = toArray(filter.level ?? filter.levels);
    if (levels.length > 0 && !levels.includes(record.level)) return false;

    const hasScoreBound =
        filter.min_score !== undefined || filter.max_score !== undefined;
    if (hasScoreBound && (record.score === null || record.score === undefined)) {
        return false;
    }
    if (filter.min_score !== undefined && record.score < Number(filter.min_score)) return false;
    if (filter.max_score !== undefined && record.score > Number(filter.max_score)) return false;

    const hasRankBound =
        filter.min_rank !== undefined || filter.max_rank !== undefined;
    if (hasRankBound && (record.rank === null || record.rank === undefined)) {
        return false;
    }
    if (filter.min_rank !== undefined && record.rank < Number(filter.min_rank)) return false;
    if (filter.max_rank !== undefined && record.rank > Number(filter.max_rank)) return false;

    const provinces = toArray(filter.province ?? filter.provinces);
    if (provinces.length > 0 && !provinces.includes(record.province)) return false;
    const schoolIds = toArray(filter.school_id ?? filter.school_ids);
    if (schoolIds.length > 0 && !schoolIds.includes(record.school_id)) return false;
    const contestIds = toArray(filter.contest_id ?? filter.contest_ids);
    if (contestIds.length > 0 && !contestIds.includes(record.contest_id)) return false;
    const years = toArray(filter.years);
    if (years.length > 0 && !years.includes(record.year)) return false;
    if (filter.year_start !== undefined && record.year < Number(filter.year_start)) return false;
    if (filter.year_end !== undefined && record.year > Number(filter.year_end)) return false;
    if (
        filter.fall_semester !== undefined &&
        record.fall_semester !== (filter.fall_semester ? 1 : 0)
    ) return false;
    const contestTypes = toArray(filter.contest_type ?? filter.contest_types);
    if (contestTypes.length > 0 && !contestTypes.includes(record.type)) return false;
    return true;
}

export function buildRecordSubquery(filter = {}, candidateUids = null, oierFilter = {}) {
    const recordWhere = [], recordParams = [];
    const contestWhere = [], contestParams = [];

    pushInClause(recordWhere, recordParams, 'cr.level', toArray(filter.level ?? filter.levels));
    if (filter.min_score !== undefined) { recordWhere.push('cr.score >= ?'); recordParams.push(Number(filter.min_score)); }
    if (filter.max_score !== undefined) { recordWhere.push('cr.score <= ?'); recordParams.push(Number(filter.max_score)); }
    if (filter.min_rank !== undefined) { recordWhere.push('cr.rank >= ?'); recordParams.push(Number(filter.min_rank)); }
    if (filter.max_rank !== undefined) { recordWhere.push('cr.rank <= ?'); recordParams.push(Number(filter.max_rank)); }
    pushInClause(recordWhere, recordParams, 'cr.province', toArray(filter.province ?? filter.provinces));
    pushInClause(recordWhere, recordParams, 'cr.school_id', toArray(filter.school_id ?? filter.school_ids));
    pushInClause(recordWhere, recordParams, 'cr.contest_id', toArray(filter.contest_id ?? filter.contest_ids));

    const hasContestFilter =
        filter.year_start !== undefined ||
        filter.year_end !== undefined ||
        toArray(filter.years).length > 0 ||
        filter.fall_semester !== undefined ||
        toArray(filter.contest_type ?? filter.contest_types).length > 0;

    if (hasContestFilter) {
        pushInClause(contestWhere, contestParams, 'c.year', toArray(filter.years));
        if (filter.year_start !== undefined) { contestWhere.push('c.year >= ?'); contestParams.push(filter.year_start); }
        if (filter.year_end !== undefined) { contestWhere.push('c.year <= ?'); contestParams.push(filter.year_end); }
        if (filter.fall_semester !== undefined) { contestWhere.push('c.fall_semester = ?'); contestParams.push(filter.fall_semester ? 1 : 0); }
        pushInClause(contestWhere, contestParams, 'c.type', toArray(filter.contest_type ?? filter.contest_types));
    }

    const filterParamCount = recordParams.length + contestParams.length;
    const needsContestJoin = contestWhere.length > 0;

    if (candidateUids === null) {
        let fromClause = 'Record r';
        const oierWhere = [], oierParams = [];
        const hasOierFilter = oierFilter && Object.keys(oierFilter).length > 0;
        const needsOierJoin = hasOierFilter && (
            toArray(oierFilter.gender ?? oierFilter.genders).length > 0 ||
            oierFilter.enroll_min !== undefined ||
            oierFilter.enroll_max !== undefined ||
            toArray(oierFilter.initials).length > 0
        );

        if (needsOierJoin) {
            fromClause += ' JOIN OIer o ON r.oier_uid = o.uid';
            pushInClause(oierWhere, oierParams, 'o.gender', toArray(oierFilter.gender ?? oierFilter.genders));
            if (oierFilter.enroll_min !== undefined) { oierWhere.push('o.enroll_middle >= ?'); oierParams.push(Number(oierFilter.enroll_min)); }
            if (oierFilter.enroll_max !== undefined) { oierWhere.push('o.enroll_middle <= ?'); oierParams.push(Number(oierFilter.enroll_max)); }
            pushInClause(oierWhere, oierParams, 'o.initials', toArray(oierFilter.initials));
        }
        if (needsContestJoin) fromClause += ' JOIN Contest c ON r.contest_id = c.id';

        const initialRecordWhereClauses = [];
        const initialRecordParams = [];
        pushInClause(initialRecordWhereClauses, initialRecordParams, 'r.level', toArray(filter.level ?? filter.levels));
        if (filter.min_score !== undefined) { initialRecordWhereClauses.push('r.score >= ?'); initialRecordParams.push(Number(filter.min_score)); }
        if (filter.max_score !== undefined) { initialRecordWhereClauses.push('r.score <= ?'); initialRecordParams.push(Number(filter.max_score)); }
        if (filter.min_rank !== undefined) { initialRecordWhereClauses.push('r.rank >= ?'); initialRecordParams.push(Number(filter.min_rank)); }
        if (filter.max_rank !== undefined) { initialRecordWhereClauses.push('r.rank <= ?'); initialRecordParams.push(Number(filter.max_rank)); }
        pushInClause(initialRecordWhereClauses, initialRecordParams, 'r.province', toArray(filter.province ?? filter.provinces));
        pushInClause(initialRecordWhereClauses, initialRecordParams, 'r.school_id', toArray(filter.school_id ?? filter.school_ids));
        pushInClause(initialRecordWhereClauses, initialRecordParams, 'r.contest_id', toArray(filter.contest_id ?? filter.contest_ids));

        const whereClauses = [...oierWhere, ...initialRecordWhereClauses, ...contestWhere];
        const whereSql = whereClauses.length > 0 ? `WHERE ${whereClauses.join(' AND ')}` : '';
        const sql = `SELECT DISTINCT r.oier_uid FROM ${fromClause} ${whereSql}`;
        const params = [...oierParams, ...initialRecordParams, ...contestParams];
        return { sql, params, filterParamCount };
    }

    const placeholders = candidateUids.map(() => '?').join(',');
    const cteSql = `WITH CandidateRecords AS (SELECT * FROM Record WHERE oier_uid IN (${placeholders}) LIMIT -1)`;
    let fromClause = 'CandidateRecords cr';
    if (needsContestJoin) fromClause += ' JOIN Contest c ON cr.contest_id = c.id';
    const whereClauses = [...recordWhere, ...contestWhere];
    const whereSql = whereClauses.length > 0 ? `WHERE ${whereClauses.join(' AND ')}` : '';
    const sql = `${cteSql} SELECT DISTINCT cr.oier_uid FROM ${fromClause} ${whereSql}`;
    const params = [...candidateUids, ...recordParams, ...contestParams];
    return { sql, params, filterParamCount };
}
