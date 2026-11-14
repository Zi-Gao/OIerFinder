CREATE TABLE OierSyncPayload (
    release_id TEXT NOT NULL CHECK (length(release_id) = 64),
    digest TEXT NOT NULL CHECK (length(digest) = 64),
    body TEXT NOT NULL CHECK (json_valid(body) AND json_type(body) = 'array' AND length(CAST(body AS BLOB)) <= 2000000),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (release_id, digest)
) WITHOUT ROWID;

CREATE TRIGGER oier_sync_payload_immutable BEFORE UPDATE ON OierSyncPayload BEGIN
    SELECT RAISE(ABORT, 'Staged sync payloads are immutable');
END;

CREATE TRIGGER oier_sync_payload_delete BEFORE DELETE ON OierSyncPayload BEGIN
    SELECT RAISE(ABORT, 'Payload cleanup requires the guarded publisher') WHERE COALESCE((SELECT writing FROM OierSyncState WHERE id = 1), 0) != 1;
END;
