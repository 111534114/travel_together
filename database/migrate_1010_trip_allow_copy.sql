-- 行程新增「允許其他會員複製」開關，對應規格書五(二)6「複製旅遊行程」：
-- 公開行程預設允許被複製，建立者可自行關閉；建立者永遠可以複製自己的行程，不受此欄位限制。
-- 執行前請先備份資料庫；使用 IF NOT EXISTS，可安全重複執行。

ALTER TABLE trips ADD COLUMN IF NOT EXISTS allow_copy TINYINT(1) NOT NULL DEFAULT 1 AFTER visibility;

