// cloudflare/worker/functions/query_oier.js

// --- [新增] 业务逻辑与安全常量 ---

// 定义比赛的筛选优先级。数字越小，优先级越高，越先被执行。
// 这是基于一个常识：NOI/CTT/WC的参与者远少于CSP/NOIP。
const CONTEST_PRIORITY = {
    'IOI': 1, 'CTT': 1, 'NOI': 1, 'WC': 1, 'APIO': 1, // 国家队/顶级赛事
    'NOIP': 2, 'CSP-S': 2, // 省选及NOIP/CSP-S级别
    'CSP-J': 3, // 入门级
};
const DEFAULT_PRIORITY = 10; // 无特定比赛类型的过滤器优先级最低

// 定义查询强度的评分标准
const STRENGTH_SCORES = {
    // 极其精确的条件
    CONTEST_ID: 10,
    SCHOOL_ID: 8,
    OIER_NAME: 10,

    // 较精确的条件
    YEAR: 3,
    PROVINCE: 2,
    HIGH_PRIORITY_CONTEST: 5, // e.g., NOI
    MID_PRIORITY_CONTEST: 3,  // e.g., CSP-S
    LOW_PRIORITY_CONTEST: 1,  // e.g., CSP-J

    // 一般条件
    LEVEL: 1,
    SCORE: 1,
    RANK: 1,
};
// 一个查询请求必须达到的最低总分，才能被执行
const MINIMUM_QUERY_STRENGTH = 4;


// --- 辅助函数 ---
function toArray(value) { if (value === undefined || value === null) return []; return Array.isArray(value) ? value.filter(v => v !== undefined && v !== null) : [value]; }
function pushInClause(targetWhere, targetParams, column, values) { if (!values || values.length === 0) return; if (values.length === 1) { targetWhere.push(`${column} = ?`); targetParams.push(values[0]); } else { const placeholders = values.map(() => '?').join(','); targetWhere.push(`${column} IN (${placeholders})`); targetParams.push(...values); } }
function normalizeLimit(value, fallback = 100) { const num = Number(value); if (!Number.isFinite(num) || num <= 0) return fallback; return Math.min(Math.floor(num), 500); }
function formatUsageStep(name, meta) { return { name, rows_read: meta?.rows_read ?? 0, rows_written: meta?.rows_written ?? 0, duration_ms: meta?.duration ?? 0 }; }


// --- [新增] 智能排序与安全验证的辅助函数 ---
function getFilterPriority(filter) {
    const types = toArray(filter.contest_type ?? filter.contest_types);
    if (types.length === 0) return DEFAULT_PRIORITY;
    let highestPriority = DEFAULT_PRIORITY;
    for (const type of types) {
        const priority = CONTEST_PRIORITY[type.toUpperCase()] ?? DEFAULT_PRIORITY;
        if (priority < highestPriority) {
            highestPriority = priority;
        }
    }
    return highestPriority;
}

function getFilterStrength(filter, isOierFilter = false) {
    let score = 0;
    if (isOierFilter) {
        if (filter.name || filter.names) score += STRENGTH_SCORES.OIER_NAME;
        if (filter.enroll_min || filter.enroll_max) score += 1;
        return score;
    }
    if (filter.contest_id || filter.contest_ids) score += STRENGTH_SCORES.CONTEST_ID;
    if (filter.school_id || filter.school_ids) score += STRENGTH_SCORES.SCHOOL_ID;
    if (filter.year || filter.year_start || filter.year_end) score += STRENGTH_SCORES.YEAR;
    if (filter.province || filter.provinces) score += STRENGTH_SCORES.PROVINCE;
    if (filter.level || filter.levels) score += STRENGTH_SCORES.LEVEL;
    if (filter.min_score || filter.max_score) score += STRENGTH_SCORES.SCORE;
    if (filter.min_rank || filter.max_rank) score += STRENGTH_SCORES.RANK;
    const types = toArray(filter.contest_type ?? filter.contest_types);
    for (const type of types) {
        const priority = CONTEST_PRIORITY[type.toUpperCase()];
        if (priority === 1) score += STRENGTH_SCORES.HIGH_PRIORITY_CONTEST;
        else if (priority === 2) score += STRENGTH_SCORES.MID_PRIORITY_CONTEST;
        else score += STRENGTH_SCORES.LOW_PRIORITY_CONTEST;
    }
    return score;
}


