// cloudflare/worker/functions/query_oier.js

// 1. [数据导入] 从外部 JSON 文件导入预计算的统计数据。
import CONTEST_STATS_DATA from './contest_stats.json';

// --- 业务逻辑与安全常量 ---
const { min_year, max_year, stats: CONTEST_STATS } = CONTEST_STATS_DATA;

const STRENGTH_SCORES = {
    CONTEST_ID: 10, SCHOOL_ID: 8, OIER_NAME: 10,
    YEAR: 3, PROVINCE: 2,
    HIGH_PRIORITY_CONTEST: 5,   // 国家级/国际级: NOI, CTSC, APIO, WC
    MID_PRIORITY_CONTEST: 3,    // 省选级: NOIP提高, NOIP
    LOW_PRIORITY_CONTEST: 1,    // 普及/入门级: CSP提高, CSP入门, NOIP普及
    LEVEL: 1, SCORE: 1, RANK: 1,
};

const CONTEST_PRIORITY = {
    'NOI': 1, 'CTSC': 1, 'APIO': 1, 'WC': 1, 'NOID类': 1,
    'NOIP提高': 2, 'NOIP': 2,
    'CSP提高': 3,
    'NOIP普及': 4, 'CSP入门': 4,
};

const MINIMUM_QUERY_STRENGTH = 20;
const MAX_FILTERS_ALLOWED = 20;


// --- 辅助函数 ---
function toArray(value) { if (value === undefined || value === null) return []; return Array.isArray(value) ? value.filter(v => v !== undefined && v !== null) : [value]; }
function pushInClause(targetWhere, targetParams, column, values) { if (!values || values.length === 0) return; if (values.length === 1) { targetWhere.push(`${column} = ?`); targetParams.push(values[0]); } else { const placeholders = values.map(() => '?').join(','); targetWhere.push(`${column} IN (${placeholders})`); targetParams.push(...values); } }
function formatUsageStep(name, meta) { return { name, rows_read: meta?.rows_read ?? 0, rows_written: meta?.rows_written ?? 0, duration_ms: meta?.duration ?? 0 }; }
function normalizeLimit(value, fallback = 100) { const num = Number(value); if (!Number.isFinite(num) || num <= 0) return fallback; return Math.min(Math.floor(num), 100); }


// --- 过滤器处理与排序函数 ---
function isSubset(filterA, filterB) {
    const check = (keyA, keyB) => {
        const valA = toArray(filterA[keyA] ?? filterA[keyB]);
        const valB = toArray(filterB[keyA] ?? filterB[keyB]);
        if (valA.length === 0) return true;
        if (valB.length === 0) return false;
        return valA.every(v => valB.includes(v));
    };
    const checkRange = (minKey, maxKey) => {
        const minA = filterA[minKey], maxA = filterA[maxKey];
        const minB = filterB[minKey], maxB = filterB[maxKey];
        if (minA !== undefined && (minB === undefined || minA < minB)) return false;
        if (maxA !== undefined && (maxB === undefined || maxA > maxB)) return false;
        return true;
    };
    return check('level', 'levels') && check('province', 'provinces') &&
           check('school_id', 'school_ids') && check('contest_id', 'contest_ids') &&
           check('contest_type', 'contest_types') &&
           checkRange('year_start', 'year_end') &&
           checkRange('min_score', 'max_score') && checkRange('min_rank', 'max_rank');
}

function getFilterSelectivity(filter) {
    if (filter.contest_id || filter.school_id) return 1;
    const years = Array.from({ length: filter.year_end - filter.year_start + 1 }, (_, i) => filter.year_start + i);
    const types = toArray(filter.contest_type ?? filter.contest_types);
    const provinces = toArray(filter.province ?? filter.provinces);
    const levels = toArray(filter.level ?? filter.levels);
    if (years.length === 0 || types.length === 0) return 100000;
    let estimatedCount = 0;
    for (const year of years) {
        if (!CONTEST_STATS[year]) continue;
        for (const type of types) {
            if (!CONTEST_STATS[year][type]) continue;
            const relevantProvinces = provinces.length > 0 ? provinces : Object.keys(CONTEST_STATS[year][type]);
            for (const province of relevantProvinces) {
                if (!CONTEST_STATS[year][type][province]) continue;
                const relevantLevels = levels.length > 0 ? levels : Object.keys(CONTEST_STATS[year][type][province]);
                for (const level of relevantLevels) {
                    estimatedCount += CONTEST_STATS[year]?.[type]?.[province]?.[level] ?? 0;
                }
            }
        }
    }
    return estimatedCount > 0 ? estimatedCount : 1;
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
        const priority = CONTEST_PRIORITY[type];
        if (priority === 1) score += STRENGTH_SCORES.HIGH_PRIORITY_CONTEST;
        else if (priority === 2) score += STRENGTH_SCORES.MID_PRIORITY_CONTEST;
        else score += STRENGTH_SCORES.LOW_PRIORITY_CONTEST;
    }
    return score;
}

