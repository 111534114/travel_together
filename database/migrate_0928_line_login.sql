-- 新增 LINE 登入支援：
-- 新增 line_sub 欄位，儲存 LINE 回傳的使用者唯一識別碼(sub)，用來比對是否為同一個 LINE 帳號。
-- LINE 預設拿不到已驗證的 Email(要另外申請權限審核)，所以 LINE 登入建立的帳號一律視為新帳號，
-- 不會像 Google 登入那樣自動跟既有的 Email 帳號合併。
-- 執行前請先備份資料庫；此 migration 僅需執行一次。

ALTER TABLE users ADD COLUMN line_sub VARCHAR(255) NULL UNIQUE AFTER google_sub;
