-- História testov kartičiek (streak, grafy aktivity, gamifikácia).
-- Spustiť na produkčnej Supabase DB (create_all nepridá tabuľku, ak migrácie
-- bežia mimo aplikácie / tabuľka ešte neexistuje).

CREATE TABLE IF NOT EXISTS test_sessions (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    total       INTEGER NOT NULL DEFAULT 0,
    correct     INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_test_sessions_user_id      ON test_sessions(user_id);
CREATE INDEX IF NOT EXISTS ix_test_sessions_created_at   ON test_sessions(created_at);
CREATE INDEX IF NOT EXISTS ix_test_sessions_user_created ON test_sessions(user_id, created_at);
