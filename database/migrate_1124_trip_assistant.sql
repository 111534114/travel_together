-- 行程助理：行程頁「每日行程」旁邊的 AI 聊天助理。
-- 每一則對話存一列(使用者問的、助理回答的)；助理建議的改動清單、套用狀態、復原用的資料也存在這裡。
-- 對話只有本人看得到(用 trip_id + user_id 查)。程式第一次用到時也會試著自動建立，這個檔案給沒有建表權限的環境手動執行。
-- 可重複執行：表已存在時 IF NOT EXISTS 會跳過。

CREATE TABLE IF NOT EXISTS trip_ai_messages (
    message_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    trip_id BIGINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    role ENUM('user','assistant') NOT NULL,                                     -- 使用者問的／助理回答的
    content TEXT NOT NULL,
    plan_json MEDIUMTEXT NULL,                                                  -- 助理建議的改動清單(伺服器檢查過的)
    plan_status ENUM('none','pending','applied','dismissed','stale','undone') NOT NULL DEFAULT 'none',
                                                                                -- 沒有改動／等待套用／已套用／不要／行程被改過已過期／已復原
    applied_by BIGINT UNSIGNED NULL,
    applied_at DATETIME NULL,
    undo_json MEDIUMTEXT NULL,                                                  -- 套用前的樣子，按「復原」時用
    undone_at DATETIME NULL,
    trace_json MEDIUMTEXT NULL,                                                 -- AI 呼叫了哪些工具(除錯用)
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_trip_ai_messages_trip_user (trip_id, user_id, message_id),
    INDEX idx_trip_ai_messages_daily (user_id, role, created_at),                -- 算「今天問了幾次」
    CONSTRAINT fk_trip_ai_messages_trip FOREIGN KEY (trip_id) REFERENCES trips(trip_id) ON DELETE CASCADE,
    CONSTRAINT fk_trip_ai_messages_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;
