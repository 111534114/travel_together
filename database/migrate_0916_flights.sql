-- 新增機票搜尋功能所需的 flights 資料表，並補上常見航點的國家／城市與範例班機資料。
-- 執行前請先備份資料庫；此 migration 可重複執行（皆使用 INSERT IGNORE / 檢查後才插入）。

START TRANSACTION;

CREATE TABLE IF NOT EXISTS `flights` (
  `flight_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT,
  `airline_name` varchar(100) NOT NULL,
  `flight_number` varchar(20) NOT NULL,
  `origin_country_id` bigint(20) UNSIGNED NOT NULL,
  `origin_city_id` bigint(20) UNSIGNED NOT NULL,
  `destination_country_id` bigint(20) UNSIGNED NOT NULL,
  `destination_city_id` bigint(20) UNSIGNED NOT NULL,
  `departure_time` time NOT NULL,
  `arrival_time` time NOT NULL,
  `duration_minutes` int(11) NOT NULL,
  `price` decimal(10,2) NOT NULL DEFAULT 0.00,
  `cabin_class` varchar(50) NOT NULL DEFAULT '經濟艙',
  `seats_available` int(11) NOT NULL DEFAULT 9,
  `status` enum('active','hidden') NOT NULL DEFAULT 'active',
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`flight_id`),
  KEY `fk_flights_origin_country` (`origin_country_id`),
  KEY `fk_flights_origin_city` (`origin_city_id`),
  KEY `fk_flights_destination_country` (`destination_country_id`),
  KEY `fk_flights_destination_city` (`destination_city_id`),
  CONSTRAINT `fk_flights_origin_country` FOREIGN KEY (`origin_country_id`) REFERENCES `countries` (`country_id`),
  CONSTRAINT `fk_flights_origin_city` FOREIGN KEY (`origin_city_id`) REFERENCES `cities` (`city_id`),
  CONSTRAINT `fk_flights_destination_country` FOREIGN KEY (`destination_country_id`) REFERENCES `countries` (`country_id`),
  CONSTRAINT `fk_flights_destination_city` FOREIGN KEY (`destination_city_id`) REFERENCES `cities` (`city_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 補上範例航點所需的國家／城市（既有的台灣／日本、台北市／東京都已存在則會被 IGNORE）。
INSERT IGNORE INTO countries (name) VALUES ('日本'), ('韓國'), ('泰國'), ('新加坡'), ('香港');

INSERT IGNORE INTO cities (country_id, name)
SELECT co.country_id, c.name
FROM (
  SELECT '日本' AS country_name, '大阪市' AS name
  UNION ALL SELECT '韓國', '首爾特別市'
  UNION ALL SELECT '泰國', '曼谷'
  UNION ALL SELECT '新加坡', '新加坡'
  UNION ALL SELECT '香港', '香港'
) c
JOIN countries co ON co.name = c.country_name;

-- 範例班機資料：涵蓋「台北」與常見航點雙向的往返班次，讓去程／回程搜尋都查得到結果。
INSERT INTO flights
  (airline_name, flight_number, origin_country_id, origin_city_id, destination_country_id, destination_city_id,
   departure_time, arrival_time, duration_minutes, price, cabin_class, seats_available, status)
SELECT v.airline_name, v.flight_number, o.country_id, o.city_id, d.country_id, d.city_id,
       v.departure_time, v.arrival_time, v.duration_minutes, v.price, v.cabin_class, v.seats_available, 'active'
FROM (
  SELECT '台北市' AS origin_city, '東京都' AS destination_city, '中華航空' AS airline_name, 'CI100' AS flight_number, '08:00:00' AS departure_time, '12:10:00' AS arrival_time, 250 AS duration_minutes, 8500.00 AS price, '經濟艙' AS cabin_class, 9 AS seats_available
  UNION ALL SELECT '台北市', '東京都', '長榮航空', 'BR198', '13:30:00', '17:35:00', 245, 9200.00, '經濟艙', 9
  UNION ALL SELECT '台北市', '東京都', '日本航空', 'JL809', '19:00:00', '23:05:00', 245, 10500.00, '經濟艙', 9
  UNION ALL SELECT '東京都', '台北市', '中華航空', 'CI101', '09:00:00', '12:45:00', 225, 8500.00, '經濟艙', 9
  UNION ALL SELECT '東京都', '台北市', '長榮航空', 'BR199', '14:00:00', '17:45:00', 225, 9200.00, '經濟艙', 9
  UNION ALL SELECT '東京都', '台北市', '日本航空', 'JL810', '19:30:00', '23:15:00', 225, 10500.00, '經濟艙', 9
  UNION ALL SELECT '台北市', '大阪市', '星宇航空', 'JX820', '09:15:00', '13:00:00', 225, 7800.00, '經濟艙', 9
  UNION ALL SELECT '台北市', '大阪市', '中華航空', 'CI160', '14:20:00', '18:05:00', 225, 8300.00, '經濟艙', 9
  UNION ALL SELECT '大阪市', '台北市', '星宇航空', 'JX821', '15:00:00', '17:35:00', 215, 7800.00, '經濟艙', 9
  UNION ALL SELECT '大阪市', '台北市', '中華航空', 'CI161', '20:00:00', '22:35:00', 215, 8300.00, '經濟艙', 9
  UNION ALL SELECT '台北市', '首爾特別市', '長榮航空', 'BR169', '07:50:00', '11:15:00', 205, 9800.00, '經濟艙', 9
  UNION ALL SELECT '台北市', '首爾特別市', '大韓航空', 'KE185', '15:10:00', '18:35:00', 205, 10200.00, '經濟艙', 9
  UNION ALL SELECT '首爾特別市', '台北市', '長榮航空', 'BR170', '13:00:00', '15:35:00', 155, 9800.00, '經濟艙', 9
  UNION ALL SELECT '首爾特別市', '台北市', '大韓航空', 'KE186', '20:00:00', '22:35:00', 155, 10200.00, '經濟艙', 9
  UNION ALL SELECT '台北市', '曼谷', '中華航空', 'CI835', '08:30:00', '11:15:00', 225, 11500.00, '經濟艙', 9
  UNION ALL SELECT '台北市', '曼谷', '泰國航空', 'TG635', '21:00:00', '23:45:00', 225, 12000.00, '經濟艙', 9
  UNION ALL SELECT '曼谷', '台北市', '中華航空', 'CI836', '09:00:00', '13:35:00', 275, 11500.00, '經濟艙', 9
  UNION ALL SELECT '曼谷', '台北市', '泰國航空', 'TG636', '19:00:00', '23:35:00', 275, 12000.00, '經濟艙', 9
  UNION ALL SELECT '台北市', '新加坡', '長榮航空', 'BR225', '09:40:00', '13:55:00', 255, 13500.00, '經濟艙', 9
  UNION ALL SELECT '台北市', '新加坡', '新加坡航空', 'SQ879', '17:15:00', '21:30:00', 255, 14200.00, '經濟艙', 9
  UNION ALL SELECT '新加坡', '台北市', '長榮航空', 'BR226', '08:00:00', '12:50:00', 290, 13500.00, '經濟艙', 9
  UNION ALL SELECT '新加坡', '台北市', '新加坡航空', 'SQ880', '15:00:00', '19:50:00', 290, 14200.00, '經濟艙', 9
  UNION ALL SELECT '台北市', '香港', '國泰航空', 'CX451', '08:00:00', '09:45:00', 105, 6200.00, '經濟艙', 9
  UNION ALL SELECT '台北市', '香港', '中華航空', 'CI605', '18:20:00', '20:05:00', 105, 6500.00, '經濟艙', 9
  UNION ALL SELECT '香港', '台北市', '國泰航空', 'CX452', '10:30:00', '12:15:00', 105, 6200.00, '經濟艙', 9
  UNION ALL SELECT '香港', '台北市', '中華航空', 'CI606', '21:00:00', '22:45:00', 105, 6500.00, '經濟艙', 9
) v
JOIN cities o ON o.name = v.origin_city
JOIN cities d ON d.name = v.destination_city
WHERE NOT EXISTS (
  SELECT 1 FROM flights f
  WHERE f.flight_number = v.flight_number
    AND f.origin_city_id = o.city_id
    AND f.destination_city_id = d.city_id
);

COMMIT;
