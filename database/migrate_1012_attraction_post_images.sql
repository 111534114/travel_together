CREATE TABLE IF NOT EXISTS attraction_post_images (
    image_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    post_id BIGINT UNSIGNED NOT NULL,
    image_path VARCHAR(255) NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    KEY idx_attraction_post_images_post (post_id, sort_order, image_id),
    CONSTRAINT fk_attraction_post_images_post FOREIGN KEY (post_id) REFERENCES attraction_posts(post_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 第一次執行時，把舊版 attraction_posts.image_path 資料搬入子表後再移除舊欄位。
SET @has_old_image = (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'attraction_posts' AND COLUMN_NAME = 'image_path'
);
SET @copy_old_images = IF(
  @has_old_image > 0,
  'INSERT INTO attraction_post_images (post_id, image_path, sort_order) SELECT post_id, image_path, 0 FROM attraction_posts WHERE image_path IS NOT NULL AND NOT EXISTS (SELECT 1 FROM attraction_post_images i WHERE i.post_id = attraction_posts.post_id)',
  'SELECT 1'
);
PREPARE stmt FROM @copy_old_images; EXECUTE stmt; DEALLOCATE PREPARE stmt;
SET @drop_old_image = IF(@has_old_image > 0, 'ALTER TABLE attraction_posts DROP COLUMN image_path', 'SELECT 1');
PREPARE stmt FROM @drop_old_image; EXECUTE stmt; DEALLOCATE PREPARE stmt;
