-- LINE 官方帳號推播紀錄：記錄每位會員、每個行程已經發過哪一種提醒，避免排程重複推播（推播會用掉每月訊息額度）。
-- notify_type 目前只有 'trip_day_before'（行程出發前一天提醒），之後新增其他提醒類型時沿用這張表。
-- 執行前請先備份資料庫；使用 IF NOT EXISTS，可安全重複執行。

CREATE TABLE IF NOT EXISTS line_notification_logs (
    log_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    trip_id BIGINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    notify_type VARCHAR(30) NOT NULL,
    notify_date DATE NOT NULL,
    sent_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_line_notification (trip_id, user_id, notify_type, notify_date),
    CONSTRAINT fk_line_notification_trip FOREIGN KEY (trip_id) REFERENCES trips (trip_id) ON DELETE CASCADE,
    CONSTRAINT fk_line_notification_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
