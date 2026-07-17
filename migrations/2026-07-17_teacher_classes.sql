-- Fáza 2 učiteľského kanála: triedy, členstvá, priradené sady, overlay pokroku.
-- Idempotentná migrácia — bezpečné spustiť opakovane (Supabase SQL editor).

-- Pseudonymné žiacke účty: e-mail už nie je povinný.
ALTER TABLE users ALTER COLUMN email DROP NOT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_pseudonymous BOOLEAN DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS classes (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    teacher_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    join_code VARCHAR(16) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_classes_teacher_id ON classes (teacher_id);

CREATE TABLE IF NOT EXISTS class_members (
    id SERIAL PRIMARY KEY,
    class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    nickname VARCHAR(50) NOT NULL,
    joined_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_class_members_class_user UNIQUE (class_id, user_id),
    CONSTRAINT uq_class_members_class_nickname UNIQUE (class_id, nickname)
);
CREATE INDEX IF NOT EXISTS ix_class_members_user_id ON class_members (user_id);

CREATE TABLE IF NOT EXISTS class_categories (
    id SERIAL PRIMARY KEY,
    class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_class_categories_class_category UNIQUE (class_id, category_id)
);
CREATE INDEX IF NOT EXISTS ix_class_categories_category_id ON class_categories (category_id);

-- Per-user pokrok na cudzích (triednych) slovách. Vlastné slová ďalej používajú
-- stĺpce priamo na words — sem sa píše len to, čo user netestuje na vlastných.
-- knowledge_level je zámerne VARCHAR: SQLAlchemy Enum(values_callable) ukladá
-- stringy ('dont_know'/'learning'/'know'), netreba PG enum typ.
CREATE TABLE IF NOT EXISTS word_progress (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    word_id INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
    knowledge_level VARCHAR(20) DEFAULT 'dont_know',
    times_tested INTEGER NOT NULL DEFAULT 0,
    times_correct INTEGER NOT NULL DEFAULT 0,
    last_tested TIMESTAMP,
    updated_at TIMESTAMP,
    CONSTRAINT uq_word_progress_user_word UNIQUE (user_id, word_id)
);
CREATE INDEX IF NOT EXISTS ix_word_progress_user_id ON word_progress (user_id);
CREATE INDEX IF NOT EXISTS ix_word_progress_word_id ON word_progress (word_id);
