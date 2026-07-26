CREATE TABLE IF NOT EXISTS DataRelease (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    upstream_sha TEXT NOT NULL,
    data_hash TEXT NOT NULL,
    worker_version TEXT,
    status TEXT NOT NULL,
    oier_count INTEGER NOT NULL,
    contest_count INTEGER NOT NULL,
    school_count INTEGER NOT NULL,
    record_count INTEGER NOT NULL,
    github_run_url TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    activated_at TEXT
);
