-- Link a friend group to its matching trip. Safe to re-run on MySQL/MariaDB.
SET @add_friend_group_trip_column = (
    SELECT IF(COUNT(*) = 0,
        'ALTER TABLE `friend_groups` ADD COLUMN `trip_id` BIGINT UNSIGNED NULL AFTER `group_id`',
        'SELECT 1')
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'friend_groups' AND COLUMN_NAME = 'trip_id'
);
PREPARE friend_group_trip_column_stmt FROM @add_friend_group_trip_column;
EXECUTE friend_group_trip_column_stmt;
DEALLOCATE PREPARE friend_group_trip_column_stmt;

SET @add_friend_group_trip_fk = (
    SELECT IF(COUNT(*) = 0,
        'ALTER TABLE `friend_groups` ADD CONSTRAINT `fk_friend_groups_trip` FOREIGN KEY (`trip_id`) REFERENCES `trips` (`trip_id`) ON DELETE SET NULL',
        'SELECT 1')
    FROM information_schema.KEY_COLUMN_USAGE
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'friend_groups'
      AND COLUMN_NAME = 'trip_id' AND REFERENCED_TABLE_NAME = 'trips'
);
PREPARE friend_group_trip_fk_stmt FROM @add_friend_group_trip_fk;
EXECUTE friend_group_trip_fk_stmt;
DEALLOCATE PREPARE friend_group_trip_fk_stmt;
