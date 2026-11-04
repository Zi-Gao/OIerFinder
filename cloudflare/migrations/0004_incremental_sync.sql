ALTER TABLE DataRelease ADD COLUMN snapshot_commit TEXT;
ALTER TABLE DataRelease ADD COLUMN snapshot_sha256 TEXT;
ALTER TABLE DataRelease ADD COLUMN projection_version TEXT;
ALTER TABLE DataRelease ADD COLUMN logical_data_hash TEXT;
ALTER TABLE DataRelease ADD COLUMN core_revision INTEGER;

CREATE TABLE OierSyncState (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    revision INTEGER NOT NULL CHECK (typeof(revision) = 'integer' AND revision >= 0 AND revision <= 9007199254740991),
    writing INTEGER NOT NULL DEFAULT 0 CHECK (writing IN (0, 1))
);
INSERT INTO OierSyncState(id,revision,writing) VALUES (1, 0, 0);

CREATE TABLE OierSyncGuard (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    ok INTEGER NOT NULL CONSTRAINT sync_assertion_failed CHECK (ok = 1)
);

CREATE TABLE OierSyncBudget (
    day TEXT PRIMARY KEY,
    estimated_writes INTEGER NOT NULL CHECK (typeof(estimated_writes) = 'integer' AND estimated_writes >= 0 AND estimated_writes <= 9007199254740991)
);

-- Every core-table mutation participates in the same transaction as its revision.
-- A missing state row must abort the write, not silently disable drift detection.
CREATE TRIGGER oier_sync_OIer_insert AFTER INSERT ON OIer BEGIN
    SELECT RAISE(ABORT, 'Missing OierSyncState') WHERE NOT EXISTS (SELECT 1 FROM OierSyncState WHERE id = 1);
    SELECT RAISE(ABORT, 'Core writes require the guarded publisher') WHERE (SELECT writing FROM OierSyncState WHERE id = 1) != 1;
    UPDATE OierSyncState SET revision = revision + 1 WHERE id = 1;
END;
CREATE TRIGGER oier_sync_OIer_update AFTER UPDATE ON OIer BEGIN
    SELECT RAISE(ABORT, 'Missing OierSyncState') WHERE NOT EXISTS (SELECT 1 FROM OierSyncState WHERE id = 1);
    SELECT RAISE(ABORT, 'Core writes require the guarded publisher') WHERE (SELECT writing FROM OierSyncState WHERE id = 1) != 1;
    UPDATE OierSyncState SET revision = revision + 1 WHERE id = 1;
END;
CREATE TRIGGER oier_sync_OIer_delete AFTER DELETE ON OIer BEGIN
    SELECT RAISE(ABORT, 'Missing OierSyncState') WHERE NOT EXISTS (SELECT 1 FROM OierSyncState WHERE id = 1);
    SELECT RAISE(ABORT, 'Core writes require the guarded publisher') WHERE (SELECT writing FROM OierSyncState WHERE id = 1) != 1;
    UPDATE OierSyncState SET revision = revision + 1 WHERE id = 1;
END;
CREATE TRIGGER oier_sync_Contest_insert AFTER INSERT ON Contest BEGIN
    SELECT RAISE(ABORT, 'Missing OierSyncState') WHERE NOT EXISTS (SELECT 1 FROM OierSyncState WHERE id = 1);
    SELECT RAISE(ABORT, 'Core writes require the guarded publisher') WHERE (SELECT writing FROM OierSyncState WHERE id = 1) != 1;
    UPDATE OierSyncState SET revision = revision + 1 WHERE id = 1;
END;
CREATE TRIGGER oier_sync_Contest_update AFTER UPDATE ON Contest BEGIN
    SELECT RAISE(ABORT, 'Missing OierSyncState') WHERE NOT EXISTS (SELECT 1 FROM OierSyncState WHERE id = 1);
    SELECT RAISE(ABORT, 'Core writes require the guarded publisher') WHERE (SELECT writing FROM OierSyncState WHERE id = 1) != 1;
    UPDATE OierSyncState SET revision = revision + 1 WHERE id = 1;
END;
CREATE TRIGGER oier_sync_Contest_delete AFTER DELETE ON Contest BEGIN
    SELECT RAISE(ABORT, 'Missing OierSyncState') WHERE NOT EXISTS (SELECT 1 FROM OierSyncState WHERE id = 1);
    SELECT RAISE(ABORT, 'Core writes require the guarded publisher') WHERE (SELECT writing FROM OierSyncState WHERE id = 1) != 1;
    UPDATE OierSyncState SET revision = revision + 1 WHERE id = 1;
END;
CREATE TRIGGER oier_sync_School_insert AFTER INSERT ON School BEGIN
    SELECT RAISE(ABORT, 'Missing OierSyncState') WHERE NOT EXISTS (SELECT 1 FROM OierSyncState WHERE id = 1);
    SELECT RAISE(ABORT, 'Core writes require the guarded publisher') WHERE (SELECT writing FROM OierSyncState WHERE id = 1) != 1;
    UPDATE OierSyncState SET revision = revision + 1 WHERE id = 1;
END;
CREATE TRIGGER oier_sync_School_update AFTER UPDATE ON School BEGIN
    SELECT RAISE(ABORT, 'Missing OierSyncState') WHERE NOT EXISTS (SELECT 1 FROM OierSyncState WHERE id = 1);
    SELECT RAISE(ABORT, 'Core writes require the guarded publisher') WHERE (SELECT writing FROM OierSyncState WHERE id = 1) != 1;
    UPDATE OierSyncState SET revision = revision + 1 WHERE id = 1;
END;
CREATE TRIGGER oier_sync_School_delete AFTER DELETE ON School BEGIN
    SELECT RAISE(ABORT, 'Missing OierSyncState') WHERE NOT EXISTS (SELECT 1 FROM OierSyncState WHERE id = 1);
    SELECT RAISE(ABORT, 'Core writes require the guarded publisher') WHERE (SELECT writing FROM OierSyncState WHERE id = 1) != 1;
    UPDATE OierSyncState SET revision = revision + 1 WHERE id = 1;
END;
CREATE TRIGGER oier_sync_Record_insert AFTER INSERT ON Record BEGIN
    SELECT RAISE(ABORT, 'Missing OierSyncState') WHERE NOT EXISTS (SELECT 1 FROM OierSyncState WHERE id = 1);
    SELECT RAISE(ABORT, 'Core writes require the guarded publisher') WHERE (SELECT writing FROM OierSyncState WHERE id = 1) != 1;
    UPDATE OierSyncState SET revision = revision + 1 WHERE id = 1;
END;
CREATE TRIGGER oier_sync_Record_update AFTER UPDATE ON Record BEGIN
    SELECT RAISE(ABORT, 'Missing OierSyncState') WHERE NOT EXISTS (SELECT 1 FROM OierSyncState WHERE id = 1);
    SELECT RAISE(ABORT, 'Core writes require the guarded publisher') WHERE (SELECT writing FROM OierSyncState WHERE id = 1) != 1;
    UPDATE OierSyncState SET revision = revision + 1 WHERE id = 1;
END;
CREATE TRIGGER oier_sync_Record_delete AFTER DELETE ON Record BEGIN
    SELECT RAISE(ABORT, 'Missing OierSyncState') WHERE NOT EXISTS (SELECT 1 FROM OierSyncState WHERE id = 1);
    SELECT RAISE(ABORT, 'Core writes require the guarded publisher') WHERE (SELECT writing FROM OierSyncState WHERE id = 1) != 1;
    UPDATE OierSyncState SET revision = revision + 1 WHERE id = 1;
END;
