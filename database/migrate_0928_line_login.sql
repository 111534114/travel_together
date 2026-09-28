-- 新增 LINE 登入使用者識別欄位；執行前請先備份資料庫，本 migration 僅需執行一次。
-- LINE Login 預設不提供 Email，因此首次登入會要求使用者自行補填。

ALTER TABLE users ADD COLUMN line_sub VARCHAR(255) NULL UNIQUE AFTER google_sub;
