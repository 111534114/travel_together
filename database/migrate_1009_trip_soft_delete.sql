-- 行程改成軟刪除：刪除時只標記 deleted_at／deleted_by，行程會進「最近刪除」，
-- 建立者 30 天內可以復原，也可以手動永久刪除；超過 30 天的會在建立者下次開啟「我的旅程」時自動永久刪除。
-- 已刪除的行程不會出現在任何清單、統計，成員也無法再進入。
-- 此 migration 可重複執行(ADD COLUMN / ADD INDEX IF NOT EXISTS，MariaDB 語法)。

ALTER TABLE `trips`
  ADD COLUMN IF NOT EXISTS `deleted_at` datetime DEFAULT NULL COMMENT '軟刪除時間；NULL 代表未刪除' AFTER `updated_at`,
  ADD COLUMN IF NOT EXISTS `deleted_by` bigint(20) UNSIGNED DEFAULT NULL COMMENT '執行刪除的使用者' AFTER `deleted_at`,
  ADD INDEX IF NOT EXISTS `idx_trips_owner_deleted` (`owner_id`, `deleted_at`);

