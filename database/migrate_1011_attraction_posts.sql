-- 景點相簿：會員可以針對某個景點分享照片＋心得（類似 IG 貼文，照片、文字都可以只填一種）。
-- 此 migration 可重複執行(CREATE TABLE IF NOT EXISTS)。

CREATE TABLE IF NOT EXISTS `attraction_posts` (
  `post_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT,
  `attraction_id` bigint(20) UNSIGNED NOT NULL,
  `user_id` bigint(20) UNSIGNED NOT NULL,
  `image_path` varchar(255) DEFAULT NULL,
  `caption` text DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`post_id`),
  KEY `idx_attraction_posts_attraction` (`attraction_id`, `created_at`),
  CONSTRAINT `fk_attraction_posts_attraction` FOREIGN KEY (`attraction_id`) REFERENCES `attractions` (`attraction_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_attraction_posts_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
