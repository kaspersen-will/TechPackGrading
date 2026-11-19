-- 002: a one-row table that GET /health writes to, so a 200 proves this
-- service can still write to its own database, not only connect to it.
-- New table, no existing rows touched. migrate.py runs this once, in one transaction.

CREATE TABLE health_check (
    id         INT NOT NULL CONSTRAINT pk_health_check PRIMARY KEY,
    checked_at DATETIME2(0) NOT NULL
               CONSTRAINT df_health_check_checked_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT ck_health_check_one_row CHECK (id = 1)
);

INSERT INTO health_check (id) VALUES (1);
