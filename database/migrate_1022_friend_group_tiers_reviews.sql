-- 交友揪團擴充兩項功能：
-- 1) 分級團長制度：friend_groups 加 end_date 支援多天行程(只有 Lv.2 資深團長能排多天，
--    Lv.1 新手團長限制單日、人數上限，等級由「累積開團次數」+「平均評價」在程式裡即時算出，不另外存欄位)
-- 2) 雙向評價(盲評)：新增 friend_group_reviews，團長評團員、團員評團長，
--    雙方都評完才會互相看到對方寫的內容
-- 可重複執行：欄位/資料表已存在時用 IF NOT EXISTS 跳過，不會報錯

ALTER TABLE friend_groups
    ADD COLUMN IF NOT EXISTS end_date DATE NULL AFTER event_date;

CREATE TABLE IF NOT EXISTS friend_group_reviews (
    review_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    group_id BIGINT UNSIGNED NOT NULL,
    reviewer_id BIGINT UNSIGNED NOT NULL,
    reviewee_id BIGINT UNSIGNED NOT NULL,
    rating TINYINT UNSIGNED NOT NULL,
    tags VARCHAR(255),
    comment VARCHAR(500),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_group_reviewer_reviewee (group_id, reviewer_id, reviewee_id),
    FOREIGN KEY (group_id) REFERENCES friend_groups(group_id) ON DELETE CASCADE,
    FOREIGN KEY (reviewer_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (reviewee_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CHECK (rating BETWEEN 1 AND 5)
) ENGINE=InnoDB;
