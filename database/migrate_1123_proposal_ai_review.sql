-- 提案 AI 小幫手：會員提議新增景點／餐廳／住宿時，AI 先幫管理員檢查，結果存在這張表(每筆提案一列)。
-- 程式第一次用到時也會自動建立這張表(proposal_review.ensure_table)，這個檔案是給要手動建立的人用。
-- 可重複執行：表已存在時 IF NOT EXISTS 會跳過；設定值已存在時 INSERT IGNORE 不會覆蓋。

CREATE TABLE IF NOT EXISTS proposal_ai_reviews (
    proposal_id BIGINT UNSIGNED PRIMARY KEY,
    status ENUM('queued','running','done','failed') NOT NULL DEFAULT 'queued',   -- 排隊中／檢查中／完成／失敗
    recommendation ENUM('approve','return','needs_human') NULL,                 -- 可以收下／建議退回／要人來看
    auto_approvable TINYINT(1) NOT NULL DEFAULT 0,                              -- AI 建議收下且電腦規則全部通過
    summary VARCHAR(255) NULL,                                                  -- 列表上顯示的一句話
    result_json MEDIUMTEXT NULL,                                                -- 原因、規則檢查、Google 結果、相似資料、建議欄位
    trace_json MEDIUMTEXT NULL,                                                 -- AI 呼叫了哪些工具(除錯用)
    model VARCHAR(80) NULL,                                                     -- 使用的 AI 模型；rules-only 代表 AI 不能用只跑規則
    error_message VARCHAR(255) NULL,
    requested_by BIGINT UNSIGNED NULL,                                          -- 按「再檢查一次」的管理員
    auto_approved_at DATETIME NULL,                                             -- 被自動收下的時間
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_proposal_ai_reviews_proposal FOREIGN KEY (proposal_id) REFERENCES proposals(proposal_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 自動收下開關，預設關閉
INSERT IGNORE INTO app_settings (setting_key, setting_value) VALUES ('proposal_ai_auto_approve', '0');
