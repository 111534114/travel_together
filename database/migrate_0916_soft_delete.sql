-- 景點、餐廳、住宿改成軟刪除：刪除時只標記 deleted_at 時間，不真的砍掉資料列，
-- 可以從回收桶復原，也可以在回收桶裡永久刪除。
-- 執行前請先備份資料庫；此 migration 僅需執行一次。

ALTER TABLE attractions ADD COLUMN deleted_at DATETIME NULL AFTER status;
ALTER TABLE restaurants ADD COLUMN deleted_at DATETIME NULL AFTER status;
ALTER TABLE accommodations ADD COLUMN deleted_at DATETIME NULL AFTER status;

-- 熱門景點檢視表也要排除已軟刪除的景點，避免刪除的景點還出現在儀表板/報表統計裡。
CREATE OR REPLACE VIEW vw_popular_attractions AS
SELECT a.attraction_id, a.name, c.name AS country, ci.name AS city,
COUNT(DISTINCT f.favorite_id) favorite_count,
COUNT(DISTINCT i.itinerary_id) itinerary_count
FROM attractions a
JOIN countries c ON c.country_id=a.country_id
JOIN cities ci ON ci.city_id=a.city_id
LEFT JOIN favorites f ON f.attraction_id=a.attraction_id
LEFT JOIN itineraries i ON i.attraction_id=a.attraction_id
WHERE a.deleted_at IS NULL
GROUP BY a.attraction_id,a.name,c.name,ci.name;