// --- 内存过滤器 ---
function recordMatchesFilter(record, filter) {
    const levels = toArray(filter.level ?? filter.levels);
    if (levels.length > 0 && !levels.includes(record.level)) return false;
    if (filter.min_score !== undefined && record.score < Number(filter.min_score)) return false;
    if (filter.max_score !== undefined && record.score > Number(filter.max_score)) return false;
    if (filter.min_rank !== undefined && record.rank < Number(filter.min_rank)) return false;
    if (filter.max_rank !== undefined && record.rank > Number(filter.max_rank)) return false;
    const provinces = toArray(filter.province ?? filter.provinces);
    if (provinces.length > 0 && !provinces.includes(record.province)) return false;
    const school_ids = toArray(filter.school_id ?? filter.school_ids);
    if (school_ids.length > 0 && !school_ids.includes(record.school_id)) return false;
    const contest_ids = toArray(filter.contest_id ?? filter.contest_ids);
    if (contest_ids.length > 0 && !contest_ids.includes(record.contest_id)) return false;
    if (filter.year !== undefined && record.year !== Number(filter.year)) return false;
    if (filter.year_start !== undefined && record.year < Number(filter.year_start)) return false;
    if (filter.year_end !== undefined && record.year > Number(filter.year_end)) return false;
    if (filter.fall_semester !== undefined && record.fall_semester !== (filter.fall_semester ? 1 : 0)) return false;    
    const contest_types = toArray(filter.contest_type ?? filter.contest_types);
    if (contest_types.length > 0 && !contest_types.includes(record.type)) return false;
    return true;
}


// --- SQL 查询构建器 ---
function buildRecordSubquery(filter = {}, candidateUids = null) {
    const recordWhere = [], recordParams = [];
    const contestWhere = [], contestParams = [];
    pushInClause(recordWhere, recordParams, 'r.level', toArray(filter.level ?? filter.levels));
    if (filter.min_score !== undefined) { recordWhere.push('r.score >= ?'); recordParams.push(Number(filter.min_score)); }
    if (filter.max_score !== undefined) { recordWhere.push('r.score <= ?'); recordParams.push(Number(filter.max_score)); }
    if (filter.min_rank !== undefined) { recordWhere.push('r.rank >= ?'); recordParams.push(Number(filter.min_rank)); }
    if (filter.max_rank !== undefined) { recordWhere.push('r.rank <= ?'); recordParams.push(Number(filter.max_rank)); }
    pushInClause(recordWhere, recordParams, 'r.province', toArray(filter.province ?? filter.provinces));
    pushInClause(recordWhere, recordParams, 'r.school_id', toArray(filter.school_id ?? filter.school_ids));
    pushInClause(recordWhere, recordParams, 'r.contest_id', toArray(filter.contest_id ?? filter.contest_ids));
    const hasContestFilter = filter.year !== undefined || filter.year_start !== undefined || filter.year_end !== undefined || filter.fall_semester !== undefined || (toArray(filter.contest_type ?? filter.contest_types)).length > 0;
    if (hasContestFilter) {
        if (filter.year !== undefined) { contestWhere.push('c.year = ?'); contestParams.push(Number(filter.year)); }
        else {
            if (filter.year_start !== undefined) { contestWhere.push('c.year >= ?'); contestParams.push(Number(filter.year_start)); }
            if (filter.year_end !== undefined) { contestWhere.push('c.year <= ?'); contestParams.push(Number(filter.year_end)); }
        }
        if (filter.fall_semester !== undefined) { contestWhere.push('c.fall_semester = ?'); contestParams.push(filter.fall_semester ? 1 : 0); }
        pushInClause(contestWhere, contestParams, 'c.type', toArray(filter.contest_type ?? filter.contest_types));
    }
    const needsContestJoin = contestWhere.length > 0;
    const fromClause = needsContestJoin ? 'Record r JOIN Contest c ON r.contest_id = c.id' : 'Record r';
    let whereClauses = [...recordWhere];
    let params = [...recordParams];
    if (needsContestJoin) {
        whereClauses.push(...contestWhere);
        params.push(...contestParams);
    }
    if (candidateUids) {
        pushInClause(whereClauses, params, 'r.oier_uid', candidateUids);
    }
    const whereSql = whereClauses.length > 0 ? `WHERE ${whereClauses.join(' AND ')}` : '';
    const sql = `SELECT DISTINCT r.oier_uid FROM ${fromClause} ${whereSql}`;
    return { sql, params, filterParamCount: recordParams.length + contestParams.length };
}


