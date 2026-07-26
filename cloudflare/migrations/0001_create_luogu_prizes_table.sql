-- migrations/0001_create_luogu_prizes_table.sql
-- 迁移必须可安全重放；已有表和数据保持不变。
CREATE TABLE IF NOT EXISTS LuoguPrizes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    luogu_uid INTEGER NOT NULL,
    contest_name TEXT NOT NULL,
    prize_level TEXT NOT NULL,
    year INTEGER,
    score REAL,
    rank INTEGER,
    event TEXT,
    is_noi_series BOOLEAN NOT NULL
);

-- 为 luogu_uid 创建索引，以加速查询和删除
CREATE INDEX IF NOT EXISTS idx_luogu_prizes_uid ON LuoguPrizes(luogu_uid);

-- wrangler d1 execute oier-db --file ../migrations/0001_create_luogu_prizes_table.sql
