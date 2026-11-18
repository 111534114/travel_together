-- 即時查詢結果(Google Flights / Google Hotels)的收藏。
-- 即時資料沒有資料庫 id，所以收藏時直接存一份當下的摘要(標題、說明、參考價格、連結)，
-- 跟原本用 id 對應 flights / accommodations 資料表的 booking_favorites 分開。
CREATE TABLE IF NOT EXISTS booking_live_favorites (
    user_id BIGINT UNSIGNED NOT NULL,
    kind ENUM('hotel','flight') NOT NULL,
    item_key VARCHAR(190) NOT NULL,
    title VARCHAR(200) NOT NULL,
    subtitle VARCHAR(300) DEFAULT NULL,
    price DECIMAL(12,2) DEFAULT NULL,
    link VARCHAR(1000) DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, kind, item_key),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
