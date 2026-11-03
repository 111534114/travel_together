-- 旅伴在行程頁「新增行程項目」手動輸入不在系統清單中的景點/餐廳/住宿時，
-- 可以勾選「送交管理員審核收錄」，這筆資料會寫進 proposals 表，用 is_catalog_submission
-- 跟旅伴之間單純討論「要不要去」的提案投票區分開：這種送審不會出現在行程的提案投票清單給旅伴看，
-- 只會出現在管理員的審核佇列，管理員核准後才會正式收錄進景點/餐廳/住宿正式資料表。
-- 可重複執行：欄位已存在時用 IF NOT EXISTS 跳過，不會報錯

ALTER TABLE proposals
    ADD COLUMN IF NOT EXISTS is_catalog_submission TINYINT(1) NOT NULL DEFAULT 0 AFTER content_review_status;
