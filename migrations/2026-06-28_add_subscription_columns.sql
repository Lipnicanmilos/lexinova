-- LexiNova — pridanie stĺpcov pre predplatné (Lemon Squeezy) do tabuľky users.
-- POZOR: app spúšťa create_all len cez RUN_DB_CREATE_ALL=1, a to NEPRIDÁVA stĺpce
-- do existujúcej tabuľky. Na produkčnej (Supabase) DB spusti tento skript ručne
-- (Supabase → SQL Editor) alebo cez psql.

ALTER TABLE users ADD COLUMN IF NOT EXISTS plus_expires_at    TIMESTAMP   NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS plus_plan          VARCHAR(20) NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS plus_status        VARCHAR(20) NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS plus_cancelled_at  TIMESTAMP   NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS ls_customer_id     VARCHAR(64) NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS ls_subscription_id VARCHAR(64) NULL;
