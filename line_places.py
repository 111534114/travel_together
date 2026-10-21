"""傳位置找附近景點：使用者在 LINE 傳送「位置資訊」，從網站景點資料庫找出附近的景點，回覆可左右滑動的卡片。

- 只使用網站自己的景點資料（attractions 表，需有經緯度），不呼叫外部 API、不產生費用。
- 「加入行程」按鈕是日期選擇器（datetimepicker），只能選使用者下一趟可編輯行程期間內的日期，
  選完由 webhook 交給 handle_postback 寫入 itineraries，規則和網站 add_attraction_to_trip 一致。
"""
from datetime import date  # 匯入日期工具

from mysql.connector import Error  # 匯入 MySQL 錯誤類別

import line_flex as flex  # 匯入卡片訊息工具
from db import get_db_connection  # 匯入資料庫連線函式
from utils import google_maps_url  # 匯入 Google 地圖連結產生函式（不需金鑰、不產生費用）

RADIUS_KM = 10  # 搜尋半徑（公里）
MAX_RESULTS = 10  # 最多回幾個景點（LINE carousel 上限 12 張）
FALLBACK_RESULTS = 3  # 半徑內找不到時，改列出最近的幾個
POSTBACK_PREFIX = "addplace"  # postback data 格式：addplace:{attraction_id}:{trip_id}
DESCRIPTION_LIMIT = 60  # 卡片上的景點介紹最多顯示幾個字

# 球面距離（公里）：Haversine 公式，MySQL / MariaDB 都支援
DISTANCE_SQL = """
    6371 * 2 * ASIN(SQRT(
        POWER(SIN(RADIANS(a.latitude - %s) / 2), 2) +
        COS(RADIANS(%s)) * COS(RADIANS(a.latitude)) * POWER(SIN(RADIANS(a.longitude - %s) / 2), 2)
    ))
"""


def _distance_text(km):
    return f"{km * 1000:.0f} 公尺" if km < 1 else f"{km:.1f} 公里"


def _nearby(cursor, latitude, longitude):  # 回傳（景點清單, 是否都在半徑內）
    cursor.execute(
        f"""
        SELECT a.attraction_id, a.name, a.address, a.latitude, a.longitude, a.image_path, a.description,
               a.ticket_price, ci.name AS city, {DISTANCE_SQL} AS distance_km
        FROM attractions a
        LEFT JOIN cities ci ON ci.city_id = a.city_id
        WHERE a.status = 'active' AND a.deleted_at IS NULL
          AND a.latitude IS NOT NULL AND a.longitude IS NOT NULL
        ORDER BY distance_km
        LIMIT %s
        """,
        (latitude, latitude, longitude, MAX_RESULTS),
    )
    places = cursor.fetchall()
    within = [place for place in places if place["distance_km"] <= RADIUS_KM]
    if within:
        return within, True
    return places[:FALLBACK_RESULTS], False


def _editable_trip(cursor, line_sub):  # 使用者下一趟（或進行中）且有編輯權限的行程，沒有就回傳 None
    cursor.execute(
        """
        SELECT t.trip_id, t.trip_name, t.start_date, t.end_date FROM users u
        JOIN trip_members tm ON tm.user_id = u.user_id AND tm.join_status = 'accepted'
                            AND tm.member_role IN ('owner', 'editor')
        JOIN trips t ON t.trip_id = tm.trip_id AND t.deleted_at IS NULL AND t.status <> 'cancelled'
        WHERE u.line_sub = %s AND u.status = 'active' AND t.end_date >= %s
        ORDER BY t.start_date, t.trip_id LIMIT 1
        """,
        (line_sub, date.today()),
    )
    return cursor.fetchone()


def _add_button(place, trip):  # 日期選擇器按鈕：預設選行程第一天（進行中的行程預設今天）
    initial = max(trip["start_date"], date.today())
    return {
        "type": "button", "style": "primary", "height": "sm", "color": flex.PRIMARY,
        "action": {
            "type": "datetimepicker", "label": "加入行程", "mode": "date",
            "data": f"{POSTBACK_PREFIX}:{place['attraction_id']}:{trip['trip_id']}",
            "initial": initial.isoformat(), "min": trip["start_date"].isoformat(), "max": trip["end_date"].isoformat(),
        },
    }


def _place_bubble(place, trip):
    body = [flex.text(f"📍 距離 {_distance_text(place['distance_km'])}", size="sm", color=flex.PRIMARY, weight="bold")]
    if place["address"]:
        body.append(flex.text(place["address"], size="xs", color=flex.MUTED))
    if place["description"]:
        description = place["description"].strip()
        if len(description) > DESCRIPTION_LIMIT:
            description = description[:DESCRIPTION_LIMIT] + "…"
        body.append(flex.text(description, size="sm", color=flex.INK, margin="md"))
    if trip:
        body.append(flex.text(f"可加入：{trip['trip_name']}", size="xs", color=flex.MUTED, margin="md"))
    maps = google_maps_url(place["address"], place["latitude"], place["longitude"])
    buttons = [
        _add_button(place, trip) if trip else None,
        {"type": "button", "style": "secondary", "height": "sm", "action": {"type": "uri", "label": "Google 地圖", "uri": maps}} if maps else None,
        flex.uri_button("景點介紹", f"/member/attractions/{place['attraction_id']}", style="link"),
    ]
    image = flex.image_url(place["image_path"])
    return flex.bubble(flex.header(place["city"] or "附近景點", place["name"]), body, buttons, hero_url=image, size="kilo")