// --- 内存过滤器 & SQL 查询构建器 ---
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

function buildRecordSubquery(filter = {}, candidateUids = null) {
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
    const hasContestFilter = filter.year_start || filter.year_end || filter.fall_semester !== undefined || toArray(filter.contest_type ?? filter.contest_types).length > 0;
    if (hasContestFilter) {
        if (filter.year_start) { contestWhere.push('c.year >= ?'); contestParams.push(filter.year_start); }
        if (filter.year_end) { contestWhere.push('c.year <= ?'); contestParams.push(filter.year_end); }
        if (filter.fall_semester !== undefined) { contestWhere.push('c.fall_semester = ?'); contestParams.push(filter.fall_semester ? 1 : 0); }
        pushInClause(contestWhere, contestParams, 'c.type', toArray(filter.contest_type ?? filter.contest_types));
    }
    const filterParamCount = recordParams.length + contestParams.length;
    const needsContestJoin = contestWhere.length > 0;
    if (candidateUids === null || candidateUids.length === 0) {
        const fromClause = needsContestJoin ? 'Record r JOIN Contest c ON r.contest_id = c.id' : 'Record r';
        const initialRecordWhereClauses = [], initialRecordParams = [];
        pushInClause(initialRecordWhereClauses, initialRecordParams, 'r.level', toArray(filter.level ?? filter.levels));
        if (filter.min_score !== undefined) { initialRecordWhereClauses.push('r.score >= ?'); initialRecordParams.push(Number(filter.min_score)); }
        if (filter.max_score !== undefined) { initialRecordWhereClauses.push('r.score <= ?'); initialRecordParams.push(Number(filter.max_score)); }
        if (filter.min_rank !== undefined) { initialRecordWhereClauses.push('r.rank >= ?'); initialRecordParams.push(Number(filter.min_rank)); }
        if (filter.max_rank !== undefined) { initialRecordWhereClauses.push('r.rank <= ?'); initialRecordParams.push(Number(filter.max_rank)); }
        pushInClause(initialRecordWhereClauses, initialRecordParams, 'r.province', toArray(filter.province ?? filter.provinces));
        pushInClause(initialRecordWhereClauses, initialRecordParams, 'r.school_id', toArray(filter.school_id ?? filter.school_ids));
        pushInClause(initialRecordWhereClauses, initialRecordParams, 'r.contest_id', toArray(filter.contest_id ?? filter.contest_ids));
        const whereClauses = [...initialRecordWhereClauses, ...contestWhere];
        const whereSql = whereClauses.length > 0 ? `WHERE ${whereClauses.join(' AND ')}` : '';
        const sql = `SELECT DISTINCT r.oier_uid FROM ${fromClause} ${whereSql}`;
        const params = [...initialRecordParams, ...contestParams];
        return { sql, params, filterParamCount };
    } else {
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
}


const D1_MAX_VARS = 100;

// --- 主处理器 ---
export default async function queryOierHandler(c) {
    if (c.req.method !== "POST") return c.json({ error: "Only POST is supported" }, 405);
    let payload;
    try { payload = await c.req.json(); } catch (err) { return c.json({ error: "Invalid JSON" }, 400); }

    try {
        const initialRecordFilters = toArray(payload.record_filters);
        const oierFilters = payload.oier_filters ?? {};
        const limit = normalizeLimit(payload.limit);

        // --- 阶段 0: 安全检查与过滤器预处理 ---
        if (initialRecordFilters.length > MAX_FILTERS_ALLOWED) {
            return c.json({ error: `Too many record filters. A maximum of ${MAX_FILTERS_ALLOWED} is allowed.` }, 400);
        }
        let processedFilters = initialRecordFilters.map(f => {
            let filter = { ...f };
            if (filter.year) {
                filter.year_start = filter.year;
                filter.year_end = filter.year;
            }
            filter.year_start = Math.max(filter.year_start ?? min_year, min_year);
            filter.year_end = Math.min(filter.year_end ?? max_year, max_year);
            return filter;
        }).filter(f => {
            const isTooBroad = f.year_start <= min_year && f.year_end >= max_year;
            const hasOtherConditions = Object.keys(f).some(k => !['year', 'year_start', 'year_end'].includes(k));
            return !(isTooBroad && !hasOtherConditions);
        });
        processedFilters = processedFilters.reduce((acc, current) => {
            let shouldAdd = true;
            const nextAcc = [];
            for (const existing of acc) {
                if (isSubset(current, existing)) {} 
                else if (isSubset(existing, current)) { shouldAdd = false; nextAcc.push(existing); } 
                else { nextAcc.push(existing); }
            }
            if (shouldAdd) nextAcc.push(current);
            return nextAcc;
        }, []);
        const totalStrength = processedFilters.reduce((sum, f) => sum + getFilterStrength(f), 0) + getFilterStrength(oierFilters, true);
        if (processedFilters.length === 0 && Object.keys(oierFilters).length === 0) {
            return c.json({ error: "Query is too broad. Please provide at least one filter." }, 400);
        }
        if (totalStrength < MINIMUM_QUERY_STRENGTH) {
            return c.json({ error: `Query is too broad. Your query strength score is ${totalStrength}, minimum required is ${MINIMUM_QUERY_STRENGTH}.` }, 400);
        }
        const recordFilters = processedFilters.sort((a, b) => getFilterSelectivity(a) - getFilterSelectivity(b));
        
        // --- 阶段 1: 核心查询逻辑 ---
        const usageSteps = [];
        let candidateUids = null; 
        if (recordFilters.length > 0 && getFilterSelectivity(recordFilters[0]) < 1) {
            candidateUids = [];
        } else {
            
            const VERIFICATION_THRESHOLD = 50;
            let verificationMode = false;
            const oierRecordsMap = new Map();
            for (let i = 0; i < recordFilters.length; i++) {
                const filter = recordFilters[i];
                if (candidateUids !== null && candidateUids.length === 0) break;
                if (i === 0 && candidateUids === null) {
                    let effectiveFilter = { ...filter };
                    const contestWhere = [], contestParams = [];
                    if (filter.year_start || filter.year_end || filter.fall_semester !== undefined || toArray(filter.contest_type ?? filter.contest_types).length > 0) {
                        if (filter.year_start) { contestWhere.push('c.year >= ?'); contestParams.push(filter.year_start); }
                        if (filter.year_end) { contestWhere.push('c.year <= ?'); contestParams.push(filter.year_end); }
                        if (filter.fall_semester !== undefined) { contestWhere.push('c.fall_semester = ?'); contestParams.push(filter.fall_semester ? 1 : 0); }
                        pushInClause(contestWhere, contestParams, 'c.type', toArray(filter.contest_type ?? filter.contest_types));
                    }
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
                    const chunks = candidateUids ? [] : [null];
                    if (candidateUids) { for (let j = 0; j < candidateUids.length; j += dynamicChunkSize) { chunks.push(candidateUids.slice(j, j + dynamicChunkSize)); } }
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
        }
        
        // --- 阶段 2: 最终 OIer 查询 ---
        if (candidateUids !== null && candidateUids.length === 0) {
            const totals = usageSteps.reduce((acc, step) => { acc.rows_read += step.rows_read; acc.rows_written += step.rows_written; return acc; }, { rows_read: 0, rows_written: 0 });
            return c.json({ data: [], usage: { steps: usageSteps, total_rows_read: totals.rows_read, total_rows_written: totals.rows_written }});
        }
        
        // --- [核心改动] 1. 在查询 OIer 详细信息前，对 UID 进行排序和截断 ---
        if (candidateUids !== null) {
            candidateUids.sort((a, b) => a - b); // 按 UID 升序排序
            candidateUids = candidateUids.slice(0, limit); // 截取前 limit 个
            if (candidateUids.length === 0) {
                // 如果截断后为空（例如 limit 为 0），直接返回
                const totals = usageSteps.reduce((acc, step) => { acc.rows_read += step.rows_read; acc.rows_written += step.rows_written; return acc; }, { rows_read: 0, rows_written: 0 });
                return c.json({ data: [], usage: { steps: usageSteps, total_rows_read: totals.rows_read, total_rows_written: totals.rows_written }});
            }
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
            // --- [核心改动] 2. 修改无候选人时的排序方式 ---
            const sql = `SELECT * FROM OIer o ${whereClause} ORDER BY o.uid ASC LIMIT ?;`;
            const params = [...oierBaseParams, limit];
            const { results, meta } = await c.env.DB.prepare(sql).bind(...params).all();
            allOiers = results || [];
            usageSteps.push(formatUsageStep("final_oier_query_no_uids", meta));
        }

        // --- [核心改動] 3. 移除 oierdb_score 排序，确保最终输出按 UID 升序 ---
        //    因为并行 chunk 查询可能打乱顺序，所以需要最后再排一次序。
        allOiers.sort((a, b) => a.uid - b.uid);
        
        const finalResults = allOiers; // 不再需要 slice，因为 UID 已经在前面截断
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