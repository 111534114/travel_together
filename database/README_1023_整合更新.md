# 1023 分支整合：資料庫更新順序

這次整合 10/21、10/22 的五份程式碼 ZIP。程式碼合併**不會自動更新資料庫**。先備份目前的 `travel_together` 資料庫，再依序執行下列尚未套用的更新；不要把多份完整資料庫匯出檔互相覆蓋。

1. `migrate_1021_proposal_review.sql`：提案核准後連結正式景點、餐廳或住宿資料。
2. `migrate_1021_restaurant_hotel_coords.sql`：餐廳、住宿地圖的經緯度欄位。
3. `migrate_1022_friend_group_event_items.sql`：揪團活動行程項目。
4. `migrate_1022_friend_group_onboarding.sql`：揪團新手引導完成紀錄。
5. `migrate_1022_friend_group_tiers_reviews.sql`：團長等級、多日活動與互評。
6. `migrate_1022_announcement_line_push.sql`：LINE 公告推播時間。

第 3–5 項須先有 `migrate_1019_friend_groups.sql` 所建立的交友揪團資料表。若是從較舊的資料庫開始，先按 `README_1014_整合更新.md`、`README_1021_整合更新.md` 補齊之前的更新。上述 SQL 多數使用 `IF NOT EXISTS`，仍建議先檢查現有結構及資料庫版本再執行。

本次只整合程式碼與 SQL 檔，**沒有執行資料庫更新，也沒有上傳 GitHub**。
