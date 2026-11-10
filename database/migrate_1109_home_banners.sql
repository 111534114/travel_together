-- 首頁圖片跑馬燈（輪播圖）
-- 系統管理員在「首頁輪播圖」後台上傳／排序／啟用或停用圖片，首頁只顯示 is_active = 1 的圖片，依 sort_order 由小到大輪播。
-- 可重複執行：資料表已存在時會跳過。

CREATE TABLE IF NOT EXISTS home_banners (
    banner_id   INT AUTO_INCREMENT PRIMARY KEY,
    image_path  VARCHAR(255) NOT NULL COMMENT '相對於 static 的圖片路徑，例如 uploads/banners/xxx.jpg',
    title       VARCHAR(100) NULL COMMENT '顯示在圖片上的標題（可空白）',
    link_url    VARCHAR(500) NULL COMMENT '點擊圖片要前往的網址（可空白）',
    sort_order  INT NOT NULL DEFAULT 0 COMMENT '排序，數字越小越前面',
    is_active   TINYINT(1) NOT NULL DEFAULT 1 COMMENT '1 = 首頁顯示，0 = 隱藏',
    focus_x     TINYINT UNSIGNED NOT NULL DEFAULT 50 COMMENT '裁切顯示位置(水平 0~100%)',
    focus_y     TINYINT UNSIGNED NOT NULL DEFAULT 50 COMMENT '裁切顯示位置(垂直 0~100%)',
    created_by  INT NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_home_banners_active_sort (is_active, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
