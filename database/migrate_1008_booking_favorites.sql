CREATE TABLE IF NOT EXISTS booking_favorites (
    user_id BIGINT UNSIGNED NOT NULL,
    kind ENUM('hotel','flight','train') NOT NULL,
    target_id BIGINT UNSIGNED NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, kind, target_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
