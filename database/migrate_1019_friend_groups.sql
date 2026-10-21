-- 交友揪團功能：全新獨立模組，需要先申請、通過審核、參加過官方活動才能解鎖加入/發起會員揪團。
-- 執行前請先備份資料庫；全部用 IF NOT EXISTS 包起來，可安全重複執行。

-- 全站功能開關(之後也可以給其他全站設定共用)
CREATE TABLE IF NOT EXISTS app_settings (
    setting_key VARCHAR(50) PRIMARY KEY,
    setting_value VARCHAR(255) NOT NULL,
    updated_by BIGINT UNSIGNED NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_app_settings_updated_by FOREIGN KEY (updated_by) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO app_settings (setting_key, setting_value) VALUES ('friend_group_enabled', '0');

-- 申請這個功能時要填生日(年齡把關用)
ALTER TABLE users ADD COLUMN IF NOT EXISTS birthdate DATE NULL AFTER phone;

-- 旅遊人格問卷結果，每人一筆；延伸自 trip_detail.html 原本「旅伴偏好」畫面預覽的欄位語彙，
-- 差別是這份是全域、每人一份，不綁定單一行程。
CREATE TABLE IF NOT EXISTS traveler_profiles (
    profile_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL UNIQUE,
    pace ENUM('relaxed','balanced','packed') NOT NULL,
    social_style ENUM('group','small_group','solo') NOT NULL,
    budget_style ENUM('frugal','moderate','generous') NOT NULL DEFAULT 'moderate',
    like_activities VARCHAR(255),
    dislike_activities VARCHAR(255),
    diet ENUM('none','vegetarian','halal','no_beef','no_seafood','other') NOT NULL DEFAULT 'none',
    transport_pref ENUM('any','public','drive','taxi','carpool') NOT NULL DEFAULT 'any',
    walk_tolerance ENUM('low','medium','high') NOT NULL DEFAULT 'medium',
    traveler_type VARCHAR(50) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_traveler_profiles_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 功能使用申請，content_admin 審核
CREATE TABLE IF NOT EXISTS friend_group_applications (
    application_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    note VARCHAR(500),
    status ENUM('pending','approved','rejected') NOT NULL DEFAULT 'pending',
    reviewed_by BIGINT UNSIGNED NULL,
    reviewed_at DATETIME NULL,
    review_note VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_friend_group_applications_user (user_id, created_at),
    CONSTRAINT fk_fg_applications_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_fg_applications_reviewer FOREIGN KEY (reviewed_by) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 官方活動，由 content_admin 建立
CREATE TABLE IF NOT EXISTS friend_group_events (
    event_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(150) NOT NULL,
    description TEXT,
    location VARCHAR(255),
    event_date DATE NOT NULL,
    start_time TIME NULL,
    end_time TIME NULL,
    capacity INT UNSIGNED NULL,
    status ENUM('open','closed','cancelled') NOT NULL DEFAULT 'open',
    created_by BIGINT UNSIGNED NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_fg_events_creator FOREIGN KEY (created_by) REFERENCES users(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 官方活動報名/出席紀錄；status='attended' 是解鎖加入/發起會員揪團的依據
CREATE TABLE IF NOT EXISTS friend_group_event_participants (
    participant_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    event_id BIGINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    status ENUM('registered','attended','no_show','cancelled') NOT NULL DEFAULT 'registered',
    registered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    checked_in_at DATETIME NULL,
    UNIQUE KEY uq_fg_event_user (event_id, user_id),
    CONSTRAINT fk_fg_participants_event FOREIGN KEY (event_id) REFERENCES friend_group_events(event_id) ON DELETE CASCADE,
    CONSTRAINT fk_fg_participants_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 會員發起的交友揪團
CREATE TABLE IF NOT EXISTS friend_groups (
    group_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    host_user_id BIGINT UNSIGNED NOT NULL,
    title VARCHAR(150) NOT NULL,
    description TEXT,
    location VARCHAR(255),
    event_date DATE NOT NULL,
    start_time TIME NULL,
    end_time TIME NULL,
    capacity INT UNSIGNED NULL,
    pace_filter ENUM('relaxed','balanced','packed') NULL,
    social_style_filter ENUM('group','small_group','solo') NULL,
    status ENUM('open','closed','cancelled') NOT NULL DEFAULT 'open',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_friend_groups_host FOREIGN KEY (host_user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 揪團成員申請/名單(團主不存進這張表，用 friend_groups.host_user_id 判斷)
CREATE TABLE IF NOT EXISTS friend_group_members (
    member_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    group_id BIGINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    status ENUM('pending','approved','rejected','left') NOT NULL DEFAULT 'pending',
    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    responded_at DATETIME NULL,
    UNIQUE KEY uq_fg_group_user (group_id, user_id),
    CONSTRAINT fk_fg_members_group FOREIGN KEY (group_id) REFERENCES friend_groups(group_id) ON DELETE CASCADE,
    CONSTRAINT fk_fg_members_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
