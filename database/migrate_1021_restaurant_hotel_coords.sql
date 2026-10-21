-- 幫餐廳、住宿補上經緯度欄位，讓這兩個模組也能像景點管理一樣提供地圖檢視
-- 可重複執行：欄位已存在時用 IF NOT EXISTS 跳過，不會報錯

ALTER TABLE restaurants
    ADD COLUMN IF NOT EXISTS latitude DECIMAL(10,7) NULL AFTER address,
    ADD COLUMN IF NOT EXISTS longitude DECIMAL(10,7) NULL AFTER latitude;

ALTER TABLE accommodations
    ADD COLUMN IF NOT EXISTS latitude DECIMAL(10,7) NULL AFTER address,
    ADD COLUMN IF NOT EXISTS longitude DECIMAL(10,7) NULL AFTER latitude;
