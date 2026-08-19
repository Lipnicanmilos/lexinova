-- Cache a počítadlo pre ukážku na /demo (neprihlásený návštevník).
--
-- Riadok vznikne len pri skutočnom volaní AI, takže počet dnešných riadkov
-- je zároveň dnešná spotreba ukážky — strop sa kontroluje proti nemu a žiadne
-- samostatné počítadlo netreba. Rovnaká téma sa druhýkrát negeneruje, podá sa
-- z cache.
--
-- Aplikácia beží aj bez tejto tabuľky: cache aj strop sú best effort, pri chybe
-- sa ukážka správa, akoby bola cache prázdna (a ponúkne zabudovanú sadu).

CREATE TABLE IF NOT EXISTS demo_generations (
    id             SERIAL PRIMARY KEY,
    topic_key      VARCHAR(120) NOT NULL,
    topic          VARCHAR(200) NOT NULL,
    language_from  VARCHAR(10)  NOT NULL DEFAULT 'en',
    language_to    VARCHAR(10)  NOT NULL DEFAULT 'sk',
    category_name  VARCHAR(120),
    words_json     TEXT         NOT NULL,
    hits           INTEGER      NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ  DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_demo_generations_topic_key  ON demo_generations(topic_key);
CREATE INDEX IF NOT EXISTS ix_demo_generations_created_at ON demo_generations(created_at);
CREATE INDEX IF NOT EXISTS ix_demo_generations_key        ON demo_generations(topic_key, language_from, language_to);
