-- Run after migrate_1009_trip_soft_delete.sql. Additive migration for MariaDB.
ALTER TABLE trips
  ADD COLUMN IF NOT EXISTS moderation_status ENUM('visible', 'hidden', 'removed') NOT NULL DEFAULT 'visible' AFTER visibility,
  ADD INDEX IF NOT EXISTS idx_trips_moderation (moderation_status, visibility, deleted_at);

CREATE TABLE IF NOT EXISTS trip_moderation_history (
  moderation_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  trip_id BIGINT UNSIGNED NOT NULL,
  admin_id BIGINT UNSIGNED NOT NULL,
  action ENUM('hide', 'restore', 'remove') NOT NULL,
  reason VARCHAR(1000) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_trip_moderation_history_trip (trip_id, created_at),
  FOREIGN KEY (trip_id) REFERENCES trips(trip_id) ON DELETE CASCADE,
  FOREIGN KEY (admin_id) REFERENCES users(user_id)
) ENGINE=InnoDB;
