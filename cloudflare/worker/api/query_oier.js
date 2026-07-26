// cloudflare/worker/functions/query_oier.js
// 1. [数据导入] 从外部 JSON 文件导入预计算的统计数据。
import CONTEST_STATS_DATA from './contest_stats.json';
import { removeRedundantFilters } from './filter_subset.js';
import {
    D1_MAX_VARS,
    assertNoConflictingFilterAliases,
    exceedsD1ParameterLimit,
    getFilterStrength,
} from './query_policy.js';
import {
    buildRecordSubquery,
    pushInClause,
    recordMatchesFilter,
    toArray,
} from './record_query.js';
// --- 业务逻辑与安全常量 ---
const { min_year, max_year, stats: CONTEST_STATS } = CONTEST_STATS_DATA;
const MINIMUM_QUERY_STRENGTH = 20;
const MAX_FILTERS_ALLOWED = 20;
const MAX_D1_CHUNKS_PER_FILTER = 50;
const D1_QUERY_CONCURRENCY = 8;
// --- 辅助函数 ---
function formatUsageStep(name, meta) { return { name, rows_read: meta?.rows_read ?? 0, rows_written: meta?.rows_written ?? 0, duration_ms: meta?.duration ?? 0 }; }
function parseFiniteNumber(value, fieldName) {
    if (
        typeof value === 'boolean' ||
        (typeof value === 'string' && value.trim().length === 0)
    ) {
        throw new Error(`'${fieldName}' must be a valid number.`);
    }
    const numberValue = Number(value);
    if (!Number.isFinite(numberValue)) {
        throw new Error(`'${fieldName}' must be a valid number.`);
    }
    return numberValue;
}
function normalizeLimit(value) {
    const numberValue = parseFiniteNumber(value, 'limit');
    if (numberValue <= 0) {
        throw new Error("'limit' must be a positive number.");
    }
    return Math.min(Math.floor(numberValue), 100);
}
async function mapWithConcurrency(items, concurrency, mapper) {
    const results = new Array(items.length);
    let nextIndex = 0;
    const workers = Array.from(
        { length: Math.min(concurrency, items.length) },
        async () => {
            while (nextIndex < items.length) {
                const currentIndex = nextIndex;
                nextIndex += 1;
                results[currentIndex] = await mapper(items[currentIndex], currentIndex);
            }
        },
    );
    await Promise.all(workers);
    return results;
}

// [新增] 输入验证与清理函数，作为第一道安全防线
const ALLOWED_RECORD_KEYS = new Set([
    'level', 'levels', 'min_score', 'max_score', 'min_rank', 'max_rank',
    'province', 'provinces', 'school_id', 'school_ids', 'contest_id', 'contest_ids',
    'year', 'years', 'year_start', 'year_end', 'fall_semester', 'contest_type', 'contest_types'
]);
const ALLOWED_OIER_KEYS = new Set(['gender', 'genders', 'enroll_min', 'enroll_max', 'initials']);

function validateAndSanitizeFilter(filter, allowedKeys) {
    if (typeof filter !== 'object' || filter === null || Array.isArray(filter)) {
        throw new Error('Filter must be an object.');
    }
    for (const key of Object.keys(filter)) {
        if (!allowedKeys.has(key)) {
            throw new Error(`Invalid filter parameter: '${key}'`);
        }
    }
    assertNoConflictingFilterAliases(filter);

    const sanitized = {};
    for (const [key, rawValue] of Object.entries(filter)) {
        if (rawValue === undefined || rawValue === null) continue;

        // 对不同类型的 key 进行类型检查和清理
        switch (key) {
            // 数值型
            case 'year': case 'year_start': case 'year_end':
            case 'enroll_min': case 'enroll_max':
            case 'min_score': case 'max_score':
            case 'min_rank': case 'max_rank':
            case 'school_id': case 'contest_id':
            {
                sanitized[key] = parseFiniteNumber(rawValue, key);
                break;
            }
            // 布尔型
            case 'fall_semester':
                if (typeof rawValue !== 'boolean') {
                    throw new Error("'fall_semester' must be a boolean.");
                }
                sanitized[key] = rawValue;
                break;
            // 字符串型
            case 'level': case 'province': case 'contest_type':
                if (typeof rawValue !== 'string' || rawValue.trim().length === 0) throw new Error(`'${key}' must be a non-empty string.`);
                sanitized[key] = rawValue.trim();
                break;
            // 数值数组
            case 'years': case 'school_ids': case 'contest_ids':
            {
                const numArray = toArray(rawValue).map(
                    value => parseFiniteNumber(value, key),
                );
                if (numArray.length > 0) sanitized[key] = [...new Set(numArray)];
                break;
            }
            // 字符串数组
            case 'levels': case 'provinces': case 'contest_types': case 'genders': case 'initials':
            {
                const strArray = toArray(rawValue);
                if (strArray.some(s => (typeof s !== 'string' && typeof s !== 'number') || String(s).trim().length === 0)) throw new Error(`All items in '${key}' must be non-empty strings or numbers.`);
                if (strArray.length > 0) {
                    sanitized[key] = [...new Set(strArray.map(s => String(s).trim()))];
                }
                break;
            }
            // 兼容性字段 (gender -> genders)
            case 'gender':
            {
                let gVal = rawValue;
                if (gVal !== null && gVal !== undefined) {
                     const gStr = String(gVal).trim();
                     if (gStr.length > 0) {
                        sanitized['genders'] = [gStr];
                     }
                }
                break;
            }
            default:
                sanitized[key] = rawValue; // 对于未明确处理但允许的键，直接赋值
                break;
        }
    }
    return sanitized;
}

