-- Migration: Add unique constraint on price_ticks to prevent duplicate entries.
-- Must remove existing duplicates first before creating the unique index.

-- Step 1: Remove duplicates, keeping the row with the smallest ctid
DELETE FROM price_ticks a
USING price_ticks b
WHERE a.time = b.time
  AND a.source = b.source
  AND a.symbol = b.symbol
  AND a.ctid > b.ctid;

-- Step 2: Create unique index (matches init.sql)
CREATE UNIQUE INDEX IF NOT EXISTS price_ticks_time_source_symbol_idx
    ON price_ticks (time, source, symbol);
