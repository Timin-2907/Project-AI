-- =============================================
-- DATABASE: Auth System  |  PostgreSQL
-- =============================================

CREATE TYPE user_status   AS ENUM ('active', 'inactive', 'banned');
CREATE TYPE verify_status AS ENUM ('pending', 'verified', 'expired');
CREATE TYPE login_status  AS ENUM ('success', 'failed');

CREATE TABLE IF NOT EXISTS "Role" (
    "RoleID"   SERIAL PRIMARY KEY,
    "RoleName" VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS "User" (
    "UserID"       SERIAL PRIMARY KEY,
    "Username"     VARCHAR(100) NOT NULL UNIQUE,
    "Email"        VARCHAR(150) NOT NULL UNIQUE,
    "PasswordHash" VARCHAR(255),
    "RoleID"       INT NOT NULL DEFAULT 1,
    "Status"       user_status NOT NULL DEFAULT 'inactive',
    "CreatedAt"    TIMESTAMP NOT NULL DEFAULT NOW(),
    FOREIGN KEY ("RoleID") REFERENCES "Role"("RoleID")
);

CREATE TABLE IF NOT EXISTS "AuthToken" (
    "TokenID"   SERIAL PRIMARY KEY,
    "UserID"    INT NOT NULL,
    "Token"     TEXT NOT NULL,
    "ExpiresAt" TIMESTAMP NOT NULL,
    "CreatedAt" TIMESTAMP NOT NULL DEFAULT NOW(),
    FOREIGN KEY ("UserID") REFERENCES "User"("UserID") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS "Verification" (
    "VerificationID" SERIAL PRIMARY KEY,
    "UserID"         INT NOT NULL,
    "Code"           VARCHAR(10) NOT NULL,
    "ExpiresAt"      TIMESTAMP NOT NULL,
    "Status"         verify_status NOT NULL DEFAULT 'pending',
    FOREIGN KEY ("UserID") REFERENCES "User"("UserID") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS "PasswordReset" (
    "ResetID"    SERIAL PRIMARY KEY,
    "UserID"     INT NOT NULL,
    "ResetToken" VARCHAR(255) NOT NULL,
    "ExpiresAt"  TIMESTAMP NOT NULL,
    FOREIGN KEY ("UserID") REFERENCES "User"("UserID") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS "LoginHistory" (
    "HistoryID" SERIAL PRIMARY KEY,
    "UserID"    INT NOT NULL,
    "Status"    login_status NOT NULL,
    "LoginAt"   TIMESTAMP NOT NULL DEFAULT NOW(),
    FOREIGN KEY ("UserID") REFERENCES "User"("UserID") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS "OAuthProvider" (
    "OAuthID"         SERIAL PRIMARY KEY,
    "UserID"          INT NOT NULL,
    "Provider"        VARCHAR(50) NOT NULL,
    "ProviderUserID"  VARCHAR(255) NOT NULL,
    "AccessTokenHash" VARCHAR(255),
    FOREIGN KEY ("UserID") REFERENCES "User"("UserID") ON DELETE CASCADE
);

INSERT INTO "Role" ("RoleName") VALUES ('user'), ('admin')
ON CONFLICT ("RoleName") DO NOTHING;