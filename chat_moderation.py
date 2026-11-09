"""Server-side checks shared by member and official-event chat."""

import json
import re
import unicodedata


SETTING_KEY = "chat_blocked_terms"
REMOVED_CHAT_CONTENT = "[訊息已由團長移除]"


def parse_terms(value):
    return list(dict.fromkeys(term.strip() for term in re.split(r"[,，\n]+", value or "") if term.strip()))


def normalized_text(value):
    return "".join(char for char in unicodedata.normalize("NFKC", value).casefold() if char.isalnum())


def blocked_term(cursor, content):
    cursor.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", (SETTING_KEY,))
    row = cursor.fetchone()
    text = normalized_text(content)
    for term in parse_terms(row["setting_value"] if row else ""):
        needle = normalized_text(term)
        if needle and needle in text:
            return term
    return None


def remove_trip_message(cursor, trip_id, message_id, moderator_id):
    cursor.execute("SELECT content FROM trip_chat_messages WHERE trip_id=%s AND message_id=%s FOR UPDATE",
                   (trip_id, message_id))
    row = cursor.fetchone()
    if not row or row["content"] == REMOVED_CHAT_CONTENT:
        return False
    cursor.execute("""INSERT INTO edit_logs (trip_id,user_id,target_table,target_id,action,before_data,after_data)
                      VALUES (%s,%s,'trip_chat_messages',%s,'delete',%s,%s)""",
                   (trip_id, moderator_id, message_id,
                    json.dumps({"content": row["content"]}, ensure_ascii=False),
                    json.dumps({"content": REMOVED_CHAT_CONTENT}, ensure_ascii=False)))
    cursor.execute("UPDATE trip_chat_messages SET content=%s WHERE trip_id=%s AND message_id=%s",
                   (REMOVED_CHAT_CONTENT, trip_id, message_id))
    return True
