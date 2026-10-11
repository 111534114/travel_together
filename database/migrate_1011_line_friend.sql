-- 新增「是否為 LINE 官方帳號好友」欄位，用來判斷能否透過官方帳號推播通知給會員。
-- 由官方帳號 webhook 的 follow / unfollow 事件，以及 LINE 登入時查詢好友狀態來更新。
-- 執行前請先備份資料庫；使用 IF NOT EXISTS，可安全重複執行。

ALTER TABLE users ADD COLUMN IF NOT EXISTS line_friend TINYINT(1) NOT NULL DEFAULT 0 AFTER line_sub;
