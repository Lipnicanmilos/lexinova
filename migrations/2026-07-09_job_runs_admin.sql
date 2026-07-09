-- Admin správa denných jobov: prestavenie cieľovej hodiny + história behov.
-- Spustiť na produkčnej Supabase DB (po 2026-07-09_job_runs.sql).

-- Override cieľovej hodiny (UTC, 0–23) nastavený z admin panela.
-- NULL = použije sa default z kódu (register_job run_after_hour).
ALTER TABLE job_runs ADD COLUMN IF NOT EXISTS run_after_hour SMALLINT;

-- História behov jobov (auto aj manuálne spustenia z admin panela).
CREATE TABLE IF NOT EXISTS job_run_history (
    id           SERIAL PRIMARY KEY,
    job_name     VARCHAR(64) NOT NULL,
    started_at   TIMESTAMP NOT NULL,
    finished_at  TIMESTAMP,
    status       VARCHAR(20) NOT NULL,
    error        VARCHAR(500),
    triggered_by VARCHAR(10) NOT NULL DEFAULT 'auto'
);

CREATE INDEX IF NOT EXISTS ix_job_run_history_job_started
    ON job_run_history(job_name, started_at);
