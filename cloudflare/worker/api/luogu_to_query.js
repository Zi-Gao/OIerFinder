// cloudflare/worker/functions/luogu_to_query.js

// --- 静态映射 ---
const CONTEST_MAPPING = {
  "CSP-J": "CSP入门", "CSP-S": "CSP提高", "NOIP 普及组": "NOIP普及",
  "NOIP 提高组": "NOIP提高", "NOIP": "NOIP", "NOI 冬令营": "WC",
  "NOI 夏令营": "NOID类", "NOI": "NOI", "APIO": "APIO",
  "APIO 线上": "APIO", "CTSC": "CTSC",
};
const LEVEL_MAPPING = {
  "金牌": "金牌", "银牌": "银牌", "铜牌": "铜牌",
  "一等奖": "一等奖", "二等奖": "二等奖", "三等奖": "三等奖",
};

// --- 核心算法 ---

/**
 * 检查 prizeContainer 是否“包含” prizeContent。
 * “包含”定义：对于 prizeContent 中所有非 null 的字段，
 * prizeContainer 的对应字段也必须不为 null 且值完全相等。
 */
function isContained(prizeContainer, prizeContent) {
    const fieldsToCheck = ['contest_name', 'prize_level', 'year', 'score', 'rank', 'event'];
    for (const key of fieldsToCheck) {
        if (prizeContent[key] !== null) {
            if (prizeContainer[key] !== prizeContent[key]) {
                return false;
            }
        }
    }
    return true;
}

/**
 * 合并两条匹配的奖项记录，优先取非 null 值，创建一个更丰富的记录。
 */
function mergeMatchedPrizes(prizeA, prizeB) {
    return {
        id: prizeA.id ?? prizeB.id,
        luogu_uid: prizeA.luogu_uid,
        contest_name: prizeA.contest_name ?? prizeB.contest_name,
        prize_level: prizeA.prize_level ?? prizeB.prize_level,
        year: prizeA.year ?? prizeB.year,
        score: prizeA.score ?? prizeB.score,
        rank: prizeA.rank ?? prizeB.rank,
        event: prizeA.event ?? prizeB.event,
        is_noi_series: prizeA.is_noi_series || prizeB.is_noi_series,
    };
}

/**
 * 核心合并逻辑：数据积累和丰富，不删除。
 */
function mergePrizes(luoguPrizes, d1Prizes) {
    const finalPrizeList = JSON.parse(JSON.stringify(d1Prizes));
    for (const luoguPrize of luoguPrizes) {
        let foundMatch = false;
        for (let i = 0; i < finalPrizeList.length; i++) {
            const existingPrize = finalPrizeList[i];
            if (isContained(luoguPrize, existingPrize) || isContained(existingPrize, luoguPrize)) {
                finalPrizeList[i] = mergeMatchedPrizes(existingPrize, luoguPrize);
                foundMatch = true;
                break;
            }
        }
        if (!foundMatch) {
            finalPrizeList.push(luoguPrize);
        }
    }
    return finalPrizeList;
}

/**
 * 为奖项记录生成一个稳定的唯一业务键。
 */
function getPrizeKey(prize) {
    return `${prize.contest_name}|${prize.prize_level}|${prize.year ?? 'null'}`;
}

/**
 * 比较两条奖项记录的内容是否完全相同（忽略 id）。
 */
function arePrizesEqual(prizeA, prizeB) {
    return prizeA.contest_name === prizeB.contest_name &&
           prizeA.prize_level === prizeB.prize_level &&
           prizeA.year === prizeB.year &&
           prizeA.score === prizeB.score &&
           prizeA.rank === prizeB.rank &&
           prizeA.event === prizeB.event &&
           (!!prizeA.is_noi_series) === (!!prizeB.is_noi_series);
}

/**
 * 增量更新 D1 数据库 (无删除逻辑)。
 */
async function updateD1PrizesIncremental(db, uid, finalMergedPrizes, originalD1Prizes) {
    const operations = [];
    const finalPrizesMap = new Map();
    // 使用更健壮的键来处理可能存在的重复业务键
    finalMergedPrizes.forEach((p, i) => finalPrizesMap.set(`${getPrizeKey(p)}-${i}`, p));
    const originalPrizesMap = new Map(originalD1Prizes.map(p => [p.id, p]));

    const matchedOriginalIds = new Set();

    for (const finalPrize of finalMergedPrizes) {
        if (finalPrize.id !== undefined && originalPrizesMap.has(finalPrize.id)) {
            // 这是一条可能被更新的现有记录
            const originalPrize = originalPrizesMap.get(finalPrize.id);
            if (!arePrizesEqual(finalPrize, originalPrize)) {
                operations.push(
                    db.prepare(`UPDATE LuoguPrizes SET contest_name = ?1, prize_level = ?2, year = ?3, score = ?4, rank = ?5, event = ?6, is_noi_series = ?7 WHERE id = ?8`)
                      .bind(finalPrize.contest_name, finalPrize.prize_level, finalPrize.year, finalPrize.score, finalPrize.rank, finalPrize.event, finalPrize.is_noi_series ? 1 : 0, finalPrize.id)
                );
            }
            matchedOriginalIds.add(finalPrize.id);
        } else {
            // 这是一条新记录
             operations.push(
                db.prepare(`INSERT INTO LuoguPrizes (luogu_uid, contest_name, prize_level, year, score, rank, event, is_noi_series) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)`)
                  .bind(uid, finalPrize.contest_name, finalPrize.prize_level, finalPrize.year, finalPrize.score, finalPrize.rank, finalPrize.event, finalPrize.is_noi_series ? 1 : 0)
            );
        }
    }

    if (operations.length > 0) {
        console.log(`Incremental update for UID ${uid}: ${operations.length} operations performed.`);
        await db.batch(operations);
    } else {
        console.log(`Incremental update for UID ${uid}: No changes detected.`);
    }
}

