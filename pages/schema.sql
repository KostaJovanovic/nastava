-- The visitor counter's D1 database (src/index.js visit). Once:
--   npx wrangler d1 execute nastava --remote --file schema.sql
CREATE TABLE IF NOT EXISTS visits (
  ip     TEXT NOT NULL,
  period TEXT NOT NULL,
  PRIMARY KEY (ip, period)
);

CREATE TABLE IF NOT EXISTS visit_total (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  n  INTEGER NOT NULL
);

INSERT OR IGNORE INTO visit_total (id, n) VALUES (1, 0);
