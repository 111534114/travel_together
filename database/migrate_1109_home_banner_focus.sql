-- 首頁輪播圖：讓管理員自己選擇圖片被裁切時要顯示的位置
-- focus_x / focus_y 是 0~100 的百分比，對應 CSS object-position，預設 50 50(置中)。
-- 已經執行過 migrate_1109_home_banners.sql 的資料庫才需要執行這支；可重複執行。

ALTER TABLE home_banners
    ADD COLUMN IF NOT EXISTS focus_x TINYINT UNSIGNED NOT NULL DEFAULT 50 COMMENT '裁切顯示位置(水平 0~100%)' AFTER is_active,
    ADD COLUMN IF NOT EXISTS focus_y TINYINT UNSIGNED NOT NULL DEFAULT 50 COMMENT '裁切顯示位置(垂直 0~100%)' AFTER focus_x;
