-- 官方活動報名截止時間；NULL 代表於活動開始時截止。
ALTER TABLE friend_group_events
    ADD COLUMN IF NOT EXISTS registration_deadline DATETIME NULL AFTER end_time;
