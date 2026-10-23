CREATE TABLE IF NOT EXISTS friend_group_onboarding (
    user_id BIGINT UNSIGNED PRIMARY KEY,
    completed_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

