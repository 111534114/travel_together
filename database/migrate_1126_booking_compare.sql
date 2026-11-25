-- 機票＋住宿比價：行程頁「住宿與預算」分頁的比價結果(每次比價一列)，所有旅伴都看得到。
-- 也用來算「每人每天最多比價幾次」。程式第一次用到時也會試著自動建立，這個檔案給沒有建表權限的環境手動執行。
-- 可重複執行：表已存在時 IF NOT EXISTS 會跳過。

CREATE TABLE IF NOT EXISTS trip_booking_compares (
    compare_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    trip_id BIGINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,                                -- 誰按了比價
    origin VARCHAR(60) NOT NULL,                                     -- 出發地(使用者填的)
    request_text VARCHAR(300) NULL,                                  -- 其他要求，例如「住車站附近」
    status ENUM('running','done','failed') NOT NULL DEFAULT 'running', -- 比價中／完成／失敗
    result_json MEDIUMTEXT NULL,                                     -- 三個方案(價錢由伺服器依真的查詢結果計算)
    trace_json MEDIUMTEXT NULL,                                      -- AI 查了哪些東西(除錯用)
    error_message VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_trip_booking_compares_trip (trip_id, compare_id),
    INDEX idx_trip_booking_compares_daily (user_id, created_at),     -- 算「今天比價了幾次」
    CONSTRAINT fk_trip_booking_compares_trip FOREIGN KEY (trip_id) REFERENCES trips(trip_id) ON DELETE CASCADE,
    CONSTRAINT fk_trip_booking_compares_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;
