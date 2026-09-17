-- 為城市加上「地區」分類(例如台灣的北部/中部/南部/東部/離島，日本的關東/關西等)，
-- 方便景點/餐廳/住宿表單的城市下拉選單分組顯示，城市一多也能一目了然。
-- 執行前請先備份資料庫；此 migration 僅需執行一次。

ALTER TABLE cities ADD COLUMN region VARCHAR(50) NULL AFTER name;
