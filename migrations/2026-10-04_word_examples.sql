-- Príkladové vety pri slovíčkach.
-- example_sentence: veta v jazyku slova (language_from), example_translation:
-- jej preklad. NULL = slovo vetu nemá (ručne pridané, importované, staršie sady).
--
-- POZOR NA PORADIE: spustiť na produkčnej Supabase DB PRED nasadením kódu.
-- Model Word tieto stĺpce číta v každom dotaze — bez nich padne každá stránka
-- so slovíčkami. Opačné poradie je bezpečné: starý kód nové stĺpce ignoruje.

ALTER TABLE words ADD COLUMN IF NOT EXISTS example_sentence VARCHAR(300);
ALTER TABLE words ADD COLUMN IF NOT EXISTS example_translation VARCHAR(300);
