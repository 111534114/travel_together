"""會員提案的「收下(核准)」與「退回」共用邏輯。

管理員按單筆按鈕、勾選後一次收下、AI 小幫手自動收下，三種情況都走這裡，確保結果一致：
收下時在景點／餐廳／住宿資料表建立一筆「待確認」資料，並把 AI 預審查到的座標、營業時間一起帶入；
收下或退回後都會通知提案的會員。

log 參數是寫操作紀錄的函式，簽名同 activity_log.log_action(cursor, action, target_type, target_id, description)；
在背景執行(沒有登入的管理員)時，呼叫端改傳自己的紀錄函式。
"""

from notification_preferences import send_notification

CATALOG_TABLES = {
    "attraction": ("attractions", "attraction_id"),
    "restaurant": ("restaurants", "restaurant_id"),
    "accommodation": ("accommodations", "accommodation_id"),
}
TYPE_LABELS = {"attraction": "景點", "restaurant": "餐廳", "accommodation": "住宿"}


def _trip_url(trip_id):
    return f"/member/trips/{trip_id}"


def _clean_suggestions(item_type, suggestions):
    """只取 AI 預審從 Google 查到、而且這個資料表有的欄位。"""
    suggestions = suggestions or {}
    fields = {}
    for key in ("latitude", "longitude"):
        try:
            value = float(suggestions.get(key))
        except (TypeError, ValueError):
            continue
        if -180 <= value <= 180:
            fields[key] = value
    hours = (suggestions.get("opening_hours") or "").strip()
    if hours and item_type in ("attraction", "restaurant"):  # 住宿沒有營業時間欄位
        fields["opening_hours"] = hours[:255]
    return fields


def load_proposal(cursor, proposal_id):
    cursor.execute(
        """
        SELECT p.proposal_id, p.trip_id, p.proposer_id, p.proposal_type, p.title, p.location, p.description,
               p.estimated_cost, p.website_url, p.linked_item_id, p.content_review_status, p.is_catalog_submission,
               t.country_id, t.city_id
        FROM proposals p JOIN trips t ON t.trip_id = p.trip_id
        WHERE p.proposal_id = %s
        """,
        (proposal_id,),
    )
    return cursor.fetchone()


def approve_proposal_record(cursor, proposal_id, reviewer_id, log, suggestions=None, require_pending=False, note=None):
    """收下一筆提案。回傳 (是否成功, 給管理員看的訊息)。呼叫端負責 commit / rollback。"""
    proposal = load_proposal(cursor, proposal_id)
    if proposal is None:
        return False, "找不到這筆提案"
    if require_pending and proposal["content_review_status"] != "pending":
        return False, f"「{proposal['title']}」已經不是待審核狀態，略過"

    created_note = ""
    catalog = CATALOG_TABLES.get(proposal["proposal_type"])
    if catalog and not proposal["linked_item_id"]:
        table, _ = catalog
        extra = _clean_suggestions(proposal["proposal_type"], suggestions)
        columns = ["name", "country_id", "city_id", "address", "description", "website_url", "status", "created_by"]
        values = [proposal["title"], proposal["country_id"], proposal["city_id"], proposal["location"],
                  proposal["description"], proposal["website_url"], "pending", reviewer_id]
        if proposal["proposal_type"] == "attraction":
            columns.append("ticket_price"); values.append(proposal["estimated_cost"] or 0)
        elif proposal["proposal_type"] == "accommodation":
            columns.append("price_per_night"); values.append(proposal["estimated_cost"] or 0)
        for key, value in extra.items():
            columns.append(key); values.append(value)
        placeholders = ",".join(["%s"] * len(values))
        cursor.execute(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})", values)
        new_item_id = cursor.lastrowid
        log(cursor, "create_from_proposal", proposal["proposal_type"], new_item_id,
            f"由提案核准建立：{proposal['title']}（提案 #{proposal_id}），狀態為待確認，請補齊分類等資訊")
        cursor.execute("UPDATE proposals SET linked_item_id = %s WHERE proposal_id = %s", (new_item_id, proposal_id))
        created_note = "，已自動建立一筆對應資料(狀態為待確認)，請記得補上分類等資訊後再啟用"

    cursor.execute(
        """
        UPDATE proposals
        SET content_review_status = 'approved', reviewed_by = %s, reviewed_at = NOW(), review_note = %s
        WHERE proposal_id = %s
        """,
        (reviewer_id, note, proposal_id),
    )
    log(cursor, "approve_proposal", "proposal", proposal_id, note or "核准提案")
    label = TYPE_LABELS.get(proposal["proposal_type"], "提案")
    send_notification(
        cursor, proposal["proposer_id"], "system", "system", "你的提案通過審核了！",
        f"你提議的{label}「{proposal['title']}」已經通過審核，收錄進網站，其他旅伴也能使用了。謝謝你的分享！",
        _trip_url(proposal["trip_id"]), proposal["trip_id"],
    )
    return True, f"提案已核准{created_note}"


def return_proposal_record(cursor, proposal_id, reviewer_id, review_note, log):
    """退回一筆提案並通知會員。回傳 (是否成功, 訊息)。呼叫端負責 commit / rollback。"""
    proposal = load_proposal(cursor, proposal_id)
    if proposal is None:
        return False, "找不到這筆提案"
    cursor.execute(
        """
        UPDATE proposals
        SET content_review_status = 'returned', reviewed_by = %s, reviewed_at = NOW(), review_note = %s
        WHERE proposal_id = %s
        """,
        (reviewer_id, review_note, proposal_id),
    )
    log(cursor, "return_proposal", "proposal", proposal_id, f"退回提案，原因：{review_note}")
    label = TYPE_LABELS.get(proposal["proposal_type"], "提案")
    send_notification(
        cursor, proposal["proposer_id"], "system", "system", "你的提案被退回了",
        f"你提議的{label}「{proposal['title']}」沒有通過審核。原因：{review_note}",
        _trip_url(proposal["trip_id"]), proposal["trip_id"],
    )
    return True, "提案已退回"
