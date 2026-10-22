-- 公告推播到 LINE 官方帳號的時間：有值代表已經推播過，後台會顯示並在重複推播前提醒（推播會用掉每月訊息額度）。
-- 執行前請先備份資料庫；使用 IF NOT EXISTS，可安全重複執行。

ALTER TABLE announcements ADD COLUMN IF NOT EXISTS line_pushed_at DATETIME NULL AFTER publish_at;
