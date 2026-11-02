-- 揪團補強：先執行既有的 1019、1022、1024 揪團遷移，再執行本檔。
-- 執行前請先備份共用資料庫。本檔不會由網站自動執行。
ALTER TABLE friend_groups
    ADD COLUMN IF NOT EXISTS show_member_list TINYINT(1) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS meeting_info TEXT NULL,
    ADD COLUMN IF NOT EXISTS moderation_locked TINYINT(1) NOT NULL DEFAULT 0;

ALTER TABLE friend_group_members
    ADD COLUMN IF NOT EXISTS application_note VARCHAR(300) NULL,
    ADD COLUMN IF NOT EXISTS show_profile TINYINT(1) NOT NULL DEFAULT 0;

ALTER TABLE traveler_profiles
    ADD COLUMN IF NOT EXISTS public_intro VARCHAR(500) NULL,
    ADD COLUMN IF NOT EXISTS is_public TINYINT(1) NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS friend_group_trip_reviews (
    review_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    group_id BIGINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    rating TINYINT UNSIGNED NOT NULL,
    comment VARCHAR(1000) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_group_trip_review (group_id, user_id),
    CONSTRAINT fk_group_trip_review_group FOREIGN KEY (group_id) REFERENCES friend_groups(group_id) ON DELETE CASCADE,
    CONSTRAINT fk_group_trip_review_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CHECK (rating BETWEEN 1 AND 5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS friend_group_album_photos (
    photo_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    group_id BIGINT UNSIGNED NOT NULL,
    uploaded_by BIGINT UNSIGNED NOT NULL,
    stored_name VARCHAR(80) NOT NULL,
    caption VARCHAR(300) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_group_album (group_id, created_at),
    CONSTRAINT fk_group_album_group FOREIGN KEY (group_id) REFERENCES friend_groups(group_id) ON DELETE CASCADE,
    CONSTRAINT fk_group_album_user FOREIGN KEY (uploaded_by) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS friend_group_content_reports (
    report_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    group_id BIGINT UNSIGNED NOT NULL,
    photo_id BIGINT UNSIGNED NULL,
    reporter_id BIGINT UNSIGNED NOT NULL,
    reason VARCHAR(255) NOT NULL,
    description VARCHAR(1000) NULL,
    status ENUM('pending','resolved','rejected') NOT NULL DEFAULT 'pending',
    handled_by BIGINT UNSIGNED NULL,
    handled_at DATETIME NULL,
    handling_result VARCHAR(1000) NULL,
    action_taken ENUM('none','close_group','remove_photo') NOT NULL DEFAULT 'none',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_group_content_reports_status (status, created_at),
    CONSTRAINT fk_group_report_group FOREIGN KEY (group_id) REFERENCES friend_groups(group_id) ON DELETE CASCADE,
    CONSTRAINT fk_group_report_photo FOREIGN KEY (photo_id) REFERENCES friend_group_album_photos(photo_id) ON DELETE SET NULL,
    CONSTRAINT fk_group_report_reporter FOREIGN KEY (reporter_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_group_report_handler FOREIGN KEY (handled_by) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS friend_group_ai_drafts (
    draft_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    country_id BIGINT UNSIGNED NOT NULL,
    city_id BIGINT UNSIGNED NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    people_count INT UNSIGNED NOT NULL,
    budget DECIMAL(14,2) NOT NULL DEFAULT 0,
    user_request VARCHAR(1000) NOT NULL,
    draft_json LONGTEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    consumed_at DATETIME NULL,
    KEY idx_group_ai_drafts_user (user_id, created_at),
    CONSTRAINT fk_group_ai_drafts_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_group_ai_drafts_country FOREIGN KEY (country_id) REFERENCES countries(country_id),
    CONSTRAINT fk_group_ai_drafts_city FOREIGN KEY (city_id) REFERENCES cities(city_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
