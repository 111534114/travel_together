-- 費用加入發票明細：一筆費用可以有多列明細，每列記錄日期、明細內容、金額與收據／發票照片。
-- 刪除費用（或整個行程）時，明細會跟著 CASCADE 刪除（照片檔案留在 static/uploads/receipts）。
-- 此 migration 可重複執行(CREATE TABLE IF NOT EXISTS)。

START TRANSACTION;

CREATE TABLE IF NOT EXISTS `expense_items` (
  `item_id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT,
  `expense_id` bigint(20) UNSIGNED NOT NULL,
  `item_date` date NOT NULL,
  `description` varchar(255) NOT NULL COMMENT '明細內容，例如 牛肉麵 x2',
  `amount` decimal(14,2) NOT NULL DEFAULT 0.00,
  `receipt_path` varchar(255) DEFAULT NULL COMMENT '收據／發票照片（圖片或 PDF）',
  `sort_order` int(11) NOT NULL DEFAULT 0,
  PRIMARY KEY (`item_id`),
  KEY `idx_expense_items_expense` (`expense_id`, `sort_order`),
  CONSTRAINT `fk_expense_items_expense` FOREIGN KEY (`expense_id`) REFERENCES `expenses` (`expense_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

COMMIT;