function validateAndSanitizePayload(payload) {
    if (typeof payload !== 'object' || payload === null || Array.isArray(payload)) {
        throw new Error("Request body must be a valid JSON object.");
    }

    const sanitizedPayload = {
        record_filters: [],
        oier_filters: {},
        limit: 100
    };

    // 验证 record_filters
    if (payload.record_filters !== undefined) {
        if (!Array.isArray(payload.record_filters)) {
            throw new Error("'record_filters' must be an array.");
        }
        sanitizedPayload.record_filters = payload.record_filters.map(f => validateAndSanitizeFilter(f, ALLOWED_RECORD_KEYS));
    }

    // 验证 oier_filters
    if (payload.oier_filters !== undefined) {
        sanitizedPayload.oier_filters = validateAndSanitizeFilter(payload.oier_filters, ALLOWED_OIER_KEYS);
    }
    
    // 验证和标准化 limit
    if (payload.limit !== undefined) {
        sanitizedPayload.limit = normalizeLimit(payload.limit);
    }

    return sanitizedPayload;
}

// --- 过滤器处理与排序函数 ---
function getFilterSelectivity(filter) {
    if (filter.contest_id || filter.school_id) return 1;
    let years;
    const yearsArray = toArray(filter.years);
    if (yearsArray.length > 0) {
        years = yearsArray;
    } else {
        years = Array.from({ length: filter.year_end - filter.year_start + 1 }, (_, i) => filter.year_start + i);
    }
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
// --- 主处理器 ---
export default async function queryOierHandler(c) {
    if (c.req.method !== "POST") return c.json({ error: "Only POST is supported" }, 405);

    try {
        let payload;
        try { payload = await c.req.json(); } catch { return c.json({ error: "Invalid JSON" }, 400); }

        // [新增] 阶段 -1: 输入验证与清理
        // 在这里调用新的验证函数，如果输入不合法，它会抛出错误，被外层 try...catch 捕获并返回 400 错误。
        const validatedPayload = validateAndSanitizePayload(payload);

        const ADMIN_SECRET = c.env.ADMIN_SECRET;
        const clientSecret = c.req.header('X-Admin-Secret');
        const isAdmin = ADMIN_SECRET && clientSecret === ADMIN_SECRET;

        // [修改] 使用经过验证和清理后的数据
        const initialRecordFilters = validatedPayload.record_filters;
        const oierFilters = validatedPayload.oier_filters;
        const limit = validatedPayload.limit;

        // --- 阶段 0: 安全检查与过滤器预处理 ---
        if (!isAdmin && initialRecordFilters.length > MAX_FILTERS_ALLOWED) {
            return c.json({ error: `Too many record filters. A maximum of ${MAX_FILTERS_ALLOWED} is allowed.` }, 400);
        }
        const strengthFilters = removeRedundantFilters(
            initialRecordFilters,
            min_year,
            max_year,
        );
        let processedFilters = initialRecordFilters.map(f => {
            let filter = { ...f };
            const yearsArray = toArray(filter.years);
            if (yearsArray.length > 0) {
                delete filter.year;
                delete filter.year_start;
                delete filter.year_end;
            } else if (filter.year !== undefined) {
                filter.year_start = filter.year;
                filter.year_end = filter.year;
                delete filter.year;
            }
            filter.year_start = Math.max(filter.year_start ?? min_year, min_year);
            filter.year_end = Math.min(filter.year_end ?? max_year, max_year);
            
            return filter;
        }).filter(f => {
            const isTooBroad = toArray(f.years).length === 0 && f.year_start <= min_year && f.year_end >= max_year;
            const hasOtherConditions = Object.keys(f).some(k => !['year', 'years', 'year_start', 'year_end'].includes(k));
            return !(isTooBroad && !hasOtherConditions);
        });
        processedFilters = removeRedundantFilters(processedFilters, min_year, max_year);
        const totalStrength = strengthFilters.reduce(
            (sum, filter) => sum + getFilterStrength(filter),
            0,
        ) + getFilterStrength(oierFilters, true);
        if (processedFilters.length === 0 && Object.keys(oierFilters).length === 0) {
            return c.json({ error: "Query is too broad. Please provide at least one filter." }, 400);
        }
        if (!isAdmin && totalStrength < MINIMUM_QUERY_STRENGTH) {
            return c.json({ error: `Query is too broad. Your query strength score is ${totalStrength}, minimum required is ${MINIMUM_QUERY_STRENGTH}.` }, 400);
        }
        const recordFilters = processedFilters.sort((a, b) => getFilterSelectivity(a) - getFilterSelectivity(b));
        // --- 阶段 1: 核心查询逻辑 ---
        const usageSteps = [];
        let candidateUids = null;
        const hasOierFilters = oierFilters && (
            toArray(oierFilters.gender ?? oierFilters.genders).length > 0 ||
            oierFilters.enroll_min !== undefined ||
            oierFilters.enroll_max !== undefined ||
            toArray(oierFilters.initials).length > 0
        );
        const oierFiltersAppliedEarly = recordFilters.length > 0 && hasOierFilters;
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
                    const { sql, params } = buildRecordSubquery(filter, null, oierFilters);
                    if (exceedsD1ParameterLimit(params.length)) {
                        return c.json({ error: `Filter at index ${i} is too complex...` }, 400);
                    }
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
                    if (exceedsD1ParameterLimit(filterParamCount, 1)) { return c.json({ error: `Filter at index ${i} is too complex...` }, 400); }
                    const dynamicChunkSize = D1_MAX_VARS - filterParamCount;
                    const chunks = candidateUids ? [] : [null];
                    if (candidateUids) { for (let j = 0; j < candidateUids.length; j += dynamicChunkSize) { chunks.push(candidateUids.slice(j, j + dynamicChunkSize)); } }
                    if (!isAdmin && chunks.length > MAX_D1_CHUNKS_PER_FILTER) {
                        return c.json({
                            error: `Filter at index ${i} would require ${chunks.length} database queries. Add a more selective filter first.`,
                        }, 400);
                    }
                    const resultsFromChunks = await mapWithConcurrency(
                        chunks,
                        D1_QUERY_CONCURRENCY,
                        (chunk) => {
                            const { sql, params } = buildRecordSubquery(filter, chunk);
                            return c.env.DB.prepare(sql).bind(...params).all();
                        },
                    );
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
        if (candidateUids !== null) {
            candidateUids.sort((a, b) => a - b);
            candidateUids = candidateUids.slice(0, limit);
            if (candidateUids.length === 0) {
                const responsePayload = { data: [] };
                if (isAdmin) {
                    const totals = usageSteps.reduce((acc, step) => { acc.rows_read += step.rows_read; acc.rows_written += step.rows_written; return acc; }, { rows_read: 0, rows_written: 0 });
                    responsePayload.usage = { steps: usageSteps, total_rows_read: totals.rows_read, total_rows_written: totals.rows_written };
                }
                return c.json(responsePayload);
            }
        }
        
        const oierWhereClauses = [], oierBaseParams = [];
        if (!oierFiltersAppliedEarly) {
            pushInClause(oierWhereClauses, oierBaseParams, 'o.gender', toArray(oierFilters.gender ?? oierFilters.genders));
            if (oierFilters.enroll_min !== undefined) { oierWhereClauses.push('o.enroll_middle >= ?'); oierBaseParams.push(Number(oierFilters.enroll_min)); }
            if (oierFilters.enroll_max !== undefined) { oierWhereClauses.push('o.enroll_middle <= ?'); oierBaseParams.push(Number(oierFilters.enroll_max)); }
            pushInClause(oierWhereClauses, oierBaseParams, 'o.initials', toArray(oierFilters.initials));
        }
        if (exceedsD1ParameterLimit(oierBaseParams.length, 1)) { return c.json({ error: "Oier filter is too complex..." }, 400); }
        
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
            const sql = `SELECT * FROM OIer o ${whereClause} ORDER BY o.uid ASC LIMIT ?;`;
            const params = [...oierBaseParams, limit];
            const { results, meta } = await c.env.DB.prepare(sql).bind(...params).all();
            allOiers = results || [];
            usageSteps.push(formatUsageStep("final_oier_query_no_uids", meta));
        }
        
        allOiers.sort((a, b) => a.uid - b.uid);
        const finalResults = allOiers;
        
        const responsePayload = { data: finalResults };
        if (isAdmin) {
            const totals = usageSteps.reduce((acc, step) => { acc.rows_read += step.rows_read; acc.rows_written += step.rows_written; return acc; }, { rows_read: 0, rows_written: 0 });
            responsePayload.usage = {
                steps: usageSteps,
                total_rows_read: totals.rows_read,
                total_rows_written: totals.rows_written,
            };
        }
        return c.json(responsePayload);
    } catch (err) {
        // [修改] 统一的错误处理，可以捕获验证错误和执行错误
        console.error('Error in queryOierHandler:', err);
        
        // 检查是否是我们的验证错误，如果是，返回一个更具体的 400 错误
        // 否则，返回通用的 500 错误
        const isValidationError = err.message.startsWith('Invalid') || err.message.includes('must be');
        if (isValidationError) {
            return c.json({ error: err.message }, 400);
        }

        const errorResponse = { error: 'An internal server error occurred.' };
        // is adamin check needs to happen outside the try block to avoid undefined variable
        const clientSecret = c.req.header('X-Admin-Secret');
        const isAdmin = c.env.ADMIN_SECRET && clientSecret === c.env.ADMIN_SECRET;
        if (isAdmin) {
            errorResponse.details = err.message;
            errorResponse.stack = err.stack;
        }
        return c.json(errorResponse, 500);
    }
}
