CREATE TABLE IF NOT EXISTS attraction_posts (
  post_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  attraction_id BIGINT UNSIGNED NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  image_path VARCHAR(255) DEFAULT NULL,
  caption TEXT DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (post_id),
  KEY idx_attraction_posts_attraction (attraction_id, created_at),
  CONSTRAINT fk_attraction_posts_attraction FOREIGN KEY (attraction_id) REFERENCES attractions (attraction_id) ON DELETE CASCADE,
  CONSTRAINT fk_attraction_posts_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
