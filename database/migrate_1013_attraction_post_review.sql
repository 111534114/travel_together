SET @had_review_status = (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'attraction_posts' AND COLUMN_NAME = 'review_status'
);

ALTER TABLE attraction_posts
    ADD COLUMN IF NOT EXISTS review_status ENUM('pending','approved','rejected') NOT NULL DEFAULT 'pending' AFTER caption,
    ADD COLUMN IF NOT EXISTS reviewed_by BIGINT UNSIGNED NULL AFTER review_status,
    ADD COLUMN IF NOT EXISTS reviewed_at DATETIME NULL AFTER reviewed_by,
    ADD COLUMN IF NOT EXISTS review_note VARCHAR(255) NULL AFTER reviewed_at;

SET @has_review_fk = (
  SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
  WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME = 'attraction_posts'
    AND CONSTRAINT_NAME = 'fk_attraction_posts_reviewed_by'
);
SET @add_review_fk = IF(
  @has_review_fk = 0,
  'ALTER TABLE attraction_posts ADD CONSTRAINT fk_attraction_posts_reviewed_by FOREIGN KEY (reviewed_by) REFERENCES users(user_id) ON DELETE SET NULL',
  'SELECT 1'
);
PREPARE stmt FROM @add_review_fk; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 既有貼文視為已核准；新貼文仍使用欄位預設值 pending。
SET @approve_legacy_posts = IF(
  @had_review_status = 0,
  "UPDATE attraction_posts SET review_status='approved', reviewed_at=COALESCE(reviewed_at, NOW()) WHERE review_status='pending'",
  'SELECT 1'
);
PREPARE stmt FROM @approve_legacy_posts; EXECUTE stmt; DEALLOCATE PREPARE stmt;
