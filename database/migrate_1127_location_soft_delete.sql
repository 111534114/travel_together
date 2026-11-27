-- 國家/城市管理加上軟刪除(回收桶)：原本刪除是直接 DELETE，刪錯沒有救回的路；
-- 改成跟景點/餐廳/住宿一樣，先標記 deleted_at，可以從回收桶復原，確定不要了才永久刪除。
-- 欄位新增用 IF NOT EXISTS，可重複執行。

ALTER TABLE countries
    ADD COLUMN IF NOT EXISTS deleted_at DATETIME NULL DEFAULT NULL AFTER name;

ALTER TABLE cities
    ADD COLUMN IF NOT EXISTS deleted_at DATETIME NULL DEFAULT NULL AFTER region;
