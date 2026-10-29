-- 會員通知偏好設定：每個會員、每個通知類別一列。
-- 沒有紀錄的類別視為開啟，所以沒設定過的會員會收到所有通知。
-- category 對應 notification_preferences.py 的 NOTIFICATION_CATEGORIES：trip、mention、friend_group、event、album
CREATE TABLE IF NOT EXISTS notification_preferences (
    user_id BIGINT UNSIGNED NOT NULL,
    category VARCHAR(30) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, category),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
