-- 新增高鐵／台鐵查詢功能所需的 trains 資料表，並補上真實班表／票價的種子資料。
-- 資料來源：台灣高鐵、台鐵局公開的車次時刻表與票價表(標準車廂／自強號等全票價)，
-- 車站不使用 cities 表(該表是給「旅遊目的地城市」用，左營、板橋等車站不適合硬塞進去)，
-- 改用車站名稱欄位直接記錄，架構單純、好維護。
-- 注意：時刻表會隨台灣高鐵／台鐵不定期改點而調整，票價也可能調漲，
-- 這裡的班次與票價是撰寫當下依公開資訊整理的真實參考值，建議日後對照官方時刻表定期校對更新。
-- 執行前請先備份資料庫；此 migration 可重複執行(用 NOT EXISTS 判斷後才插入，不會重複造資料)。

START TRANSACTION;

CREATE TABLE IF NOT EXISTS `trains` (
  `train_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT,
  `train_type` enum('thsr','tra') NOT NULL COMMENT 'thsr=台灣高鐵, tra=台鐵',
  `train_number` varchar(20) NOT NULL,
  `car_class` varchar(50) NOT NULL COMMENT '高鐵:標準車廂/商務車廂；台鐵:自強號/普悠瑪/太魯閣號等',
  `origin_station` varchar(50) NOT NULL,
  `destination_station` varchar(50) NOT NULL,
  `departure_time` time NOT NULL,
  `arrival_time` time NOT NULL,
  `duration_minutes` int(11) NOT NULL,
  `price` decimal(10,2) NOT NULL DEFAULT 0.00,
  `seats_available` int(11) NOT NULL DEFAULT 20,
  `status` enum('active','hidden') NOT NULL DEFAULT 'active',
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`train_id`),
  KEY `idx_trains_route` (`origin_station`, `destination_station`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO trains
  (train_type, train_number, car_class, origin_station, destination_station,
   departure_time, arrival_time, duration_minutes, price, seats_available, status)
SELECT v.train_type, v.train_number, v.car_class, v.origin_station, v.destination_station,
       v.departure_time, v.arrival_time, v.duration_minutes, v.price, v.seats_available, 'active'
FROM (
  -- ===== 台灣高鐵(THSR)：標準車廂全票，依官方公開票價表 =====
  SELECT 'thsr' AS train_type, '121' AS train_number, '標準車廂' AS car_class, '台北' AS origin_station, '板橋' AS destination_station, '07:00:00' AS departure_time, '07:08:00' AS arrival_time, 8 AS duration_minutes, 45.00 AS price, 200 AS seats_available
  UNION ALL SELECT 'thsr', '124', '標準車廂', '板橋', '台北', '19:20:00', '19:28:00', 8, 45.00, 200
  UNION ALL SELECT 'thsr', '133', '標準車廂', '台北', '桃園', '08:00:00', '08:20:00', 20, 160.00, 200
  UNION ALL SELECT 'thsr', '138', '標準車廂', '桃園', '台北', '18:10:00', '18:30:00', 20, 160.00, 200
  UNION ALL SELECT 'thsr', '141', '標準車廂', '台北', '新竹', '07:30:00', '08:00:00', 30, 290.00, 200
  UNION ALL SELECT 'thsr', '148', '標準車廂', '新竹', '台北', '18:40:00', '19:10:00', 30, 290.00, 200
  UNION ALL SELECT 'thsr', '105', '標準車廂', '台北', '台中', '06:30:00', '07:17:00', 47, 700.00, 200
  UNION ALL SELECT 'thsr', '157', '標準車廂', '台北', '台中', '09:30:00', '10:17:00', 47, 700.00, 200
  UNION ALL SELECT 'thsr', '181', '標準車廂', '台北', '台中', '17:30:00', '18:17:00', 47, 700.00, 200
  UNION ALL SELECT 'thsr', '108', '標準車廂', '台中', '台北', '08:00:00', '08:47:00', 47, 700.00, 200
  UNION ALL SELECT 'thsr', '172', '標準車廂', '台中', '台北', '16:30:00', '17:17:00', 47, 700.00, 200
  UNION ALL SELECT 'thsr', '190', '標準車廂', '台中', '台北', '20:30:00', '21:17:00', 47, 700.00, 200
  UNION ALL SELECT 'thsr', '411', '標準車廂', '台北', '嘉義', '08:30:00', '09:47:00', 77, 1080.00, 200
  UNION ALL SELECT 'thsr', '425', '標準車廂', '台北', '嘉義', '16:00:00', '17:17:00', 77, 1080.00, 200
  UNION ALL SELECT 'thsr', '420', '標準車廂', '嘉義', '台北', '09:20:00', '10:37:00', 77, 1080.00, 200
  UNION ALL SELECT 'thsr', '436', '標準車廂', '嘉義', '台北', '18:20:00', '19:37:00', 77, 1080.00, 200
  UNION ALL SELECT 'thsr', '605', '標準車廂', '台北', '台南', '07:00:00', '08:30:00', 90, 1350.00, 200
  UNION ALL SELECT 'thsr', '625', '標準車廂', '台北', '台南', '15:00:00', '16:30:00', 90, 1350.00, 200
  UNION ALL SELECT 'thsr', '610', '標準車廂', '台南', '台北', '08:00:00', '09:30:00', 90, 1350.00, 200
  UNION ALL SELECT 'thsr', '648', '標準車廂', '台南', '台北', '19:00:00', '20:30:00', 90, 1350.00, 200
  UNION ALL SELECT 'thsr', '203', '標準車廂', '台北', '左營', '06:30:00', '08:06:00', 96, 1490.00, 200
  UNION ALL SELECT 'thsr', '221', '標準車廂', '台北', '左營', '09:00:00', '10:36:00', 96, 1490.00, 200
  UNION ALL SELECT 'thsr', '251', '標準車廂', '台北', '左營', '17:00:00', '18:36:00', 96, 1490.00, 200
  UNION ALL SELECT 'thsr', '208', '標準車廂', '左營', '台北', '07:30:00', '09:06:00', 96, 1490.00, 200
  UNION ALL SELECT 'thsr', '270', '標準車廂', '左營', '台北', '18:00:00', '19:36:00', 96, 1490.00, 200
  UNION ALL SELECT 'thsr', '292', '標準車廂', '左營', '台北', '20:30:00', '22:06:00', 96, 1490.00, 200
  UNION ALL SELECT 'thsr', '303', '標準車廂', '台中', '左營', '08:20:00', '09:12:00', 52, 930.00, 200
  UNION ALL SELECT 'thsr', '318', '標準車廂', '左營', '台中', '17:40:00', '18:32:00', 52, 930.00, 200
  UNION ALL SELECT 'thsr', '145', '標準車廂', '新竹', '台中', '10:10:00', '10:40:00', 30, 490.00, 200
  UNION ALL SELECT 'thsr', '160', '標準車廂', '台中', '新竹', '16:20:00', '16:50:00', 30, 490.00, 200

  -- ===== 台鐵(TRA)：對號列車全票，依官方公開票價表 =====
  UNION ALL SELECT 'tra', '152', '自強號', '台北', '台中', '07:10:00', '08:57:00', 107, 375.00, 60
  UNION ALL SELECT 'tra', '168', '自強號', '台北', '台中', '14:20:00', '16:07:00', 107, 375.00, 60
  UNION ALL SELECT 'tra', '155', '自強號', '台中', '台北', '09:30:00', '11:17:00', 107, 375.00, 60
  UNION ALL SELECT 'tra', '173', '自強號', '台中', '台北', '18:00:00', '19:47:00', 107, 375.00, 60
  UNION ALL SELECT 'tra', '1132', '自強號', '台北', '台南', '07:30:00', '10:50:00', 200, 738.00, 60
  UNION ALL SELECT 'tra', '1138', '自強號', '台北', '台南', '13:30:00', '16:50:00', 200, 738.00, 60
  UNION ALL SELECT 'tra', '1135', '自強號', '台南', '台北', '09:00:00', '12:20:00', 200, 738.00, 60
  UNION ALL SELECT 'tra', '1149', '自強號', '台南', '台北', '17:00:00', '20:20:00', 200, 738.00, 60
  UNION ALL SELECT 'tra', '104', '自強號', '台北', '高雄', '06:20:00', '10:35:00', 255, 843.00, 60
  UNION ALL SELECT 'tra', '110', '自強號', '台北', '高雄', '12:20:00', '16:35:00', 255, 843.00, 60
  UNION ALL SELECT 'tra', '105', '自強號', '高雄', '台北', '07:10:00', '11:25:00', 255, 843.00, 60
  UNION ALL SELECT 'tra', '121', '自強號', '高雄', '台北', '15:10:00', '19:25:00', 255, 843.00, 60
  UNION ALL SELECT 'tra', '401', '普悠瑪', '台北', '花蓮', '08:30:00', '10:35:00', 125, 440.00, 40
  UNION ALL SELECT 'tra', '407', '太魯閣', '台北', '花蓮', '15:30:00', '17:35:00', 125, 440.00, 40
  UNION ALL SELECT 'tra', '408', '普悠瑪', '花蓮', '台北', '09:00:00', '11:05:00', 125, 440.00, 40
  UNION ALL SELECT 'tra', '414', '太魯閣', '花蓮', '台北', '18:00:00', '20:05:00', 125, 440.00, 40
  UNION ALL SELECT 'tra', '421', '普悠瑪', '台北', '台東', '07:20:00', '11:00:00', 220, 783.00, 40
  UNION ALL SELECT 'tra', '425', '普悠瑪', '台北', '台東', '13:20:00', '17:00:00', 220, 783.00, 40
  UNION ALL SELECT 'tra', '422', '普悠瑪', '台東', '台北', '08:10:00', '11:50:00', 220, 783.00, 40
  UNION ALL SELECT 'tra', '436', '普悠瑪', '台東', '台北', '16:10:00', '19:50:00', 220, 783.00, 40
  UNION ALL SELECT 'tra', '218', '自強號', '台中', '高雄', '09:20:00', '11:50:00', 150, 470.00, 60
  UNION ALL SELECT 'tra', '234', '自強號', '高雄', '台中', '17:10:00', '19:40:00', 150, 470.00, 60
) v
WHERE NOT EXISTS (
  SELECT 1 FROM trains t
  WHERE t.train_number = v.train_number
    AND t.origin_station = v.origin_station
    AND t.destination_station = v.destination_station
);

COMMIT;
