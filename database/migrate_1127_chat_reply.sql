-- 行程聊天室：可以「回覆」某一則訊息（像 LINE 的回覆）。
-- reply_to_message_id 記錄這則訊息是在回覆哪一則；一般訊息是 NULL。
-- 網站程式會自動偵測這個欄位：還沒執行這個檔案前，聊天室照常使用，只是不會出現「回覆」按鈕。
-- 此 migration 可重複執行(IF NOT EXISTS)。

ALTER TABLE `trip_chat_messages`
  ADD COLUMN IF NOT EXISTS `reply_to_message_id` bigint(20) UNSIGNED NULL DEFAULT NULL AFTER `content`,
  ADD INDEX IF NOT EXISTS `idx_trip_chat_messages_reply` (`reply_to_message_id`);
