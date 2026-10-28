-- AI tútor s pamäťou (/tutor): profil, relácie, správy a spomienky s vektorom.
--
-- Poradie: spustiť na Supabase PRED nasadením kódu. Starý kód tieto tabuľky
-- nepozná, takže opačné poradie (migrácia, potom kód) je vždy bezpečné.
-- Bez tabuliek padne len /tutor — zvyšok appky ich nečíta.
--
-- pgvector: na Supabase je rozšírenie dostupné, len sa musí zapnúť. Ak je už
-- zapnuté (Database → Extensions → vector), prvý príkaz nič neurobí.
-- Typ `vector` je potom v schéme `extensions`, ktorá je na Supabase v search_path.

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

CREATE TABLE IF NOT EXISTS tutor_profiles (
    user_id         INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    level           VARCHAR(4)  NOT NULL DEFAULT 'A2',
    language_from   VARCHAR(10) NOT NULL DEFAULT 'en',
    language_to     VARCHAR(10) NOT NULL DEFAULT 'sk',
    facts           TEXT,
    mistakes        TEXT,
    sessions_count  INTEGER     NOT NULL DEFAULT 0,
    created_at      TIMESTAMP   DEFAULT (now() AT TIME ZONE 'utc'),
    updated_at      TIMESTAMP   DEFAULT (now() AT TIME ZONE 'utc')
);

CREATE TABLE IF NOT EXISTS tutor_sessions (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER   NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    started_at      TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    ended_at        TIMESTAMP,
    summary         TEXT,
    user_messages   INTEGER   NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_tutor_sessions_user_id ON tutor_sessions(user_id);

CREATE TABLE IF NOT EXISTS tutor_messages (
    id          SERIAL PRIMARY KEY,
    session_id  INTEGER     NOT NULL REFERENCES tutor_sessions(id) ON DELETE CASCADE,
    user_id     INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role        VARCHAR(10) NOT NULL,
    text        TEXT        NOT NULL,
    created_at  TIMESTAMP   NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS ix_tutor_messages_session_id      ON tutor_messages(session_id);
CREATE INDEX IF NOT EXISTS ix_tutor_messages_user_id         ON tutor_messages(user_id);
CREATE INDEX IF NOT EXISTS ix_tutor_messages_session_created ON tutor_messages(session_id, created_at);

CREATE TABLE IF NOT EXISTS tutor_memories (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id  INTEGER     REFERENCES tutor_sessions(id) ON DELETE SET NULL,
    kind        VARCHAR(16) NOT NULL,
    text        TEXT        NOT NULL,
    embedding   extensions.vector(768),
    created_at  TIMESTAMP   NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS ix_tutor_memories_user_id      ON tutor_memories(user_id);
CREATE INDEX IF NOT EXISTS ix_tutor_memories_user_created ON tutor_memories(user_id, created_at);
-- HNSW index na kosínusovú vzdialenosť. Kým má používateľ spomienok málo,
-- Postgres aj tak zvolí filter cez user_id; index sa oplatí až pri tisícoch riadkov.
CREATE INDEX IF NOT EXISTS ix_tutor_memories_embedding
    ON tutor_memories USING hnsw (embedding extensions.vector_cosine_ops);
