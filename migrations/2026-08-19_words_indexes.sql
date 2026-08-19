-- Indexy na tabuľke words — bez nich šiel každý dotaz štatistík seq scanom.
--
-- /api/user/stats filtruje výhradne cez words.user_id (počty, sumy, netestované,
-- dávno netestované, úrovne), zoznam slov v kategórii cez words.category_id.
-- user_id nemal index vôbec a nad cudzím kľúčom category_id si ho Postgres sám
-- nevytvorí. Merané na produkcii: endpoint 1,9 s pri 4 kB odpovede.
--
-- Spustiteľné rovno v Supabase SQL Editore. Ten obaľuje príkazy do transakcie,
-- takže CREATE INDEX CONCURRENTLY tam skončí na "25001: cannot run inside a
-- transaction block" — a netreba ho: tabuľka je malá, zámok potrvá chvíľu.
-- Ak by words niekedy narástla na milióny riadkov, spusti tie isté príkazy
-- s CONCURRENTLY cez psql (mimo transakcie, jeden po druhom).

CREATE INDEX IF NOT EXISTS ix_words_user_id     ON words(user_id);
CREATE INDEX IF NOT EXISTS ix_words_category_id ON words(category_id);
CREATE INDEX IF NOT EXISTS ix_words_user_tested ON words(user_id, times_tested);

-- Aby plánovač o nových indexoch hneď vedel a nečakal na autovacuum.
ANALYZE words;
