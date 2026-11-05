-- NoticeNest database layout (SQLite).
-- Run automatically by init_db() every time the app or a job starts.

CREATE TABLE IF NOT EXISTS sources (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT UNIQUE NOT NULL,
    kind        TEXT NOT NULL,
    location    TEXT
);

CREATE TABLE IF NOT EXISTS notices (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id        INTEGER NOT NULL REFERENCES sources(id),
    fingerprint      TEXT UNIQUE NOT NULL,   -- hash of source + url (or title): spots duplicates
    title            TEXT NOT NULL,
    url              TEXT,
    published_date   TEXT,                   -- ISO date (YYYY-MM-DD) if the site shows one
    first_seen       TEXT NOT NULL,
    raw_text         TEXT,
    text_hash        TEXT,                   -- hash of the text: spots revised notices
    notice_type      TEXT NOT NULL DEFAULT 'other',
    summary          TEXT,
    applies_to_json  TEXT,                   -- {"all":false,"courses":[],"semesters":[],"batches":[]}
    fees_json        TEXT,
    action_required  TEXT,
    extraction_mode  TEXT,                   -- 'llm' or 'regex'
    review_status    TEXT NOT NULL DEFAULT 'verified',   -- 'verified' or 'needs_review'
    issues_json      TEXT,                   -- list of things the validator flagged
    version          INTEGER NOT NULL DEFAULT 1,
    last_changed     TEXT
);

CREATE TABLE IF NOT EXISTS notice_versions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    notice_id      INTEGER NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
    version        INTEGER NOT NULL,
    text_hash      TEXT,
    raw_text       TEXT,
    seen_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deadlines (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    notice_id  INTEGER NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
    label      TEXT NOT NULL,
    due_date   TEXT NOT NULL,                -- ISO date
    snippet    TEXT,                         -- exact words from the notice
    verified   INTEGER NOT NULL DEFAULT 0    -- 1 = date was found in the notice text
);

CREATE TABLE IF NOT EXISTS changes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    notice_id           INTEGER NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
    related_notice_id   INTEGER,
    kind                TEXT NOT NULL,       -- 'revised_in_place' or 'revision_notice'
    summary             TEXT NOT NULL,
    created_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    name               TEXT NOT NULL,
    email              TEXT UNIQUE NOT NULL,
    token              TEXT UNIQUE NOT NULL,   -- private link: /u/<token>
    telegram_chat_id   TEXT,
    course             TEXT NOT NULL,
    semester           INTEGER NOT NULL,
    batch              TEXT,
    created_at         TEXT NOT NULL
);

-- deadline_id = 0 means a notice-level alert ("new notice" or "notice revised").
-- offset_days: 3/1/0 = days before the deadline, -1 = new notice, -(100+version) = revised.
CREATE TABLE IF NOT EXISTS alerts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    notice_id    INTEGER NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
    deadline_id  INTEGER NOT NULL DEFAULT 0,
    offset_days  INTEGER NOT NULL,
    remind_on    TEXT NOT NULL,
    sent_at      TEXT,
    channel      TEXT,
    status       TEXT NOT NULL DEFAULT 'pending',   -- pending / sent / failed / expired
    UNIQUE (user_id, notice_id, deadline_id, offset_days)
);

CREATE TABLE IF NOT EXISTS fetch_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id   INTEGER REFERENCES sources(id),
    ran_at      TEXT NOT NULL,
    found       INTEGER NOT NULL DEFAULT 0,
    new_count   INTEGER NOT NULL DEFAULT 0,
    error       TEXT
);

-- Remembers LLM answers so the same notice text never costs a second API call.
CREATE TABLE IF NOT EXISTS llm_cache (
    cache_key   TEXT PRIMARY KEY,
    response    TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_deadlines_due ON deadlines(due_date);
CREATE INDEX IF NOT EXISTS idx_alerts_due ON alerts(remind_on, sent_at);
