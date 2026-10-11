-- 完整會員帳號管理：加入「審查中」狀態與帳號處理歷程。
-- 執行前請先備份資料庫。此檔可重複執行。

ALTER TABLE `users`
  MODIFY COLUMN `status`
    ENUM('active','under_review','disabled','deleted')
    NOT NULL DEFAULT 'active';

CREATE TABLE IF NOT EXISTS `user_moderation_history` (
  `moderation_id` BIGINT(20) UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT(20) UNSIGNED NOT NULL,
  `admin_id` BIGINT(20) UNSIGNED NOT NULL,
  `action` VARCHAR(30) NOT NULL,
  `from_status` ENUM('active','under_review','disabled','deleted') NOT NULL,
  `to_status` ENUM('active','under_review','disabled','deleted') NOT NULL,
  `reason` VARCHAR(1000) NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`moderation_id`),
  KEY `idx_user_moderation_user_created` (`user_id`, `created_at`),
  KEY `idx_user_moderation_admin` (`admin_id`),
  CONSTRAINT `fk_user_moderation_user`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_user_moderation_admin`
    FOREIGN KEY (`admin_id`) REFERENCES `users` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
