-- 003: record which factory sent each sample round.
-- Changes a table that already holds data: SQL Server fills the default into
-- every existing row, so old rounds read 'unassigned' and none is dropped or
-- rewritten. Never edit this file once applied; corrections go in 004.

ALTER TABLE sample_round ADD factory NVARCHAR(100) NOT NULL
    CONSTRAINT df_sample_round_factory DEFAULT N'unassigned';
