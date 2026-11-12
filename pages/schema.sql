-- The visitor counter's D1 database (src/index.js visit). Once:
--   npx wrangler d1 execute nastava --remote --file schema.sql
CREATE TABLE IF NOT EXISTS visits (
  ip     TEXT NOT NULL,
  period TEXT NOT NULL,
  PRIMARY KEY (ip, period)
);
-- The Worker's DELETE of the old periods, on each new visitor: reads only those rows, not the whole table.
CREATE INDEX IF NOT EXISTS visits_period ON visits (period);

CREATE TABLE IF NOT EXISTS visit_total (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  n  INTEGER NOT NULL
);

INSERT OR IGNORE INTO visit_total (id, n) VALUES (1, 0);
