-- 將 trips.country / trips.city 文字欄位正規化為 countries、cities 外鍵。
-- 執行前請先備份資料庫；此 migration 僅需執行一次。

START TRANSACTION;

ALTER TABLE trips
    ADD COLUMN country_id BIGINT UNSIGNED NULL AFTER cover_image_path,
    ADD COLUMN city_id BIGINT UNSIGNED NULL AFTER country_id;

INSERT IGNORE INTO countries(name)
SELECT DISTINCT COALESCE(NULLIF(TRIM(country), ''), '未設定')
FROM trips;

INSERT IGNORE INTO cities(country_id, name)
SELECT DISTINCT co.country_id,
       COALESCE(NULLIF(TRIM(t.city), ''), '未設定')
FROM trips t
JOIN countries co
  ON co.name = COALESCE(NULLIF(TRIM(t.country), ''), '未設定');

UPDATE trips t
JOIN countries co
  ON co.name = COALESCE(NULLIF(TRIM(t.country), ''), '未設定')
JOIN cities ci
  ON ci.country_id = co.country_id
 AND ci.name = COALESCE(NULLIF(TRIM(t.city), ''), '未設定')
SET t.country_id = co.country_id,
    t.city_id = ci.city_id;

ALTER TABLE trips
    MODIFY country_id BIGINT UNSIGNED NOT NULL,
    MODIFY city_id BIGINT UNSIGNED NOT NULL,
    ADD CONSTRAINT fk_trips_country
        FOREIGN KEY (country_id) REFERENCES countries(country_id),
    ADD CONSTRAINT fk_trips_city
        FOREIGN KEY (city_id) REFERENCES cities(city_id),
    DROP COLUMN country,
    DROP COLUMN city;

COMMIT;
