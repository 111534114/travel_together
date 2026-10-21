# 1021 分支整合：資料庫更新

本次整合四份 10/19 程式碼 ZIP，新增 LINE 互動與 LIFF、交友揪團、公開行程審核、行程變更提案、留言檢舉與忘記密碼。程式碼合併**不會自動更新既有資料庫**。

若目前資料庫已具備 10/14 版本的結構，請先備份，再依序執行：

1. `migrate_1019_friend_groups.sql`
2. `migrate_1019_trip_moderation.sql`
3. `migrate_1019_itinerary_change_proposals.sql`
4. `migrate_1019_proposal_cancelled.sql`
5. `migrate_1019_password_resets.sql`

其中 `migrate_1019_itinerary_change_proposals.sql` 的新增欄位與外鍵不是可重複執行的操作；若已套用過，不要再執行一次。全新安裝可先建立空的 `travel_together` 資料庫並匯入 `travel_together1014Yuan.sql`，再執行上述五份更新。請勿把完整資料庫匯出檔直接匯入已有資料的資料庫，以免資料衝突。

若使用 `travel_together完整資料庫.sql` 作為起點，該檔已包含交友揪團及公開行程審核的資料表／欄位，仍需確認並套用其餘三份更新；不要將多份完整資料庫匯出檔混合匯入。
