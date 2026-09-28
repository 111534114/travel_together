-- 新增 Google 登入支援：
-- 1. password_hash 改成可為 NULL，因為用 Google 登入建立的帳號沒有密碼。
-- 2. 新增 google_sub 欄位，儲存 Google 回傳的使用者唯一識別碼(sub)，用來比對是否為同一個 Google 帳號。
-- 執行前請先備份資料庫；此 migration 僅需執行一次。

ALTER TABLE users MODIFY COLUMN password_hash VARCHAR(255) NULL;
ALTER TABLE users ADD COLUMN google_sub VARCHAR(255) NULL UNIQUE AFTER password_hash;
