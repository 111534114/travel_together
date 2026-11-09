-- Existing groups use a two-day cutoff. New groups store their choice in
-- app_settings under friend_group_deadline_<group_id>.
INSERT INTO app_settings (setting_key, setting_value)
VALUES ('chat_blocked_terms', '加我賴投資,保證獲利,私訊匯款,色情服務,援交,約砲,成人影片,裸聊,性交易,18禁')
ON DUPLICATE KEY UPDATE setting_value=setting_value;
