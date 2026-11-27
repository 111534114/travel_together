-- 允許系統管理員儲存較長的聊天室敏感詞清單；原有設定值會保留。
-- 執行前請先備份資料庫。
ALTER TABLE app_settings MODIFY COLUMN setting_value LONGTEXT NOT NULL;
