-- ============================================================================
-- LexiNova → Grafana: read-only rola pre Supabase Postgres
-- ----------------------------------------------------------------------------
-- Spusti v Supabase → SQL Editor (ako owner/postgres).
-- Rola smie IBA čítať (SELECT). Z tabuľky `users` nedostane prístup k
-- citlivým stĺpcom (password, reset_token) — Grafana ich ani neuvidí.
--
-- 1) Zmeň heslo nižšie za silné a náhodné.
-- 2) To isté heslo potom zadáš v Grafane pri pripojení datasource.
-- ============================================================================

-- Ak by rola už existovala z predošlého pokusu, odkomentuj nasledujúci riadok:
-- drop role if exists grafana_ro;

create role grafana_ro with login password 'ZMEN_TOTO_SILNE_HESLO';

-- Pripojenie do databázy + čítanie schémy public
grant connect on database postgres to grafana_ro;
grant usage   on schema   public   to grafana_ro;

-- users: len bezpečné stĺpce (BEZ password, reset_token, reset_token_expires)
grant select (
  id, email, name, is_plus, dark_mode, created_at, last_login,
  plus_expires_at, plus_plan, plus_status, plus_cancelled_at,
  paddle_customer_id, paddle_subscription_id, ai_uses_date, ai_uses_count
) on public.users to grafana_ro;

-- Ostatné tabuľky neobsahujú tajomstvá → celý SELECT
grant select on public.words         to grafana_ro;
grant select on public.categories    to grafana_ro;
grant select on public.test_sessions to grafana_ro;
grant select on public.payments      to grafana_ro;

-- ── Kontrola (voliteľné) ────────────────────────────────────────────────────
-- select table_name, privilege_type
-- from information_schema.role_table_grants
-- where grantee = 'grafana_ro' order by table_name;
