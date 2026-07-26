CREATE TABLE IF NOT EXISTS School (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    province TEXT,
    city TEXT,
    score REAL
);

CREATE TABLE IF NOT EXISTS Contest (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT,
    year INTEGER,
    fall_semester BOOLEAN,
    full_score INTEGER
);

CREATE TABLE IF NOT EXISTS OIer (
    uid INTEGER PRIMARY KEY,
    initials TEXT,
    name TEXT NOT NULL,
    gender INTEGER,
    enroll_middle INTEGER,
    oierdb_score REAL,
    ccf_score REAL,
    ccf_level INTEGER
);

CREATE TABLE IF NOT EXISTS Record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    oier_uid INTEGER,
    contest_id INTEGER,
    school_id INTEGER,
    score REAL,
    rank INTEGER,
    province TEXT,
    level TEXT,
    FOREIGN KEY(oier_uid) REFERENCES OIer(uid),
    FOREIGN KEY(contest_id) REFERENCES Contest(id),
    FOREIGN KEY(school_id) REFERENCES School(id)
);
