-- 讓「收藏」功能也能收藏住宿、餐廳，不再只能收藏景點(配合新增的「探索住宿」「探索餐廳」頁面)
-- 欄位新增用 IF NOT EXISTS，可重複執行；但外鍵/唯一索引那段只能執行一次，執行過就不要再執行第二次

ALTER TABLE favorites
    MODIFY COLUMN target_type ENUM('trip','attraction','restaurant','accommodation') NOT NULL;

ALTER TABLE favorites
    ADD COLUMN IF NOT EXISTS restaurant_id BIGINT UNSIGNED NULL AFTER attraction_id,
    ADD COLUMN IF NOT EXISTS accommodation_id BIGINT UNSIGNED NULL AFTER restaurant_id;

ALTER TABLE favorites
    ADD CONSTRAINT fk_favorites_restaurant FOREIGN KEY (restaurant_id) REFERENCES restaurants(restaurant_id) ON DELETE CASCADE,
    ADD CONSTRAINT fk_favorites_accommodation FOREIGN KEY (accommodation_id) REFERENCES accommodations(accommodation_id) ON DELETE CASCADE,
    ADD UNIQUE KEY uniq_user_restaurant (user_id, restaurant_id),
    ADD UNIQUE KEY uniq_user_accommodation (user_id, accommodation_id);
