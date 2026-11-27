-- 003: store each measurement's pass/fail verdict when the round is recorded,
-- instead of recomputing it on every read. The verdict becomes part of the
-- snapshot (ADR-2): if the tolerance rule ever changes, rounds recorded under
-- the old rule keep the verdict the factory was given.
--
-- round_measurement already holds data, so the column is added nullable,
-- backfilled from the rule in force today (inclusive tolerance, ADR-3), then
-- made NOT NULL. Existing rows are kept and none is recomputed later.
-- The UPDATE and the second ALTER run through EXEC because SQL Server compiles
-- a batch before running it, and the new column doesn't exist at compile time.
-- migrate.py runs the whole file in one transaction: a failure leaves no column.

ALTER TABLE round_measurement ADD passes BIT NULL;

EXEC (N'UPDATE round_measurement
        SET passes = CASE WHEN ABS(measured_mm - target_mm) <= tolerance_mm THEN 1 ELSE 0 END;');

EXEC (N'ALTER TABLE round_measurement ALTER COLUMN passes BIT NOT NULL;');