// --- 主处理器 (集成了智能排序和安全验证) ---
export default async function queryOierHandler(c) {
    if (c.req.method !== "POST") return c.json({ error: "Only POST is supported" }, 405);
    let payload;
    try { payload = await c.req.json(); } catch (err) { return c.json({ error: "Invalid JSON" }, 400); }

    try {
        const initialRecordFilters = toArray(payload.record_filters);
        const oierFilters = payload.oier_filters ?? {};
        const limit = normalizeLimit(payload.limit, 100);

        // --- 安全与优化前置处理 ---
        const totalStrength = initialRecordFilters.reduce((sum, f) => sum + getFilterStrength(f), 0) + getFilterStrength(oierFilters, true);
        if (initialRecordFilters.length === 0 && Object.keys(oierFilters).length === 0) {
            return c.json({ error: "Query is too broad. Please provide at least one filter." }, 400);
        }
        if (totalStrength < MINIMUM_QUERY_STRENGTH) {
            return c.json({ error: `Query is too broad and may cause high resource usage. Please add more specific conditions (e.g., year, province, school, or a more selective contest type). Your query strength score is ${totalStrength}, minimum required is ${MINIMUM_QUERY_STRENGTH}.` }, 400);
        }
        const recordFilters = [...initialRecordFilters].sort((a, b) => getFilterPriority(a) - getFilterPriority(b));
        
        // --- 核心查询逻辑 ---
        const usageSteps = [];
        let candidateUids = null; 
        const D1_MAX_VARS = 99;
        const VERIFICATION_THRESHOLD = 50;
        let verificationMode = false;
        const oierRecordsMap = new Map();

        for (let i = 0; i < recordFilters.length; i++) {
            const filter = recordFilters[i];
            
            if (candidateUids !== null && candidateUids.length === 0) break;
            
            // 特殊处理第一个过滤器，采用预过滤策略
            if (i === 0 && candidateUids === null) {
                let effectiveFilter = { ...filter };
                const contestWhere = [], contestParams = [];
                if (filter.year !== undefined) { contestWhere.push('c.year = ?'); contestParams.push(Number(filter.year)); }
                else {
                    if (filter.year_start !== undefined) { contestWhere.push('c.year >= ?'); contestParams.push(Number(filter.year_start)); }
                    if (filter.year_end !== undefined) { contestWhere.push('c.year <= ?'); contestParams.push(Number(filter.year_end)); }
                }
                if (filter.fall_semester !== undefined) { contestWhere.push('c.fall_semester = ?'); contestParams.push(filter.fall_semester ? 1 : 0); }
                pushInClause(contestWhere, contestParams, 'c.type', toArray(filter.contest_type ?? filter.contest_types));

                if (contestWhere.length > 0) {
                    const contestSql = `SELECT id FROM Contest c WHERE ${contestWhere.join(' AND ')}`;
                    const { results: contestResults, meta: contestMeta } = await c.env.DB.prepare(contestSql).bind(...contestParams).all();
                    usageSteps.push(formatUsageStep("initial_contest_prefilter", contestMeta));
                    const candidateContestIds = contestResults ? contestResults.map(row => row.id) : [];
                    if (candidateContestIds.length === 0) { candidateUids = []; break; }
                    const existingIds = toArray(effectiveFilter.contest_id ?? effectiveFilter.contest_ids);
                    effectiveFilter.contest_ids = [...new Set([...existingIds, ...candidateContestIds])];
                }

                const { sql, params } = buildRecordSubquery(effectiveFilter, null);
                const { results: recordResults, meta: recordMeta } = await c.env.DB.prepare(sql).bind(...params).all();
                usageSteps.push(formatUsageStep("initial_record_query", recordMeta));
                const uids = new Set();
                if (recordResults) recordResults.forEach(row => uids.add(row.oier_uid));
                candidateUids = Array.from(uids);
                continue;
            }

            // 后续过滤器或已进入验证模式的逻辑
            if (!verificationMode && candidateUids !== null && candidateUids.length > 0 && candidateUids.length < VERIFICATION_THRESHOLD) {
                verificationMode = true;
                const chunks = [];
                for (let j = 0; j < candidateUids.length; j += D1_MAX_VARS) { chunks.push(candidateUids.slice(j, j + D1_MAX_VARS)); }
                const promises = chunks.map((chunk) => {
                    const placeholders = chunk.map(() => '?').join(',');
                    const sql = `SELECT r.oier_uid, r.contest_id, r.level, r.score, r.rank, r.province, r.school_id, c.year, c.fall_semester, c.type FROM Record r JOIN Contest c ON r.contest_id = c.id WHERE r.oier_uid IN (${placeholders})`;
                    return c.env.DB.prepare(sql).bind(...chunk).all();
                });
                const resultsFromChunks = await Promise.all(promises);
                resultsFromChunks.forEach((res, chunkIndex) => {
                    usageSteps.push(formatUsageStep(`fetch_records_for_verification_chunk_${chunkIndex}`, res.meta));
                    if (res.results) {
                        res.results.forEach(record => {
                            if (!oierRecordsMap.has(record.oier_uid)) oierRecordsMap.set(record.oier_uid, []);
                            oierRecordsMap.get(record.oier_uid).push(record);
                        });
                    }
                });
            }

            if (verificationMode) {
                const uidsAfterVerification = [];
                for (const uid of candidateUids) {
                    const records = oierRecordsMap.get(uid) || [];
                    if (records.some(record => recordMatchesFilter(record, filter))) { uidsAfterVerification.push(uid); }
                }
                candidateUids = uidsAfterVerification;
                usageSteps.push(formatUsageStep(`in_memory_verification_${i}`, {}));
            } else {
                const { filterParamCount } = buildRecordSubquery(filter);
                if (filterParamCount >= D1_MAX_VARS) { return c.json({ error: `Filter at index ${i} is too complex...` }, 400); }
                const dynamicChunkSize = D1_MAX_VARS - filterParamCount;
                const chunks = [];
                if (candidateUids === null) { chunks.push(null); } 
                else {
                    for (let j = 0; j < candidateUids.length; j += dynamicChunkSize) { chunks.push(candidateUids.slice(j, j + dynamicChunkSize)); }
                }
                const promises = chunks.map(chunk => {
                    const { sql, params } = buildRecordSubquery(filter, chunk);
                    return c.env.DB.prepare(sql).bind(...params).all();
                });
                const resultsFromChunks = await Promise.all(promises);
                const newUids = new Set();
                resultsFromChunks.forEach((res, chunkIndex) => {
                    usageSteps.push(formatUsageStep(`record_filter_${i}_chunk_${chunkIndex}`, res.meta));
                    if (res.results) res.results.forEach(row => newUids.add(row.oier_uid));
                });
                candidateUids = Array.from(newUids);
            }
        }

        // --- 最终 OIer 查询逻辑 ---
        if (candidateUids !== null && candidateUids.length === 0) {
            const totals = usageSteps.reduce((acc, step) => { acc.rows_read += step.rows_read; acc.rows_written += step.rows_written; return acc; }, { rows_read: 0, rows_written: 0 });
            return c.json({ data: [], usage: { steps: usageSteps, total_rows_read: totals.rows_read, total_rows_written: totals.rows_written }});
        }
        const oierWhereClauses = [], oierBaseParams = [];
        pushInClause(oierWhereClauses, oierBaseParams, 'o.gender', toArray(oierFilters.gender ?? oierFilters.genders));
        if (oierFilters.enroll_min !== undefined) { oierWhereClauses.push('o.enroll_middle >= ?'); oierBaseParams.push(Number(oierFilters.enroll_min)); }
        if (oierFilters.enroll_max !== undefined) { oierWhereClauses.push('o.enroll_middle <= ?'); oierBaseParams.push(Number(oierFilters.enroll_max)); }
        pushInClause(oierWhereClauses, oierBaseParams, 'o.name', toArray(oierFilters.name ?? oierFilters.names));
        if (oierFilters.min_oierdb_score !== undefined) { oierWhereClauses.push('o.oierdb_score >= ?'); oierBaseParams.push(Number(oierFilters.min_oierdb_score)); }
        if (oierBaseParams.length >= D1_MAX_VARS) { return c.json({ error: "Oier filter is too complex..." }, 400); }
        let allOiers = [];
        if (candidateUids !== null) {
            const dynamicChunkSize = D1_MAX_VARS - oierBaseParams.length;
            const chunks = [];
            for (let i = 0; i < candidateUids.length; i += dynamicChunkSize) { chunks.push(candidateUids.slice(i, i + dynamicChunkSize)); }
            const promises = chunks.map((chunk) => {
                const chunkWhere = [...oierWhereClauses];
                const chunkParams = [...oierBaseParams];
                pushInClause(chunkWhere, chunkParams, 'o.uid', chunk);
                const whereClause = `WHERE ${chunkWhere.join(' AND ')}`;
                const sql = `SELECT * FROM OIer o ${whereClause};`;
                return c.env.DB.prepare(sql).bind(...chunkParams).all();
            });
            const resultsFromChunks = await Promise.all(promises);
            resultsFromChunks.forEach((res, chunkIndex) => {
                usageSteps.push(formatUsageStep(`final_oier_query_chunk_${chunkIndex}`, res.meta));
                if (res.results) allOiers.push(...res.results);
            });
        } else {
            const whereClause = oierWhereClauses.length > 0 ? `WHERE ${oierWhereClauses.join(' AND ')}` : '';
            const sql = `SELECT * FROM OIer o ${whereClause} ORDER BY o.oierdb_score DESC, o.uid ASC LIMIT ?;`;
            const params = [...oierBaseParams, limit];
            const { results, meta } = await c.env.DB.prepare(sql).bind(...params).all();
            allOiers = results || [];
            usageSteps.push(formatUsageStep("final_oier_query_no_uids", meta));
        }
        if (candidateUids !== null) {
            allOiers.sort((a, b) => {
                if (b.oierdb_score !== a.oierdb_score) { return b.oierdb_score - a.oierdb_score; }
                return a.uid - b.uid;
            });
        }
        const finalResults = allOiers.slice(0, limit);
        const totals = usageSteps.reduce((acc, step) => { acc.rows_read += step.rows_read; acc.rows_written += step.rows_written; return acc; }, { rows_read: 0, rows_written: 0 });
        return c.json({
            data: finalResults,
            usage: { steps: usageSteps, total_rows_read: totals.rows_read, total_rows_written: totals.rows_written },
        });

    } catch (err) {
        console.error('Error in queryOierHandler:', err);
        return c.json({ error: 'An internal server error occurred.', details: err.message }, 500);
    }
}