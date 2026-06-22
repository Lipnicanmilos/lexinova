> pozri sa na admin stranku co vsetko by tam este malo byt a co je potrebne zohladnovat a nastavit na plus ucte, pravidelne platby automaticke predlzovanie uctu atd.

● Pozriem sa na admin stránku a súvisiace súbory naraz.

  Searched for 3 patterns, read 4 files (ctrl+o to expand)

● Mám jasný obraz. Dovolím si dať ti komplexnú analýzu — čo existuje, čo chýba a čo treba rozhodnúť.

  ---
  Čo existuje teraz

  Model User:
  - is_plus: Boolean — jednoduchý prepínač on/off
  - Žiadny dátum expirácie, žiadny platobný záznam

  Admin:
  - Zobrazí zoznam užívateľov + toggle Plus ručne
  - Žiadne platobné info, žiadne štatistiky príjmov

  Záver: platobný systém neexistuje vôbec. togglePlus() na profile stránke len prepne boolean — bez platby.

  ---
  Čo všetko treba pre funkčný platobný systém

  1. Databáza — chýbajúce stĺpce v User

  plus_expires_at       = Column(DateTime, nullable=True)   # kedy vyprší predplatné
  stripe_customer_id    = Column(String, nullable=True)      # ID zákazníka v Stripe
  stripe_subscription_id = Column(String, nullable=True)     # aktívna subscription
  plus_plan             = Column(String, nullable=True)      # 'monthly' / 'annual'
  plus_cancelled_at     = Column(DateTime, nullable=True)    # kedy zrušil

  Bez plus_expires_at nevieš automaticky odstaviť prístup po skončení.

  ---
  2. Platobný provider — Stripe (odporúčam)

  Potrebuješ nastaviť:
  - Produkt + ceny: napr. PLUS Monthly (€4.99/mes), PLUS Annual (€39.99/rok)
  - Checkout Session — redirect na platbu
  - Webhook endpoint /api/webhooks/stripe — prijímaš udalosti od Stripe:
    - checkout.session.completed → aktivuj Plus, nastav plus_expires_at
    - invoice.paid → predlž plus_expires_at o ďalší mesiac/rok
    - customer.subscription.deleted → deaktivuj Plus po plus_expires_at
    - invoice.payment_failed → notifikuj užívateľa emailom
  - Customer Portal — užívateľ si sám zmení/zruší predplatné

  ---
  3. Backend — čo treba dopísať

  ┌────────────────────────────┬─────────────────────────────────────────────────────┐
  │          Endpoint          │                        Popis                        │
  ├────────────────────────────┼─────────────────────────────────────────────────────┤
  │ POST /api/v1/checkout      │ Vytvorí Stripe Checkout Session, vráti URL          │
  ├────────────────────────────┼─────────────────────────────────────────────────────┤
  │ GET /api/v1/billing/portal │ Vráti URL na Stripe Customer Portal                 │
  ├────────────────────────────┼─────────────────────────────────────────────────────┤
  │ POST /api/webhooks/stripe  │ Prijíma webhooky od Stripe (podpisová verifikácia!) │
  ├────────────────────────────┼─────────────────────────────────────────────────────┤
  │ GET /api/v1/subscription   │ Vráti stav predplatného pre prihláseného užívateľa  │
  └────────────────────────────┴─────────────────────────────────────────────────────┘

  Plus background job (napr. cez APScheduler alebo Cloud Scheduler):
  - Každý deň skontroluje užívateľov kde plus_expires_at < now() a nastaví is_plus = False

  ---
  4. Admin stránka — čo by mala ukazovať

  Momentálne chýba:
  - Počet PLUS užívateľov / Standard
  - Príjmy (MRR — monthly recurring revenue)
  - Dátum expirácie predplatného pre každého užívateľa
  - Status: active / cancelled / expired / payment_failed
  - Filter/hľadanie v tabuľke
  - Manuálny grant Plus (s dátumom expirácie — napr. "+30 dní")
  - Export CSV

  ---
  5. Profil užívateľa — čo by mal vidieť

  - "Predplatné aktívne do: 15.7.2025"
  - Tlačidlo "Spravovať predplatné" → Stripe Portal
  - Tlačidlo "Upgradovať na PLUS" → Checkout
  - Pri expirácii: banner "Tvoje predplatné vypršalo"

  ---
  Čo treba rozhodnúť skôr než sa čokoľvek píše

  Potrebujem vedieť od teba:
  1. Chceš použiť Stripe? (je to štandard, má webhooky, sandbox, lokalizáciu) — alebo niečo iné (PayPal, Paddle)?
  2. Aké ceny/plány? (mesačný, ročný, trial?)
  3. Kde beží backend? Cloud Run — to je bezproblémové pre webhooky
  4. Chceš zastaviť aktuálne fake togglePlus() a nahradiť ho reálnou platbou, alebo nechať admin override ako záložný?

  Ak mi odpovieš na tieto 4 veci, môžem ísť rovnou implementovať celý flow od DB migrácie po Stripe webhooky.

✻ Crunched for 1m 2s

※ recap: Redesigning LexiNova's app pages to match a unified style (Inter font, sticky header, gradient logo). Last task was analyzing the admin/Plus subscription system. Next: user needs to answer 4 questions
  about payment provider, pricing, and plan structure before implementation can begin.