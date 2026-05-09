-- =============================================
-- MIGRATION: Folder & Document Management
-- =============================================

-- Thư mục (cây phân cấp, tự tham chiếu)
CREATE TABLE IF NOT EXISTS "Folder" (
    "FolderID"  SERIAL PRIMARY KEY,
    "Name"      VARCHAR(255) NOT NULL,
    "ParentID"  INT REFERENCES "Folder"("FolderID") ON DELETE CASCADE,
    "Path"      TEXT NOT NULL,              -- ví dụ: /root/toan/chuong1
    "OwnerID"   INT REFERENCES "User"("UserID") ON DELETE SET NULL,
    "CreatedAt" TIMESTAMP NOT NULL DEFAULT NOW(),
    "UpdatedAt" TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE ("ParentID", "Name")             -- không trùng tên trong cùng cha
);

-- Tài liệu bên trong folder
CREATE TABLE IF NOT EXISTS "Document" (
    "DocumentID" SERIAL PRIMARY KEY,
    "FolderID"   INT REFERENCES "Folder"("FolderID") ON DELETE SET NULL,
    "Name"       VARCHAR(255) NOT NULL,
    "Path"       TEXT NOT NULL,
    "MimeType"   VARCHAR(100),
    "Size"       BIGINT DEFAULT 0,
    "OwnerID"    INT REFERENCES "User"("UserID") ON DELETE SET NULL,
    "CreatedAt"  TIMESTAMP NOT NULL DEFAULT NOW(),
    "UpdatedAt"  TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_folder_parent ON "Folder"("ParentID");
CREATE INDEX IF NOT EXISTS idx_folder_path   ON "Folder"("Path");
CREATE INDEX IF NOT EXISTS idx_folder_owner  ON "Folder"("OwnerID");
CREATE INDEX IF NOT EXISTS idx_doc_folder    ON "Document"("FolderID");

-- Seed: thư mục gốc
INSERT INTO "Folder" ("Name", "ParentID", "Path")
VALUES ('root', NULL, '/root')
ON CONFLICT DO NOTHING;