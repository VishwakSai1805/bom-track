#!/usr/bin/env bash
# Return the database to the real data set: drop demo builds, stock movements, uploaded boards and app-entered quotes.
psql -h ${PGHOST:-/tmp} -U postgres -d bomtrack -q <<'SQL'
TRUNCATE build, stock_movement RESTART IDENTITY;
DELETE FROM board WHERE source LIKE 'Uploaded file%';
DELETE FROM price_quote WHERE captured_at > '2026-10-14 00:00:01';
UPDATE part SET description = NULL WHERE value_text = 'AT89S52';
SQL
