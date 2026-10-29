-- 五(四) 旅伴偏好管理：之前「旅伴偏好」分頁整個是假資料(填完按送出只有 alert，統計數字也是寫死的範例)，
-- 現在改成真的存進資料庫，而且團體統計數字是即時從這裡算出來的。
CREATE TABLE IF NOT EXISTS `trip_preferences` (
  `preference_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `trip_id` BIGINT UNSIGNED NOT NULL,
  `user_id` BIGINT UNSIGNED NOT NULL,
  `like_activities` VARCHAR(500) DEFAULT NULL,
  `dislike_activities` VARCHAR(500) DEFAULT NULL,
  `must_visit` TEXT DEFAULT NULL,
  `avoid_places` TEXT DEFAULT NULL,
  `budget_limit` DECIMAL(12,2) DEFAULT NULL,
  `diet` VARCHAR(20) NOT NULL DEFAULT 'none',
  `transport_pref` VARCHAR(20) NOT NULL DEFAULT 'any',
  `walk_tolerance` VARCHAR(20) NOT NULL DEFAULT 'medium',
  `intensity` VARCHAR(20) DEFAULT NULL,
  `special_needs` TEXT DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`preference_id`),
  UNIQUE KEY `uniq_trip_user` (`trip_id`, `user_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `trip_preferences_ibfk_1` FOREIGN KEY (`trip_id`) REFERENCES `trips` (`trip_id`) ON DELETE CASCADE,
  CONSTRAINT `trip_preferences_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
