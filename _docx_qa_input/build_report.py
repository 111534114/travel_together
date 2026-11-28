import json
import re
from collections import defaultdict
from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


ROOT = Path(r"C:\Users\WH\Desktop\travel_together")
SOURCE = Path(r"C:\Users\WH\Downloads\581480981.docx")
OUT = ROOT / "deliverables" / "走吧揪團_期中進度審查申請表.docx"
SCHEMA = json.loads((ROOT / "_docx_qa_input" / "schema.json").read_text(encoding="utf-8"))


def set_text(paragraph, value):
    if paragraph.runs:
        paragraph.runs[0].text = value
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.add_run(value)


def cell_text(cell, value, size=None, bold=False):
    cell.text = value
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    for p in cell.paragraphs:
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.space_before = Pt(0)
        for run in p.runs:
            run.font.name = "Microsoft JhengHei"
            run._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft JhengHei")
            if size:
                run.font.size = Pt(size)
            run.bold = bold


def shade(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def no_split(row):
    tr_pr = row._tr.get_or_add_trPr()
    tr_pr.append(OxmlElement("w:cantSplit"))


def repeat_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    e = OxmlElement("w:tblHeader")
    e.set(qn("w:val"), "true")
    tr_pr.append(e)


def insert_para_after(doc, anchor, value, size=9, bold=False):
    from docx.text.paragraph import Paragraph
    p = OxmlElement("w:p")
    anchor.addnext(p)
    paragraph = Paragraph(p, doc._body)
    paragraph.style = "Normal"
    paragraph.paragraph_format.space_before = Pt(4)
    paragraph.paragraph_format.space_after = Pt(4)
    run = paragraph.add_run(value)
    run.font.name = "Microsoft JhengHei"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft JhengHei")
    run.font.size = Pt(size)
    run.bold = bold
    return p


def make_table_after(doc, anchor, headers, widths, rows, size=8, header_fill="DDECF0"):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.autofit = False
    for i, width in enumerate(widths):
        table.columns[i].width = Cm(width)
        table.rows[0].cells[i].width = Cm(width)
        cell_text(table.rows[0].cells[i], headers[i], size, True)
        shade(table.rows[0].cells[i], header_fill)
    repeat_header(table.rows[0])
    no_split(table.rows[0])
    for values in rows:
        row = table.add_row()
        no_split(row)
        for i, value in enumerate(values):
            row.cells[i].width = Cm(widths[i])
            cell_text(row.cells[i], str(value), size)
    anchor.addnext(table._tbl)
    return table._tbl


groups = [
    ("一、帳號、基礎資料與通知", [
        "users", "countries", "cities", "categories", "app_settings", "password_resets",
        "notification_preferences", "notifications", "line_notification_logs", "home_banners",
        "announcements", "content_admin_denials",
    ]),
    ("二、景點、餐宿、交通與收藏", [
        "attractions", "restaurants", "accommodations", "attraction_posts", "attraction_post_images",
        "favorites", "flights", "trains", "booking_favorites", "booking_live_favorites",
    ]),
    ("三、旅程協作、投票與記帳", [
        "trips", "trip_members", "itineraries", "trip_preferences", "trip_invitations", "comments",
        "votes", "vote_options", "vote_records", "proposals", "attachments", "expenses",
        "expense_items", "expense_splits", "edit_logs", "trip_chat_messages", "trip_chat_reads",
    ]),
    ("四、交友揪團與官方活動", [
        "friend_groups", "friend_group_members", "friend_group_applications", "friend_group_onboarding",
        "friend_group_events", "friend_group_event_items", "friend_group_event_participants",
        "friend_group_event_chat_messages", "friend_group_event_announcements", "friend_group_reviews",
        "friend_group_trip_reviews", "friend_group_album_photos", "friend_group_content_reports",
        "friend_group_ai_drafts", "traveler_profiles",
    ]),
    ("五、管理紀錄與資料庫檢視表", [
        "reports", "admin_logs", "user_moderation_history", "trip_moderation_history",
        "vw_popular_attractions", "vw_trip_expense_summary",
    ]),
]

purpose = {
    "users": "會員帳號、身分與登入資料", "countries": "國家清單", "cities": "城市與所屬國家",
    "categories": "景點、餐廳、住宿分類", "app_settings": "網站設定值", "password_resets": "密碼重設紀錄",
    "notification_preferences": "通知偏好", "notifications": "站內通知", "line_notification_logs": "LINE 通知紀錄",
    "home_banners": "首頁輪播圖", "announcements": "公告", "content_admin_denials": "內容管理權限限制",
    "attractions": "景點資料", "restaurants": "餐廳資料", "accommodations": "住宿資料",
    "attraction_posts": "會員景點貼文", "attraction_post_images": "景點貼文圖片", "favorites": "會員收藏",
    "flights": "航班資料", "trains": "鐵路班次資料", "booking_favorites": "預訂項目收藏",
    "booking_live_favorites": "即時查詢收藏快照", "trips": "旅程主檔", "trip_members": "旅程成員與權限",
    "itineraries": "每日行程項目", "trip_preferences": "旅程偏好", "trip_invitations": "旅程邀請",
    "comments": "留言", "votes": "投票主檔", "vote_options": "投票選項", "vote_records": "投票紀錄",
    "proposals": "行程提案", "attachments": "附件", "expenses": "旅程支出",
    "expense_items": "支出明細", "expense_splits": "分帳資料", "edit_logs": "編輯歷程",
    "trip_chat_messages": "旅程聊天室訊息", "trip_chat_reads": "聊天室已讀紀錄",
    "friend_groups": "會員揪團主檔", "friend_group_members": "揪團成員與申請",
    "friend_group_applications": "揪團資格審核申請", "friend_group_onboarding": "新手開團引導",
    "friend_group_events": "官方活動", "friend_group_event_items": "官方活動行程",
    "friend_group_event_participants": "官方活動報名與報到",
    "friend_group_event_chat_messages": "官方活動聊天室",
    "friend_group_event_announcements": "官方活動公告", "friend_group_reviews": "團員互評",
    "friend_group_trip_reviews": "揪團行程評價", "friend_group_album_photos": "揪團共享相簿",
    "friend_group_content_reports": "揪團內容檢舉", "friend_group_ai_drafts": "智慧規劃草稿",
    "traveler_profiles": "旅遊人格與偏好", "reports": "內容檢舉與問題回報",
    "admin_logs": "後台操作紀錄", "user_moderation_history": "會員停權歷程",
    "trip_moderation_history": "公開行程審核歷程", "vw_popular_attractions": "熱門景點統計檢視",
    "vw_trip_expense_summary": "旅程支出彙總檢視",
}


# The example is a field-level dictionary. Labels below are editorial descriptions;
# SQL types, keys, and relationships always come from the schema export.
field_overrides = {
    "username": "登入帳號", "password_hash": "密碼雜湊值", "full_name": "姓名",
    "nickname": "暱稱", "birthdate": "出生日期", "google_sub": "Google 帳號識別碼",
    "line_sub": "LINE 帳號識別碼", "line_friend": "是否為 LINE 好友",
    "avatar_path": "頭像檔案路徑", "ip_address": "IP 位址",
    "last_login_at": "最後登入時間", "last_seen_at": "最後上線時間",
    "is_active": "是否啟用", "is_public": "是否公開", "is_read": "是否已讀",
    "is_all_day": "是否全天", "is_pinned": "是否置頂", "is_popular": "是否熱門",
    "is_catalog_submission": "是否送審為正式資料",
    "allow_change": "是否允許變更", "allow_copy": "是否允許複製",
    "show_member_list": "是否顯示成員名單", "show_profile": "是否顯示個人檔案",
    "share_token": "分享權杖", "invite_token": "邀請權杖", "invite_code": "邀請代碼",
    "cover_image_path": "封面圖片路徑", "receipt_path": "收據檔案路徑",
    "registration_deadline": "報名截止時間", "content_review_status": "內容審核狀態",
    "moderation_locked": "是否鎖定審核", "moderation_status": "審核狀態",
    "review_status": "審查狀態", "review_note": "審查備註",
    "approval_choice": "審核決定", "handling_result": "處理結果",
    "settlement_status": "結算狀態", "join_status": "加入狀態",
    "actual_expense": "實際支出", "estimated_cost": "預估費用",
    "remaining_budget": "剩餘預算", "budget_limit": "預算上限",
    "price_per_night": "每晚價格", "ticket_price": "票價",
    "seats_available": "剩餘座位數", "people_count": "人數",
    "trip_name": "旅程名稱", "opening_hours": "營業時間",
    "meeting_info": "集合資訊", "public_intro": "公開自我介紹",
    "user_request": "使用者需求", "draft_json": "規劃草稿資料",
    "focus_x": "圖片焦點 X 座標", "focus_y": "圖片焦點 Y 座標",
    "latitude": "緯度", "longitude": "經度",
    "from_status": "原狀態", "to_status": "新狀態",
    "before_data": "異動前資料", "after_data": "異動後資料",
    "last_read_message_id": "最後已讀訊息編號",
    "country": "國家名稱", "city": "城市名稱", "region": "地區",
    "origin_station": "出發車站", "destination_station": "抵達車站",
    "origin_country_id": "出發國家編號", "origin_city_id": "出發城市編號",
    "destination_country_id": "目的地國家編號", "destination_city_id": "目的地城市編號",
    "check_in_time": "入住時間", "check_out_time": "退房時間",
    "checked_in_at": "報到時間", "arrival_time": "抵達時間",
    "departure_time": "出發時間", "line_pushed_at": "LINE 推播時間",
    "ai_verified_at": "AI 驗證時間", "ai_verified_by": "AI 驗證者編號",
    "website_url": "網站網址", "link_url": "連結網址",
    "file_name": "原始檔名", "stored_name": "儲存檔名",
    "file_path": "檔案路徑", "file_size": "檔案大小",
    "file_type": "檔案類型", "image_path": "圖片路徑",
    "payment_status": "付款狀態", "car_class": "車廂等級",
    "cabin_class": "艙等", "airline_name": "航空公司名稱",
    "flight_number": "航班編號", "train_number": "車次編號",
    "train_type": "列車類型", "transport_method": "交通方式",
    "transport_minutes": "交通時間（分鐘）", "transport_pref": "交通偏好",
    "walk_tolerance": "步行可接受程度", "special_needs": "特殊需求",
    "like_activities": "偏好活動", "dislike_activities": "不喜歡的活動",
    "avoid_places": "避開地點", "must_visit": "必訪地點",
    "social_style": "社交風格", "social_style_filter": "社交風格篩選",
    "budget_style": "預算風格", "pace_filter": "步調篩選",
    "price_level": "價格等級", "cuisine_type": "料理類型",
    "favorite_count": "收藏數", "itinerary_count": "行程數",
    "split_amount": "分攤金額", "sort_order": "排序順序",
    "suggested_duration_minutes": "建議停留時間（分鐘）",
}

word_zh = {
    "accommodation": "住宿", "action": "操作", "active": "啟用", "activities": "活動", "actual": "實際",
    "address": "地址", "admin": "管理員", "after": "異動後", "ai": "AI", "airline": "航空公司",
    "all": "全部", "allow": "允許", "amount": "金額", "announcement": "公告", "application": "申請",
    "applied": "申請", "approval": "審核", "arrival": "抵達", "assigned": "指定", "at": "時間",
    "attachment": "附件", "attraction": "景點", "available": "可用", "avatar": "頭像", "avoid": "避開",
    "banner": "輪播圖", "before": "異動前", "birthdate": "出生日期", "budget": "預算", "by": "者",
    "cabin": "艙等", "capacity": "容量", "caption": "圖片說明", "car": "車廂", "catalog": "正式資料",
    "category": "分類", "change": "變更", "check": "檢查", "checked": "已檢查", "choice": "選擇",
    "city": "城市", "class": "等級", "code": "代碼", "comment": "留言", "completed": "完成",
    "consumed": "使用", "content": "內容", "copy": "複製", "cost": "費用", "count": "數量",
    "country": "國家", "cover": "封面", "created": "建立", "cuisine": "料理", "currency": "幣別",
    "data": "資料", "date": "日期", "day": "每日", "deadline": "截止", "deleted": "刪除",
    "departure": "出發", "description": "描述", "destination": "目的地", "diet": "飲食偏好",
    "dislike": "不喜歡", "draft": "草稿", "duration": "時長", "edit": "編輯", "email": "電子郵件",
    "enabled": "是否啟用", "end": "結束", "estimated": "預估", "event": "活動", "expense": "支出",
    "expires": "到期", "favorite": "收藏", "file": "檔案", "filter": "篩選", "flight": "航班",
    "focus": "焦點", "friend": "交友", "from": "原", "full": "完整", "google": "Google",
    "group": "揪團", "handled": "處理", "handling": "處理", "hash": "雜湊值", "host": "主揪",
    "hours": "時段", "id": "編號", "image": "圖片", "in": "進入", "info": "資訊",
    "intensity": "強度", "intro": "簡介", "introduction": "自我介紹", "invitation": "邀請",
    "invite": "邀請", "invitee": "受邀者", "inviter": "邀請者", "ip": "IP", "is": "是否",
    "item": "項目", "itinerary": "行程", "join": "加入", "joined": "加入", "json": "JSON",
    "key": "鍵值", "kind": "種類", "last": "最後", "latitude": "緯度", "level": "等級",
    "like": "喜歡", "limit": "上限", "line": "LINE", "link": "連結", "linked": "關聯",
    "list": "名單", "location": "地點", "locked": "鎖定", "log": "紀錄", "login": "登入",
    "longitude": "經度", "meeting": "集合", "member": "成員", "message": "訊息", "method": "方式",
    "minutes": "分鐘", "moderation": "審核", "module": "模組", "must": "必須", "name": "名稱",
    "needs": "需求", "nickname": "暱稱", "night": "每晚", "note": "備註", "notes": "備註",
    "notification": "通知", "notify": "通知", "number": "編號", "opening": "營業", "option": "選項",
    "order": "順序", "origin": "出發地", "out": "離開", "owner": "擁有者", "pace": "步調",
    "paid": "付款", "parent": "上層", "participant": "參加者", "password": "密碼", "path": "路徑",
    "payer": "付款人", "people": "人數", "per": "每", "phone": "電話", "photo": "照片",
    "pinned": "置頂", "places": "地點", "popular": "熱門", "post": "貼文", "posted": "發布",
    "pref": "偏好", "preference": "偏好", "price": "價格", "profile": "個人檔案",
    "proposal": "提案", "proposed": "提議", "proposer": "提案人", "public": "公開",
    "publish": "發布", "pushed": "推播", "rating": "評分", "read": "已讀", "reason": "原因",
    "receipt": "收據", "record": "紀錄", "region": "地區", "registered": "報名",
    "registration": "報名", "remaining": "剩餘", "report": "檢舉", "reporter": "檢舉人",
    "request": "需求", "reset": "重設", "responded": "回覆", "restaurant": "餐廳",
    "result": "結果", "review": "評價", "reviewed": "審核", "reviewee": "受評者",
    "reviewer": "評價者", "role": "角色", "scope": "範圍", "seats": "座位",
    "seen": "查看", "sent": "寄送", "setting": "設定", "settlement": "結算",
    "share": "分享", "show": "顯示", "size": "大小", "social": "社交", "sort": "排序",
    "special": "特殊", "split": "分帳", "start": "開始", "station": "車站", "status": "狀態",
    "stops": "經停", "stored": "儲存", "style": "風格", "sub": "識別碼",
    "submission": "送審", "subtitle": "副標題", "suggested": "建議", "table": "資料表",
    "tags": "標籤", "taken": "採取", "target": "目標", "text": "文字", "ticket": "票券",
    "time": "時間", "title": "標題", "to": "新", "token": "權杖", "tolerance": "容忍度",
    "total": "總計", "train": "列車", "transport": "交通", "traveler": "旅人",
    "trip": "旅程", "type": "類型", "updated": "更新", "uploaded": "上傳", "url": "網址",
    "used": "使用", "user": "會員", "username": "帳號", "value": "值", "verified": "驗證",
    "visibility": "可見範圍", "visit": "到訪", "vote": "投票", "voted": "已投票",
    "walk": "步行", "website": "網站", "x": "X", "y": "Y",
}


def field_label(name):
    if name in field_overrides:
        return field_overrides[name]
    parts = name.split("_")
    missing = [part for part in parts if part not in word_zh]
    if missing:
        raise ValueError(f"Missing translation for {name}: {missing}")
    return "".join(word_zh[part] for part in parts)


def type_and_length(raw):
    match = re.match(r"([a-z]+)(?:\(([^)]*)\))?(.*)", raw, re.I)
    if not match:
        return raw, "—"
    base, length, suffix = match.groups()
    if base.lower() == "enum":
        return "enum", "—"
    return (base + suffix).strip(), length or "—"


def sample_value(name, raw_type):
    lower = raw_type.lower()
    if name in {"password_hash", "token", "invite_token", "share_token", "google_sub", "line_sub"}:
        return "（遮蔽）"
    if name == "email" or name == "invitee_email":
        return "demo@example.com"
    if name == "phone":
        return "0900-000-000"
    if name == "ip_address":
        return "192.0.2.1"
    if "url" in name or name == "link":
        return "https://example.com"
    if "path" in name or name == "stored_name":
        return "sample.jpg"
    if name == "file_name":
        return "sample.jpg"
    if name == "latitude":
        return "25.0330"
    if name == "longitude":
        return "121.5654"
    if name == "birthdate":
        return "2000-01-01"
    if name == "username":
        return "demo_user"
    if name == "full_name":
        return "王小明"
    if name in {"country", "name"} and "varchar" in lower:
        return "示例名稱"
    if name == "city":
        return "台北市"
    if name == "address":
        return "示例地址"
    if name == "currency":
        return "TWD"
    if name == "file_size":
        return "1024"
    if lower.startswith("enum("):
        values = re.findall(r"'([^']*)'", raw_type)
        return values[0] if values else "示例值"
    if "datetime" in lower or "timestamp" in lower:
        return "2026-11-21 10:00"
    if lower.startswith("date"):
        return "2026-11-21"
    if lower.startswith("time"):
        return "10:00"
    if lower.startswith("json"):
        return '{"sample":1}'
    if "decimal" in lower or "double" in lower or "float" in lower:
        return "100.00"
    if any(lower.startswith(prefix) for prefix in ("int", "bigint", "smallint", "tinyint")):
        return "1"
    match = re.search(r"(?:var)?char\((\d+)\)", lower)
    if match and int(match.group(1)) == 1:
        return "A"
    return "示例文字"


def main():
    doc = Document(SOURCE)
    paras = list(doc.paragraphs)
    tables = list(doc.tables)
    set_text(paras[5], "115級畢業班專題製作")
    set_text(paras[10], "專題題目：走吧揪團 AI多人協作旅遊規劃系統")
    set_text(paras[20], "中華民國115年11月21日")
    students = [
        ("111534114", "吳若瑄"), ("111534119", "游蕓安"),
        ("111534122", "吳安婷"), ("111534129", "楊雅鈞"),
    ]
    for i, (student_id, name) in enumerate(students):
        cell_text(tables[0].rows[i].cells[1], student_id, 13)
        cell_text(tables[0].rows[i].cells[2], name, 13)
    cell_text(tables[0].rows[7].cells[1], "周建羽　老師", 13)

    # Keep the template synopsis, correcting the external-service wording and
    # adding enough verified implementation detail to pass the 600-character requirement.
    for idx in (25, 26, 27):
        original = paras[idx].text
        original = original.replace("即時報價", "查詢結果").replace("真實價格", "參考價格")
        set_text(paras[idx], original)
    addendum = (
        "系統以 Flask 的藍圖分離訪客、會員與管理後台，MySQL 保存帳號、旅程、投票、揪團及審核紀錄；"
        "頁面依使用者角色檢查權限。會員可先完成揪團資格申請，再報名並實際出席官方活動，"
        "取得參加其他會員揪團的資格；主揪管理成員與行程，團員依授權查看或共同編輯。"
        "第三方交通、地圖與 AI 服務需要有效金鑰及連線，查詢價格與規劃內容僅供參考。"
    )
    set_text(paras[27], paras[27].text + addendum)

    set_text(paras[31], "（截至115年11月21日；「已完成」指程式已實作，「進行中」指整合或實際環境測試。）")
    progress = [
        (tables[3].rows[1], "訪客",
         "\n".join([
             "1. 瀏覽首頁、公開行程及景點／餐廳／住宿資料（已完成）",
             "2. 帳號註冊、帳密登入與忘記密碼（已完成）",
             "3. Google、LINE 第三方登入（程式已完成）",
             "4. 機票、高鐵／台鐵及住宿搜尋（程式已完成）",
             "5. 忘記密碼郵件跨電腦收信測試（進行中）",
             "6. 第三方登入回呼及交通住宿即時資料測試（進行中）",
         ]),
         "\n".join([
             "1. 未登入也能查看網站介紹、公開旅程和景點餐宿詳情；收藏與加入行程須登入。",
             "2. 使用電子郵件或帳號建立會員並登入；忘記密碼可申請重設連結，寄信需正確設定 SMTP。",
             "3. 提供 Google 與 LINE 帳號登入入口；不同電腦與正式網址的回呼設定仍要逐一測試。",
             "4. 輸入地點、日期與人數查詢交通及住宿；班次、供應量與價格依外部服務回傳，不能視為已訂位。",
             "5. 確認 SMTP 設定後，從另一台電腦申請重設密碼，檢查郵件是否送達及連結是否有效。",
             "6. 使用正式網址測 Google／LINE 回呼，並核對外部服務回傳的搜尋結果。",
         ])),
        (tables[3].rows[2], "會員",
         "\n".join([
             "1. 搜尋、收藏景點／餐廳／住宿並加入行程（已完成）",
             "2. 建立、編輯旅程及邀請旅伴共同規劃（已完成）",
             "3. 投票及旅程聊天室（已完成）",
             "4. 記帳、自動分帳與費用明細（已完成）",
             "5. 交友揪團資格申請、官方活動報名與報到（已完成）",
             "6. 發起／搜尋／申請加入揪團與管理名額（已完成）",
             "7. 團員查看／共同編輯權限、名單隱私及到場紀錄（已完成）",
             "8. 旅遊相簿、團員互評與行程心得（已完成）",
             "9. 智慧規劃行程、費用影像辨識（程式已完成）",
             "10. AI 規劃與影像辨識實際服務測試（進行中）",
             "11. 多帳號揪團及成員權限完整流程測試（進行中）",
         ]),
         "\n".join([
             "1. 依國家、城市或關鍵字找景點餐宿；收藏後可在個人頁查看，並將資料加入旅程。",
             "2. 建立日期與目的地，邀請成員；主揪可設定成員僅查看或共同編輯。",
             "3. 團員可建立提案與投票、在聊天室討論與回覆訊息；投票結果供主揪決策。",
             "4. 登錄支出與付款者，依團員分攤金額並顯示各自應收、應付。",
             "5. 先送交揪團資格審核，再報名官方活動；需實際出席活動才解鎖會員揪團。",
             "6. 主揪設定行程、日期、名額與招募說明；其他會員查看詳情並提出申請，由主揪審核。",
             "7. 主揪管理成員權限與到場狀態；可控制加入前是否公開參加者名單。",
             "8. 上傳並展示旅行照片；旅後可給團員評價，並分享行程心得與相簿。",
             "9. 依目的地、日期、預算產生行程草稿，確認後再儲存；AI 與辨識功能需要有效金鑰。",
             "10. 以有效金鑰確認草稿與辨識結果能正常產生、顯示並儲存。",
             "11. 分別用主揪及參加者帳號測試資格、申請、核准、退出、查看與共同編輯權限。",
         ])),
        (tables[4].rows[0], "旅遊內容管理員",
         "\n".join([
             "1. 景點／餐廳／住宿新增、編輯、下架及圖片上傳（已完成）",
             "2. CSV 批次匯入與 Google 地圖資料搜尋匯入（程式已完成）",
             "3. 國家、城市資料管理與匯入（已完成）",
             "4. 景點／餐廳／住宿分類管理（已完成）",
             "5. 會員新增或修改資料提案審核（已完成）",
             "6. 會員景點相簿照片審核（已完成）",
             "7. 揪團資格審核與官方活動管理（已完成）",
             "8. AI 資料驗證、補齊與管理助理（程式已完成）",
             "9. Google 地圖匯入與 AI 資料維護實測（進行中）",
         ]),
         "\n".join([
             "1. 維護景點餐宿的名稱、地址、分類等內容，並上傳單張或批次照片。",
             "2. 依 CSV 範本匯入多筆資料；Google 地圖搜尋可帶入地址等候選資訊，確認後才儲存。",
             "3. 可新增、編輯國家與城市，並使用內建或外部資料來源匯入清單。",
             "4. 管理景點、餐廳與住宿使用的分類，方便前台篩選。",
             "5. 檢查會員提出的新增或修改建議，通過後才更新正式資料。",
             "6. 審核會員上傳的景點照片是否合適，通過後再公開。",
             "7. 審核會員的揪團使用申請，建立官方活動並管理報名、截止時間與報到。",
             "8. 提供資料缺漏查核與自動補齊入口；實際執行仍需有效 AI 金鑰及資料驗證。",
             "9. 以有效金鑰匯入真實地點並核對地址、照片；測試 AI 建議內容後再由管理員確認。",
         ])),
        (tables[4].rows[1], "系統管理員",
         "\n".join([
             "1. 會員帳號啟用、停權與角色調整（已完成）",
             "2. 公開行程內容審核（已完成）",
             "3. 問題回報處理（已完成）",
             "4. 公告發布及 LINE 推播（程式已完成）",
             "5. 全站使用統計報表（已完成）",
             "6. 管理員操作紀錄查核（已完成）",
             "7. LINE 推播與管理員跨帳號流程測試（進行中）",
         ]),
         "\n".join([
             "1. 查詢會員帳號狀態，依管理權限啟用、停權或調整角色。",
             "2. 審核會員公開分享的行程，通過後才顯示在公開頁面。",
             "3. 查看會員回報的問題，記錄處理結果。",
             "4. 發布或修改全站公告；LINE 推播須設定可用的通知服務。",
             "5. 查看會員與景點餐宿等使用數據，支援管理判斷。",
             "6. 查詢重要後台操作紀錄，追蹤資料異動。",
             "7. 設定通知服務後發送測試公告；用不同管理員帳號檢查權限與審核結果。",
         ])),
    ]
    for row, role, functions, details in progress:
        cell_text(row.cells[0], role, 9)
        cell_text(row.cells[1], functions, 9)
        cell_text(row.cells[2], details, 9)
        cell_text(row.cells[3], "全組", 9)

    # Replace the example image with a field-level dictionary for every object.
    set_text(paras[34], "資料字典（請列出所有資料表）")
    columns = defaultdict(list)
    for c in SCHEMA["columns"]:
        columns[c["TABLE_NAME"]].append(c)
    fks = {(f["TABLE_NAME"], f["COLUMN_NAME"]):
           (f["REFERENCED_TABLE_NAME"], f["REFERENCED_COLUMN_NAME"]) for f in SCHEMA["fks"]}
    objects = {t["TABLE_NAME"]: t["TABLE_TYPE"] for t in SCHEMA["tables"]}
    grouped = [name for _, names in groups for name in names]
    assert set(grouped) == set(objects), (set(objects) - set(grouped), set(grouped) - set(objects))
    anchor = insert_para_after(
        doc, paras[34]._p,
        "共 58 個資料表、2 個檢視表。欄位、型態、主鍵與外鍵依目前資料庫結構整理；資料範例均為虛構示意，未使用正式資料。",
        8,
    )
    for title, names in groups:
        anchor = insert_para_after(doc, anchor, title, 10, True)
        for name in names:
            cols = columns[name]
            kind = "檢視表" if objects[name] == "VIEW" else "資料表"
            anchor = insert_para_after(doc, anchor, f"{kind}名稱：{name}", 9, True)
            anchor = insert_para_after(doc, anchor, f"資料描述：{purpose[name]}", 8)
            rows = []
            for c in cols:
                raw = c["COLUMN_TYPE"]
                data_type, length = type_and_length(raw)
                fk = fks.get((name, c["COLUMN_NAME"]))
                rows.append((
                    c["COLUMN_NAME"], field_label(c["COLUMN_NAME"]), data_type, length,
                    sample_value(c["COLUMN_NAME"], raw),
                    "Y" if c["COLUMN_KEY"] == "PRI" else "",
                    f"{fk[0]}.{fk[1]}" if fk else "",
                ))
            anchor = make_table_after(
                doc, anchor,
                ["欄位名稱", "中文名稱", "資料型態", "長度", "資料範例", "主鍵", "外來鍵"],
                [2.6, 2.8, 2.1, 1.1, 3.0, 0.8, 4.55], rows, 7.5,
                header_fill="AFCBE3",
            )

    set_text(paras[36], "Repository 更新紀錄")
    set_text(paras[37], "")
    anchor = insert_para_after(doc, paras[36]._p, "資料來源：本機 Git 的 main 分支提交紀錄（截至115年11月21日）；下列為近期具代表性的更新。", 8)
    commits = [
        ("2026-11-19", "5bd5f43", "整合會員頁面、自然語言規劃、費用與飯店資訊"),
        ("2026-11-19", "66a8b47", "加入智慧規劃、住宿預算、費用影像辨識與管理輔助"),
        ("2026-11-19", "d4ed748", "補充揪團當日報到時間檢查"),
        ("2026-11-19", "23869e8", "調整揪團成員當日報到流程"),
        ("2026-11-19", "5395ccb", "加入官方活動報名截止時間設定"),
        ("2026-11-18", "9ddc9c0", "將飯店圖片連結到住宿資料"),
        ("2026-11-16", "0531e0c", "更新旅客選擇、國家與機場搜尋"),
    ]
    anchor = make_table_after(doc, anchor, ["日期", "提交版本", "更新內容"], [2.7, 2.7, 11.55], commits, 9)
    anchor = insert_para_after(doc, anchor, "專案儲存庫：https://github.com/111534114/travel_together", 8)

    set_text(paras[39], "每位組員在 GitHub 上的活動紀錄")
    author_rows = [
        ("111534114 吳若瑄", "132", "5bd5f43：整合 11/19 會員更新；另有 AI 規劃與官方活動報名截止設定。"),
        ("111534119 游蕓安", "29", "12056af：調整飯店詳情價格標示及優惠資訊；另有多城市機票搜尋。"),
        ("111534122 吳安婷", "5", "dc7d134：更新訪客目錄瀏覽與投票分享。"),
        ("111534129 楊雅鈞", "35", "7a37b13：加入自然語言 AI 行程與幣別預估。"),
    ]
    anchor = insert_para_after(doc, paras[39]._p, "統計方式：本機保存的所有分支，以 Git 作者識別比對學號；為提交數，並非 GitHub Contributions 圖上的活動次數。", 8)
    anchor = make_table_after(doc, anchor, ["組員", "提交數", "可核對的提交範例"], [4.2, 1.8, 10.95], author_rows, 9)
    anchor = insert_para_after(doc, anchor, "附註：依 Git 提交紀錄列示，不以壓縮檔匯入紀錄推估個人工作量。", 8)

    doc.core_properties.title = "走吧揪團 AI多人協作旅遊規劃系統—期中進度審查申請表"
    doc.core_properties.author = "吳若瑄、游蕓安、吳安婷、楊雅鈞"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    synopsis = "".join(p.text for p in paras[25:28])
    print(f"OUTPUT={OUT}")
    print(f"HAN_COUNT={len(re.findall(r'[\u4e00-\u9fff]', synopsis))}")
    print(f"TABLES={len(doc.tables)}")


if __name__ == "__main__":
    main()
