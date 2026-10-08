# 10/08 四份壓縮檔整合

整合分支：`1009合併`。整合基準：`e6e9fb0`。

| 來源壓縮檔 | 保留的更新 |
| --- | --- |
| travel_together-111534119_20261008.zip | 全天／開始／結束時間模式、行程類型中文標示、交通時間統計、樂園營業時間查詢 |
| travel_together-1008-.zip | 交通住宿搜尋驗證、單程／來回、預算與票種篩選、會員收藏、景點預覽 |
| travel_together--10.08.zip | 投票理由與取消投票、已加入成員可提案／投票／留言／新增費用 |
| travel_together-10-8.zip | 聊天室、已讀狀態、投票進度與提醒、收據明細與自選分攤成員 |

## 重疊修改的整合方式

- 每日行程保留既有景點詳細資料，並同時加入時間模式、樂園查詢與景點預覽。
- 投票理由與投票者清單同時載入；頁面與聊天室的投票進度均包含所有已加入成員。
- 新增費用表單與後端保持相同權限；保留收據明細與指定分攤成員功能。
- 樂園服務暫時失敗時，舊快取仍先篩選指定日期，維持前端預期的回傳格式。
- 原有管理員問題回報測試改用目前後端的字典資料格式；管理員處理流程未修改。

## 資料庫更新

既有資料庫需先備份，再依序執行：

1. `database/migrate_1008_itinerary_enhancements.sql`
2. `database/migrate_1008_vote_reason.sql`
3. `database/migrate_1008_booking_favorites.sql`
4. `database/migrate_1008_expense_invoice.sql`
5. `database/migrate_1008_trip_chat.sql`

前兩份含新增欄位，執行前須檢查 `itineraries.is_all_day` 與 `vote_records.reason` 是否已存在，不能直接重複執行。完整資料庫 SQL 已包含 `reason`，以該檔建立資料庫時應略過第二份。

本次已在使用者同意後備份並更新本機資料庫，原有 29 張資料表筆數維持不變。`database/backup_*.sql` 已由 `.gitignore` 排除，不會加入提交。

## 驗證

- `python -m unittest discover -s tests -v`：15 項通過。
- Python 編譯、全部 Jinja 樣板編譯、新增 JavaScript 語法檢查通過。
- 使用本機現有資料測試登入、註冊、訪客與交通住宿搜尋頁，以及 5 筆既有行程的詳細頁、聊天室查詢和收藏頁，均回傳 HTTP 200。
- 以上頁面檢查替代了外部天氣查詢；未向外部 LINE、Google 或樂園 API 執行登入／授權／查詢測試。
- Google／LINE 登入設定沿用目前分支，未匯入或覆蓋 `.env`。
