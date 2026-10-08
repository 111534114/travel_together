-- 每日行程功能強化：
-- 1) item_type 新增「遊樂園」(amusement_park)
-- 2) 新增 is_all_day，用來區分「整天」跟「沒有填時間」
-- 執行前請先備份資料庫；此 migration 僅需執行一次。

ALTER TABLE itineraries
  MODIFY COLUMN item_type ENUM('attraction','restaurant','accommodation','transport','shopping','meeting','free_time','amusement_park','other') NOT NULL;

ALTER TABLE itineraries
  ADD COLUMN is_all_day TINYINT(1) NOT NULL DEFAULT 0 AFTER end_time;
