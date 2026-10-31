# 10/29 合併：通知設定與旅伴偏好

這份分支保留既有的 `trip_preferences` 資料表及其中資料，不另建壓縮檔中的 `trip_member_preferences` 重複表。

已有資料庫時，先備份，再確認：

1. 旅伴偏好沿用 `migrate_1028_trip_preferences.sql`；若先前已執行，不必再執行。
2. 新的通知設定需執行 `migrate_1029_notification_preferences.sql`。

若第 2 項尚未執行，既有通知仍照常發送，但個人資料頁的通知設定暫時無法儲存。
旅伴偏好現在會預填會員的旅遊人格問卷、驗證表單，並只統計仍在行程中的成員。