def nearby_reply(line_sub, latitude, longitude):  # 收到位置訊息時呼叫，回傳卡片（dict）或文字（str）
    connection = get_db_connection()
    if connection is None:
        return "系統暫時無法查詢，請稍後再試。"
    cursor = connection.cursor(dictionary=True)
    try:
        places, within = _nearby(cursor, latitude, longitude)
        if not places:
            return "目前網站還沒有收錄有座標的景點，之後再來看看吧！"
        trip = _editable_trip(cursor, line_sub)
    except Error as error:
        print("LINE 附近景點查詢失敗：", error)
        return "系統暫時無法查詢，請稍後再試。"
    finally:
        cursor.close()
        connection.close()
    bubbles = [_place_bubble(place, trip) for place in places]
    if within:
        alt = f"附近 {RADIUS_KM} 公里內有 {len(places)} 個景點：" + "、".join(place["name"] for place in places)
    else:
        alt = f"附近 {RADIUS_KM} 公里內沒有收錄的景點，離你最近的是：" + "、".join(place["name"] for place in places)
    card = flex.flex_message(alt, flex.carousel(bubbles))
    if within:
        return card
    return [f"附近 {RADIUS_KM} 公里內沒有收錄的景點 🙇\n以下是離你最近的景點：", card]


def parse_postback(data):  # 解析「加入行程」的 postback data，不是的回傳 None
    parts = (data or "").split(":")
    if len(parts) != 3 or parts[0] != POSTBACK_PREFIX or not (parts[1].isdigit() and parts[2].isdigit()):
        return None
    return int(parts[1]), int(parts[2])


def add_to_trip(line_sub, attraction_id, trip_id, day_text):  # 把景點加入行程的指定日期，回傳回覆文字
    try:
        day_value = date.fromisoformat(day_text or "")
    except ValueError:
        return "請選擇要加入的日期。"
    connection = get_db_connection()
    if connection is None:
        return "系統暫時無法加入行程，請稍後再試。"
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT u.user_id, t.trip_id, t.trip_name, t.start_date, t.end_date FROM users u
            JOIN trip_members tm ON tm.user_id = u.user_id AND tm.trip_id = %s AND tm.join_status = 'accepted'
                                AND tm.member_role IN ('owner', 'editor')
            JOIN trips t ON t.trip_id = tm.trip_id AND t.deleted_at IS NULL
            WHERE u.line_sub = %s AND u.status = 'active'
            """,
            (trip_id, line_sub),
        )
        trip = cursor.fetchone()
        if not trip:
            return "你沒有編輯這個行程的權限，或還沒有綁定網站帳號。"
        if not trip["start_date"] <= day_value <= trip["end_date"]:
            return f"日期必須在行程期間內（{trip['start_date']} ～ {trip['end_date']}）。"
        cursor.execute(
            "SELECT name, address, ticket_price FROM attractions WHERE attraction_id=%s AND status='active' AND deleted_at IS NULL",
            (attraction_id,),
        )
        attraction = cursor.fetchone()
        if not attraction:
            return "找不到這個景點，或已被下架。"
        cursor.execute("SELECT COALESCE(MAX(sort_order),0)+1 AS next_order FROM itineraries WHERE trip_id=%s AND itinerary_date=%s",
                       (trip_id, day_value))
        order = cursor.fetchone()["next_order"]
        cursor.execute(
            """
            INSERT INTO itineraries (trip_id, created_by, itinerary_date, item_type, title, start_time, end_time, is_all_day,
                                     address, transport_minutes, estimated_cost, attraction_id, sort_order)
            VALUES (%s, %s, %s, 'attraction', %s, NULL, NULL, 0, %s, 0, %s, %s, %s)
            """,
            (trip_id, trip["user_id"], day_value, attraction["name"][:150], attraction["address"],
             attraction["ticket_price"] or 0, attraction_id, order),
        )
        connection.commit()
    except Error as error:
        connection.rollback()
        print("LINE 加入行程失敗：", error)
        return "加入行程失敗，請稍後再試。"
    finally:
        cursor.close()
        connection.close()
    return (f"✅ 已將「{attraction['name']}」加入「{trip['trip_name']}」\n"
            f"日期：{day_value.month}/{day_value.day}\n\n可以到網站調整時間和順序。")


def handle_postback(line_sub, data, params):  # webhook 收到 postback 時呼叫；不是「加入行程」的回傳 None
    parsed = parse_postback(data)
    if parsed is None:
        return None
    return add_to_trip(line_sub, *parsed, (params or {}).get("date"))
