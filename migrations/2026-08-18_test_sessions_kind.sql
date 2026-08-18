-- Rozlíšenie testu kartičiek od opakovania (auto-play).
--
-- Opakovanie doteraz nezapisovalo nič — používateľ si prešiel sto slovíčok
-- a v štatistikách sa nestalo nič. Teraz sa zapíše ako riadok s kind='review':
-- ráta sa do série dní a do grafu aktivity, ale NIE do úspešnosti, keďže pri
-- prehrávaní nie sú správne/nesprávne odpovede.
--
-- Existujúce riadky sú testy, preto DEFAULT 'test'.

ALTER TABLE test_sessions ADD COLUMN IF NOT EXISTS kind VARCHAR(10) NOT NULL DEFAULT 'test';

CREATE INDEX IF NOT EXISTS ix_test_sessions_user_kind ON test_sessions(user_id, kind);
