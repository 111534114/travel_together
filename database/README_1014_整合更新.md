# 1014 分支整合：資料庫更新順序

既有的 `travel_together` 資料庫請先備份，再依下列順序執行：

1. `migrate_1011_attraction_posts.sql`
2. `migrate_1012_attraction_post_images.sql`
3. `migrate_1013_attraction_post_review.sql`
4. `migrate_1012_content_admin_permissions.sql`
5. `migrate_1012_flight_stops.sql`
6. `migrate_1012_line_notification_logs.sql`

這些更新分別加入景點相簿與審核、內容管理員細部權限、航班直飛／轉機篩選，以及 LINE 行程提醒紀錄。已執行過的環境可以再次執行；腳本會保留既有資料。

本機在整合時的備份檔名為 `backup_before_merge_1014_20261014.sql`，備份檔含帳號資料且已被 `.gitignore` 排除，不應上傳 GitHub。
