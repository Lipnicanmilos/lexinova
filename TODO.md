# LexiNova – TODO

## Platobná brána (Stripe) — implementovať

### Pred začatím — rozhodnúť
- [ ] Ceny a plány (napr. PLUS Monthly €4.99 / PLUS Annual €39.99?)
- [ ] Chceš nechať admin manuálny override (toggle is_plus) ako záložku?
- [ ] Trial period? (napr. 7 dní zadarmo)

### 1. Databáza — migrácia User modelu
- [ ] Pridať stĺpce do `User`:
  - `plus_expires_at` (DateTime, nullable)
  - `stripe_customer_id` (String, nullable)
  - `stripe_subscription_id` (String, nullable)
  - `plus_plan` (String: 'monthly' / 'annual', nullable)
  - `plus_cancelled_at` (DateTime, nullable)
- [ ] Spustiť migráciu (`RUN_DB_CREATE_ALL=1`)

### 2. Stripe setup
- [ ] Vytvoriť Stripe účet (test mode)
- [ ] Vytvoriť produkt + ceny v Stripe dashboarde
- [ ] Nastaviť env vars: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_MONTHLY`, `STRIPE_PRICE_ANNUAL`

### 3. Backend — nové endpointy
- [ ] `POST /api/v1/checkout` — vytvorí Stripe Checkout Session, vráti URL
- [ ] `GET /api/v1/billing/portal` — vráti URL na Stripe Customer Portal
- [ ] `POST /api/webhooks/stripe` — prijíma webhooky (podpisová verifikácia!):
  - `checkout.session.completed` → aktivuj Plus, nastav `plus_expires_at`
  - `invoice.paid` → predlž `plus_expires_at`
  - `customer.subscription.deleted` → deaktivuj Plus po expirácii
  - `invoice.payment_failed` → notifikuj emailom
- [ ] `GET /api/v1/subscription` — stav predplatného pre prihláseného užívateľa

### 4. Automatická expirácia
- [ ] Background job (APScheduler alebo Cloud Scheduler):
  - Každý deň: `plus_expires_at < now()` → `is_plus = False`

### 5. Frontend — profil stránka
- [ ] Zobraziť "Predplatné aktívne do: DD.MM.YYYY"
- [ ] Tlačidlo "Upgradovať na PLUS" → Checkout
- [ ] Tlačidlo "Spravovať predplatné" → Stripe Portal
- [ ] Banner pri expirácii

### 6. Admin stránka
- [ ] Dátum expirácie predplatného pre každého užívateľa
- [ ] Subscription status (active / cancelled / expired / payment_failed)
- [ ] Manuálny grant Plus s dátumom (+30 dní)
- [ ] MRR štatistika

---

## Ďalšie nápady / backlog
- [ ] Pridať pätičku (site-footer.js) aj na dashboard, test, repeat stránky
- [ ] Import slovíčok (Excel/CSV) — overiť že funguje
- [ ] Rate limiting na inquiry endpoint
