-- 行程內「旅伴偏好」：每位成員在每趟行程各一筆，用來統計團體偏好。
-- 跟 traveler_profiles（交友揪團的全域旅遊人格問卷）不同，這份綁定單一行程；
-- 成員第一次打開表單時會先帶入問卷裡的活動、飲食、交通、步行偏好當預設值。
CREATE TABLE IF NOT EXISTS trip_member_preferences (
    trip_id BIGINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    like_activities VARCHAR(255),
    dislike_activities VARCHAR(255),
    must_visit TEXT,
    avoid_places TEXT,
    budget_limit DECIMAL(12,2),
    diet ENUM('none','vegetarian','halal','no_beef','no_seafood','other') NOT NULL DEFAULT 'none',
    transport_pref ENUM('any','public','drive','taxi','carpool') NOT NULL DEFAULT 'any',
    walk_tolerance ENUM('low','medium','high') NOT NULL DEFAULT 'medium',
    intensity ENUM('relaxed','standard','packed','family','senior_friendly'),
    special_needs VARCHAR(500),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (trip_id, user_id),
    FOREIGN KEY (trip_id) REFERENCES trips(trip_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
