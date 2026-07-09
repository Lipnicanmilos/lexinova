-- Stav denných jobov pre lazy „anacron" scheduler (app/services/scheduler.py).
-- Cloud Run škáluje na nulu → in-process cron nie je spoľahlivý; job sa dobehne
-- pri prvom requeste v daný deň. Atomický UPDATE tohto riadku (WHERE
-- last_run_date < today) zaručí, že naprieč inštanciami beží job práve raz.
-- Spustiť na produkčnej Supabase DB.

CREATE TABLE IF NOT EXISTS job_runs (
    job_name      VARCHAR(64) PRIMARY KEY,
    last_run_date DATE,
    last_run_at   TIMESTAMP,
    last_status   VARCHAR(20),
    last_error    VARCHAR(500)
);
