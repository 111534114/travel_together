# 10/24 ZIP 整合：資料庫更新順序

程式碼合併到 `1025合併` 分支不會自動更新本機資料庫。已有 `travel_together` 資料庫時，先備份，確認已完成 `README_1023_整合更新.md` 所列更新，再依序執行：

1. `migrate_1024_event_chat_announcements.sql`：官方活動公告與聊天室。
2. `migrate_1024_friend_group_trip_link.sql`：揪團與對應行程的關聯。
3. `migrate_1024_trip_join_requests.sql`：旅伴申請加入行程的狀態。

這三份更新依賴先前建立的揪團與行程資料表。不要直接把 `travel_together完整資料庫.sql` 匯入已有資料的資料庫：該檔開頭會刪除並重建整個 `travel_together` 資料庫。此次僅整合 SQL 檔，未代替使用者執行資料庫更新。
