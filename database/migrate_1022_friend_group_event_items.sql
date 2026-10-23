CREATE TABLE IF NOT EXISTS friend_group_event_items (
    item_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    event_id BIGINT UNSIGNED NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NULL,
    title VARCHAR(150) NOT NULL,
    location VARCHAR(255),
    sort_order INT UNSIGNED NOT NULL DEFAULT 0,
    FOREIGN KEY (event_id) REFERENCES friend_group_events(event_id) ON DELETE CASCADE
) ENGINE=InnoDB;

