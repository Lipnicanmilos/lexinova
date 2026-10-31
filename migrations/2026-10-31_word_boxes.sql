-- Opakovanie s rozostupmi (Leitnerove priehradky).
-- box: 0 = nové slovo, 1–5 = priehradka (čím vyššia, tým neskôr sa slovo vráti).
-- due_at: odkedy sa má slovo znova opakovať; NULL = ešte sa neučilo.
-- Vlastné slová majú stĺpce na `words`, slová zo sád tried na `word_progress`.
--
-- POZOR NA PORADIE: spustiť na produkčnej Supabase DB PRED nasadením kódu.
-- Model Word tieto stĺpce číta v každom dotaze — bez nich padne každá stránka
-- so slovíčkami. Opačné poradie je bezpečné: starý kód nové stĺpce ignoruje.
-- Skript sa dá spustiť aj viackrát: dopĺňa len riadky bez due_at.

ALTER TABLE words ADD COLUMN IF NOT EXISTS box INTEGER NOT NULL DEFAULT 0;
ALTER TABLE words ADD COLUMN IF NOT EXISTS due_at TIMESTAMP;
ALTER TABLE word_progress ADD COLUMN IF NOT EXISTS box INTEGER NOT NULL DEFAULT 0;
ALTER TABLE word_progress ADD COLUMN IF NOT EXISTS due_at TIMESTAMP;

-- Doterajší pokrok sa nestratí: čo vieš, ide do priehradky 2 (vráti sa o 3 dni
-- od posledného testu), čo si skúšal a nevedel, do priehradky 1 (o deň).
-- Netestované slová ostávajú nové. Čo vyšlo do minulosti, je na rade hneď.
UPDATE words
SET box = 2,
    due_at = COALESCE(last_tested, now() AT TIME ZONE 'utc') + INTERVAL '3 days'
WHERE due_at IS NULL AND knowledge_level::text = 'know';

UPDATE words
SET box = 1,
    due_at = COALESCE(last_tested, now() AT TIME ZONE 'utc') + INTERVAL '1 day'
WHERE due_at IS NULL AND knowledge_level::text <> 'know' AND times_tested > 0;

UPDATE word_progress
SET box = 2,
    due_at = COALESCE(last_tested, now() AT TIME ZONE 'utc') + INTERVAL '3 days'
WHERE due_at IS NULL AND knowledge_level::text = 'know';

UPDATE word_progress
SET box = 1,
    due_at = COALESCE(last_tested, now() AT TIME ZONE 'utc') + INTERVAL '1 day'
WHERE due_at IS NULL AND knowledge_level::text <> 'know' AND times_tested > 0;

-- Denná dávka a jej počet filtrujú podľa používateľa a termínu.
CREATE INDEX IF NOT EXISTS ix_words_user_due ON words (user_id, due_at);
CREATE INDEX IF NOT EXISTS ix_word_progress_user_due ON word_progress (user_id, due_at);
