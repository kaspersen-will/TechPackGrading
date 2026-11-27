-- 001: the Sample Fit Review schema, ported from the SQLite SCHEMA of Assignment 1.
-- All lengths are integer mm (ADR-3). migrate.py runs this file once, as one
-- batch in one transaction, so it must not contain GO.
--
-- Codes and labels use a BIN2 collation so they compare exactly as the specs
-- service stores them (case-sensitive), as they did in SQLite.

-- style_id deliberately has no REFERENCES: styles live in the specs service's
-- database. A round keeps its own snapshot of the spec (ADR-2), so it still
-- renders if the style is deleted.
CREATE TABLE sample_round (
    id          INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_sample_round PRIMARY KEY,
    style_id    INT NOT NULL,
    style_code  NVARCHAR(50) COLLATE Latin1_General_100_BIN2 NOT NULL,
    size_label  NVARCHAR(20) COLLATE Latin1_General_100_BIN2 NOT NULL,
    stage       NVARCHAR(20) NOT NULL
                CONSTRAINT ck_sample_round_stage CHECK (stage IN ('proto', 'fit', 'pre-production')),
    recorded_at DATETIME2(0) NOT NULL
                CONSTRAINT df_sample_round_recorded_at DEFAULT SYSUTCDATETIME()
);

-- A foreign key inside this service's own database, which is fine.
CREATE TABLE round_measurement (
    round_id     INT NOT NULL
                 CONSTRAINT fk_round_measurement_round REFERENCES sample_round (id) ON DELETE CASCADE,
    pom_code     NVARCHAR(50)  COLLATE Latin1_General_100_BIN2 NOT NULL,
    description  NVARCHAR(200) NOT NULL,
    target_mm    INT NOT NULL,
    tolerance_mm INT NOT NULL,
    measured_mm  INT NOT NULL,
    CONSTRAINT pk_round_measurement PRIMARY KEY (round_id, pom_code)
);
