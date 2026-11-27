-- 001: the Specs & Grading schema, ported from the SQLite SCHEMA of Assignment 1.
-- All lengths are integer mm (ADR-3). migrate.py runs this file once, as one
-- batch in one transaction, so it must not contain GO.
--
-- Codes and size labels use a BIN2 collation: SQL Server's default collation is
-- case-insensitive and would make "jk-014" a duplicate of "JK-014" and size "m"
-- match "M". BIN2 keeps SQLite's behaviour: case-sensitive, code-point order.

-- IDENTITY, like AUTOINCREMENT before it, never hands a deleted style's id to a
-- new style, so a sample round in the other service can't end up on the wrong style.
CREATE TABLE style (
    id        INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_style PRIMARY KEY,
    code      NVARCHAR(50)  COLLATE Latin1_General_100_BIN2 NOT NULL
              CONSTRAINT uq_style_code UNIQUE,
    name      NVARCHAR(200) NOT NULL,
    base_size NVARCHAR(20)  COLLATE Latin1_General_100_BIN2 NOT NULL
);

CREATE TABLE style_size (
    id       INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_style_size PRIMARY KEY,
    style_id INT NOT NULL
             CONSTRAINT fk_style_size_style REFERENCES style (id) ON DELETE CASCADE,
    label    NVARCHAR(20) COLLATE Latin1_General_100_BIN2 NOT NULL,
    position INT NOT NULL,
    CONSTRAINT uq_style_size_label UNIQUE (style_id, label),
    CONSTRAINT uq_style_size_position UNIQUE (style_id, position)
);

CREATE TABLE point_of_measure (
    id            INT IDENTITY(1,1) NOT NULL CONSTRAINT pk_point_of_measure PRIMARY KEY,
    style_id      INT NOT NULL
                  CONSTRAINT fk_point_of_measure_style REFERENCES style (id) ON DELETE CASCADE,
    code          NVARCHAR(50)  COLLATE Latin1_General_100_BIN2 NOT NULL,
    description   NVARCHAR(200) NOT NULL,
    base_value_mm INT NOT NULL,
    tolerance_mm  INT NOT NULL,
    CONSTRAINT uq_point_of_measure_code UNIQUE (style_id, code)
);

-- SQL Server refuses two cascade paths from style into one table (error 1785),
-- so only the point-of-measure key cascades. store.delete_style deletes a
-- style's rules itself before deleting the style.
CREATE TABLE grade_rule (
    pom_id       INT NOT NULL
                 CONSTRAINT fk_grade_rule_pom REFERENCES point_of_measure (id) ON DELETE CASCADE,
    size_id      INT NOT NULL
                 CONSTRAINT fk_grade_rule_size REFERENCES style_size (id),
    increment_mm INT NOT NULL,
    CONSTRAINT pk_grade_rule PRIMARY KEY (pom_id, size_id)
);
