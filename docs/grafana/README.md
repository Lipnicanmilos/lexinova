# LexiNova → Grafana (biznis dashboard)

Napojenie **Grafana Cloud (free)** priamo na **Supabase Postgres** cez read-only
rolu. Bez zmien v aplikácii, bez extra infraštruktúry, **0 € navyše**.

Dáta číta Grafana naživo SQL dotazmi z existujúcich tabuliek
(`users`, `words`, `categories`, `test_sessions`, `payments`).

## Súbory

| Súbor | Načo |
|---|---|
| `01_grafana_readonly_role.sql` | Vytvorí read-only DB rolu `grafana_ro` (bez prístupu k heslám). |
| `02_panel_queries.sql` | Jednotlivé SQL dotazy pre panely (na kopírovanie). |
| `03_grafana_rls_policies.sql` | RLS select-only policies — bez nich `grafana_ro` vidí 0 riadkov. |
| `lexinova_dashboard.json` | Hotový dashboard na import (15 panelov). |

---

## Krok 1 — Read-only rola v Supabase

1. Otvor **Supabase → SQL Editor**.
2. Otvor `01_grafana_readonly_role.sql`, zmeň `ZMEN_TOTO_SILNE_HESLO` za silné heslo.
3. Spusti. Vznikne rola `grafana_ro`, ktorá vie iba `SELECT` a **nevidí** stĺpce
   `password` / `reset_token` v tabuľke `users`.
4. Spusti aj `03_grafana_rls_policies.sql` — tabuľky majú zapnuté RLS a bez
   select policy by `grafana_ro` videla 0 riadkov.

## Krok 2 — Pripojovacie údaje zo Supabase

**Supabase → Project Settings → Database → Connection pooling.**

Použi **Session pooler** (nie Transaction) — Grafana používa dlhšie spojenia:

- **Host:** `aws-0-<región>.pooler.supabase.com`
- **Port:** `5432` (Session mode)
- **Database:** `postgres`
- **User:** `grafana_ro.<project-ref>` ← pri pooleri je za rolou bodka a project ref
  (skopíruj presný tvar z poľa *User* v Supabase a nahraď `postgres` za `grafana_ro`)
- **Password:** heslo z kroku 1
- **TLS/SSL Mode:** `require`

> Pozn.: priame spojenie (`db.<ref>.supabase.co:5432`) je len cez IPv6 — pooler je
> spoľahlivejší a šetrí spojenia aplikácii.

## Krok 3 — Datasource v Grafane

1. Grafana Cloud → **Connections → Add new connection → PostgreSQL → Add new data source**.
2. Vyplň údaje z kroku 2, **TLS/SSL Mode = require**.
3. **Save & test** → musí byť zelené „Database Connection OK".

## Krok 4 — Import dashboardu

1. Grafana → **Dashboards → New → Import**.
2. Nahraj `lexinova_dashboard.json` (alebo vlož jeho obsah).
3. Keď sa spýta na datasource **LexiNova Postgres**, vyber ten z kroku 3.
4. **Import.** Hotovo — uvidíš používateľov, PLUS/MRR/ARR, testy, DAU, úspešnosť,
   tržby a rozdelenia.

Časový rozsah je vpravo hore (default posledných 90 dní), refresh 1 h.
Vlastné panely staviaš dotazmi z `02_panel_queries.sql`.

---

## Náklady

| Zložka | Náklad |
|---|---|
| Grafana Cloud free (3 užívatelia, 14 dní retencia) | **0 €** |
| Supabase — dotazy sú malé agregácie, egress zanedbateľný | **0 € navyše** |
| Google Cloud (appky sa to netýka) | **0 € navyše** |

**Tip:** nedávaj refresh na sekundy s ťažkými dotazmi — kvôli egress/latencii.
1 h alebo manuálny refresh úplne stačí.
