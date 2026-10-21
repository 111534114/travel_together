-- 把「會員旅遊內容提案審核」功能真正接上：
-- 會員提議景點/餐廳/住宿類型的提案時，改成需要 content_admin 審核；
-- 審核核准後，系統會自動在對應的正式資料表建立一筆資料(狀態為待確認，仍需人工補齊分類等欄位)。
-- 用 linked_item_id 記錄核准後建立的那筆資料 ID(景點/餐廳/住宿三選一，不設外鍵，依 proposal_type 判斷要查哪張表)，
-- 避免同一筆提案被重複核准時又建立第二筆重複資料。
-- 可重複執行：欄位已存在時用 IF NOT EXISTS 跳過，不會報錯

ALTER TABLE proposals
    ADD COLUMN IF NOT EXISTS linked_item_id BIGINT UNSIGNED NULL AFTER review_note;
