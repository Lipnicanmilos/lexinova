-- ============================================================================
-- LexiNova → Grafana: SQL dotazy pre panely
-- ----------------------------------------------------------------------------
-- Skopíruj konkrétny dotaz do panelu (Grafana → panel → Query → Code).
-- `$__timeFilter(created_at)` je Grafana makro — obmedzí dáta na časový
-- rozsah zvolený vpravo hore v dashboarde. Funguje len v Grafane, nie v
-- Supabase SQL editore (tam si makro nahraď napr. za `created_at > now() - interval '90 days'`).
--
-- MRR/ARR sa počítajú rovnako ako v admin API:
--   platiace = is_plus = true AND plus_status IN ('active','past_due')
--   MRR = mesačné * 4.99 + ročné * (39.99 / 12)
-- ============================================================================


-- ── STAT PANELY (jedno číslo) ───────────────────────────────────────────────

-- Používatelia spolu
select count(*) as "Users" from users;

-- PLUS používatelia
select count(*) as "PLUS" from users where is_plus is true;

-- Noví používatelia za 7 dní
select count(*) as "New 7d" from users where created_at > now() - interval '7 days';

-- Noví používatelia za 30 dní
select count(*) as "New 30d" from users where created_at > now() - interval '30 days';

-- MRR (€) — mesačný opakovaný príjem
select round(
         sum(case when plus_plan = 'monthly' then 4.99        else 0 end) +
         sum(case when plus_plan = 'annual'  then 39.99/12.0  else 0 end)
       , 2) as "MRR"
from users
where is_plus is true and plus_status in ('active','past_due');

-- ARR (€) — ročný opakovaný príjem = MRR * 12
select round(
         12 * (
           sum(case when plus_plan = 'monthly' then 4.99        else 0 end) +
           sum(case when plus_plan = 'annual'  then 39.99/12.0  else 0 end)
         )
       , 2) as "ARR"
from users
where is_plus is true and plus_status in ('active','past_due');

-- Testy spolu
select count(*) as "Tests" from test_sessions;

-- Slovíčka spolu
select count(*) as "Words" from words;


-- ── ČASOVÉ RADY (timeseries) ────────────────────────────────────────────────

-- Noví používatelia za deň
select date_trunc('day', created_at) as time,
       count(*)                       as "New users"
from users
where $__timeFilter(created_at)
group by 1
order by 1;

-- Kumulatívny rast používateľov (celkový počet v čase)
select time, sum(cnt) over (order by time) as "Total users"
from (
  select date_trunc('day', created_at) as time, count(*) as cnt
  from users
  group by 1
) d
order by time;

-- Testy za deň
select date_trunc('day', created_at) as time,
       count(*)                       as "Tests"
from test_sessions
where $__timeFilter(created_at)
group by 1
order by 1;

-- Denne aktívni používatelia (DAU) — unikátni, čo spravili aspoň 1 test
select date_trunc('day', created_at) as time,
       count(distinct user_id)        as "DAU"
from test_sessions
where $__timeFilter(created_at)
group by 1
order by 1;

-- Úspešnosť testov za deň (%)
select date_trunc('day', created_at)                        as time,
       round(100.0 * sum(correct) / nullif(sum(total),0), 1) as "Accuracy %"
from test_sessions
where $__timeFilter(created_at)
group by 1
order by 1;

-- Tržby za deň (€) — len úspešné platby
-- (refundované/chargebacknuté platby majú iný status, takže tu automaticky nie sú)
select date_trunc('day', created_at) as time,
       sum(amount)                    as "Revenue EUR"
from payments
where status = 'succeeded' and $__timeFilter(created_at)
group by 1
order by 1;

-- Refundy — počet + vrátená suma (stat panel, voliteľný)
-- statusy nastavuje webhook z Paddle adjustment.* eventov (od 2026-07-10)
select count(*)                 as "Refunds",
       coalesce(sum(amount), 0) as "Refunded EUR"
from payments
where status in ('refunded', 'refund_pending', 'chargeback');


-- ── ROZDELENIA (piechart / bar) ─────────────────────────────────────────────

-- Slovíčka podľa úrovne znalosti
-- Pozn.: `knowledge_level` je Postgres ENUM → bez `::text` sa reťazcové vetvy
-- CASE pokúsi Postgres pretypovať na enum a spadne to na
-- „invalid input value for enum knowledgelevel: 'Neviem'".
select case knowledge_level::text
         when 'dont_know' then 'Neviem'
         when 'learning'  then 'Učím sa'
         when 'know'      then 'Viem'
         else knowledge_level::text
       end        as metric,
       count(*)   as value
from words
group by knowledge_level
order by value desc;

-- Aktívne PLUS predplatné podľa plánu
select coalesce(plus_plan, '—') as metric,
       count(*)                 as value
from users
where is_plus is true and plus_status in ('active','past_due')
group by plus_plan
order by value desc;


-- ── TABUĽKA ─────────────────────────────────────────────────────────────────

-- Najaktívnejší používatelia za posledných 30 dní
select u.email                                             as "Email",
       count(t.id)                                         as "Tests 30d",
       sum(t.total)                                        as "Cards",
       round(100.0 * sum(t.correct) / nullif(sum(t.total),0), 1) as "Accuracy %"
from test_sessions t
join users u on u.id = t.user_id
where t.created_at > now() - interval '30 days'
group by u.email
order by "Tests 30d" desc
limit 20;
