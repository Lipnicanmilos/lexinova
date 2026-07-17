-- Zdieľanie sady kódom/linkom (Fáza 1 učiteľského kanála).
-- share_code: NULL = sada nie je zdieľaná; unikátny kód (napr. A7K2M9QX)
-- sa generuje na vyžiadanie vlastníka a dá sa zrušiť (SET NULL).
-- Spustiť na produkčnej Supabase DB.

ALTER TABLE categories ADD COLUMN IF NOT EXISTS share_code VARCHAR(16);
CREATE UNIQUE INDEX IF NOT EXISTS ix_categories_share_code ON categories (share_code);