// --- 数据获取与协调 ---

async function fetchAndProcessLuoguPrizes(uid) {
  const luoguApiUrl = `https://www.luogu.com.cn/offlinePrize/getList/${uid}`;
  const response = await fetch(luoguApiUrl, { headers: { "User-Agent": "OIerFinder-Worker/1.0" } });
  if (!response.ok) throw new Error(`Failed to fetch from Luogu API, status: ${response.status}`);
  const luoguData = await response.json();
  if (!luoguData || !Array.isArray(luoguData.prizes)) throw new Error("Invalid data structure from Luogu API");
  return luoguData.prizes.map(({ prize }) => {
    if (!prize) return null;
    return {
      luogu_uid: parseInt(uid, 10), contest_name: prize.contest, prize_level: prize.prize,
      year: prize.year ?? null, score: prize.score ?? null, rank: prize.rank ?? null, event: prize.event ?? null,
      is_noi_series: prize.contest in CONTEST_MAPPING,
    };
  }).filter(Boolean);
}

async function fetchD1Prizes(db, uid) {
  const stmt = db.prepare("SELECT * FROM LuoguPrizes WHERE luogu_uid = ?1").bind(uid);
  const { results } = await stmt.all(); return results || [];
}

export async function getPrizes(uid, sync, env, ctx) {
    const originalD1Prizes = await fetchD1Prizes(env.DB, uid);
    if (sync) {
        const luoguPrizes = await fetchAndProcessLuoguPrizes(uid);
        const finalMergedPrizes = mergePrizes(luoguPrizes, originalD1Prizes);
        ctx.waitUntil(updateD1PrizesIncremental(env.DB, uid, finalMergedPrizes, originalD1Prizes));
        return finalMergedPrizes;
    }
    return originalD1Prizes;
}


// --- 端点处理器 (适配为 Hono Handler) ---
function generateQueryPayload(prizes) {
    const noiSeriesPrizes = prizes.filter(p => p.is_noi_series);
    const recordFilters = noiSeriesPrizes.map(prize => {
        const mappedContest = CONTEST_MAPPING[prize.contest_name];
        const mappedLevel = LEVEL_MAPPING[prize.prize_level];
        if (!mappedContest || !mappedLevel) return null;
        const filter = {
            contest_type: mappedContest,
            level: mappedLevel,
            year: prize.year,
        };
        if (prize.score !== null) { filter.min_score = prize.score; filter.max_score = prize.score; }
        if (prize.rank !== null) { filter.min_rank = prize.rank; filter.max_rank = prize.rank; }
        return filter;
    }).filter(Boolean);
    return { record_filters: recordFilters, oier_filters: {} };
}

export default async function luoguToQueryHandler(c) {
    // c.executionCtx: 相当于之前的 ctx
    const ADMIN_SECRET = c.env.ADMIN_SECRET;
    const clientSecret = c.req.header('X-Admin-Secret');
    const isAdmin = ADMIN_SECRET && clientSecret === ADMIN_SECRET;
    try {
        const uid = c.req.query("uid");
        const sync = c.req.query("sync") === 'true' || c.req.query("sync") === '1';

        if (!uid) {
            return c.json({ error: "Missing 'uid' query parameter" }, 400);
        }

        const prizeList = await getPrizes(uid, sync, c.env, c.executionCtx);
        const queryPayload = generateQueryPayload(prizeList);
        
        return c.json(queryPayload);

    } catch (err) {
        console.error('Error in queryOierHandler:', err);

        // 默认返回通用的、不含细节的错误信息
        const errorResponse = { error: 'An internal server error occurred.' };

        // 如果是管理员，则添加详细的调试信息
        if (isAdmin) {
            errorResponse.details = err.message;
            errorResponse.stack = err.stack; // 堆栈信息对调试非常有用
        }

        return c.json(errorResponse, 500);
    }
}
