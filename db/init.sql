-- Local only: creates each service's databases and login inside the compose
-- SQL Server. Run by the db-init service on every `docker compose up`, so every
-- statement checks before it creates. On Azure the logins are created once
-- during the initial setup instead (README).
--
-- Each login is db_owner of its own service's databases (migrations need DDL)
-- and has no user at all in the other service's databases.
-- Passwords arrive as sqlcmd variables from compose; none are written here.

:on error exit

IF DB_ID(N'specs') IS NULL CREATE DATABASE specs;
IF DB_ID(N'specs_test') IS NULL CREATE DATABASE specs_test;
IF DB_ID(N'samples') IS NULL CREATE DATABASE samples;
IF DB_ID(N'samples_test') IS NULL CREATE DATABASE samples_test;
GO

-- ALTER on a re-run keeps the login in step with the password in compose.
IF SUSER_ID(N'specs_user') IS NULL
    CREATE LOGIN specs_user WITH PASSWORD = N'$(SPECS_DB_PASSWORD)';
ELSE
    ALTER LOGIN specs_user WITH PASSWORD = N'$(SPECS_DB_PASSWORD)';
IF SUSER_ID(N'samples_user') IS NULL
    CREATE LOGIN samples_user WITH PASSWORD = N'$(SAMPLES_DB_PASSWORD)';
ELSE
    ALTER LOGIN samples_user WITH PASSWORD = N'$(SAMPLES_DB_PASSWORD)';
GO

USE specs;
IF USER_ID(N'specs_user') IS NULL CREATE USER specs_user FOR LOGIN specs_user;
ALTER ROLE db_owner ADD MEMBER specs_user;
GO
USE specs_test;
IF USER_ID(N'specs_user') IS NULL CREATE USER specs_user FOR LOGIN specs_user;
ALTER ROLE db_owner ADD MEMBER specs_user;
GO
USE samples;
IF USER_ID(N'samples_user') IS NULL CREATE USER samples_user FOR LOGIN samples_user;
ALTER ROLE db_owner ADD MEMBER samples_user;
GO
USE samples_test;
IF USER_ID(N'samples_user') IS NULL CREATE USER samples_user FOR LOGIN samples_user;
ALTER ROLE db_owner ADD MEMBER samples_user;
GO

PRINT 'db/init.sql: databases and logins ready';
