CREATE TABLE IF NOT EXISTS content_admin_denials (
    user_id BIGINT UNSIGNED NOT NULL,
    module VARCHAR(40) NOT NULL,
    PRIMARY KEY (user_id, module),
    CONSTRAINT fk_content_admin_denials_user
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
