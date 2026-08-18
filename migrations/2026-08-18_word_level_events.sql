-- História zmien úrovne znalosti slovíčka (naučené za týždeň, krivka učenia).
-- Riadok pribudne len pri skutočnej zmene úrovne, nie pri každom opakovaní.
-- Spustiť na produkčnej Supabase DB pred/po deployi — aplikácia beží aj bez
-- tejto tabuľky (zápis aj čítanie sú best effort), len metriku ukáže ako 0.

CREATE TABLE IF NOT EXISTS word_level_events (
    id             SERIAL PRIMARY KEY,
    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    word_id        INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
    level          VARCHAR(20) NOT NULL,
    previous_level VARCHAR(20),
    created_at     TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_word_level_events_user_id      ON word_level_events(user_id);
CREATE INDEX IF NOT EXISTS ix_word_level_events_word_id      ON word_level_events(word_id);
CREATE INDEX IF NOT EXISTS ix_word_level_events_created_at   ON word_level_events(created_at);
CREATE INDEX IF NOT EXISTS ix_word_level_events_user_created ON word_level_events(user_id, created_at);
