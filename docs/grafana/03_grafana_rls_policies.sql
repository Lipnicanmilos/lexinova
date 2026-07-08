-- ============================================================================
-- LexiNova → Grafana: RLS read-only policies pre rolu grafana_ro
-- ----------------------------------------------------------------------------
-- Tabuľky users/categories/words/test_sessions majú zapnuté RLS
-- (relrowsecurity = true). Owner (appka, rola postgres) RLS obchádza, ale
-- read-only rola grafana_ro nie → bez policy vidí 0 riadkov.
--
-- Tieto policies dovolia grafana_ro IBA ČÍTAŤ (SELECT) všetky riadky.
-- Zápis nepovoľujú (žiadna INSERT/UPDATE/DELETE policy) a appky sa netýkajú.
--
-- Spusti v Supabase → SQL Editor (ako owner/postgres).
-- payments RLS nemá → policy netreba.
-- ============================================================================

drop policy if exists grafana_ro_select on public.users;
create policy grafana_ro_select on public.users
  for select to grafana_ro using (true);

drop policy if exists grafana_ro_select on public.categories;
create policy grafana_ro_select on public.categories
  for select to grafana_ro using (true);

drop policy if exists grafana_ro_select on public.words;
create policy grafana_ro_select on public.words
  for select to grafana_ro using (true);

drop policy if exists grafana_ro_select on public.test_sessions;
create policy grafana_ro_select on public.test_sessions
  for select to grafana_ro using (true);

-- ── Kontrola: po spustení musí grafana_ro vidieť riadky ─────────────────────
-- set role grafana_ro;
-- select count(*) from users;         -- teraz už > 0
-- select count(*) from test_sessions; -- teraz už > 0
-- reset role;
