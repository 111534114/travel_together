-- 行程聊天室：成員即時聊天＋已讀回條（誰看過訊息）。
-- trip_chat_messages 存聊天訊息；trip_chat_reads 記錄每位成員在每個行程讀到哪一則訊息，
-- 用「最後已讀的 message_id」判斷某則訊息被誰看過，不用每則訊息都存一筆已讀紀錄。
-- 刪除行程或使用者時，聊天紀錄會跟著 CASCADE 刪除。
-- 此 migration 可重複執行(CREATE TABLE IF NOT EXISTS)。

START TRANSACTION;

CREATE TABLE IF NOT EXISTS `trip_chat_messages` (
  `message_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT,
  `trip_id` bigint(20) UNSIGNED NOT NULL,
  `user_id` bigint(20) UNSIGNED NOT NULL,
  `content` text NOT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`message_id`),
  KEY `idx_trip_chat_messages_trip` (`trip_id`, `message_id`),
  CONSTRAINT `fk_trip_chat_messages_trip` FOREIGN KEY (`trip_id`) REFERENCES `trips` (`trip_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_trip_chat_messages_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `trip_chat_reads` (
  `trip_id` bigint(20) UNSIGNED NOT NULL,
  `user_id` bigint(20) UNSIGNED NOT NULL,
  `last_read_message_id` bigint(20) UNSIGNED NOT NULL DEFAULT 0,
  `last_seen_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`trip_id`, `user_id`),
  CONSTRAINT `fk_trip_chat_reads_trip` FOREIGN KEY (`trip_id`) REFERENCES `trips` (`trip_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_trip_chat_reads_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

COMMIT;
