from markupsafe import Markup  # 匯入 Markup，money() 輸出的 HTML 不要被跳脫
import json  # 匯入 json 模組，解析來回票第二步帶回來的去程資料
from concurrent.futures import ThreadPoolExecutor  # 日期列的價格同時查
import time  # 匯入 time 模組，幣別匯率的快取過期判斷
import os  # 匯入作業系統功能，用來判斷 Flask 開發伺服器是哪一個行程
import re  # 匯入正規表示式模組，用來驗證註冊欄位格式
import secrets  # 匯入 secrets 模組，用來產生忘記密碼用的隨機 token
from urllib.parse import quote, unquote_plus, urlsplit # SerpApi 表單資料解碼與公開 OAuth 網址判斷
from booking_search import (
    TRAIN_TYPE_LABELS, apply_facets, apply_time_band, apply_value_range, booking_bp, facet_options,
    filter_prices, mark_saved_live_trains, price_buckets, price_range, time_band_options, value_range,
)
import link_check  # 飯店官網連結檢查
import requests  # 匯入 requests，用來呼叫 LINE 的個人資料 API
from datetime import datetime, timedelta
from authlib.integrations.flask_client import OAuth  # 匯入 Authlib 的 Flask 整合，處理 Google 登入 OAuth 流程
from attraction_rankings import TAIWAN_COUNTIES, fetch_attraction_rankings
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify  # 匯入 Flask 核心功能：建立 App、渲染樣板、取得請求、導向、產生網址、session、顯示訊息
from mysql.connector import Error  # 匯入 MySQL 連線錯誤類別，用來捕捉資料庫例外
from werkzeug.security import check_password_hash, generate_password_hash  # 匯入密碼工具：驗證密碼、產生密碼雜湊值
from werkzeug.middleware.proxy_fix import ProxyFix

from config import FLASK_SECRET_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, LINE_CHANNEL_ID, LINE_CHANNEL_SECRET  # 匯入第三方登入設定
from config import LIFF_ID, PUBLIC_BASE_URL  # 匯入 LIFF ID 與網站公開網址(分享給別人的連結要用這個網址)
from db import get_db_connection  # 匯入自訂的資料庫連線函式
from auth import remember_next_page  # 沒登入被擋下時記住原本要去的頁面
import pending_actions  # 訪客按的收藏／加入行程／上傳照片：登入後自動完成
from blueprints.attractions import attractions_bp  # 匯入景點管理的藍圖(Blueprint)
from blueprints.restaurants import restaurants_bp  # 匯入餐廳管理的藍圖
from blueprints.accommodations import accommodations_bp  # 匯入住宿管理的藍圖
from blueprints.locations import locations_bp  # 匯入國家/城市管理的藍圖
from blueprints.categories import categories_bp  # 匯入分類管理的藍圖
from blueprints.proposals import proposals_bp  # 匯入會員提案審核的藍圖
from blueprints.ai_data import ai_data_bp  # 匯入 AI 使用資料維護的藍圖
from blueprints.reports import reports_bp  # 匯入統計報表匯出的藍圖
from blueprints.logs import logs_bp  # 匯入操作紀錄查詢的藍圖
from blueprints.ai_chat import ai_chat_bp  # 匯入 AI 助理對話的藍圖
from blueprints.content_admin_accounts import content_admin_accounts_bp
from blueprints.attraction_posts_admin import attraction_posts_admin_bp
from blueprints.friend_groups import friend_groups_bp  # 匯入交友揪團(會員端)的藍圖
from blueprints.friend_groups_admin import friend_groups_admin_bp  # 匯入交友揪團(後台審核)的藍圖
from content_admin_permissions import CONTENT_ADMIN_ACTIONS, content_admin_can
from blueprints.member import COMMENT_REPORT_PREFIX, ISSUE_PREFIX, member_bp, _fetch_featured_public_trips  # 匯入會員功能的藍圖
from blueprints.line_webhook import line_webhook_bp  # 匯入 LINE 官方帳號 webhook 的藍圖
from blueprints.booking_compare import booking_compare_bp  # 匯入機票＋住宿比價的藍圖
from blueprints.trip_assistant import trip_assistant_bp  # 匯入行程助理(行程頁 AI 聊天)的藍圖
from blueprints.home_banners import fetch_active_banners, home_banners_bp  # 匯入首頁輪播圖(跑馬燈)後台與首頁查詢
from activity_log import ACTION_LABELS, log_action
from mailer import send_password_reset_email  # 匯入忘記密碼重設信的寄送函式
from utils import google_maps_url, google_maps_embed_url, format_hm, friend_group_feature_enabled, get_cities  # 匯入組 Google 地圖連結/嵌入縮圖地圖、格式化 TIME 欄位、查交友揪團總開關的共用函式，註冊成樣板全域函式讓所有頁面都能直接呼叫
import weather  # 匯入中央氣象署天氣預報模組(訪客頁面「目的地天氣」功能用)
import amadeus_client  # 匯入 Amadeus 機票比價 API 模組(機票搜尋的真實即時報價，備用資料來源)
import serpapi_flights  # 匯入 SerpApi 的 Google Flights 模組(機票搜尋的真實即時報價，優先資料來源)
import google_places  # 匯入 Google 地點 API 模組(住宿目的地自動完成)
import serpapi_hotels  # 匯入 SerpApi 的 Google Hotels 模組(住宿搜尋的真實即時報價與圖片，優先資料來源)
import tdx_trains  # 匯入交通部 TDX 模組(高鐵／台鐵指定日期的真實班表與票價，優先資料來源)
import popular_cities  # 匯入「輸入國家名稱時列出熱門城市」的工具
import hotel_review_ai  # 匯入住客評價的 AI 整理工具
from ai_client import AIUnavailable
import flight_combine  # 匯入小機場(國內線)接國際航班的組合行程工具
import flight_links  # 匯入城市->機場代碼對照表、Skyscanner 比價連結組網址工具
import airports  # 匯入全球機場資料庫(約 6000 筆真實機場資料)，給出發地/目的地自動完成用
import line_messaging  # 匯入 LINE 官方帳號共用工具(加好友連結、QR Code)
import line_announcements  # 匯入公告推播到 LINE
import trip_reminders

app = Flask(__name__)  # 建立 Flask 應用程式實例
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.register_blueprint(booking_bp)

# 未設定 .env 時只使用每次啟動都不同的暫時金鑰；對外服務入口會要求固定金鑰。
app.secret_key = FLASK_SECRET_KEY or secrets.token_urlsafe(48)

# 上傳圖片大小限制（8MB）
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 限制單次請求上傳資料的最大位元組數為 8MB

app.jinja_env.globals["google_maps_url"] = google_maps_url  # 註冊成樣板全域函式，任何頁面都能直接用 google_maps_url(...) 組地圖連結
app.jinja_env.globals["google_maps_embed_url"] = google_maps_embed_url  # 註冊成樣板全域函式，任何頁面都能直接用 google_maps_embed_url(...) 組嵌入縮圖地圖的網址


def public_url(endpoint, **values):
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL + url_for(endpoint, **values)
    return url_for(endpoint, _external=True, **values)


def oauth_callback_url(endpoint):
    # ngrok 對外是 HTTPS、轉給本機時是 HTTP；公開登入必須使用固定的 HTTPS 回呼網址。
    # 直接在 localhost 開發時仍保留本機網址，不會誤導向公開網站。
    if PUBLIC_BASE_URL and request.host.casefold() == urlsplit(PUBLIC_BASE_URL).netloc.casefold():
        return public_url(endpoint)
    return url_for(endpoint, _external=True)


def flight_trip_item(flight, date_value, pax=1, cost=None, bundled=False):
    # 給「我已訂票，加入旅程」用：把一班機票整理成一筆行程項目(交通)需要的資料，由前端確認視窗送到後端
    stops = flight.get("stops") or 0
    price = flight.get("price") or 0
    notes = [flight.get("cabin_class") or "", "直飛" if not stops else f"轉機 {stops} 次", f"{pax} 人"]
    if bundled:
        notes.append("價格為來回總價")
    notes.append("使用者自行確認已訂票")
    origin = flight.get("origin_airport_code") or flight.get("origin_city") or ""
    destination = flight.get("destination_airport_code") or flight.get("destination_city") or ""
    return {
        "date": date_value or "",
        "title": f"{flight.get('airline_name', '')} {flight.get('flight_number', '')}｜{origin} → {destination}".strip(),
        "start_time": format_hm(flight.get("departure_time")),
        "end_time": format_hm(flight.get("arrival_time")),
        "cost": float(price) * pax if cost is None else cost,
        "notes": "・".join(part for part in notes if part),
    }


def live_flight_favorite(flight, date_value, origin_keyword, destination_keyword, pax=1):
    # 即時機票的收藏摘要(愛心按下去時存進 booking_live_favorites)
    origin = flight.get("origin_airport_code") or flight.get("origin_city") or ""
    destination = flight.get("destination_airport_code") or flight.get("destination_city") or ""
    stops = flight.get("stops") or 0
    dep = format_hm(flight.get("departure_time"))
    return {
        "kind": "flight",
        "key": f"{flight.get('flight_number', '')}|{date_value}|{dep}|{origin}|{destination}"[:190],
        "title": f"{flight.get('airline_name', '')} {flight.get('flight_number', '')}｜{origin} → {destination}".strip(),
        "subtitle": f"{date_value} {dep}–{format_hm(flight.get('arrival_time'))}・{flight.get('cabin_class') or '經濟艙'}・{'直飛' if not stops else f'轉機 {stops} 次'}",
        "price": float(flight.get("price") or 0),
        "link": url_for("visitor_flight_search", **{"from": origin_keyword, "to": destination_keyword, "depart": date_value, "trip_mode": "oneway", "pax": pax}),
    }


def live_hotel_favorite(hotel, destination, checkin, checkout):
    # 即時住宿的收藏摘要
    parts = [hotel.get("property_type") or "", f"{hotel['star']} 星級" if hotel.get("star") else "", f"{checkin} ～ {checkout}"]
    return {
        "kind": "hotel",
        "key": (hotel.get("detail", {}).get("property_token") or hotel.get("name") or "")[:190],
        "title": hotel.get("name", ""),
        "subtitle": "・".join(p for p in parts if p),
        "price": float(hotel.get("price") or 0),
        "link": hotel.get("website_url") or url_for("visitor_hotel_search", destination=destination, checkin=checkin, checkout=checkout),
    }


def _parse_outbound_item(raw):
    # 來回票第二步(選回程)頁面帶回來的去程資料；來自網址，只收預期的欄位並限制長度，壞掉就當沒有
    try:
        data = json.loads(raw or "")
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    try:
        cost = float(data.get("cost") or 0)
    except (TypeError, ValueError):
        cost = 0
    return {
        "date": str(data.get("date", ""))[:10],
        "title": str(data.get("title", ""))[:150],
        "start_time": str(data.get("start_time", ""))[:5],
        "end_time": str(data.get("end_time", ""))[:5],
        "cost": max(cost, 0),
        "notes": str(data.get("notes", ""))[:500],
    }


app.jinja_env.globals["public_url"] = public_url
app.jinja_env.globals["flight_trip_item"] = flight_trip_item
app.jinja_env.globals["live_flight_favorite"] = live_flight_favorite
app.jinja_env.globals["live_hotel_favorite"] = live_hotel_favorite
app.jinja_env.globals["line_add_friend_url"] = line_messaging.add_friend_url()  # LINE 官方帳號加好友連結，會員首頁與個人資料頁共用
app.jinja_env.globals["line_qr_code_url"] = line_messaging.qr_code_url()  # LINE 官方帳號加好友 QR Code 圖片網址
app.jinja_env.globals["station_label"] = lambda name: tdx_trains.normalize_station(name) if name and name.isascii() else name  # 車票結果頁顯示站名：英文輸入換成中文
app.jinja_env.filters["hm"] = format_hm  # 註冊成樣板過濾器，任何頁面都能直接用 {{ 值 | hm }} 把 TIME 欄位格式化成 HH:MM
app.jinja_env.filters["weekday_cn"] = lambda d: "一二三四五六日"[d.weekday()] if d else ""  # DATE 欄位轉成中文星期（一～日），例如旅遊手冊的日期顯示
app.jinja_env.globals["content_admin_can"] = content_admin_can
app.jinja_env.globals["friend_group_feature_enabled"] = friend_group_feature_enabled  # 任何頁面都能直接用 friend_group_feature_enabled() 判斷交友揪團總開關是否開啟

oauth = OAuth(app)  # 建立 Authlib 的 OAuth 註冊器
google_oauth = oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

line_oauth = oauth.register(
    name="line",
    client_id=LINE_CHANNEL_ID,
    client_secret=LINE_CHANNEL_SECRET,
    access_token_url="https://api.line.me/oauth2/v2.1/token",
    authorize_url="https://access.line.me/oauth2/v2.1/authorize",
    client_kwargs={
        "scope": "profile",
        # LINE 要求 client_id 與 client_secret 放在 token 請求的表單內容，
        # 不能使用 Authlib 預設的 HTTP Basic 驗證方式。
        "token_endpoint_auth_method": "client_secret_post",
    },
)

app.register_blueprint(attractions_bp)  # 註冊景點管理路由
app.register_blueprint(restaurants_bp)  # 註冊餐廳管理路由
app.register_blueprint(accommodations_bp)  # 註冊住宿管理路由
app.register_blueprint(locations_bp)  # 註冊國家/城市管理路由
app.register_blueprint(categories_bp)  # 註冊分類管理路由
app.register_blueprint(proposals_bp)  # 註冊提案審核路由
app.register_blueprint(ai_data_bp)  # 註冊 AI 資料維護路由
app.register_blueprint(reports_bp)  # 註冊統計報表路由
app.register_blueprint(logs_bp)  # 註冊操作紀錄路由
app.register_blueprint(ai_chat_bp)  # 註冊 AI 助理對話路由
app.register_blueprint(content_admin_accounts_bp)
app.register_blueprint(attraction_posts_admin_bp)
app.register_blueprint(home_banners_bp)  # 註冊首頁輪播圖管理路由
app.register_blueprint(friend_groups_bp)  # 註冊交友揪團(會員端)路由
app.register_blueprint(friend_groups_admin_bp)  # 註冊交友揪團(後台審核)路由
app.register_blueprint(member_bp)  # 註冊會員功能路由
app.register_blueprint(trip_assistant_bp)  # 註冊行程助理(AI 聊天)路由
app.register_blueprint(booking_compare_bp)  # 註冊機票＋住宿比價路由
app.register_blueprint(line_webhook_bp)  # 註冊 LINE 官方帳號 webhook 路由


USER_STATUS_LABELS = {
    "active": "正常",
    "under_review": "審查中",
    "disabled": "已停用",
    "deleted": "已刪除",
}


def inactive_account_message(status):
    """Return the login message that matches a non-active account status."""
    return {
        "under_review": "此帳號目前正在審查中，暫時無法登入。",
        "disabled": "此帳號目前已停用，無法登入。",
        "deleted": "此帳號已刪除，無法登入。",
    }.get(status, "此帳號目前無法登入。")


ROLE_AREAS = {"member": "/member", "content_admin": "/content-admin", "system_admin": "/system-admin"}


def _remembered_page(role):
    """沒登入時被擋下來的頁面(auth.remember_next_page 記的)：只有在自己身分能用的區域才帶回去，用過就清掉。"""
    path = session.pop("pending_next", None)
    area = ROLE_AREAS.get(role)
    if not path or not area or path.startswith("//"):
        return None
    if path == area or path.startswith(area + "/") or path.startswith(area + "?"):
        return path
    return None


def redirect_by_role(role):  # 定義函式：依照使用者角色導向對應首頁
    remembered_page = _remembered_page(role)  # 登入前原本要去的頁面(例如「尋找旅伴」、填好資料的「建立行程」)
    if role == "member":  # 如果角色是一般會員
        pending_invite_token = session.pop("pending_invite_token", None)  # 如果是透過邀請連結導來登入/註冊的，登入後直接回去接受邀請
        if pending_invite_token:
            return redirect(url_for("member.accept_invite_link", token=pending_invite_token))
        pending_apply_trip_id = session.get("pending_apply_trip_id")  # 訪客按「登入後一鍵套用」的行程：登入後直接幫他套用
        if pending_apply_trip_id:
            return redirect(url_for("member.apply_trip_after_login", trip_id=pending_apply_trip_id))
        pending_favorite_trip_id = session.get("pending_favorite_trip_id")  # 訪客按「☆ 收藏」的行程：登入後直接幫他收藏
        if pending_favorite_trip_id:
            return redirect(url_for("member.favorite_trip_after_login", trip_id=pending_favorite_trip_id))
        if session.get("pending_action"):  # 訪客按的收藏／加入行程／上傳照片：登入後自動完成再帶回原本頁面
            return redirect(url_for("member.run_pending_action"))
        if session.get("pending_ai_query"):  # 訪客登入前打好的 AI 排行程需求：回會員首頁自動開始排
            return redirect(url_for("member.dashboard") + "#ai-home")
        if remembered_page:  # 回到登入前原本要去的頁面
            return redirect(remembered_page)
        return redirect(url_for("member_home"))  # 導向會員首頁路由

    if role == "content_admin":  # 如果角色是旅遊內容管理員
        if remembered_page:
            return redirect(remembered_page)
        return redirect(url_for("content_admin_home"))  # 導向內容管理員首頁路由

    if role == "system_admin":  # 如果角色是系統管理員
        if remembered_page:
            return redirect(remembered_page)
        return redirect(url_for("system_admin_home"))  # 導向系統管理員首頁路由

    session.clear()  # 角色不在預期範圍內，清空 session 避免殘留錯誤狀態
    flash("帳號角色設定錯誤。", "error")  # 顯示錯誤訊息給使用者
    return redirect(url_for("login"))  # 導回登入頁


def generate_unique_username(cursor, seed):
    """依 Email 帳號部分產生未被使用且符合 9 碼限制的英數帳號。"""
    base = re.sub(r"[^A-Za-z0-9]", "", seed).lower()[:9] or "user"
    username = base
    suffix = 1
    while True:
        cursor.execute("SELECT 1 FROM users WHERE username = %s LIMIT 1", (username,))
        if cursor.fetchone() is None:
            return username
        suffix_text = str(suffix)
        username = base[: 9 - len(suffix_text)] + suffix_text
        suffix += 1


@app.route("/")  # 設定網站根目錄路由
def index():  # 定義首頁進入點函式
    if "user_id" in session:  # 如果 session 裡已經有登入者
        return redirect_by_role(session.get("role"))  # 依角色導向對應首頁

    return redirect(url_for("visitor"))  # 尚未登入則導向訪客頁面


@app.route("/visitor")
def visitor():
    """訪客首頁：版面與會員首頁相同，AI 排行程、套用、收藏等功能需登入才能使用。"""
    home_banners, featured_trips, trips_timeline_json, quick_cities = [], [], {}, []
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        try:
            home_banners = fetch_active_banners(cursor)  # 首頁圖片跑馬燈(後台可修改)
            featured_trips, trips_timeline_json = _fetch_featured_public_trips(cursor, None)  # 熱門公開行程(訪客沒有收藏/回報紀錄)
            quick_cities = get_cities(cursor)
        except Exception as error:
            print("訪客頁面資料庫查詢失敗：", error)
        finally:
            cursor.close()
            connection.close()

    return render_template(
        "visitor.html",
        is_member=False,
        trips_timeline_json=trips_timeline_json,
        home_banners=home_banners,
        featured_trips=featured_trips,
        planning_trips=[],
        quick_cities=quick_cities,
    )


@app.route("/visitor/remember", methods=["POST"])
def visitor_remember_action():
    """訪客按了要登入才能用的按鈕(收藏、加入行程、上傳照片、訂房／機票／火車的 ♡)：先記住，登入後自動完成。"""
    action = pending_actions.remember(request.form.get("target"), request.form.get("back"), request.form)
    if action is None:
        flash("請先登入再使用這個功能。", "error")
        return redirect(url_for("login"))
    session["pending_action"] = action
    if session.get("role") == "member":  # 已經登入的會員直接執行
        return redirect(url_for("member.run_pending_action"))
    flash(pending_actions.MESSAGES[action["type"]] + "還沒有帳號的話，先免費註冊再登入也可以。", "success")
    return redirect(url_for("login"))


@app.route("/visitor/ai-plan", methods=["POST"])
def visitor_ai_plan():
    """訪客在首頁打好 AI 排行程需求：先記住，登入(或註冊後登入)完成就自動幫他排。"""
    query = request.form.get("q", "").strip()[:1000]
    if not query:
        flash("請先說說你想去哪裡、玩幾天。", "error")
        return redirect(url_for("visitor") + "#ai-home")
    session["pending_ai_query"] = query
    if session.get("role") == "member":  # 已經登入的會員直接回會員首頁開始排
        return redirect(url_for("member.dashboard") + "#ai-home")
    flash("登入後就會自動用你剛剛寫的需求幫你排行程。還沒有帳號的話，先免費註冊再登入也可以。", "success")
    return redirect(url_for("login"))


@app.route("/visitor/trips/<int:trip_id>/favorite")
def favorite_trip_after_login(trip_id):
    """訪客按「☆ 收藏」：先記住要收藏哪一趟，登入(或註冊後登入)完成就自動收藏。"""
    session["pending_favorite_trip_id"] = trip_id
    if session.get("role") == "member":  # 已經登入的會員直接收藏
        return redirect(url_for("member.favorite_trip_after_login", trip_id=trip_id))
    flash("登入後就會自動幫你收藏這個行程。還沒有帳號的話，先免費註冊再登入也可以。", "success")
    return redirect(url_for("login"))


@app.route("/visitor/trips/<int:trip_id>/apply")
def apply_trip_after_login(trip_id):
    """訪客按「登入後一鍵套用」：先記住要套用哪一趟，登入(或註冊後登入)完成就自動複製到他的行程。"""
    if session.get("role") == "member":  # 已經登入的會員直接套用
        session["pending_apply_trip_id"] = trip_id
        return redirect(url_for("member.apply_trip_after_login", trip_id=trip_id))
    session["pending_apply_trip_id"] = trip_id
    flash("登入後就會自動幫你套用這個行程。還沒有帳號的話，先免費註冊再登入也可以。", "success")
    return redirect(url_for("login"))


@app.route("/api/hotel-place-search")  # 住宿目的地自動完成打字時用的 AJAX 端點：全世界(Google 地點自動完成)，退回站內台灣住宿資料
def api_hotel_place_search():
    raw_keyword = request.args.get("q", "").strip()
    if not raw_keyword:
        return jsonify([])
    raw_keyword = google_places.to_chinese_keyword(raw_keyword)  # 打英文也可以，建議一律用中文顯示
    # 優先用 Google 地點自動完成：全世界的國家、城市、景點、飯店(繁體中文)；沒金鑰或失敗才退回下面站內(台灣)的資料
    world = google_places.autocomplete_destinations(raw_keyword)
    popular = popular_cities.suggestions(raw_keyword)  # 輸入國家名稱時，最前面先列出該國的熱門城市(像 Agoda 的「倫敦, 英國　人氣王」)
    if world or popular:
        found_country = popular_cities.country_of(raw_keyword)
        world = world or []
        if popular and found_country and not any(item.get("label") == found_country[1] for item in world):
            # 國家本身放在熱門城市後面(搜「澳大利亞」要看得到「澳大利亞」，不只是「澳大利亞首都領地」)
            world = [{"label": found_country[1], "sub": "國家", "value": found_country[1], "kind": "place"}] + world
        return jsonify(popular + world)
    keyword = raw_keyword.replace("台", "臺")
    connection = get_db_connection()
    if not connection:
        return jsonify([])
    cursor = connection.cursor(dictionary=True)
    try:
        like = "%" + keyword + "%"
        cursor.execute(
            """
            SELECT ac.name, ac.address
            FROM accommodations ac
            JOIN countries co ON co.country_id = ac.country_id
            JOIN cities ci ON ci.city_id = ac.city_id
            WHERE ac.status = 'active' AND ac.deleted_at IS NULL AND co.name IN ('台灣', '臺灣')
              AND (REPLACE(ac.name,'台','臺') LIKE %s OR REPLACE(ci.name,'台','臺') LIKE %s OR REPLACE(ac.address,'台','臺') LIKE %s)
            """,
            (like, like, like),
        )
        rows = cursor.fetchall()
    except Exception as error:
        print("住宿目的地建議查詢失敗：", error)
        rows = []
    finally:
        cursor.close()
        connection.close()

    # 從地址抓出「縣市＋鄉鎮市區」(例如 臺北市信義區)，統計每個地區有幾間住宿；
    # 回傳「台北市 信義區」這種用空白隔開的字串，住宿搜尋會拆成兩個關鍵字分別比對，一定查得到
    areas = {}
    for row in rows:
        match = re.search(r"([一-鿿]{2}[市縣])([一-鿿]{1,3}?[區鄉鎮市])", (row["address"] or "").replace("臺", "台"))
        if match and keyword.replace("臺", "台") in match.group(1) + match.group(2):
            area = f"{match.group(1)} {match.group(2)}"
            areas[area] = areas.get(area, 0) + 1
    hotel_names = [row["name"] for row in rows if keyword in row["name"].replace("台", "臺")]
    results = [{"label": area, "sub": f"{count} 間住宿", "value": area}
               for area, count in sorted(areas.items(), key=lambda item: -item[1])[:8]]
    results += [{"label": name, "sub": "住宿", "value": name} for name in hotel_names[:6]]
    return jsonify(results)


_currency_cache = {"expires": 0, "rates": {"TWD": 1.0}, "updated": ""}
_CURRENCY_NAMES = {}


def _currency_names():
    if not _CURRENCY_NAMES:
        try:
            with open(os.path.join(os.path.dirname(__file__), "database", "currencies_zh.json"), encoding="utf-8") as f:
                _CURRENCY_NAMES.update(json.load(f))
        except (OSError, ValueError):
            pass
    return _CURRENCY_NAMES


@app.route("/api/currencies")  # 幣別選單用：全世界貨幣的中文名稱與對台幣的匯率(免費匯率服務，每 6 小時更新一次，所有人共用同一份快取)
def api_currencies():
    now = time.time()
    if now >= _currency_cache["expires"]:
        try:
            resp = requests.get("https://open.er-api.com/v6/latest/TWD", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get("result") == "success" and data.get("rates"):
                _currency_cache.update(rates=data["rates"], updated=data.get("time_last_update_utc", ""), expires=now + 6 * 3600)
        except Exception as error:
            print("匯率查詢失敗(沿用上一次的匯率)：", error)
            _currency_cache["expires"] = now + 300  # 失敗時 5 分鐘後再試，不要每個請求都重打
    names = _currency_names()
    rates = {code: rate for code, rate in _currency_cache["rates"].items() if code == "TWD" or code in names}
    return jsonify(base="TWD", updated=_currency_cache["updated"], rates=rates, names={c: names.get(c, c) for c in rates})


def money(amount):
    """價格的顯示：預設是台幣；網頁上的幣別選單(static/js/currency.js)會把 data-twd 的金額換算成使用者選的貨幣。"""
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return ""
    return Markup(f'<span data-twd="{value:.2f}">NT$ {value:,.0f}</span>')


app.jinja_env.globals["money"] = money


def _review_query_args():
    """評論總覽、AI 整理共用：飯店 token、目的地、日期、人數。回傳 (參數 dict, 錯誤回應)。"""
    token = request.args.get("token", "").strip()
    destination = request.args.get("destination", "").strip()[:100]
    checkin = request.args.get("checkin", "").strip()
    checkout = request.args.get("checkout", "").strip()
    party = _parse_guest_party(request.args)
    try:
        datetime.strptime(checkin, "%Y-%m-%d"); datetime.strptime(checkout, "%Y-%m-%d")
    except ValueError:
        return None, (jsonify(error="日期格式不正確"), 400)
    if not re.fullmatch(r"[A-Za-z0-9_\-]{10,300}", token):
        return None, (jsonify(error="飯店資料不正確"), 400)
    return {"token": token, "destination": destination, "checkin": checkin, "checkout": checkout,
            "adults": party["adults_per_room"], "child_ages": party["ages_per_room"]}, None


@app.route("/api/hotel-reviews")  # 住宿詳情視窗「查看住客評論」用的 AJAX 端點，使用者按了才查(每次用 1 次 SerpApi 額度)
def api_hotel_reviews():
    token = request.args.get("token", "").strip()
    page_token = request.args.get("page_token", "").strip() or None
    category = request.args.get("category", "").strip() or None  # 只看某個面向(清潔、服務⋯)的留言
    if (not re.fullmatch(r"[A-Za-z0-9_\-]{10,300}", token)
            or (page_token and not re.fullmatch(r"[A-Za-z0-9_\-=%.]{1,2000}", page_token))
            or (category and not re.fullmatch(r"[A-Za-z0-9_\-=%.]{1,600}", category))):
        return jsonify(error="飯店資料不正確"), 400
    result = serpapi_hotels.get_reviews(token, page_token, category)
    if result is None:
        return jsonify(error="暫時查不到住客評論，請稍後再試。"), 502
    return jsonify(result)


@app.route("/api/hotel-review-overview")  # 評論視窗上方的星等分布與各面向統計(跟「比價」共用同一次查詢)
def api_hotel_review_overview():
    args, error = _review_query_args()
    if error:
        return error
    overview = serpapi_hotels.get_review_overview(args["token"], args["destination"], args["checkin"], args["checkout"], args["adults"], args["child_ages"])
    if overview is None:
        return jsonify(error="暫時查不到評價統計，請稍後再試。"), 502
    return jsonify(overview)


@app.route("/api/hotel-review-ai")  # 「AI 整理住客評價」：按了才呼叫 AI，結果快取一小時
def api_hotel_review_ai():
    args, error = _review_query_args()
    if error:
        return error
    overview = serpapi_hotels.get_review_overview(args["token"], args["destination"], args["checkin"], args["checkout"], args["adults"], args["child_ages"])
    first_page = serpapi_hotels.get_reviews(args["token"])
    if overview is None and first_page is None:
        return jsonify(error="暫時查不到住客評價，請稍後再試。"), 502
    try:
        result = hotel_review_ai.summarize(
            args["token"], request.args.get("name", "").strip()[:120], request.args.get("rating", "").strip()[:6],
            request.args.get("reviews", "").strip()[:12], overview, (first_page or {}).get("reviews"))
    except AIUnavailable as exc:
        return jsonify(error=str(exc)), 503
    return jsonify(result)


@app.route("/api/hotel-offers")  # 住宿詳情視窗「查看各訂房網站價格」用的 AJAX 端點，使用者按了才查(每次用 1 次 SerpApi 額度)
def api_hotel_offers():
    token = request.args.get("token", "").strip()
    destination = request.args.get("destination", "").strip()[:100]
    checkin = request.args.get("checkin", "").strip()
    checkout = request.args.get("checkout", "").strip()
    party = _parse_guest_party(request.args)
    try:
        datetime.strptime(checkin, "%Y-%m-%d"); datetime.strptime(checkout, "%Y-%m-%d")
    except ValueError:
        return jsonify(error="日期格式不正確"), 400
    if not re.fullmatch(r"[A-Za-z0-9_\-]{10,300}", token):
        return jsonify(error="飯店資料不正確"), 400
    offers = serpapi_hotels.get_offers(token, destination, checkin, checkout, party["adults_per_room"], party["ages_per_room"])
    if offers is None:
        return jsonify(error="暫時查不到各訂房網站的價格，請稍後再試。"), 502
    return jsonify(offers=offers)


@app.route("/api/hotel-link-check")  # 檢查飯店官網連結是否還有效：失效的連結詳情頁就隱藏「前往飯店官網」按鈕
def api_hotel_link_check():
    url = request.args.get("url", "").strip()
    if len(url) > 500 or urlsplit(url).scheme not in ("http", "https"):
        return jsonify(alive=True)
    return jsonify(alive=link_check.check(url))


@app.route("/visitor/hotels/detail")  # 飯店詳情整頁(點「查看詳情」開新分頁)：內容由前端從瀏覽器暫存讀取，不再多花 API 額度
def visitor_hotel_detail():
    return render_template("hotel_detail.html")


MAX_HOTEL_NIGHTS = 30  # 住宿即時報價最多可查的晚數


@app.route("/visitor/hotels")  # 設定訪客住宿搜尋結果頁路由(從訪客頁面的住宿搜尋表單導入，帶入目的地/日期/人數)
def visitor_hotel_search():
    destination = google_places.to_chinese_keyword(request.args.get("destination", "").strip())  # 取得使用者輸入的目的地關鍵字；打英文會轉成中文，頁面和搜尋都用中文
    checkin = request.args.get("checkin", "").strip()  # 取得入住日期(YYYY-MM-DD)
    checkout = request.args.get("checkout", "").strip()  # 取得退房日期(YYYY-MM-DD)

    party = _parse_guest_party(request.args)  # 房間數、成人、兒童(含年齡)；guests 沿用成人人數，其他程式還在用
    guests = party["adults"]

    nights = None  # 預設住宿晚數未知
    if checkin and checkout:  # 如果入住與退房日期都有填
        try:
            check_in_date = datetime.strptime(checkin, "%Y-%m-%d").date()  # 解析入住日期
            check_out_date = datetime.strptime(checkout, "%Y-%m-%d").date()  # 解析退房日期
            diff = (check_out_date - check_in_date).days  # 計算相差天數
            nights = diff if diff > 0 else None  # 退房要晚於入住才算合理晚數
        except ValueError:  # 如果日期格式不正確
            nights = None

    live_hotels = None  # 即時住宿資料(Google Hotels)；沒金鑰、沒填日期或查詢失敗時維持 None，退回資料庫的住宿
    next_page_token = None
    live_failed = False
    page_token = request.args.get("page_token", "").strip() or None
    stay_too_long = bool(nights and nights > MAX_HOTEL_NIGHTS)  # Google Hotels 超過 30 晚就查不到(實測 30 晚有結果、31 晚是 0 筆)，不浪費 API 額度
    if destination and nights and not stay_too_long and serpapi_hotels.is_configured():
        live = serpapi_hotels.search_hotels(destination, checkin, checkout, party["adults_per_room"], page_token, party["ages_per_room"])
        if live and live["hotels"]:
            live_hotels, next_page_token = live["hotels"], live["next_page_token"]
        else:
            live_failed = True

    accommodations = []  # 預設搜尋結果為空清單
    connection = get_db_connection() if live_hotels is None else None

    if connection:
        cursor = connection.cursor(dictionary=True)
        try:
            conditions = ["ac.status = 'active'", "ac.deleted_at IS NULL"]  # 只搜尋已啟用、且不在回收桶裡的住宿
            params = []

            one_keyword = "(REPLACE(ac.name,'台','臺') LIKE %s OR REPLACE(ci.name,'台','臺') LIKE %s OR co.name LIKE %s OR REPLACE(ac.address,'台','臺') LIKE %s)"
            for keyword in destination.split():
                # 打英文城市名(例如 Taipei)時，資料庫的城市是中文，所以把英文轉成中文城市名一起比對
                words = [keyword]
                zh = flight_links.to_chinese_city_name(keyword.title()) if keyword.isascii() else None
                if zh and zh != keyword:
                    words.append(zh)
                conditions.append("(" + " OR ".join(one_keyword for _ in words) + ")")
                for word in words:
                    like = '%' + word.replace('台', '臺') + '%'
                    params.extend([like, like, like, like])

            where_clause = "WHERE " + " AND ".join(conditions)

            cursor.execute(
                f"""
                SELECT ac.accommodation_id, ac.name, ac.address, ac.accommodation_type,
                       ac.price_per_night, ac.check_in_time, ac.check_out_time,
                       ac.image_path, ac.description, ac.website_url, ac.latitude, ac.longitude,
                       co.name AS country_name, ci.name AS city_name
                FROM accommodations ac
                JOIN countries co ON co.country_id = ac.country_id
                JOIN cities ci ON ci.city_id = ac.city_id
                {where_clause}
                ORDER BY ac.accommodation_id DESC
                """,
                params
            )
            accommodations = cursor.fetchall()
        except Exception as error:
            print("住宿搜尋查詢失敗：", error)
        finally:
            cursor.close()
            connection.close()

    if live_hotels is not None:
        return _render_live_hotels(live_hotels, destination, checkin, checkout, guests, nights, next_page_token, party)

    # 沒有連上 API(沒金鑰、查詢失敗)時，資料庫的住宿也用跟即時資料一樣的版面顯示
    cards = [_db_hotel_card(row, nights) for row in accommodations]
    serpapi_hotels.translate_names(cards)  # 資料庫裡少數英文名稱的住宿也翻成中文
    return _render_live_hotels(cards, destination, checkin, checkout, guests, nights, None, party, source="db", live_failed=live_failed, stay_too_long=stay_too_long)


HOTEL_MAX_GUESTS = 60  # 住客上限(成人+兒童)，比照 Agoda；Trip.com 只有 8 人，太少
HOTEL_MAX_ROOMS = 30
HOTEL_MAX_ADULTS_PER_ROOM = 4  # 每間房最多 4 位成人，人數超過就自動增加房間
HOTEL_MAX_CHILDREN = 20


def _parse_guest_party(args):
    """住宿搜尋的房間數、成人、兒童(含年齡)。SerpApi 沒有房間數參數，所以多間房時改成「平均分配到每間房」
    (成人、兒童都無條件進位)去查每間房的價格，頁面再用「每間價格 x 房間數」估算總價並標明是估算。"""
    def clamp(raw, default, low, high):
        raw = str(raw if raw is not None else "").strip()
        value = int(raw) if raw.isdigit() else default
        return max(low, min(high, value))

    adults = clamp(args.get("guests"), 2, 1, HOTEL_MAX_GUESTS)
    rooms = max(clamp(args.get("rooms"), 1, 1, HOTEL_MAX_ROOMS), -(-adults // HOTEL_MAX_ADULTS_PER_ROOM))  # 人多時自動補足房間數
    adults = max(adults, rooms)  # 每間房至少要有一位成人
    ages_raw = [a for a in str(args.get("child_ages", "")).split(",") if a.strip().isdigit()]
    children = clamp(args.get("children", len(ages_raw)), len(ages_raw), 0, min(HOTEL_MAX_CHILDREN, max(0, HOTEL_MAX_GUESTS - adults)))
    ages = [max(1, min(17, int(a))) for a in ages_raw][:children]
    ages += [8] * (children - len(ages))  # 年齡沒填完整時用 8 歲補(SerpApi 要求年齡數量要跟兒童數一致)
    adults_per_room = -(-adults // rooms)
    kids_per_room = -(-children // rooms)
    label = f"{adults} 位成人" + (f"、{children} 位兒童" if children else "")
    if rooms > 1:
        label = f"{rooms} 間房，每間以 {adults_per_room} 位成人" + (f"、{kids_per_room} 位兒童" if kids_per_room else "") + "計價"
    else:
        label = "以 " + label + "計價"
    note = f"需要 {rooms} 間房，是否有足夠空房請向訂房網站確認" if rooms > 1 else ""  # Google 沒有飯店房間總數或剩餘房數的資料
    return {"rooms": rooms, "adults": adults, "children": children, "ages": ages, "adults_per_room": adults_per_room,
            "ages_per_room": ages[:kids_per_room], "label": label, "note": note}


def _hotel_facet(rows, key, label_of, sort_key=None):
    # 住宿篩選的選項：算出每個值有幾間、最低價多少(都是從這批即時結果實際算出來的)；只有一種值就沒有篩選意義
    groups = {}
    for row in rows:
        value = row.get(key)
        if value is None or value == "":
            continue
        group = groups.setdefault(value, {"count": 0, "min_price": None})
        group["count"] += 1
        if group["min_price"] is None or row["price"] < group["min_price"]:
            group["min_price"] = row["price"]
    if len(groups) < 2:
        return []
    options = [{"value": str(value), "label": label_of(value), "count": g["count"], "min_price": g["min_price"]} for value, g in groups.items()]
    return sorted(options, key=sort_key or (lambda o: -o["count"]))


def _db_hotel_card(row, nights):
    """把資料庫的住宿(accommodations)轉成跟 Google 即時資料一樣的卡片資料，讓兩種來源用同一個版面。
    資料庫沒有評分、星級、設施，這些欄位就是空的(卡片上不顯示)；價格是 0 代表「價格洽詢」。"""
    price = float(row["price_per_night"] or 0)
    image = url_for("static", filename=row["image_path"]) if row.get("image_path") else None
    images = [{"thumb": image, "full": image}] if image else []
    check_in, check_out = format_hm(row.get("check_in_time")), format_hm(row.get("check_out_time"))
    website = row.get("website_url") or ""
    lat = float(row["latitude"]) if row.get("latitude") is not None else None
    lng = float(row["longitude"]) if row.get("longitude") is not None else None
    kind = row.get("accommodation_type") or "住宿"
    return {
        "accommodation_id": row["accommodation_id"], "name": row["name"], "description": row.get("description") or "",
        "images": images, "price": price, "total_price": price * nights if price and nights else None,
        "flags": [], "rating": None, "reviews": 0, "star": None, "property_type": kind, "amenities": [], "deal": "",
        "website_url": website, "latitude": lat, "longitude": lng, "check_in_time": check_in, "check_out_time": check_out,
        "address": row.get("address") or "",
        "detail": {
            "name": row["name"], "address": row.get("address") or "", "place_id": "", "description": row.get("description") or "",
            "images": [img["full"] for img in images], "amenities": [], "rating": None, "reviews": 0, "location_rating": None,
            "rating_counts": [], "topics": [], "nearby": [], "check_in_time": check_in, "check_out_time": check_out,
            "website_url": website, "latitude": lat, "longitude": lng, "star": None, "property_type": kind,
            "price": price, "total_price": price * nights if price and nights else None, "property_token": "",
        },
    }


def _render_live_hotels(hotels, destination, checkin, checkout, guests, nights, next_page_token, party, source="live", live_failed=False, stay_too_long=False):
    star_facets = _hotel_facet(hotels, "star", lambda v: f"{v} 星級", sort_key=lambda o: -int(o["value"]))
    # 側邊欄不列「度假租屋」，只留「飯店」一個選項(結果裡有混到租屋時才有篩選意義)
    type_facets = [f for f in _hotel_facet(hotels, "property_type", lambda v: v) if f["value"] == "飯店"]

    amenity_counts = {}
    for hotel in hotels:
        for label in hotel["amenities"]:
            amenity_counts[label] = amenity_counts.get(label, 0) + 1
    amenity_facets = [{"value": label, "label": label, "count": count, "min_price": None}
                      for label, count in sorted(amenity_counts.items(), key=lambda item: -item[1])[:20]
                      if count < len(hotels) and label != "親子友善"]

    # 熱門篩選條件：只列這批結果裡真的有符合的項目(沒有任何一間符合就不顯示，不放點了沒結果的選項)
    popular_labels = {"parking": "設有停車位", "breakfast": "包含早餐", "pets": "可攜帶寵物"}
    kids_label = {"kids": "親子友善"}  # Google 對整間飯店的標示，不代表有親子房
    # 有帶兒童時排在最前面，沒帶兒童一樣列出來，只是不優先
    popular_labels = {**kids_label, **popular_labels} if party["children"] else {**popular_labels, **kids_label}
    popular_facets = [{"value": key, "label": label, "count": sum(1 for h in hotels if key in h["flags"])}
                      for key, label in popular_labels.items()]
    popular_facets = [f for f in popular_facets if f["count"]]
    rating_facets = [{"value": str(score), "label": f"{score} 星以上", "count": sum(1 for h in hotels if (h["rating"] or 0) >= score)}
                     for score in (4.5, 4)]
    rating_facets = [f for f in rating_facets if f["count"]]

    rows = hotels
    selected_stars = request.args.getlist("star")
    if selected_stars:
        rows = [h for h in rows if str(h["star"]) in selected_stars]
    selected_types = request.args.getlist("property_type")
    if selected_types:
        rows = [h for h in rows if h["property_type"] in selected_types]
    for label in request.args.getlist("amenity"):
        rows = [h for h in rows if label in h["amenities"]]
    for key in request.args.getlist("popular"):
        rows = [h for h in rows if key in h["flags"]]
    rating_values = [float(v) for v in request.args.getlist("rating_min") if v.replace(".", "", 1).isdigit()]
    if rating_values:
        rows = [h for h in rows if (h["rating"] or 0) >= max(rating_values)]

    price_max = price_range(hotels, "price")
    rows = filter_prices(rows, "price")
    sort = request.args.get("sort", "")
    if sort == "rating":
        rows = sorted(rows, key=lambda h: -(h["rating"] or 0))
    elif sort == "star":
        rows = sorted(rows, key=lambda h: -(h["star"] or 0))
    elif party["children"] and not sort:
        # 有帶兒童且沒指定排序時，親子友善的飯店排最前面(其餘維持 Google 原本的順序)；指定了排序就照使用者選的排
        rows = sorted(rows, key=lambda h: "kids" not in h["flags"])

    return render_template(
        "hotel_search.html", destination=destination, checkin=checkin, checkout=checkout, guests=guests, nights=nights,
        using_live_data=True, hotels=rows, hotel_total=len(hotels), price_max=price_max, price_buckets=[],
        star_facets=star_facets, type_facets=type_facets, amenity_facets=amenity_facets,
        popular_facets=popular_facets, rating_facets=rating_facets,
        map_url="https://www.google.com/maps/search/?api=1&query=" + quote(f"{destination} 飯店"),
        next_page_token=next_page_token, accommodations=[],
        party=party, rooms=party["rooms"], party_label=party["label"], hotel_source=source, live_failed=live_failed, stay_too_long=stay_too_long,
    )


def _search_flights(from_keyword, to_keyword, pax):
    """依出發地/目的地關鍵字查詢班機，機票搜尋(單程/來回)跟多座城市搜尋共用這個函式。"""
    results = []  # 預設搜尋結果為空清單
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        try:
            conditions = ["f.status = 'active'", "f.seats_available >= %s"]  # 只搜尋已啟用且座位足夠的班機
            params = [pax]

            if from_keyword:  # 如果有輸入出發地關鍵字，依城市/國家名稱模糊搜尋
                conditions.append("(oc.name LIKE %s OR ocn.name LIKE %s)")
                like = f"%{from_keyword}%"
                params.extend([like, like])

            if to_keyword:  # 如果有輸入目的地關鍵字，依城市/國家名稱模糊搜尋
                conditions.append("(dc.name LIKE %s OR dcn.name LIKE %s)")
                like = f"%{to_keyword}%"
                params.extend([like, like])

            where_clause = "WHERE " + " AND ".join(conditions)

            cursor.execute(
                f"""
                SELECT f.flight_id, f.airline_name, f.flight_number,
                       f.departure_time, f.arrival_time, f.duration_minutes,
                       f.price, f.cabin_class, f.stops, f.seats_available,
                       ocn.name AS origin_country, oc.name AS origin_city,
                       dcn.name AS destination_country, dc.name AS destination_city
                FROM flights f
                JOIN countries ocn ON ocn.country_id = f.origin_country_id
                JOIN cities oc ON oc.city_id = f.origin_city_id
                JOIN countries dcn ON dcn.country_id = f.destination_country_id
                JOIN cities dc ON dc.city_id = f.destination_city_id
                {where_clause}
                ORDER BY f.departure_time
                """,
                params
            )
            results = cursor.fetchall()
            for row in results:
                row["airline_logo"] = flight_links.airline_logo_url(row["airline_name"])
        except Exception as error:  # 如果查詢過程發生錯誤
            print("機票搜尋查詢失敗：", error)
        finally:
            cursor.close()
            connection.close()
    return results


def _flight_party():
    """旅客組成：成人、兒童(2–11 歲，佔位)、嬰兒(未滿 2 歲，不佔位)。回傳 (成人, 兒童, 嬰兒, pax)，
    pax = 佔位人數(成人 + 兒童)，沿用到處在用的 pax 參數；Google Flights 一筆最多 9 位，嬰兒不能比成人多。"""
    def num(name, default):
        raw = (request.args.get(name) or "").strip()
        return int(raw) if raw.isdigit() else default

    if any((request.args.get(key) or "") != "" for key in ("adults", "children", "infants")):
        adults = min(max(num("adults", 1), 1), 9)
        children = min(max(num("children", 0), 0), 9 - adults)
        infants = min(max(num("infants", 0), 0), adults)
    else:
        adults, children, infants = min(max(num("pax", 1), 1), 9), 0, 0
    return adults, children, infants, adults + children


def _live_flight_search(origin_keyword, destination_keyword, depart_date, return_date=None, pax=1, cabin_class=None, more=False, children=0, infants=0):
    """依序嘗試 SerpApi(Google Flights) -> Amadeus，兩個都沒設定金鑰/查不到/失敗就回傳 (None, False)，
    呼叫端自己改用本地資料庫的固定班表資料。回傳 (flights, is_live)。
    cabin_class：Google Flights 預設只查經濟艙，要查商務/頭等艙要指定這個，所以使用者在「艙等」篩選
    選了特定艙等時，呼叫端要帶這個參數重新查一次，不是拿經濟艙資料硬篩。"""
    flights = serpapi_flights.search_flight_offers(origin_keyword, destination_keyword, depart_date, return_date, pax - children, cabin_class=cabin_class, more=more, children=children, infants=infants)
    if flights:
        return flights, True
    flights = amadeus_client.search_flight_offers(origin_keyword, destination_keyword, depart_date, pax)
    if flights:
        return flights, True
    return None, False


def _live_airport_label(iata_code, typed_keyword):
    """即時資料每筆航班實際起降的機場代碼(例如搜尋「東京（所有機場）」時，不同班機可能分別是
    NRT 或 HND)，換成比較好懂的機場中文名稱，而不是整段原始搜尋關鍵字──不然同一個城市選了
    「所有機場」時，不同機場的航班會全部顯示同一個字串，看不出班機之間落地機場的差異。
    查不到這個代碼的資料就退回使用者原本輸入的關鍵字，不要顯示原始的機場代碼。"""
    airport = airports.get_airport(iata_code)
    if not airport:
        return typed_keyword or iata_code
    return flight_links.AIRPORT_NAME_ZH.get(iata_code) or airport.get("name_zh") or airport["city"]


def _hm_to_minutes(hm_value):
    """把 "HH:MM" 字串轉成從 00:00 起算的分鐘數，給出發/抵達時間篩選滑桿用；格式不對就回傳 None。"""
    try:
        hour, minute = str(hm_value).split(":")
        return int(hour) * 60 + int(minute)
    except (ValueError, AttributeError):
        return None


def _airport_facet_label(iata_code):
    """「機場」篩選選項的顯示文字，格式「TSA 臺北松山機場」(代碼+機場名稱)，查不到名稱就只顯示代碼。"""
    label = _live_airport_label(iata_code, None)
    return f"{iata_code} {label}" if label and label != iata_code else iata_code


def _live_layover_city_label(layovers):
    """中停城市篩選用：多段中停時，用第一個中停站代表(絕大多數航班只中停一次)，
    換成比較好懂的中文城市名稱，查不到就用 SerpApi 給的機場名稱原文。"""
    if not layovers:
        return None
    first = layovers[0]
    city_zh = flight_links.to_chinese_city_name(airports.get_airport(first.get("iata", "")).get("city", "")) if airports.get_airport(first.get("iata", "")) else None
    return city_zh or first.get("name")


def _live_cheapest_price(origin_keyword, destination_keyword, depart_date, pax=1, return_date=None):
    """只拿某一天最低價，給日期選擇列用；依序試 SerpApi -> Amadeus，兩個都查不到就回傳 None。
    有給 return_date 時，SerpApi 回傳的就已經是去程+回程配好的真實來回總價(不是分開查兩段單程再加總)。"""
    price = serpapi_flights.cheapest_price(origin_keyword, destination_keyword, depart_date, return_date, pax)
    if price is not None:
        return price
    return amadeus_client.cheapest_price(origin_keyword, destination_keyword, depart_date, pax)


@app.route("/api/station-search")  # 出發站/到達站自動完成打字時用的 AJAX 端點，查高鐵 12 站＋台鐵全部車站
def api_station_search():
    return jsonify(tdx_trains.search_stations(request.args.get("q", ""), rail=request.args.get("rail")))


@app.route("/api/city-search")  # 出發地/目的地自動完成打字時用的 AJAX 端點，查全球機場資料庫(不只是手動整理的常見城市)
def api_city_search():
    keyword = flight_links.canonical_country_keyword(request.args.get("q", "").strip())  # 國家官方全名轉簡稱
    if len(keyword) < 1:
        return jsonify([])
    # 北海道、九州等地區涵蓋多個城市，合併查詢各城市機場。
    region_cities = flight_links.REGION_CITIES.get(keyword)
    country_found = [] if region_cities else flight_links.country_airports(keyword)
    # 打國家名稱(中文或英文，例如 Japan、日本)：國際機場不多的小國直接列出「所有機場」；
    # 機場很多的大國列出航線最多的前 10 個機場，讓使用者自己挑
    big_country = []
    if not region_cities and not country_found:
        country_en = flight_links.COUNTRY_NAME_EN.get(keyword) or airports.match_country_name(keyword)
        if country_en:
            big_country = airports.get_country_airports(country_en, limit=15)
    if country_found:
        results = country_found
    elif big_country:
        results = big_country
    elif region_cities:
        results = []
        seen_iata = set()
        for city in region_cities:
            for airport in airports.get_city_airports(city, "Japan"):
                if airport["iata"] not in seen_iata:
                    seen_iata.add(airport["iata"])
                    results.append(airport)
    else:
        # 全球機場資料庫是英文資料，中文關鍵字先轉成英文城市名。
        alias_airport = airports.get_airport(flight_links.TOURIST_ALIAS.get(keyword))
        if alias_airport:
            # 旅客常用別名(普吉島、摩納哥⋯)：直接指到那個機場所在城市的機場，不用文字比對(代碼的三個字母會誤中別的機場)
            results = airports.get_city_airports(alias_airport["city"], alias_airport["country"], include_domestic=True) or [alias_airport]
        else:
            search_keyword = flight_links.to_english_city_name(keyword)
            results = airports.search_airports(search_keyword, limit=10)
    # search_airports() 回傳的是模組內共用資料的參照，這裡組新的 dict 回傳，不要直接改到原始資料上。
    # 中文機場名稱優先用手動整理過、確認無誤的 AIRPORT_NAME_ZH；查不到的話，
    # 用資料庫裡從維基數據(Wikidata)合併進來的 name_zh(真正的中文機場名稱，不是機器翻譯)；
    # 兩邊都沒有(非常冷門的小機場，中文維基百科也沒有條目)才會是 None，前端會 fallback 顯示英文原名。
    payload = [
        dict(
            row,
            name_zh=flight_links.AIRPORT_NAME_ZH.get(row["iata"]) or row.get("name_zh") or None,
            city_zh=flight_links.to_chinese_city_name(row["city"]),
            label_zh=airports.CITY_LABEL_ZH.get(row["iata"]),
            country_zh=flight_links.COUNTRY_ZH.get(row["country"]),
            region=keyword if (region_cities or country_found) else None,
        )
        for row in results
    ]
    # 同一次結果裡中文名稱重複(例如墨爾本有兩個「墨爾本機場」)：重複的補上英文名稱，才分得出是哪一個
    seen_names = {}
    for item in sorted(payload, key=lambda it: -int(it.get("routes") or 0)):
        if item["name_zh"]:
            seen_names[item["name_zh"]] = seen_names.get(item["name_zh"], 0) + 1
            if seen_names[item["name_zh"]] > 1:  # 第二個起才補英文(航線最多的保持簡潔)
                item["name_zh"] = f"{item['name_zh']}（{item['name']}）"
    return jsonify(payload)


@app.route("/visitor/flights")  # 設定訪客機票搜尋結果頁路由(從訪客頁面的機票搜尋表單導入，帶入出發地/目的地/日期/人數)
def visitor_flight_search():
    origin = request.args.get("from", "").strip()  # 取得出發地關鍵字
    destination = request.args.get("to", "").strip()  # 取得目的地關鍵字
    depart_date = request.args.get("depart", "").strip()  # 取得去程日期(YYYY-MM-DD)
    return_date = request.args.get("return", "").strip()  # 取得回程日期(YYYY-MM-DD)，有填才會查回程班機

    adults, children, infants, pax = _flight_party()  # 成人/兒童/嬰兒；pax = 佔位人數

    is_roundtrip = return_date and request.args.get('trip_mode', 'roundtrip') == 'roundtrip'

    # 選到只飛國內線的小機場(花蓮、澎湖⋯)：出發地是小機場時，先找「小機場→轉運站」的國內航班，
    # 有找到就把它接上轉運站出發的國際航班，組成完整行程；找不到就退回改用最近的國際機場查，並在頁面上說明
    transfer_notes = []
    domestic_plan = None
    small_origin_code = (flight_links.to_iata(origin) or "").split(",")
    if len(small_origin_code) == 1 and small_origin_code[0] in airports.DOMESTIC_FEEDERS and depart_date:
        small = small_origin_code[0]
        for feeder in airports.DOMESTIC_FEEDERS[small]:
            domestic = [row for row in (serpapi_flights.search_flight_offers(small, feeder, depart_date, None, pax) or [])
                        if row.get("destination_city") == feeder]
            if domestic:
                feeder_label = flight_links.AIRPORT_NAME_ZH.get(feeder) or airports.get_airport(feeder)["name_zh"]
                small_label = flight_links.AIRPORT_NAME_ZH.get(small) or airports.get_airport(small)["name_zh"]
                domestic_plan = {"small": small, "feeder": feeder, "domestic": domestic, "feeder_label": feeder_label, "small_label": small_label}
                origin = f"{feeder_label} ({feeder})"
                break
    # 目的地是小機場：國際航班先抵達轉運站，再接「轉運站→小機場」的國內航班(抵達當天或隔天)
    tail_plan = None
    small_dest_code = (flight_links.to_iata(destination) or "").split(",")
    if len(small_dest_code) == 1 and small_dest_code[0] in airports.DOMESTIC_FEEDERS and depart_date:
        small = small_dest_code[0]
        try:
            base_day = datetime.strptime(depart_date, "%Y-%m-%d").date()
        except ValueError:
            base_day = None
        for feeder in (airports.DOMESTIC_FEEDERS[small] if base_day else []):
            domestic = []
            for offset in (0, 1):
                day = (base_day + timedelta(days=offset)).isoformat()
                domestic += [row for row in (serpapi_flights.search_flight_offers(feeder, small, day, None, pax) or [])
                             if row.get("destination_city") == small]
            if domestic:
                feeder_label = flight_links.AIRPORT_NAME_ZH.get(feeder) or airports.get_airport(feeder)["name_zh"]
                small_label = flight_links.AIRPORT_NAME_ZH.get(small) or airports.get_airport(small)["name_zh"]
                tail_plan = {"small": small, "feeder": feeder, "domestic": domestic, "feeder_label": feeder_label, "small_label": small_label}
                destination = f"{feeder_label} ({feeder})"
                break
    for _name in ("origin", "destination"):
        if (_name == "origin" and domestic_plan) or (_name == "destination" and tail_plan):
            continue
        _new, _note = flight_links.transfer_hub(locals()[_name])
        if _note:
            transfer_notes.append(_note)
            if _name == "origin":
                origin = _new
            else:
                destination = _new

    # 優先打真實機票報價 API（SerpApi 的 Google Flights，查不到再試 Amadeus），價格會依日期浮動；
    # 兩個都沒設定金鑰、查不到這條航線、或 API 呼叫失敗，就自動改用本地資料庫裡固定班表的機票資料，
    # 兩種情況畫面都看得出差異(有沒有「即時報價」標籤)。
    # 「艙等」篩選選了特定艙等(不是「全部艙等」)時要重新查那個艙等，Google Flights 預設只回傳經濟艙，
    # 商務艙/頭等艙的航班不會自動出現在經濟艙的查詢結果裡。
    selected_cabin = request.args.get("cabin", "all")
    cabin_query = selected_cabin if selected_cabin != "all" else None
    show_more = request.args.get("more") == "1"  # 「顯示更多航班」：多查幾種條件把更多航班合併進來(多用幾次額度)
    outbound_flights, using_live_data = _live_flight_search(origin, destination, depart_date, return_date if is_roundtrip else None, pax, cabin_class=cabin_query, more=show_more, children=children, infants=infants)
    if using_live_data and domestic_plan:
        combined = flight_combine.combine_with_domestic(
            domestic_plan["domestic"], outbound_flights, domestic_plan["feeder"], domestic_plan["feeder_label"])
        if combined:
            outbound_flights = combined
            transfer_notes.append(
                f"{domestic_plan['small_label']}沒有國際航班，以下行程是「{domestic_plan['small_label']} → {domestic_plan['feeder_label']}（國內線）」"
                f"接「{domestic_plan['feeder_label']} → 目的地（國際線）」的組合。兩段是分開購買的機票，行李需在轉機點自行提領並重新報到，轉機至少預留 2.5 小時。")
        else:
            outbound_flights = []
            transfer_notes.append(
                f"找不到能順利接上的行程：{domestic_plan['small_label']}到{domestic_plan['feeder_label']}的國內航班，"
                f"跟{domestic_plan['feeder_label']}出發的國際航班之間，這一天沒有至少相隔 2.5 小時的組合，可以換個日期試試。")
    if using_live_data and tail_plan and outbound_flights:
        combined = flight_combine.combine_with_domestic_tail(
            outbound_flights, tail_plan["domestic"], tail_plan["feeder"], tail_plan["feeder_label"])
        if combined:
            outbound_flights = combined
            transfer_notes.append(
                f"{tail_plan['small_label']}沒有國際航班，以下行程是「國際線 → {tail_plan['feeder_label']}」接"
                f"「{tail_plan['feeder_label']} → {tail_plan['small_label']}（國內線）」的組合。兩段是分開購買的機票，"
                "行李需在轉機點自行提領並重新報到，轉機至少預留 2.5 小時。")
        else:
            outbound_flights = []
            transfer_notes.append(
                f"找不到能順利接上的行程：國際航班抵達{tail_plan['feeder_label']}之後，"
                f"沒有至少相隔 2.5 小時、飛往{tail_plan['small_label']}的國內航班，可以換個日期試試。")
    if using_live_data:
        for row in outbound_flights:
            # 「機場」篩選要用真正的機場代碼當篩選值，所以先把代碼存起來，再把顯示用的欄位換成好懂的名稱
            row["origin_airport_code"] = row.get("origin_city")
            row["destination_airport_code"] = row.get("destination_city")
            row["origin_city"] = _live_airport_label(row.get("origin_city"), origin)
            row["destination_city"] = _live_airport_label(row.get("destination_city"), destination)
            row["layover_city"] = _live_layover_city_label(row.get("layovers"))
    else:
        outbound_flights = _search_flights(origin, destination, pax)  # 去程：出發地 -> 目的地

    # 來回票：即時資料時，SerpApi 第一次查詢回傳的「去程」清單，price 其實已經是 Google 配好最便宜回程的
    # 真實來回總價估計(不是我們自己拿兩段單程價格加起來估的)，每筆都帶 departure_token，
    # 使用者選了某班去程之後，要再帶 departure_token 查一次才能看到「真的配這班去程」的回程選項和真實來回總價，
    # 所以這裡不再另外查一次單程回程清單，選去程的按鈕會導去 visitor_flight_return_options 那個步驟二頁面。
    bundled_roundtrip = is_roundtrip and using_live_data
    return_flights = []
    if is_roundtrip and not using_live_data:
        return_flights = _search_flights(destination, origin, pax)

    all_flights = outbound_flights + return_flights
    # 聯盟是航空公司真正隸屬的公開資料(不是算出來的)，直接幫每筆航班標上聯盟代碼，
    # 這樣就能沿用跟「航空公司」篩選一樣的 facet_options/apply_facets 邏輯，不用另外寫一套。
    for row in all_flights:
        row["alliance"] = flight_links.AIRLINE_ALLIANCE.get(row.get("airline_name"))
        row["stops_label"] = "直飛" if not row.get("stops") else f"轉機 {row['stops']} 次"
        row["departure_minutes"] = _hm_to_minutes(row.get("departure_time"))
        row["arrival_minutes"] = _hm_to_minutes(row.get("arrival_time"))
    flight_price_buckets = price_buckets(all_flights, "price")
    flight_price_max = price_range(all_flights, "price")
    airline_facets = facet_options(all_flights, "airline_name", price_field="price")
    alliance_facets = facet_options(all_flights, "alliance", labels=flight_links.ALLIANCE_NAMES, price_field="price")
    stops_facets = facet_options(all_flights, "stops_label", price_field="price")
    layover_city_facets = facet_options(all_flights, "layover_city", price_field="price")
    aircraft_facets = facet_options(all_flights, "airplane_category", price_field="price")
    origin_airport_labels = {code: _airport_facet_label(code) for code in {r.get("origin_airport_code") for r in all_flights if r.get("origin_airport_code")}}
    destination_airport_labels = {code: _airport_facet_label(code) for code in {r.get("destination_airport_code") for r in all_flights if r.get("destination_airport_code")}}
    origin_airport_facets = facet_options(all_flights, "origin_airport_code", labels=origin_airport_labels, price_field="price")
    destination_airport_facets = facet_options(all_flights, "destination_airport_code", labels=destination_airport_labels, price_field="price")
    duration_bounds = value_range(all_flights, "duration_minutes")
    layover_bounds = value_range(all_flights, "layover_minutes")
    depart_band_options = time_band_options(all_flights, "departure_time")
    facet_fields = (
        ("airline_name", "airline"), ("alliance", "alliance"), ("stops_label", "stops_count"),
        ("layover_city", "layover_city"), ("airplane_category", "aircraft"),
        ("origin_airport_code", "origin_airport"), ("destination_airport_code", "destination_airport"),
    )
    outbound_flights = apply_facets(outbound_flights, facet_fields)
    return_flights = apply_facets(return_flights, facet_fields)
    range_bounds = {"duration": duration_bounds, "layover": layover_bounds, "depart_time": (0, 1439), "arrival_time": (0, 1439)}
    for field, param_prefix in (
        ("duration_minutes", "duration"), ("layover_minutes", "layover"),
        ("departure_minutes", "depart_time"), ("arrival_minutes", "arrival_time"),
    ):
        outbound_flights = apply_value_range(outbound_flights, field, param_prefix, range_bounds[param_prefix])
        return_flights = apply_value_range(return_flights, field, param_prefix, range_bounds[param_prefix])
    outbound_flights = apply_time_band(outbound_flights, "departure_time")
    return_flights = apply_time_band(return_flights, "departure_time")

    # 日期選擇列：即時報價時，其他 6 個日期也各自另外打一次 API 才能拿到那天真正的價格(每天浮動)，
    # cheapest_price() 內建短時間快取，同一條航線/日期不會短時間內重複打，但每次換日期組合最多還是會多花 12 次查詢額度。
    # 本地班表為固定每日資料，票價不分日期，所以不用另外查，直接沿用同一組最低參考價。
    date_strip = []
    strip_prev = strip_next = None
    strip_prices = [row["price"] for row in all_flights if row.get("price")]
    strip_price = min(strip_prices) if strip_prices else None
    if depart_date:
        try:
            base_depart = datetime.strptime(depart_date, "%Y-%m-%d").date()
            base_return = datetime.strptime(return_date, "%Y-%m-%d").date() if return_date else None

            def shifted(offset):
                d = base_depart + timedelta(days=offset)
                r = base_return + timedelta(days=offset) if base_return else None
                return {"depart": d.isoformat(), "return": r.isoformat() if r else ""}

            def strip_lookup(offset):
                d = base_depart + timedelta(days=offset)
                r = base_return + timedelta(days=offset) if base_return else None
                # r 有值時，SerpApi 直接回傳配好最便宜回程的真實來回總價，不用自己查兩段單程再加總。
                # 偶爾單次查詢會逾時或被限流，所以失敗時再試一次，不要讓那天的價格留白。
                for _attempt in range(2):
                    price = _live_cheapest_price(origin, destination, d.isoformat(), pax, return_date=(r.isoformat() if r else None))
                    if price is not None:
                        return price
                return None

            # 6 個日期同時查(原本是一個一個等，慢又容易逾時)
            today = datetime.now().date()
            strip_offsets = [o for o in range(-3, 4) if o != 0 and base_depart + timedelta(days=o) >= today]  # 過去的日期查不到也不能訂，不查
            if using_live_data:
                with ThreadPoolExecutor(max_workers=6) as pool:
                    strip_results = dict(zip(strip_offsets, pool.map(strip_lookup, strip_offsets)))
            else:
                strip_results = {}
            for offset in range(-3, 4):
                if base_depart + timedelta(days=offset) < today:
                    continue  # 日期列不顯示已經過去的日子
                entry = shifted(offset)
                d = base_depart + timedelta(days=offset)
                r = base_return + timedelta(days=offset) if base_return else None
                entry["label"] = f"{d.month}月{d.day}日" + (f"－{r.month}月{r.day}日" if r else "")
                entry["selected"] = offset == 0
                if using_live_data:
                    entry["price"] = strip_price if offset == 0 else strip_results.get(offset)
                else:
                    entry["price"] = strip_price
                date_strip.append(entry)
            strip_prev = shifted(-7)
            strip_next = shifted(7)
        except ValueError:
            date_strip = []

    # 「前往比價訂票」：帶使用者去 Skyscanner 看這條航線的即時報價並完成真正的訂票，
    # 我們自己不用寫金流/結帳。純粹組網址(不是串 API)，查不到城市代碼就不顯示這顆按鈕。
    skyscanner_url = flight_links.skyscanner_search_url(origin, destination, depart_date, return_date if is_roundtrip else None, pax)

    return render_template(
        "flight_search.html",
        adults=adults, children=children, infants=infants,
        transfer_notes=transfer_notes,
        show_more=show_more,
        origin=origin,
        destination=destination,
        depart_date=depart_date,
        return_date=return_date,
        pax=pax,
        outbound_flights=filter_prices(outbound_flights, 'price', 'duration_minutes', 'stops', cabin_field='cabin_class'),
        return_flights=filter_prices(return_flights, 'price', 'duration_minutes', 'stops', cabin_field='cabin_class'),
        price_buckets=flight_price_buckets,
        price_max=flight_price_max,
        airline_facets=airline_facets,
        alliance_facets=alliance_facets,
        stops_facets=stops_facets,
        layover_city_facets=layover_city_facets,
        aircraft_facets=aircraft_facets,
        origin_airport_facets=origin_airport_facets,
        destination_airport_facets=destination_airport_facets,
        duration_bounds=duration_bounds,
        layover_bounds=layover_bounds,
        depart_band_options=depart_band_options,
        date_strip=date_strip,
        strip_price=strip_price,
        strip_prev=strip_prev,
        strip_next=strip_next,
        using_live_data=using_live_data,
        skyscanner_url=skyscanner_url,
        is_roundtrip=bool(is_roundtrip),
        bundled_roundtrip=bundled_roundtrip,
    )


@app.route("/visitor/flights/return-options")  # 來回機票選完去程之後的步驟二：顯示配這班去程的回程選項，每個選項都是真實來回總價
def visitor_flight_return_options():
    origin = request.args.get("from", "").strip()
    destination = request.args.get("to", "").strip()
    depart_date = request.args.get("depart", "").strip()
    return_date = request.args.get("return", "").strip()
    departure_token = request.args.get("departure_token", "").strip()
    pax_raw = request.args.get("pax", "1").strip()
    pax = int(pax_raw) if pax_raw.isdigit() and int(pax_raw) > 0 else 1
    cabin_query = request.args.get("cabin", "").strip() or None  # 跟去程選的艙等一致，才會配到正確的回程選項
    skyscanner_url = flight_links.skyscanner_search_url(origin, destination, depart_date, return_date, pax)
    outbound_item = _parse_outbound_item(request.args.get("ob"))

    return_flights = serpapi_flights.search_return_offers(origin, destination, depart_date, return_date, departure_token, pax, cabin_class=cabin_query)
    if return_flights is None:
        return render_template(
            "flight_return_options.html", origin=origin, destination=destination, depart_date=depart_date,
            return_date=return_date, pax=pax, return_flights=[], lookup_failed=True, skyscanner_url=skyscanner_url,
            outbound_item=outbound_item,
        )

    for row in return_flights:
        row["origin_city"] = _live_airport_label(row.get("origin_city"), destination)
        row["destination_city"] = _live_airport_label(row.get("destination_city"), origin)

    return_flights = filter_prices(return_flights, 'price', 'duration_minutes', 'stops', cabin_field='cabin_class')
    separate_fallback = False
    outbound_single = None
    if not return_flights and not request.args.get("stops"):
        # Google 對少數去程(常見於便宜但轉機很久的組合)回「完全沒有結果」，實測就是沒有配套的來回票。
        # 這時改列出回程當天的「單程」航班，讓旅客至少能分開買回程；價格是單程價，不是來回總價。
        single, live = _live_flight_search(destination, origin, return_date, None, pax, cabin_class=cabin_query)
        if live and single:
            for row in single:
                row["origin_city"] = _live_airport_label(row.get("origin_city"), destination)
                row["destination_city"] = _live_airport_label(row.get("destination_city"), origin)
            return_flights = filter_prices(single, 'price', 'duration_minutes', 'stops', cabin_field='cabin_class')
            separate_fallback = bool(return_flights)
        if separate_fallback and outbound_item:
            # 去程也要能單獨買：查同一天的單程，用班號和起飛時間找出同一班，拿它的單程訂票資料
            # 這類便宜組合常常不在 Google 預設的前幾筆裡，先用一般搜尋找，找不到再用「更多航班」(多花幾次額度)找
            for want_more in (False, True):
                outs, out_live = _live_flight_search(origin, destination, depart_date, None, pax, cabin_class=cabin_query, more=want_more)
                for row in (outs if out_live else []):
                    number = (row.get("flight_number") or "").strip()
                    if number and number in outbound_item["title"] and format_hm(row.get("departure_time")) == outbound_item["start_time"]:
                        row["origin_city"] = _live_airport_label(row.get("origin_city"), origin)
                        row["destination_city"] = _live_airport_label(row.get("destination_city"), destination)
                        outbound_single = row
                        break
                if outbound_single:
                    break

    return render_template(
        "flight_return_options.html",
        origin=origin, destination=destination, depart_date=depart_date, return_date=return_date, pax=pax,
        return_flights=return_flights, separate_fallback=separate_fallback, outbound_single=outbound_single,
        lookup_failed=False, skyscanner_url=skyscanner_url, outbound_item=outbound_item,
    )


@app.route("/visitor/flights/multi-city")  # 多座城市機票搜尋：一次查多段航班，每段都是獨立的單程搜尋；左邊的篩選跟單程/來回完全一樣
def visitor_multi_city_flight_search():
    adults, children, infants, pax = _flight_party()

    try:
        leg_count = int(request.args.get("legs", "2"))
    except ValueError:
        leg_count = 2
    leg_count = max(2, min(6, leg_count))  # 至少 2 段、最多 6 段，避免被亂帶參數灌爆查詢量

    selected_cabin = request.args.get("cabin", "all")
    cabin_query = selected_cabin if selected_cabin != "all" else None

    legs = []
    all_rows = []
    any_live = False
    for i in range(1, leg_count + 1):
        leg_origin = request.args.get(f"from{i}", "").strip()
        leg_destination = request.args.get(f"to{i}", "").strip()
        leg_date = request.args.get(f"date{i}", "").strip()
        flights = None
        leg_is_live = False
        if leg_origin or leg_destination:
            flights, leg_is_live = _live_flight_search(leg_origin, leg_destination, leg_date, None, pax, cabin_class=cabin_query, children=children, infants=infants)
        if leg_is_live:
            for row in flights:
                # 「機場」篩選要用真正的機場代碼當篩選值，所以先存代碼，再把顯示用的欄位換成好懂的名稱
                row["origin_airport_code"] = row.get("origin_city")
                row["destination_airport_code"] = row.get("destination_city")
                row["origin_city"] = _live_airport_label(row.get("origin_city"), leg_origin)
                row["destination_city"] = _live_airport_label(row.get("destination_city"), leg_destination)
                row["layover_city"] = _live_layover_city_label(row.get("layovers"))
        elif leg_origin or leg_destination:
            flights = _search_flights(leg_origin, leg_destination, pax)
        else:
            flights = []
        any_live = any_live or leg_is_live
        all_rows.extend(flights)
        legs.append({
            "index": i,
            "origin": leg_origin,
            "destination": leg_destination,
            "date": leg_date,
            "flights": flights,
            "is_live": leg_is_live,
            "skyscanner_url": flight_links.skyscanner_search_url(leg_origin, leg_destination, leg_date, None, pax),
        })

    # 篩選選項：把所有段的航班合在一起統計(跟單程/來回同一套邏輯)，每一段再各自套用篩選與排序
    for row in all_rows:
        row["alliance"] = flight_links.AIRLINE_ALLIANCE.get(row.get("airline_name"))
        row["stops_label"] = "直飛" if not row.get("stops") else f"轉機 {row['stops']} 次"
        row["departure_minutes"] = _hm_to_minutes(row.get("departure_time"))
        row["arrival_minutes"] = _hm_to_minutes(row.get("arrival_time"))
    origin_airport_labels = {code: _airport_facet_label(code) for code in {r.get("origin_airport_code") for r in all_rows if r.get("origin_airport_code")}}
    destination_airport_labels = {code: _airport_facet_label(code) for code in {r.get("destination_airport_code") for r in all_rows if r.get("destination_airport_code")}}
    facet_fields = (
        ("airline_name", "airline"), ("alliance", "alliance"), ("stops_label", "stops_count"),
        ("layover_city", "layover_city"), ("airplane_category", "aircraft"),
        ("origin_airport_code", "origin_airport"), ("destination_airport_code", "destination_airport"),
    )
    duration_bounds = value_range(all_rows, "duration_minutes")
    layover_bounds = value_range(all_rows, "layover_minutes")
    range_bounds = {"duration": duration_bounds, "layover": layover_bounds, "depart_time": (0, 1439), "arrival_time": (0, 1439)}
    for leg in legs:
        rows = apply_facets(leg["flights"], facet_fields)
        for field, param_prefix in (
            ("duration_minutes", "duration"), ("layover_minutes", "layover"),
            ("departure_minutes", "depart_time"), ("arrival_minutes", "arrival_time"),
        ):
            rows = apply_value_range(rows, field, param_prefix, range_bounds[param_prefix])
        rows = apply_time_band(rows, "departure_time")
        leg["flights"] = filter_prices(rows, "price", "duration_minutes", "stops", cabin_field="cabin_class")

    return render_template(
        "multi_city_flight_search.html",
        legs=legs,
        pax=pax, adults=adults, children=children, infants=infants,
        using_live_data=any_live,
        price_buckets=price_buckets(all_rows, "price"),
        price_max=price_range(all_rows, "price"),
        airline_facets=facet_options(all_rows, "airline_name", price_field="price"),
        alliance_facets=facet_options(all_rows, "alliance", labels=flight_links.ALLIANCE_NAMES, price_field="price"),
        stops_facets=facet_options(all_rows, "stops_label", price_field="price"),
        layover_city_facets=facet_options(all_rows, "layover_city", price_field="price"),
        aircraft_facets=facet_options(all_rows, "airplane_category", price_field="price"),
        origin_airport_facets=facet_options(all_rows, "origin_airport_code", labels=origin_airport_labels, price_field="price"),
        destination_airport_facets=facet_options(all_rows, "destination_airport_code", labels=destination_airport_labels, price_field="price"),
        duration_bounds=duration_bounds,
        layover_bounds=layover_bounds,
        depart_band_options=time_band_options(all_rows, "departure_time"),
    )


@app.route("/visitor/flights/booking-redirect")  # 點「選擇」之後先到這個載入畫面，背景去查這班飛機真正的訂票連結(要等 30~45 秒)
def visitor_flight_booking_redirect():
    return render_template(
        "flight_booking_redirect.html",
        token=request.args.get("token", "").strip(),
        origin=request.args.get("from", "").strip(),
        destination=request.args.get("to", "").strip(),
        depart_date=request.args.get("depart", "").strip(),
        return_date=request.args.get("return", "").strip(),
        pax=request.args.get("pax", "1").strip(),
        fallback_url=request.args.get("fallback", "").strip(),
    )


@app.route("/visitor/flights/booking-redirect/lookup")  # 載入畫面用 AJAX 打這個路由，拿到結果才自動送出表單跳轉
def visitor_flight_booking_redirect_lookup():
    token = request.args.get("token", "").strip()
    origin = request.args.get("from", "").strip()
    destination = request.args.get("to", "").strip()
    depart_date = request.args.get("depart", "").strip()
    return_date = request.args.get("return", "").strip() or None
    pax_raw = request.args.get("pax", "1").strip()
    pax = int(pax_raw) if pax_raw.isdigit() and int(pax_raw) > 0 else 1

    redirect_info = serpapi_flights.get_booking_redirect(origin, destination, depart_date, token, return_date, pax)
    if not redirect_info:
        return jsonify({"ok": False})

    # post_data 是單一一組 key=value(例如 "u=AAcR...")，是 Google 點擊追蹤轉址用的表單資料。
    # 這裡把值解碼出來，交給前端組一個隱藏表單再用瀏覽器原生的表單編碼送出，
    # 避免我們自己手動組 POST body editing 編碼跟 Google 原本預期的不一致。
    post_data = redirect_info["post_data"]
    field_name, _, raw_value = post_data.partition("=")
    field_value = unquote_plus(raw_value)
    return jsonify({
        "ok": True,
        "url": redirect_info["url"],
        "field_name": field_name or "u",
        "field_value": field_value,
        "book_with": redirect_info.get("book_with") or "",
        "price": float(redirect_info["price"]) if redirect_info.get("price") is not None else None,
    })


@app.route("/visitor/trains")  # 設定訪客高鐵／台鐵搜尋結果頁路由(從訪客頁面的高鐵/火車票搜尋表單導入，帶入出發站/到達站/日期/人數)
def visitor_train_search():
    origin = request.args.get("from", "").strip()  # 取得出發站關鍵字
    destination = request.args.get("to", "").strip()  # 取得到達站關鍵字
    travel_date = request.args.get("date", "").strip()  # 取得查詢日期(YYYY-MM-DD)，TDX 依日期查當天班表；本地資料庫是固定每日時刻
    return_date = request.args.get("return", "").strip()
    is_roundtrip = request.args.get('trip_mode') == 'roundtrip' and return_date
    rail = request.args.get("rail", "").strip()  # 使用者選的系統：thsr=高鐵、tra=台鐵；沒選(舊連結)就兩個都查
    if rail not in TRAIN_TYPE_LABELS:
        rail = ""

    pax_raw = request.args.get("pax", "1").strip()  # 取得人數參數(字串)
    pax = int(pax_raw) if pax_raw.isdigit() and int(pax_raw) > 0 else 1  # 驗證人數為正整數，否則預設 1 人

    trains = []  # 預設搜尋結果為空清單
    return_trains = []

    # 優先查交通部 TDX 的真實班表與票價；沒設定金鑰、站名對不到、或 API 失敗(例如超過每分鐘次數限制)，
    # 就自動改用本地資料庫 trains 資料表的固定班表
    live_trains = tdx_trains.search_trains(origin, destination, travel_date, rail)
    using_live_data = live_trains is not None
    if using_live_data:
        trains = live_trains
        if is_roundtrip:
            return_trains = tdx_trains.search_trains(destination, origin, return_date, rail) or []
    connection = None if using_live_data else get_db_connection()

    if connection:
        cursor = connection.cursor(dictionary=True)
        try:
            conditions = ["t.status = 'active'", "t.seats_available >= %s"]  # 只搜尋已啟用且座位足夠的車次
            params = [pax]

            # 英文站名(例如 taipei)先換成中文；本地資料表的站名是中文
            db_origin = tdx_trains.normalize_station(origin) if origin else ""
            db_destination = tdx_trains.normalize_station(destination) if destination else ""
            if db_origin:  # 如果有輸入出發站關鍵字，依站名模糊搜尋
                conditions.append("t.origin_station LIKE %s")
                params.append(f"%{db_origin}%")

            if db_destination:  # 如果有輸入到達站關鍵字，依站名模糊搜尋
                conditions.append("t.destination_station LIKE %s")
                params.append(f"%{db_destination}%")

            if rail:  # 只查使用者選的高鐵或台鐵
                conditions.append("t.train_type = %s")
                params.append(rail)

            where_clause = "WHERE " + " AND ".join(conditions)

            cursor.execute(
                f"""
                SELECT t.train_id, t.train_type, t.train_number, t.car_class,
                       t.origin_station, t.destination_station,
                       t.departure_time, t.arrival_time, t.duration_minutes,
                       t.price, t.seats_available
                FROM trains t
                {where_clause}
                ORDER BY t.departure_time
                """,
                params
            )
            trains = cursor.fetchall()
            if is_roundtrip:
                cursor.execute("""SELECT * FROM trains WHERE status='active' AND seats_available >= %s
                                  AND origin_station LIKE %s AND destination_station LIKE %s
                                  AND (%s = '' OR train_type = %s)
                                  ORDER BY departure_time""", (pax, '%' + db_destination + '%', '%' + db_origin + '%', rail, rail))
                return_trains = cursor.fetchall()
        except Exception as error:  # 如果查詢過程發生錯誤(例如資料表尚未建立)
            print("高鐵／台鐵搜尋查詢失敗：", error)
        finally:
            cursor.close()
            connection.close()

    all_trains = trains + return_trains
    mark_saved_live_trains(all_trains)  # 已收藏的即時車次，愛心要顯示成已收藏
    for row in all_trains:  # 高鐵即時車次的官網連結先指到下面的轉址路由，使用者按下才去高鐵官網加密查詢條件
        if row.get("official_query"):
            row["booking_url"] = url_for("thsr_timetable_redirect", **row["official_query"])
    train_price_buckets = price_buckets(all_trains, "price")
    train_price_max = price_range(all_trains, "price")
    train_type_facets = facet_options(all_trains, "train_type", TRAIN_TYPE_LABELS, price_field="price")
    car_class_facets = facet_options(all_trains, "car_class", price_field="price")
    depart_band_options = time_band_options(all_trains, "departure_time")
    trains = apply_time_band(apply_facets(trains, (("train_type", "train_type"), ("car_class", "car_class"))), "departure_time")
    return_trains = apply_time_band(apply_facets(return_trains, (("train_type", "train_type"), ("car_class", "car_class"))), "departure_time")
    trains = filter_prices(trains, 'price', 'duration_minutes')
    return_trains = filter_prices(return_trains, 'price', 'duration_minutes')
    return render_template(
        "train_search.html",
        origin=origin,
        destination=destination,
        travel_date=travel_date,
        pax=pax,
        rail=rail,
        rail_label=TRAIN_TYPE_LABELS.get(rail, "高鐵／台鐵"),
        trains=trains,
        return_trains=return_trains,
        train_groups=_group_trains(trains),
        return_groups=_group_trains(return_trains),
        price_buckets=train_price_buckets,
        price_max=train_price_max,
        train_type_facets=train_type_facets,
        car_class_facets=car_class_facets,
        depart_band_options=depart_band_options,
        using_live_data=using_live_data,
    )


def _group_trains(rows):
    """同時勾選 2 個以上「車廂等級」(例如普悠瑪、自強、區間)時，結果依車種分組顯示(照勾選的順序)，
    不要不同車種混在一起排；只勾 1 個或都沒勾就維持單一清單。"""
    selected = [c for c in request.args.getlist("car_class") if c]
    if len(selected) < 2 or not rows:
        return [{"label": None, "rows": rows}] if rows else []
    groups = [{"label": name, "rows": [r for r in rows if r.get("car_class") == name]} for name in selected]
    return [g for g in groups if g["rows"]]


@app.route("/visitor/trains/thsr-timetable")  # 轉址到高鐵官網時刻表頁，並帶入這班車的起訖站、日期、時間
def thsr_timetable_redirect():
    origin_id = request.args.get("from", "")
    destination_id = request.args.get("to", "")
    travel_date = request.args.get("date", "")
    start_time = request.args.get("time", "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", travel_date) or not re.fullmatch(r"\d{2}:\d{2}", start_time):
        return redirect(tdx_trains.THSR_TIMETABLE_URL)
    return redirect(tdx_trains.thsr_timetable_url(origin_id, destination_id, travel_date, start_time))


@app.route("/login", methods=["GET", "POST"])  # 設定登入頁路由，允許 GET(顯示表單) 與 POST(送出表單)
def login():  # 定義登入功能函式
    if "user_id" in session:  # 如果已經登入
        return redirect_by_role(session.get("role"))  # 直接依角色導向，不用再登入一次

    if request.method == "POST":  # 如果是表單送出(POST)請求
        username = request.form.get("username", "").strip()  # 取得使用者輸入的帳號或電子郵件並去除頭尾空白
        password = request.form.get("password", "")  # 取得使用者輸入的密碼

        if not username or not password:  # 如果帳號或密碼有一個是空的
            flash("請輸入帳號（或電子郵件）和密碼。", "error")  # 顯示錯誤提示
            return render_template("login.html")  # 重新顯示登入頁

        connection = get_db_connection()  # 嘗試建立資料庫連線

        if connection is None:  # 如果連線失敗
            flash("資料庫連線失敗，請稍後再試。", "error")  # 顯示錯誤提示
            return render_template("login.html")  # 重新顯示登入頁

        cursor = connection.cursor(dictionary=True)  # 建立資料庫游標，查詢結果以字典格式回傳

        try:  # 開始執行查詢，之後不論成功失敗都要關閉連線
            cursor.execute(  # 執行 SQL 查詢
                """
                SELECT user_id, username, password_hash,
                       full_name, nickname, role, status
                FROM users
                WHERE username = %s OR email = %s
                ORDER BY (username = %s) DESC
                LIMIT 1
                """,  # 依帳號或電子郵件查詢使用者資料(只取一筆，帳號完全相符的優先)
                (username, username, username)  # 帶入查詢參數：使用者輸入的帳號或電子郵件
            )

            user = cursor.fetchone()  # 取得查詢結果的第一筆(查無資料則為 None)

        finally:  # 不論上面有沒有出錯，都要執行以下清理動作
            cursor.close()  # 關閉游標
            connection.close()  # 關閉資料庫連線

        if user is None:  # 如果查無此帳號
            flash("帳號或密碼錯誤。", "error")  # 顯示錯誤提示(刻意不區分帳號或密碼錯誤，避免洩漏帳號是否存在)
            return render_template("login.html")  # 重新顯示登入頁

        if user["status"] != "active":  # 如果帳號狀態不是啟用中
            flash(inactive_account_message(user["status"]), "error")
            return render_template("login.html")  # 重新顯示登入頁

        if not user["password_hash"] or not check_password_hash(user["password_hash"], password):  # Google 帳號沒有密碼，或密碼與雜湊值不符
            flash("帳號或密碼錯誤。", "error")  # 密碼不符，顯示錯誤提示
            return render_template("login.html")  # 重新顯示登入頁

        pending_invite_token = session.get("pending_invite_token")  # 清空 session 前先保留邀請連結的 token，避免被清掉
        pending_apply_trip_id = session.get("pending_apply_trip_id")  # 也保留「登入後一鍵套用」的行程
        pending_ai_query = session.get("pending_ai_query")  # 也保留訪客打好的 AI 排行程需求
        pending_favorite_trip_id = session.get("pending_favorite_trip_id")  # 也保留「登入後收藏」的行程
        pending_next = session.get("pending_next")  # 也保留登入前原本要去的頁面
        pending_action = session.get("pending_action")  # 也保留訪客按的收藏／加入行程／上傳照片
        session.clear()  # 登入成功前先清空舊的 session 資料
        session["user_id"] = user["user_id"]  # 把使用者 ID 存入 session
        session["username"] = user["username"]  # 把帳號存入 session
        session["full_name"] = user["full_name"]  # 把姓名存入 session
        session["nickname"] = user["nickname"]  # 把暱稱存入 session
        session["role"] = user["role"]  # 把角色存入 session
        if pending_invite_token:
            session["pending_invite_token"] = pending_invite_token
        if pending_apply_trip_id:
            session["pending_apply_trip_id"] = pending_apply_trip_id
        if pending_ai_query:
            session["pending_ai_query"] = pending_ai_query
        if pending_favorite_trip_id:
            session["pending_favorite_trip_id"] = pending_favorite_trip_id
        if pending_next:
            session["pending_next"] = pending_next
        if pending_action:
            session["pending_action"] = pending_action

        return redirect_by_role(user["role"])  # 登入成功，依角色導向對應首頁

    return render_template("login.html")  # GET 請求，直接顯示登入表單頁


PASSWORD_RESET_TTL_MINUTES = 30  # 重設密碼連結的有效時間(分鐘)


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()

        if not username or not email:
            flash("請輸入帳號和電子郵件。", "error")
            return render_template("forgot_password.html")

        connection = get_db_connection()
        if connection is None:
            flash("資料庫連線失敗，請稍後再試。", "error")
            return render_template("forgot_password.html")

        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT user_id, email, status FROM users WHERE username = %s AND email = %s LIMIT 1",
                (username, email),
            )
            user = cursor.fetchone()
            if user and user["status"] == "active":
                token = secrets.token_urlsafe(32)
                expires_at = datetime.now() + timedelta(minutes=PASSWORD_RESET_TTL_MINUTES)
                cursor.execute(
                    "INSERT INTO password_resets (user_id, token, expires_at) VALUES (%s, %s, %s)",
                    (user["user_id"], token, expires_at),
                )
                connection.commit()
                reset_url = public_url("reset_password", token=token)
                send_password_reset_email(user["email"], reset_url)
        finally:
            cursor.close()
            connection.close()

        # 不論帳號／Email 是否存在或對得上，都顯示同一句訊息，避免讓人用這個表單去試探帳號是否存在
        flash("如果帳號與電子郵件相符，我們已經寄出重設密碼信，請到信箱收信（記得看一下垃圾郵件）。", "success")
        return redirect(url_for("login"))

    return render_template("forgot_password.html")


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗，請稍後再試。", "error")
        return redirect(url_for("login"))

    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT reset_id, user_id, expires_at, used_at FROM password_resets WHERE token = %s LIMIT 1",
            (token,),
        )
        reset_row = cursor.fetchone()

        if not reset_row or reset_row["used_at"] is not None or reset_row["expires_at"] < datetime.now():
            flash("這個重設密碼連結已失效，請重新申請。", "error")
            return redirect(url_for("forgot_password"))

        if request.method == "POST":
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")

            if not re.fullmatch(r"(?=.*[A-Za-z])(?=.*\d)\S{9,}", password):
                flash("密碼至少需要9碼，並同時包含英文與數字。", "error")
                return render_template("reset_password.html", token=token)

            if password != confirm_password:
                flash("兩次輸入的密碼不一致。", "error")
                return render_template("reset_password.html", token=token)

            cursor.execute(
                "UPDATE users SET password_hash = %s WHERE user_id = %s",
                (generate_password_hash(password), reset_row["user_id"]),
            )
            cursor.execute(
                "UPDATE password_resets SET used_at = NOW() WHERE reset_id = %s",
                (reset_row["reset_id"],),
            )
            connection.commit()
            flash("密碼已重設，請用新密碼登入。", "success")
            return redirect(url_for("login"))
    finally:
        cursor.close()
        connection.close()

    return render_template("reset_password.html", token=token)


@app.route("/auth/google/login")
def google_login():
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        flash("Google 登入尚未完成設定，請先使用帳號密碼登入。", "error")
        return redirect(url_for("login"))
    redirect_uri = oauth_callback_url("google_callback")
    try:
        return google_oauth.authorize_redirect(redirect_uri)
    except requests.RequestException:
        app.logger.exception("無法連線至 Google OAuth 服務")
        flash("目前無法連線至 Google 登入服務，請檢查網路後重試，或先使用帳號密碼登入。", "error")
        return redirect(url_for("login"))


@app.route("/auth/google/callback")
def google_callback():
    try:
        token = google_oauth.authorize_access_token()
    except Exception as error:
        print("Google 登入失敗：", error)
        flash("Google 登入失敗，請再試一次。", "error")
        return redirect(url_for("login"))

    userinfo = token.get("userinfo")
    google_sub = userinfo.get("sub") if userinfo else None
    email = userinfo.get("email") if userinfo else None
    if not google_sub or not email or not userinfo.get("email_verified"):
        flash("無法取得已驗證的 Google 帳號資訊，請改用帳號密碼登入。", "error")
        return redirect(url_for("login"))

    full_name = userinfo.get("name") or email.split("@")[0]
    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗，請稍後再試。", "error")
        return redirect(url_for("login"))

    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT user_id, username, full_name, nickname, role, status, google_sub
            FROM users
            WHERE google_sub = %s OR email = %s
            LIMIT 1
            """,
            (google_sub, email),
        )
        user = cursor.fetchone()
        if user is None:
            username = generate_unique_username(cursor, email.split("@")[0])
            cursor.execute(
                """
                INSERT INTO users
                (username, password_hash, full_name, nickname, email, google_sub, role, status)
                VALUES (%s, NULL, %s, %s, %s, %s, 'member', 'active')
                """,
                (username, full_name, full_name, email, google_sub),
            )
            connection.commit()
            cursor.execute(
                """
                SELECT user_id, username, full_name, nickname, role, status, google_sub
                FROM users WHERE user_id = %s
                """,
                (cursor.lastrowid,),
            )
            user = cursor.fetchone()
        elif not user["google_sub"]:
            cursor.execute(
                "UPDATE users SET google_sub = %s WHERE user_id = %s",
                (google_sub, user["user_id"]),
            )
            connection.commit()
    except Error as error:
        connection.rollback()
        print("Google 登入建立帳號失敗：", error)
        flash("Google 登入失敗，請稍後再試。", "error")
        return redirect(url_for("login"))
    finally:
        cursor.close()
        connection.close()

    if user["status"] != "active":
        flash(inactive_account_message(user["status"]), "error")
        return redirect(url_for("login"))

    pending_invite_token = session.get("pending_invite_token")
    pending_apply_trip_id = session.get("pending_apply_trip_id")
    pending_ai_query = session.get("pending_ai_query")
    pending_favorite_trip_id = session.get("pending_favorite_trip_id")
    pending_next = session.get("pending_next")
    pending_action = session.get("pending_action")
    session.clear()
    session["user_id"] = user["user_id"]
    session["username"] = user["username"]
    session["full_name"] = user["full_name"]
    session["nickname"] = user["nickname"]
    session["role"] = user["role"]
    if pending_invite_token:
        session["pending_invite_token"] = pending_invite_token
    if pending_apply_trip_id:
        session["pending_apply_trip_id"] = pending_apply_trip_id
    if pending_ai_query:
        session["pending_ai_query"] = pending_ai_query
    if pending_favorite_trip_id:
        session["pending_favorite_trip_id"] = pending_favorite_trip_id
    if pending_next:
        session["pending_next"] = pending_next
    if pending_action:
        session["pending_action"] = pending_action
    return redirect_by_role(user["role"])


@app.route("/auth/line/login")
def line_login():
    if not LINE_CHANNEL_ID or not LINE_CHANNEL_SECRET:
        flash("LINE 登入尚未完成設定，請先使用帳號密碼登入。", "error")
        return redirect(url_for("login"))
    redirect_uri = oauth_callback_url("line_callback")
    # bot_prompt：登入同意畫面會一併詢問是否加入官方帳號好友
    # （需先在 LINE Login channel 的 Linked LINE Official Account 選好官方帳號才會出現）
    return line_oauth.authorize_redirect(redirect_uri, bot_prompt="aggressive")


@app.route("/auth/line/bind")
def line_bind():
    if session.get("role") != "member":
        return redirect(url_for("login"))
    if not LINE_CHANNEL_ID or not LINE_CHANNEL_SECRET:
        flash("LINE 尚未完成設定，暫時無法綁定。", "error")
        return redirect(url_for("member.profile"))
    session["line_bind_user_id"] = session["user_id"]
    next_url = safe_next_url(request.args.get("next"))
    if next_url:
        session["line_bind_next"] = next_url
    else:
        session.pop("line_bind_next", None)
    return line_oauth.authorize_redirect(oauth_callback_url("line_callback"), bot_prompt="aggressive")


@app.route("/auth/line/unbind", methods=["POST"])
def line_unbind():
    if session.get("role") != "member":
        return redirect(url_for("login"))
    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗，請稍後再試。", "error")
        return redirect(url_for("member.profile"))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT password_hash,google_sub FROM users WHERE user_id=%s", (session["user_id"],))
        user = cursor.fetchone()
        if user and not user["password_hash"] and not user["google_sub"]:
            flash("這個帳號只能用 LINE 登入，請先設定其他登入方式再解除綁定。", "error")
            return redirect(url_for("member.profile"))
        cursor.execute("UPDATE users SET line_sub=NULL,line_friend=0 WHERE user_id=%s", (session["user_id"],))
        connection.commit()
        flash("已解除 LINE 綁定。", "success")
    except Error as error:
        connection.rollback()
        print("解除 LINE 綁定失敗：", error)
        flash("解除綁定失敗，請稍後再試。", "error")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for("member.profile"))


def bind_line_to_current_user(line_sub, friend_flag, next_url=None):
    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗，請稍後再試。", "error")
        return redirect(url_for("member.profile"))
    cursor = connection.cursor(dictionary=True)
    redirect_url = url_for("member.profile")
    try:
        cursor.execute("SELECT user_id FROM users WHERE line_sub=%s AND user_id<>%s LIMIT 1",
                       (line_sub, session["user_id"]))
        if cursor.fetchone():
            flash("這個 LINE 已經綁定其他帳號。", "error")
            return redirect(url_for("member.profile"))
        cursor.execute("UPDATE users SET line_sub=%s,line_friend=%s WHERE user_id=%s",
                       (line_sub, 1 if friend_flag else 0, session["user_id"]))
        connection.commit()
        flash("LINE 綁定完成！" + ("之後會收到行程提醒。" if friend_flag else "請再加入官方帳號好友。"), "success")
        redirect_url = next_url or redirect_url
    except Error as error:
        connection.rollback()
        print("綁定 LINE 失敗：", error)
        flash("綁定 LINE 失敗，請稍後再試。", "error")
    finally:
        cursor.close()
        connection.close()
    return redirect(redirect_url)


def fetch_line_friend_flag(access_token):  # 查詢使用者是否為官方帳號好友，查不到時回傳 None
    try:
        response = requests.get(
            "https://api.line.me/friendship/v1/status",
            headers={"Authorization": "Bearer " + access_token},
            timeout=10,
        )
        response.raise_for_status()
        return bool(response.json().get("friendFlag"))
    except (requests.RequestException, ValueError) as error:
        print("查詢 LINE 好友狀態失敗：", error)
        return None


@app.route("/auth/line/callback")
def line_callback():
    bind_user_id = session.pop("line_bind_user_id", None)
    bind_next_url = session.pop("line_bind_next", None)
    binding = bind_user_id is not None and bind_user_id == session.get("user_id")
    fail_redirect = url_for("member.profile") if binding else url_for("login")
    try:
        token = line_oauth.authorize_access_token()
        profile_response = requests.get(
            "https://api.line.me/v2/profile",
            headers={"Authorization": "Bearer " + token["access_token"]},
            timeout=10,
        )
        profile_response.raise_for_status()
        profile = profile_response.json()
        friend_flag = fetch_line_friend_flag(token["access_token"])
    except (Exception, requests.RequestException) as error:
        print("LINE 登入失敗：", error)
        flash("LINE 綁定失敗，請再試一次。" if binding else "LINE 登入失敗，請再試一次。", "error")
        return redirect(fail_redirect)

    line_sub = profile.get("userId")
    if not line_sub:
        flash("無法取得 LINE 帳號資訊，請改用其他方式登入。", "error")
        return redirect(fail_redirect)

    if binding:
        return bind_line_to_current_user(line_sub, friend_flag, next_url=bind_next_url)
    return finish_line_login(line_sub, profile.get("displayName"), friend_flag)


def finish_line_login(line_sub, display_name, friend_flag, next_url=None):  # LINE 登入與 LIFF 共用：找到綁定的帳號就登入，找不到就進入補填資料註冊
    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗，請稍後再試。", "error")
        return redirect(url_for("login"))

    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT user_id, username, full_name, nickname, role, status
            FROM users WHERE line_sub = %s LIMIT 1
            """,
            (line_sub,),
        )
        user = cursor.fetchone()
        if user is not None and friend_flag is not None:  # 順便同步官方帳號好友狀態
            cursor.execute(
                "UPDATE users SET line_friend = %s WHERE user_id = %s",
                (1 if friend_flag else 0, user["user_id"]),
            )
            connection.commit()
    except Error as error:
        print("LINE 登入查詢帳號失敗：", error)
        flash("LINE 登入失敗，請稍後再試。", "error")
        return redirect(url_for("login"))
    finally:
        cursor.close()
        connection.close()

    if user is None:
        session["pending_line_sub"] = line_sub
        session["pending_line_name"] = display_name or "LINE 使用者"
        session["pending_line_friend"] = 1 if friend_flag else 0
        return redirect(url_for("line_complete_profile"))

    if user["status"] != "active":
        flash(inactive_account_message(user["status"]), "error")
        return redirect(url_for("login"))

    pending_invite_token = session.get("pending_invite_token")
    pending_apply_trip_id = session.get("pending_apply_trip_id")
    pending_ai_query = session.get("pending_ai_query")
    pending_favorite_trip_id = session.get("pending_favorite_trip_id")
    pending_next = session.get("pending_next")
    pending_action = session.get("pending_action")
    session.clear()
    session.update(
        user_id=user["user_id"], username=user["username"],
        full_name=user["full_name"], nickname=user["nickname"], role=user["role"],
    )
    if pending_invite_token:
        session["pending_invite_token"] = pending_invite_token
    if pending_apply_trip_id:
        session["pending_apply_trip_id"] = pending_apply_trip_id
    if pending_ai_query:
        session["pending_ai_query"] = pending_ai_query
    if pending_favorite_trip_id:
        session["pending_favorite_trip_id"] = pending_favorite_trip_id
    if pending_next:
        session["pending_next"] = pending_next
    if pending_action:
        session["pending_action"] = pending_action
    if next_url and not pending_invite_token and not pending_apply_trip_id and not pending_ai_query and not pending_favorite_trip_id and not pending_action:
        return redirect(next_url)
    return redirect_by_role(user["role"])


def safe_next_url(value):  # 只允許站內路徑，避免被當成跳轉到外部網站的跳板
    value = (value or "").strip()
    if value.startswith("/") and not value.startswith("//") and "\\" not in value:
        return value
    return None


@app.route("/liff")
@app.route("/liff/<path:subpath>")
def liff_entry(subpath=""):  # LIFF 入口：在 LINE 裡打開時自動用 LINE 身分登入網站，再轉到目標頁面
    if not LIFF_ID:
        flash("LIFF 尚未設定，請先使用一般方式登入。", "error")
        return redirect(url_for("login"))
    return render_template("liff.html", liff_id=LIFF_ID)


@app.route("/auth/liff", methods=["POST"])
def liff_login():  # LIFF 頁面拿到 LINE 的 ID token 後送來這裡驗證並登入
    next_url = safe_next_url(request.form.get("next")) or url_for("member.dashboard")
    try:
        response = requests.post(  # 請 LINE 驗證 ID token，確認是發給我們 LINE Login channel 的
            "https://api.line.me/oauth2/v2.1/verify",
            data={"id_token": request.form.get("id_token", ""), "client_id": LINE_CHANNEL_ID},
            timeout=10,
        )
        response.raise_for_status()
        claims = response.json()
    except (requests.RequestException, ValueError) as error:
        print("LIFF 登入驗證失敗：", error)
        flash("LINE 自動登入失敗，請改用一般方式登入。", "error")
        return redirect(url_for("login"))

    line_sub = claims.get("sub")
    if not line_sub:
        flash("無法取得 LINE 帳號資訊，請改用一般方式登入。", "error")
        return redirect(url_for("login"))
    friend_flag = {"1": True, "0": False}.get(request.form.get("friend"))  # 前端查不到好友狀態時是空值

    if session.get("role") == "member":  # 已經登入的會員：就是這個 LINE 的帳號，或帳號還沒綁 LINE，都直接沿用目前登入狀態
        connection = get_db_connection()
        if connection is not None:
            cursor = connection.cursor()
            try:
                cursor.execute("SELECT line_sub FROM users WHERE user_id = %s", (session["user_id"],))
                row = cursor.fetchone()
            finally:
                cursor.close()
                connection.close()
            if row and row[0] == line_sub:
                return redirect(next_url)
            if row and not row[0]:
                flash("你的 LINE 還沒綁定這個帳號，可以到個人資料頁按「綁定 LINE」。", "success")
                return redirect(next_url)
    return finish_line_login(line_sub, claims.get("name"), friend_flag, next_url)


@app.route("/auth/line/complete-profile", methods=["GET", "POST"])
def line_complete_profile():
    line_sub = session.get("pending_line_sub")
    full_name = session.get("pending_line_name")
    if not line_sub:
        flash("請重新使用 LINE 登入。", "error")
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template("line_complete_profile.html", full_name=full_name)

    email = request.form.get("email", "").strip()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        flash("請輸入正確的電子郵件格式。", "error")
        return render_template("line_complete_profile.html", full_name=full_name)

    nickname = request.form.get("nickname", "").strip()[:50] or full_name  # 暱稱沒填就沿用 LINE 名稱
    password = request.form.get("password", "")
    if not re.fullmatch(r"(?=.*[A-Za-z])(?=.*\d)\S{9,}", password):  # 跟一般註冊一樣：9 碼以上且同時包含英文與數字
        flash("密碼至少需要9碼，並同時包含英文與數字。", "error")
        return render_template("line_complete_profile.html", full_name=full_name)
    if password != request.form.get("confirm_password", ""):
        flash("兩次輸入的密碼不一致。", "error")
        return render_template("line_complete_profile.html", full_name=full_name)

    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗，請稍後再試。", "error")
        return render_template("line_complete_profile.html", full_name=full_name)

    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT user_id FROM users WHERE email = %s LIMIT 1", (email,))
        if cursor.fetchone():
            flash("這個電子郵件已經被使用，請換一個。", "error")
            return render_template("line_complete_profile.html", full_name=full_name)

        username = generate_unique_username(cursor, line_sub)
        cursor.execute(
            """
            INSERT INTO users
            (username, password_hash, full_name, nickname, email, line_sub, line_friend, role, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'member', 'active')
            """,
            (username, generate_password_hash(password), full_name, nickname, email, line_sub, session.get("pending_line_friend", 0)),
        )
        new_user_id = cursor.lastrowid
        connection.commit()
        cursor.execute(
            """
            SELECT user_id, username, full_name, nickname, role
            FROM users WHERE user_id = %s
            """,
            (new_user_id,),
        )
        user = cursor.fetchone()
    except Error as error:
        connection.rollback()
        print("LINE 登入建立帳號失敗：", error)
        flash("註冊失敗，請稍後再試。", "error")
        return render_template("line_complete_profile.html", full_name=full_name)
    finally:
        cursor.close()
        connection.close()

    pending_invite_token = session.get("pending_invite_token")
    pending_apply_trip_id = session.get("pending_apply_trip_id")
    pending_ai_query = session.get("pending_ai_query")
    pending_favorite_trip_id = session.get("pending_favorite_trip_id")
    pending_next = session.get("pending_next")
    pending_action = session.get("pending_action")
    session.clear()
    session.update(
        user_id=user["user_id"], username=user["username"],
        full_name=user["full_name"], nickname=user["nickname"], role=user["role"],
    )
    if pending_invite_token:
        session["pending_invite_token"] = pending_invite_token
    if pending_apply_trip_id:
        session["pending_apply_trip_id"] = pending_apply_trip_id
    if pending_ai_query:
        session["pending_ai_query"] = pending_ai_query
    if pending_favorite_trip_id:
        session["pending_favorite_trip_id"] = pending_favorite_trip_id
    if pending_next:
        session["pending_next"] = pending_next
    if pending_action:
        session["pending_action"] = pending_action
    return redirect_by_role(user["role"])


@app.route("/register", methods=["GET", "POST"])  # 設定註冊頁路由
def register():  # 定義註冊功能函式
    if request.method == "POST":  # 如果是表單送出請求
        username = request.form.get("username", "").strip()  # 取得帳號輸入值
        full_name = request.form.get("full_name", "").strip()  # 取得姓名輸入值
        nickname = request.form.get("nickname", "").strip()  # 取得暱稱輸入值
        email = request.form.get("email", "").strip()  # 取得 Email 輸入值
        password = request.form.get("password", "")  # 取得密碼輸入值
        confirm_password = request.form.get("confirm_password", "")  # 取得確認密碼輸入值

        if not username or not full_name or not email or not password:  # 檢查必填欄位是否都有填
            flash("請填寫所有必填欄位。", "error")  # 顯示錯誤提示
            return render_template("register.html")  # 重新顯示註冊頁

        if not re.fullmatch(r"[A-Za-z0-9]{1,9}", username):  # 帳號限制為 9 碼以內的英文或數字
            flash("帳號請輸入9碼以內的英文或數字。", "error")  # 顯示錯誤提示
            return render_template("register.html")  # 重新顯示註冊頁

        if not re.fullmatch(r"[A-Za-z一-龥][A-Za-z一-龥\s]*", full_name):  # 姓名僅允許中英文字與空白，不可包含數字或符號
            flash("姓名請輸入真實姓名，不可包含數字或特殊符號。", "error")  # 顯示錯誤提示
            return render_template("register.html")  # 重新顯示註冊頁

        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):  # Email 需符合含有 @ 與網域的基本格式
            flash("請輸入正確的電子郵件格式。", "error")  # 顯示錯誤提示
            return render_template("register.html")  # 重新顯示註冊頁

        if not re.fullmatch(r"(?=.*[A-Za-z])(?=.*\d)\S{9,}", password):  # 密碼需 9 碼以上且同時包含英文與數字
            flash("密碼至少需要9碼，並同時包含英文與數字。", "error")  # 顯示錯誤提示
            return render_template("register.html")  # 重新顯示註冊頁

        if password != confirm_password:  # 檢查兩次輸入的密碼是否一致
            flash("兩次輸入的密碼不一致。", "error")  # 顯示錯誤提示
            return render_template("register.html")  # 重新顯示註冊頁

        connection = get_db_connection()  # 嘗試建立資料庫連線

        if connection is None:  # 如果連線失敗
            flash("資料庫連線失敗，請稍後再試。", "error")  # 顯示錯誤提示
            return render_template("register.html")  # 重新顯示註冊頁

        cursor = connection.cursor(dictionary=True)  # 建立字典格式的資料庫游標

        try:  # 開始執行資料庫操作
            cursor.execute(  # 查詢帳號或 Email 是否已被使用
                """
                SELECT user_id
                FROM users
                WHERE username = %s OR email = %s
                LIMIT 1
                """,  # 只要帳號或 Email 其中一個重複就算已存在
                (username, email)  # 帶入查詢參數
            )

            existing_user = cursor.fetchone()  # 取得查詢結果

            if existing_user:  # 如果已經有相同帳號或 Email 的使用者
                flash("帳號或電子郵件已被使用。", "error")  # 顯示錯誤提示
                return render_template("register.html")  # 重新顯示註冊頁

            password_hash = generate_password_hash(password)  # 把明文密碼轉換成雜湊值，不儲存明文密碼

            cursor.execute(  # 執行新增使用者的 SQL
                """
                INSERT INTO users
                (username, password_hash, full_name, nickname,
                 email, role, status)
                VALUES (%s, %s, %s, %s, %s, 'member', 'active')
                """,  # 新帳號預設角色為一般會員(member)、狀態為啟用(active)
                (
                    username,  # 帳號
                    password_hash,  # 密碼雜湊值
                    full_name,  # 姓名
                    nickname or None,  # 暱稱，若空字串則存 NULL
                    email  # Email
                )
            )

            connection.commit()  # 提交交易，正式寫入資料庫

        except Error as error:  # 如果資料庫操作發生錯誤
            connection.rollback()  # 回復交易，避免留下不完整的資料
            print("註冊失敗：", error)  # 在伺服器端印出錯誤內容方便除錯
            flash("註冊失敗，請稍後再試。", "error")  # 顯示錯誤提示給使用者
            return render_template("register.html")  # 重新顯示註冊頁

        finally:  # 不論成功或失敗都要執行
            cursor.close()  # 關閉游標
            connection.close()  # 關閉資料庫連線

        flash("註冊成功，請使用新帳號登入。", "success")  # 顯示註冊成功訊息
        return redirect(url_for("login"))  # 導向登入頁

    return render_template("register.html")  # GET 請求，顯示註冊表單頁


@app.route("/member")  # 設定會員首頁路由
def member_home():  # 定義會員首頁導向函式
    if "user_id" not in session:  # 如果尚未登入
        return redirect(url_for("login"))  # 導向登入頁

    if session.get("role") != "member":  # 如果登入者角色不是一般會員
        return redirect_by_role(session.get("role"))  # 依實際角色導向對應首頁

    return redirect(url_for("member.dashboard"))  # 轉導到會員藍圖裡的會員儀表板路由


@app.route("/content-admin")  # 設定內容管理員首頁路由
def content_admin_home():  # 定義內容管理員儀表板函式
    if "user_id" not in session:  # 如果尚未登入
        return redirect(url_for("login"))  # 導向登入頁

    if session.get("role") != "content_admin":  # 如果角色不是內容管理員
        return redirect_by_role(session.get("role"))  # 依實際角色導向對應首頁

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return render_template(  # 回傳儀表板頁面，所有統計數字都給預設值 0 或空陣列
            "content_admin_home.html",
            attraction_count=0, restaurant_count=0, accommodation_count=0,
            pending_proposal_count=0, top_attractions=[], top_restaurants=[],
            top_accommodations=[]
        )

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 開始查詢各項統計資料
        cursor.execute("SELECT COUNT(*) AS total FROM attractions WHERE deleted_at IS NULL")  # 查詢景點總數(不含回收桶裡的)
        attraction_count = cursor.fetchone()["total"]  # 取出景點總數

        cursor.execute("SELECT COUNT(*) AS total FROM restaurants WHERE deleted_at IS NULL")  # 查詢餐廳總數(不含回收桶裡的)
        restaurant_count = cursor.fetchone()["total"]  # 取出餐廳總數

        cursor.execute("SELECT COUNT(*) AS total FROM accommodations WHERE deleted_at IS NULL")  # 查詢住宿總數(不含回收桶裡的)
        accommodation_count = cursor.fetchone()["total"]  # 取出住宿總數

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM proposals
            WHERE content_review_status = 'pending'
        """)  # 查詢待審核提案數量
        pending_proposal_count = cursor.fetchone()["total"]  # 取出待審核提案數

        cursor.execute("""
            SELECT name, country, city, favorite_count, itinerary_count
            FROM vw_popular_attractions
            ORDER BY (favorite_count + itinerary_count) DESC, name
            LIMIT 5
        """)  # 從熱門景點檢視表查詢，依收藏數+行程使用數排序，取前5筆
        top_attractions = cursor.fetchall()  # 取出熱門景點清單

        cursor.execute("""
            SELECT r.name, co.name AS country, ci.name AS city,
                   COUNT(i.itinerary_id) AS itinerary_count
            FROM restaurants r
            JOIN countries co ON co.country_id = r.country_id
            JOIN cities ci ON ci.city_id = r.city_id
            LEFT JOIN itineraries i ON i.restaurant_id = r.restaurant_id
            WHERE r.deleted_at IS NULL
            GROUP BY r.restaurant_id, r.name, co.name, ci.name
            ORDER BY itinerary_count DESC, r.name
            LIMIT 5
        """)  # 查詢餐廳被排入行程的次數，取使用次數最多的前5筆(不含回收桶裡的)
        top_restaurants = cursor.fetchall()  # 取出熱門餐廳清單

        cursor.execute("""
            SELECT ac.name, co.name AS country, ci.name AS city,
                   COUNT(i.itinerary_id) AS itinerary_count
            FROM accommodations ac
            JOIN countries co ON co.country_id = ac.country_id
            JOIN cities ci ON ci.city_id = ac.city_id
            LEFT JOIN itineraries i ON i.accommodation_id = ac.accommodation_id
            WHERE ac.deleted_at IS NULL
            GROUP BY ac.accommodation_id, ac.name, co.name, ci.name
            ORDER BY itinerary_count DESC, ac.name
            LIMIT 5
        """)  # 查詢住宿被排入行程的次數，取使用次數最多的前5筆(不含回收桶裡的)
        top_accommodations = cursor.fetchall()  # 取出熱門住宿清單

        status_distribution = []  # 準備景點/餐廳/住宿各自的狀態分布統計
        for label, table in [("景點", "attractions"), ("餐廳", "restaurants"), ("住宿", "accommodations")]:  # 依序查詢三種資源類型(資料表名稱固定寫死，非使用者輸入，可安全用於 SQL)
            cursor.execute(f"SELECT status, COUNT(*) AS total FROM {table} WHERE deleted_at IS NULL GROUP BY status")  # 依狀態分組計算數量(不含回收桶裡的)
            counts = {row["status"]: row["total"] for row in cursor.fetchall()}  # 整理成 {狀態: 數量} 字典
            status_distribution.append({  # 加入這個資源類型的統計結果
                "label": label,  # 中文顯示名稱
                "active": counts.get("active", 0),  # 啟用數量，沒有就是 0
                "pending": counts.get("pending", 0),  # 待確認數量，沒有就是 0
                "hidden": counts.get("hidden", 0),  # 隱藏數量，沒有就是 0
            })

    except Error as error:  # 如果查詢過程中資料庫報錯(例如資料表結構還沒更新)
        print("內容管理資料庫結構尚未更新：", error)  # 在伺服器端印出錯誤內容
        flash("資料庫結構尚未更新，請先執行 database/migrate_0812_content_admin.sql。", "error")  # 提示使用者要先執行遷移腳本
        attraction_count = 0  # 景點總數退回預設值
        restaurant_count = 0  # 餐廳總數退回預設值
        accommodation_count = 0  # 住宿總數退回預設值
        pending_proposal_count = 0  # 待審核提案數退回預設值
        top_attractions = []  # 熱門景點清單退回空陣列
        top_restaurants = []  # 熱門餐廳清單退回空陣列
        top_accommodations = []  # 熱門住宿清單退回空陣列
        status_distribution = []  # 狀態分布統計退回空陣列

    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return render_template(  # 渲染內容管理員儀表板頁面，帶入所有統計資料
        "content_admin_home.html",
        attraction_count=attraction_count,  # 景點總數
        restaurant_count=restaurant_count,  # 餐廳總數
        accommodation_count=accommodation_count,  # 住宿總數
        pending_proposal_count=pending_proposal_count,  # 待審核提案數
        top_attractions=top_attractions,  # 熱門景點清單
        top_restaurants=top_restaurants,  # 熱門餐廳清單
        top_accommodations=top_accommodations,  # 熱門住宿清單
        status_distribution=status_distribution,  # 景點/餐廳/住宿的狀態分布統計
    )


@app.route("/system-admin")  # 設定系統管理員首頁路由
def system_admin_home():  # 定義系統管理員儀表板函式

    # 檢查是否登入
    if "user_id" not in session:  # 如果尚未登入
        return redirect(url_for("login"))  # 導向登入頁

    # 只有 system_admin 可以進入
    if session.get("role") != "system_admin":  # 如果角色不是系統管理員
        return redirect(url_for("login"))  # 導向登入頁

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return render_template(  # 回傳儀表板頁面，統計數字給預設值 0
            "system_admin_home.html",
            member_count=0,
            content_admin_count=0,
            trip_count=0,
            public_trip_count=0,
            issue_count=0
        )

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 開始查詢各項統計資料

        # 一般會員數量
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM users
            WHERE role = 'member'
            AND status != 'deleted'
        """)  # 統計角色為會員且未被刪除的人數

        member_count = cursor.fetchone()["total"]  # 取出會員總數

        # 旅遊內容管理員數量
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM users
            WHERE role = 'content_admin'
            AND status != 'deleted'
        """)  # 統計角色為內容管理員且未被刪除的人數

        content_admin_count = cursor.fetchone()["total"]  # 取出內容管理員總數

        # 所有行程數量
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM trips
            WHERE deleted_at IS NULL
        """)  # 統計所有行程數量

        trip_count = cursor.fetchone()["total"]  # 取出行程總數

        # 公開行程數量
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM trips
            WHERE visibility = 'public' AND moderation_status = 'visible' AND deleted_at IS NULL
        """)  # 統計可見度為公開的行程數量

        public_trip_count = cursor.fetchone()["total"]  # 取出公開行程總數

        cursor.execute("""
            SELECT COUNT(*) AS total FROM reports
            WHERE target_type = 'trip' AND reason LIKE %s AND status = 'pending'
        """, (ISSUE_PREFIX + "%",))
        issue_count = cursor.fetchone()["total"]

        # 最近加入會員
        cursor.execute("""
            SELECT user_id,
                   username,
                   full_name,
                   email,
                   status,
                   created_at
            FROM users
            WHERE role = 'member'
            AND status != 'deleted'
            ORDER BY created_at DESC
            LIMIT 5
        """)  # 查詢最近註冊的 5 位會員資料

        recent_users = cursor.fetchall()  # 取出最近加入會員清單

    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return render_template(  # 渲染系統管理員儀表板頁面
        "system_admin_home.html",
        member_count=member_count,  # 會員總數
        content_admin_count=content_admin_count,  # 內容管理員總數
        trip_count=trip_count,  # 行程總數
        public_trip_count=public_trip_count,  # 公開行程總數
        issue_count=issue_count,
        recent_users=recent_users  # 最近加入會員清單
    )
@app.route("/system-admin/users")  # 設定會員管理列表頁路由
def admin_users():  # 定義會員管理列表函式

    if "user_id" not in session:  # 如果尚未登入
        return redirect(url_for("login"))  # 導向登入頁

    if session.get("role") != "system_admin":  # 如果角色不是系統管理員
        return redirect(url_for("login"))  # 導向登入頁

    keyword = request.args.get("keyword", "").strip()  # 取得網址上的搜尋關鍵字參數
    status_filter = request.args.get("status", "").strip()
    if status_filter not in USER_STATUS_LABELS:
        status_filter = ""

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return render_template(
            "admin_users.html", users=[], keyword=keyword,
            status_filter=status_filter, status_labels=USER_STATUS_LABELS,
        )

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 開始查詢帳號資料
        conditions = ["1 = 1"]
        params = []

        if keyword:  # 如果有輸入搜尋關鍵字
            search = "%" + keyword + "%"  # 組成 SQL LIKE 模糊搜尋用的字串
            conditions.append("(u.username LIKE %s OR u.full_name LIKE %s OR u.email LIKE %s)")
            params.extend([search, search, search])

        if status_filter:
            conditions.append("u.status = %s")
            params.append(status_filter)

        cursor.execute(f"""
            SELECT u.user_id, u.username, u.full_name, u.nickname, u.email,
                   u.role, u.status, u.created_at,
                   (SELECT COUNT(*) FROM trips t
                    WHERE t.owner_id = u.user_id AND t.deleted_at IS NULL) AS trip_count,
                   (SELECT COUNT(*) FROM reports r
                    WHERE r.reporter_id = u.user_id
                      AND r.target_type = 'trip' AND r.reason LIKE %s) AS issue_count
            FROM users u
            WHERE {' AND '.join(conditions)}
            ORDER BY FIELD(u.status, 'under_review', 'active', 'disabled', 'deleted'),
                     FIELD(u.role, 'system_admin', 'content_admin', 'member'),
                     u.user_id DESC
        """, tuple([ISSUE_PREFIX + "%"] + params))

        users = cursor.fetchall()  # 取出查詢結果

    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return render_template(  # 渲染會員管理列表頁面
        "admin_users.html",
        users=users,  # 會員清單
        keyword=keyword,  # 搜尋關鍵字(用來顯示在搜尋框裡)
        status_filter=status_filter,
        status_labels=USER_STATUS_LABELS,
    )


@app.route("/system-admin/users/<int:user_id>")
def admin_user_detail(user_id):
    denied = system_admin_required()
    if denied:
        return denied

    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("admin_users"))

    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT user_id, username, full_name, nickname, email, phone,
                   avatar_path, role, status, last_login_at, created_at, updated_at
            FROM users
            WHERE user_id = %s
        """, (user_id,))
        user = cursor.fetchone()
        if user is None:
            flash("找不到指定帳號", "error")
            return redirect(url_for("admin_users"))

        cursor.execute("""
            SELECT COUNT(*) AS trip_count,
                   COALESCE(SUM(visibility = 'public' AND moderation_status = 'visible'), 0) AS public_trip_count
            FROM trips
            WHERE owner_id = %s AND deleted_at IS NULL
        """, (user_id,))
        trip_counts = cursor.fetchone()

        cursor.execute("""
            SELECT COUNT(*) AS issue_count
            FROM reports
            WHERE reporter_id = %s AND target_type = 'trip' AND reason LIKE %s
        """, (user_id, ISSUE_PREFIX + "%"))
        issue_count = cursor.fetchone()["issue_count"]

        cursor.execute("""
            SELECT t.trip_id, t.trip_name, t.visibility, t.status,
                   t.start_date, t.end_date, t.created_at,
                   co.name AS country_name, ci.name AS city_name
            FROM trips t
            LEFT JOIN countries co ON co.country_id = t.country_id
            LEFT JOIN cities ci ON ci.city_id = t.city_id
            WHERE t.owner_id = %s AND t.deleted_at IS NULL
            ORDER BY t.created_at DESC
            LIMIT 100
        """, (user_id,))
        trips = cursor.fetchall()

        cursor.execute("""
            SELECT r.report_id, r.target_id AS trip_id, r.reason, r.description,
                   r.status, r.handling_result, r.created_at, r.handled_at,
                   t.trip_name, handler.username AS handler_username
            FROM reports r
            LEFT JOIN trips t ON t.trip_id = r.target_id
            LEFT JOIN users handler ON handler.user_id = r.handled_by
            WHERE r.reporter_id = %s AND r.target_type = 'trip' AND r.reason LIKE %s
            ORDER BY r.created_at DESC
            LIMIT 100
        """, (user_id, ISSUE_PREFIX + "%"))
        issues = cursor.fetchall()
        for issue in issues:
            issue["reason"] = issue["reason"][len(ISSUE_PREFIX):]

        cursor.execute("""
            SELECT h.moderation_id, h.action, h.from_status, h.to_status,
                   h.reason, h.created_at,
                   a.username AS admin_username, a.full_name AS admin_name
            FROM user_moderation_history h
            JOIN users a ON a.user_id = h.admin_id
            WHERE h.user_id = %s
            ORDER BY h.created_at DESC, h.moderation_id DESC
            LIMIT 100
        """, (user_id,))
        moderation_history = cursor.fetchall()
    except Error as error:
        print("載入會員詳細資料失敗：", error)
        flash("會員詳細資料載入失敗，請確認已執行會員管理資料庫更新。", "error")
        return redirect(url_for("admin_users"))
    finally:
        cursor.close()
        connection.close()

    return render_template(
        "admin_user_detail.html",
        user=user,
        trip_count=trip_counts["trip_count"],
        public_trip_count=trip_counts["public_trip_count"],
        issue_count=issue_count,
        trips=trips,
        issues=issues,
        moderation_history=moderation_history,
        status_labels=USER_STATUS_LABELS,
    )


@app.route("/system-admin/users/<int:user_id>/role", methods=["POST"])
def update_user_role(user_id):
    if "user_id" not in session or session.get("role") != "system_admin":
        return redirect(url_for("login"))

    new_role = request.form.get("role", "").strip()
    role_labels = {
        "member": "一般會員",
        "content_admin": "內容管理員",
        "system_admin": "系統管理員",
    }
    if new_role not in role_labels:
        flash("帳號角色不正確", "error")
        return redirect(url_for("admin_users"))

    if user_id == session.get("user_id"):
        flash("不能修改自己目前登入帳號的角色", "error")
        return redirect(url_for("admin_users"))

    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("admin_users"))

    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT user_id, username, role, status
            FROM users
            WHERE user_id = %s AND status != 'deleted'
        """, (user_id,))
        target = cursor.fetchone()

        if target is None:
            flash("找不到指定帳號", "error")
            return redirect(url_for("admin_users"))

        if target["role"] == new_role:
            flash("帳號角色沒有變更", "success")
            return redirect(url_for("admin_users"))

        if target["role"] == "system_admin" and new_role != "system_admin" and target["status"] == "active":
            cursor.execute("""
                SELECT COUNT(*) AS total FROM users
                WHERE role = 'system_admin' AND status = 'active'
            """)
            if cursor.fetchone()["total"] <= 1:
                flash("系統至少需要保留一位啟用中的系統管理員", "error")
                return redirect(url_for("admin_users"))

        old_role = target["role"]
        cursor.execute("UPDATE users SET role = %s WHERE user_id = %s", (new_role, user_id))
        if new_role == "content_admin":
            cursor.execute("DELETE FROM content_admin_denials WHERE user_id = %s", (user_id,))
            cursor.executemany(
                "INSERT INTO content_admin_denials (user_id, module) VALUES (%s, %s)",
                [(user_id, f"{module}:{action}")
                 for module, actions in CONTENT_ADMIN_ACTIONS.items() for action in actions],
            )
        log_action(
            cursor, "change_user_role", "user", user_id,
            f"帳號 {target['username']}：{role_labels[old_role]}改為{role_labels[new_role]}"
        )
        connection.commit()
        if new_role == "content_admin":
            flash(f"已將 {target['username']} 設為內容管理員；請接著設定權限。", "success")
        else:
            flash(f"已將 {target['username']} 設為{role_labels[new_role]}，下次登入生效", "success")
    except Exception as error:
        connection.rollback()
        print("修改帳號角色失敗：", error)
        flash("修改帳號角色失敗", "error")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("admin_users"))


@app.route("/system-admin/public-trips")  # 設定公開行程管理頁路由
def admin_public_trips():  # 定義公開行程管理列表函式
    if "user_id" not in session or session.get("role") != "system_admin":  # 如果尚未登入或角色不是系統管理員
        return redirect(url_for("login"))  # 導向登入頁

    keyword = request.args.get("keyword", "").strip()  # 取得搜尋關鍵字參數
    trip_status = request.args.get("status", "").strip()  # 取得行程狀態篩選參數
    moderation = request.args.get("moderation", "").strip()
    if moderation not in {"visible", "hidden", "removed"}:
        moderation = ""
    allowed_statuses = {"planning", "upcoming", "completed", "cancelled"}  # 定義允許的行程狀態集合
    if trip_status not in allowed_statuses:  # 如果傳入的狀態不在允許範圍內
        trip_status = ""  # 視為沒有篩選狀態

    connection = get_db_connection()  # 建立資料庫連線
    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return render_template(  # 回傳空清單頁面
            "admin_public_trips.html",
            trips=[], keyword=keyword, trip_status=trip_status,
            moderation=moderation, public_count=0, hidden_count=0, removed_count=0
        )

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標
    try:  # 開始查詢公開行程資料
        conditions = ["(t.visibility = 'public' OR t.moderation_status != 'visible')",
                      "(t.deleted_at IS NULL OR t.moderation_status = 'removed')"]
        params = []  # 對應條件的參數清單

        if keyword:  # 如果有輸入搜尋關鍵字
            search = f"%{keyword}%"  # 組成模糊搜尋字串
            conditions.append("""
                (t.trip_name LIKE %s OR co.name LIKE %s OR ci.name LIKE %s
                 OR u.username LIKE %s OR u.full_name LIKE %s)
            """)  # 加入依行程名稱、國家、城市、擁有者帳號、姓名搜尋的條件
            params.extend([search] * 5)  # 5 個搜尋欄位都用同一個關鍵字

        if trip_status:  # 如果有指定行程狀態
            conditions.append("t.status = %s")  # 加入狀態篩選條件
            params.append(trip_status)  # 加入對應參數
        if moderation:
            conditions.append("t.moderation_status = %s")
            params.append(moderation)

        where_clause = " AND ".join(conditions)  # 把所有條件用 AND 串起來
        cursor.execute(f"""
            SELECT t.trip_id, t.trip_name, co.name AS country, ci.name AS city,
                   t.start_date, t.end_date, t.status, t.created_at, t.moderation_status,
                   u.username AS owner_username, u.full_name AS owner_name,
                   COUNT(DISTINCT CASE WHEN tm.join_status = 'accepted'
                                      THEN tm.trip_member_id END) AS member_count,
                   COUNT(DISTINCT i.itinerary_id) AS itinerary_count
            FROM trips t
            JOIN users u ON u.user_id = t.owner_id
            JOIN countries co ON co.country_id = t.country_id
            JOIN cities ci ON ci.city_id = t.city_id
            LEFT JOIN trip_members tm ON tm.trip_id = t.trip_id
            LEFT JOIN itineraries i ON i.trip_id = t.trip_id
            WHERE {where_clause}
            GROUP BY t.trip_id, t.trip_name, co.name, ci.name,
                     t.start_date, t.end_date, t.status, t.created_at, t.moderation_status,
                     u.username, u.full_name
            ORDER BY t.created_at DESC
        """, tuple(params))  # 查詢公開行程清單，附帶成員數、行程項目數
        trips = cursor.fetchall()  # 取出公開行程清單

        cursor.execute("SELECT COUNT(*) AS total FROM trips WHERE visibility = 'public' AND moderation_status = 'visible' AND deleted_at IS NULL")
        public_count = cursor.fetchone()["total"]  # 取出公開行程總數
        cursor.execute("SELECT moderation_status, COUNT(*) AS total FROM trips WHERE moderation_status != 'visible' GROUP BY moderation_status")
        moderation_counts = {row["moderation_status"]: row["total"] for row in cursor.fetchall()}

    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return render_template(  # 渲染公開行程管理頁面
        "admin_public_trips.html",
        trips=trips,  # 公開行程清單
        keyword=keyword,  # 搜尋關鍵字
        trip_status=trip_status,  # 狀態篩選值
        moderation=moderation,
        public_count=public_count,  # 公開行程總數
        hidden_count=moderation_counts.get("hidden", 0),
        removed_count=moderation_counts.get("removed", 0),
    )


@app.route("/system-admin/public-trips/<int:trip_id>")
def admin_public_trip_detail(trip_id):
    denied = system_admin_required()
    if denied:
        return denied
    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("admin_public_trips"))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT t.*, co.name AS country, ci.name AS city,
                   u.username AS owner_username, u.full_name AS owner_name
            FROM trips t JOIN users u ON u.user_id = t.owner_id
            JOIN countries co ON co.country_id = t.country_id
            JOIN cities ci ON ci.city_id = t.city_id
            WHERE t.trip_id = %s
              AND (t.visibility = 'public' OR t.moderation_status != 'visible')
              AND (t.deleted_at IS NULL OR t.moderation_status = 'removed')
        """, (trip_id,))
        trip = cursor.fetchone()
        if not trip:
            flash("找不到指定的公開行程", "error")
            return redirect(url_for("admin_public_trips"))
        cursor.execute("""
            SELECT itinerary_date, item_type, title, start_time, end_time,
                   address, notes, estimated_cost
            FROM itineraries WHERE trip_id = %s
            ORDER BY itinerary_date, sort_order, start_time
        """, (trip_id,))
        itinerary = cursor.fetchall()
        cursor.execute("""
            SELECT h.action, h.reason, h.created_at, u.username AS admin_username
            FROM trip_moderation_history h JOIN users u ON u.user_id = h.admin_id
            WHERE h.trip_id = %s ORDER BY h.created_at DESC, h.moderation_id DESC
        """, (trip_id,))
        history = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()
    return render_template("admin_public_trip_detail.html", trip=trip,
                           itinerary=itinerary, history=history, active_page="trips")


@app.route("/system-admin/public-trips/<int:trip_id>/moderate", methods=["POST"])
def moderate_public_trip(trip_id):
    denied = system_admin_required()
    if denied:
        return denied
    action = request.form.get("action", "").strip()
    reason = request.form.get("reason", "").strip()
    if action not in {"hide", "restore", "remove"} or not 1 <= len(reason) <= 1000:
        flash("請選擇處理方式並填寫 1 至 1000 字的原因", "error")
        return redirect(url_for("admin_public_trip_detail", trip_id=trip_id))
    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("admin_public_trip_detail", trip_id=trip_id))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT trip_id, trip_name, owner_id, visibility, moderation_status, deleted_at
            FROM trips WHERE trip_id = %s FOR UPDATE
        """, (trip_id,))
        trip = cursor.fetchone()
        allowed = bool(trip) and (
            (action == "hide" and trip["visibility"] == "public"
             and trip["moderation_status"] == "visible" and trip["deleted_at"] is None)
            or (action == "restore" and trip["moderation_status"] == "hidden")
            or (action == "remove" and trip["moderation_status"] == "hidden" and trip["deleted_at"] is None)
            or (action == "remove" and trip["moderation_status"] == "visible"
                and trip["visibility"] == "public" and trip["deleted_at"] is None)
        )
        if not allowed:
            flash("目前行程狀態不允許這項操作", "error")
            return redirect(url_for("admin_public_trip_detail", trip_id=trip_id))
        if action == "hide":
            cursor.execute("UPDATE trips SET moderation_status = 'hidden' WHERE trip_id = %s", (trip_id,))
        elif action == "restore":
            cursor.execute("UPDATE trips SET moderation_status = 'visible' WHERE trip_id = %s", (trip_id,))
        else:
            cursor.execute("""
                UPDATE trips SET moderation_status = 'removed', deleted_at = NOW(), deleted_by = %s
                WHERE trip_id = %s
            """, (session["user_id"], trip_id))
        cursor.execute("""
            INSERT INTO trip_moderation_history (trip_id, admin_id, action, reason)
            VALUES (%s, %s, %s, %s)
        """, (trip_id, session["user_id"], action, reason))
        action_label = {"hide": "已隱藏", "restore": "已恢復", "remove": "已移除"}[action]
        cursor.execute("""
            INSERT INTO notifications
                (user_id, trip_id, notification_type, title, message, target_url)
            VALUES (%s, %s, 'system', %s, %s, %s)
        """, (trip["owner_id"], trip_id, "公開行程管理通知",
              f"你的行程「{trip['trip_name']}」{action_label}。處理原因：{reason}",
              url_for("member.dashboard") + "#trips" if action == "remove"
              else url_for("member.trip_detail", trip_id=trip_id)))
        log_action(cursor, f"{action}_trip", "trip", trip_id,
                   f"公開行程 {trip['trip_name']}；原因：{reason}")
        connection.commit()
        flash({"hide": "行程已隱藏", "restore": "行程已恢復", "remove": "行程已移除"}[action], "success")
    except Exception:
        connection.rollback()
        app.logger.exception("管理公開行程失敗")
        flash("處理失敗，請確認已執行公開行程管理資料庫更新", "error")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for("admin_public_trip_detail", trip_id=trip_id))

USER_STATUS_TRANSITIONS = {
    "active": {"under_review", "disabled", "deleted"},
    "under_review": {"active", "disabled", "deleted"},
    "disabled": {"active", "under_review", "deleted"},
    "deleted": {"active"},
}


def _admin_user_redirect(user_id):
    if request.form.get("return_to") == "detail":
        return redirect(url_for("admin_user_detail", user_id=user_id))
    return redirect(url_for("admin_users"))


def _update_user_status(user_id, new_status):
    denied = system_admin_required()
    if denied:
        return denied

    if new_status not in USER_STATUS_LABELS:
        flash("帳號狀態不正確", "error")
        return _admin_user_redirect(user_id)

    reason = request.form.get("reason", "").strip()
    if not reason or len(reason) > 1000:
        flash("請填寫 1 至 1000 字的處理原因", "error")
        return _admin_user_redirect(user_id)

    if user_id == session.get("user_id") and new_status != "active":
        flash("不能變更自己目前登入帳號的使用狀態", "error")
        return _admin_user_redirect(user_id)

    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
        return _admin_user_redirect(user_id)

    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT user_id, username, role, status
            FROM users
            WHERE user_id = %s
        """, (user_id,))
        target = cursor.fetchone()
        if target is None:
            flash("找不到指定帳號", "error")
            return _admin_user_redirect(user_id)

        old_status = target["status"]
        if old_status == new_status:
            flash("帳號已經是指定狀態", "error")
            return _admin_user_redirect(user_id)

        if new_status not in USER_STATUS_TRANSITIONS.get(old_status, set()):
            flash("不允許這項帳號狀態變更", "error")
            return _admin_user_redirect(user_id)

        if target["role"] == "system_admin" and old_status == "active" and new_status != "active":
            cursor.execute("""
                SELECT COUNT(*) AS total FROM users
                WHERE role = 'system_admin' AND status = 'active'
            """)
            if cursor.fetchone()["total"] <= 1:
                flash("不能變更最後一位啟用中的系統管理員", "error")
                return _admin_user_redirect(user_id)

        cursor.execute("UPDATE users SET status = %s WHERE user_id = %s", (new_status, user_id))

        action = {
            "under_review": "review_user",
            "disabled": "disable_user",
            "deleted": "delete_user",
            "active": "restore_user",
        }[new_status]
        cursor.execute("""
            INSERT INTO user_moderation_history
                (user_id, admin_id, action, from_status, to_status, reason)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            user_id, session["user_id"], action, old_status, new_status, reason,
        ))
        log_action(
            cursor, action, "user", user_id,
            f"帳號 {target['username']}：{USER_STATUS_LABELS.get(old_status, old_status)}"
            f"改為{USER_STATUS_LABELS[new_status]}；原因：{reason}",
        )
        connection.commit()
        flash(f"帳號已改為「{USER_STATUS_LABELS[new_status]}」", "success")
    except Exception as error:
        connection.rollback()
        print("更新會員狀態失敗：", error)
        flash("更新會員狀態失敗，請確認已執行會員管理資料庫更新", "error")
    finally:
        cursor.close()
        connection.close()

    return _admin_user_redirect(user_id)


@app.route("/system-admin/users/<int:user_id>/status", methods=["POST"])
def change_user_status(user_id):
    return _update_user_status(user_id, request.form.get("new_status", "").strip())


@app.route("/system-admin/users/<int:user_id>/disable", methods=["POST"])
def disable_user(user_id):
    return _update_user_status(user_id, "disabled")


@app.route("/system-admin/users/<int:user_id>/enable", methods=["POST"])
def enable_user(user_id):
    return _update_user_status(user_id, "active")
def system_admin_required():
    """Return a redirect when the current user is not a system administrator."""
    if "user_id" not in session or session.get("role") != "system_admin":
        if "user_id" not in session:
            remember_next_page()  # 記住原本要去的後台頁面，登入後帶回來
        return redirect(url_for("login"))
    return None


@app.route("/system-admin/issues")
def admin_issues():
    denied = system_admin_required()
    if denied:
        return denied
    status = request.args.get("status", "").strip()
    if status not in {"pending", "processing", "resolved", "rejected"}:
        status = ""
    issues = []
    counts = {"pending": 0, "processing": 0, "resolved": 0, "rejected": 0}
    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
    else:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT status, COUNT(*) AS total FROM reports
                WHERE target_type = 'trip' AND reason LIKE %s
                GROUP BY status
            """, (ISSUE_PREFIX + "%",))
            for row in cursor.fetchall():
                counts[row["status"]] = row["total"]
            cursor.execute("""
                SELECT r.report_id, r.target_id AS trip_id, r.reason, r.description,
                       r.status, r.created_at, r.handling_result, r.handled_at,
                       t.trip_name, t.visibility, u.username AS reporter_username,
                       u.full_name AS reporter_name
                FROM reports r
                LEFT JOIN trips t ON t.trip_id = r.target_id
                LEFT JOIN users u ON u.user_id = r.reporter_id  -- 檢舉人帳號被刪除時仍要顯示這筆回報，否則會出現「待處理(1)」卻查不到資料
                WHERE r.target_type = 'trip' AND r.reason LIKE %s
                  AND (%s = '' OR r.status = %s)
                ORDER BY FIELD(r.status, 'pending', 'processing', 'resolved', 'rejected'),
                         r.created_at DESC
                LIMIT 200
            """, (ISSUE_PREFIX + "%", status, status))
            issues = cursor.fetchall()
            for issue in issues:
                issue["reason"] = issue["reason"][len(ISSUE_PREFIX):]
        finally:
            cursor.close()
            connection.close()
    return render_template("admin_issues.html", issues=issues, counts=counts, issue_status=status)


@app.route("/system-admin/issues/<int:issue_id>/handle", methods=["POST"])
def handle_admin_issue(issue_id):
    denied = system_admin_required()
    if denied:
        return denied
    status = request.form.get("status", "").strip()
    result = request.form.get("handling_result", "").strip()
    if status not in {"processing", "resolved", "rejected"}:
        flash("問題狀態不正確。", "error")
        return redirect(url_for("admin_issues"))
    if len(result) > 1000 or (status in {"resolved", "rejected"} and not result):
        flash("結案或駁回時請填寫不超過 1000 字的處理結果。", "error")
        return redirect(url_for("admin_issues"))
    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("admin_issues"))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT r.report_id, r.reporter_id, r.status, r.handling_result, r.target_id AS trip_id,
                   t.owner_id, t.trip_name, t.visibility, t.moderation_status,
                   ru.user_id IS NOT NULL AS reporter_exists
            FROM reports r
            JOIN trips t ON t.trip_id = r.target_id
            LEFT JOIN users ru ON ru.user_id = r.reporter_id
            WHERE r.report_id = %s AND r.target_type = 'trip' AND r.reason LIKE %s
        """, (issue_id, ISSUE_PREFIX + "%"))
        issue = cursor.fetchone()
        if not issue:
            flash("找不到這筆問題回報。", "error")
            return redirect(url_for("admin_issues"))
        was_hidden = False
        if status == "resolved" and issue["visibility"] == "public" and issue["moderation_status"] == "visible":
            cursor.execute("""
                UPDATE trips SET moderation_status = 'hidden'
                WHERE trip_id = %s AND visibility = 'public' AND moderation_status = 'visible'
            """, (issue["trip_id"],))
            was_hidden = cursor.rowcount > 0
            if was_hidden:
                cursor.execute("""
                    INSERT INTO trip_moderation_history (trip_id, admin_id, action, reason)
                    VALUES (%s, %s, 'hide', %s)
                """, (issue["trip_id"], session["user_id"], result))
        cursor.execute("""
            UPDATE reports SET status = %s, handling_result = %s, handled_by = %s,
                handled_at = CASE WHEN %s IN ('resolved', 'rejected') THEN NOW() ELSE NULL END
            WHERE report_id = %s AND target_type = 'trip' AND reason LIKE %s
        """, (status, result or None, session["user_id"], status, issue_id, ISSUE_PREFIX + "%"))
        if issue["status"] != status or result != (issue.get("handling_result") or ""):
            status_text = {
                "processing": "處理中",
                "resolved": "已結案",
                "rejected": "已駁回",
            }[status]
            if status == "processing":
                notification_user_id = issue["owner_id"]
                title = "問題回報處理中"
                message = f"管理員正在處理你的公開行程「{issue['trip_name']}」的問題。"
                target_url = url_for("member.trip_detail", trip_id=issue["trip_id"])
            elif status == "resolved":
                notification_user_id = issue["owner_id"]
                title = "問題回報已結案"
                message = (
                    f"你的公開行程「{issue['trip_name']}」問題回報已結案。"
                    f"處理結果：{result}"
                )
                if was_hidden or issue["moderation_status"] == "hidden":
                    message += " 此行程目前已被管理員隱藏。"
                target_url = url_for("member.trip_detail", trip_id=issue["trip_id"])
            else:
                notification_user_id = issue["reporter_id"]
                title = "你的問題回報已駁回"
                message = (
                    f"你對公開行程「{issue['trip_name']}」提出的問題回報已駁回。"
                    f"處理結果：{result}"
                )
                target_url = url_for("member.dashboard") + "#trips"
            # 回報人帳號已不存在時不寫通知給他(避免寫入失敗導致整筆處理失敗)
            if notification_user_id != issue["reporter_id"] or issue.get("reporter_exists", True):
                cursor.execute("""
                    INSERT INTO notifications
                        (user_id, trip_id, notification_type, title, message, target_url)
                    VALUES (%s, %s, 'system', %s, %s, %s)
                """, (
                    notification_user_id, issue["trip_id"], title, message, target_url,
                ))
            if (status in {"processing", "resolved"} and issue["reporter_id"] != notification_user_id
                    and issue.get("reporter_exists", True)):
                reporter_message = (
                    f"你對公開行程「{issue['trip_name']}」提出的問題回報{status_text}。"
                    + (f"處理結果：{result}" if result else "")
                )
                cursor.execute("""
                    INSERT INTO notifications
                        (user_id, trip_id, notification_type, title, message, target_url)
                    VALUES (%s, %s, 'system', %s, %s, %s)
                """, (
                    issue["reporter_id"], issue["trip_id"], f"你的問題回報{status_text}",
                    reporter_message, url_for("member.dashboard"),
                ))
        log_action(cursor, "handle_issue", "report", issue_id, f"問題回報狀態更新為 {status}")
        connection.commit()
        if was_hidden:
            flash("問題回報已結案，該行程已由管理員隱藏。", "success")
        elif status == "rejected":
            flash("問題回報已駁回，已通知回報會員；行程公開狀態不會自動改變。", "success")
        else:
            flash("問題回報已更新。", "success")
    except Exception as error:
        connection.rollback()
        print("更新問題回報失敗：", error)
        flash("更新問題回報失敗。", "error")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for("admin_issues"))


@app.route("/system-admin/comment-reports")
def admin_comment_reports():
    denied = system_admin_required()
    if denied:
        return denied
    status = request.args.get("status", "").strip()
    if status not in {"pending", "processing", "resolved", "rejected"}:
        status = ""
    reports_rows = []
    counts = {"pending": 0, "processing": 0, "resolved": 0, "rejected": 0}
    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
    else:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT status, COUNT(*) AS total FROM reports
                WHERE target_type = 'comment' AND reason LIKE %s
                GROUP BY status
            """, (COMMENT_REPORT_PREFIX + "%",))
            for row in cursor.fetchall():
                counts[row["status"]] = row["total"]
            cursor.execute("""
                SELECT r.report_id, r.target_id AS comment_id, r.reason, r.description,
                       r.status, r.created_at, r.handling_result, r.handled_at,
                       c.content AS comment_content, c.status AS comment_status, c.trip_id,
                       t.trip_name, au.username AS comment_author_username, au.full_name AS comment_author_name,
                       u.username AS reporter_username, u.full_name AS reporter_name
                FROM reports r
                LEFT JOIN comments c ON c.comment_id = r.target_id
                LEFT JOIN trips t ON t.trip_id = c.trip_id
                LEFT JOIN users au ON au.user_id = c.user_id
                LEFT JOIN users u ON u.user_id = r.reporter_id  -- 檢舉人帳號被刪除時仍要顯示這筆回報，否則會出現「待處理(1)」卻查不到資料
                WHERE r.target_type = 'comment' AND r.reason LIKE %s
                  AND (%s = '' OR r.status = %s)
                ORDER BY FIELD(r.status, 'pending', 'processing', 'resolved', 'rejected'),
                         r.created_at DESC
                LIMIT 200
            """, (COMMENT_REPORT_PREFIX + "%", status, status))
            reports_rows = cursor.fetchall()
            for row in reports_rows:
                row["reason"] = row["reason"][len(COMMENT_REPORT_PREFIX):]
        finally:
            cursor.close()
            connection.close()
    return render_template("admin_comment_reports.html", reports=reports_rows, counts=counts, report_status=status)


@app.route("/system-admin/comment-reports/<int:report_id>/handle", methods=["POST"])
def handle_admin_comment_report(report_id):
    denied = system_admin_required()
    if denied:
        return denied
    status = request.form.get("status", "").strip()
    result = request.form.get("handling_result", "").strip()
    if status not in {"processing", "resolved", "rejected"}:
        flash("處理狀態不正確。", "error")
        return redirect(url_for("admin_comment_reports"))
    if len(result) > 1000 or (status in {"resolved", "rejected"} and not result):
        flash("結案或駁回時請填寫不超過 1000 字的處理結果。", "error")
        return redirect(url_for("admin_comment_reports"))
    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("admin_comment_reports"))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT report_id, target_id AS comment_id FROM reports
            WHERE report_id = %s AND target_type = 'comment' AND reason LIKE %s
        """, (report_id, COMMENT_REPORT_PREFIX + "%"))
        report = cursor.fetchone()
        if not report:
            flash("找不到這筆檢舉。", "error")
            return redirect(url_for("admin_comment_reports"))
        if status == "resolved":
            cursor.execute("UPDATE comments SET status='hidden' WHERE comment_id=%s AND status='visible'", (report["comment_id"],))
        cursor.execute("""
            UPDATE reports SET status = %s, handling_result = %s, handled_by = %s,
                handled_at = CASE WHEN %s IN ('resolved', 'rejected') THEN NOW() ELSE NULL END
            WHERE report_id = %s AND target_type = 'comment' AND reason LIKE %s
        """, (status, result or None, session["user_id"], status, report_id, COMMENT_REPORT_PREFIX + "%"))
        log_action(cursor, "handle_comment_report", "comment", report["comment_id"], f"留言檢舉狀態更新為 {status}")
        connection.commit()
        flash("檢舉已結案，該留言已隱藏。" if status == "resolved" else "檢舉已更新。", "success")
    except Exception as error:
        connection.rollback()
        print("更新留言檢舉失敗：", error)
        flash("更新失敗。", "error")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for("admin_comment_reports"))


@app.route("/system-admin/announcements", methods=["GET", "POST"])
def admin_announcements():
    denied = system_admin_required()
    if denied:
        return denied
    connection = get_db_connection()
    announcements = []
    if connection is None:
        flash("資料庫連線失敗", "error")
        return render_template("admin_announcements.html", announcements=[])
    cursor = connection.cursor(dictionary=True)
    try:
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            content = request.form.get("content", "").strip()
            status = request.form.get("status", "draft")
            is_pinned = 1 if request.form.get("is_pinned") else 0
            if status not in {"draft", "published"}:
                status = "draft"
            if not title or not content:
                flash("請填寫公告標題與內容", "error")
            else:
                cursor.execute("""
                    INSERT INTO announcements
                    (created_by, title, content, is_pinned, status, publish_at)
                    VALUES (%s, %s, %s, %s, %s,
                            CASE WHEN %s = 'published' THEN NOW() ELSE NULL END)
                """, (session["user_id"], title, content, is_pinned, status, status))
                announcement_id = cursor.lastrowid
                log_action(cursor, "create_announcement", "announcement", announcement_id,
                           f"新增公告：{title}")
                connection.commit()
                flash("公告已建立", "success")
                if status == "published" and request.form.get("push_line"):
                    ok, message = line_announcements.push_announcement(announcement_id)
                    flash(message, "success" if ok else "error")
                return redirect(url_for("admin_announcements"))
        cursor.execute("""
            SELECT a.*, u.full_name AS creator_name
            FROM announcements a
            JOIN users u ON u.user_id = a.created_by
            ORDER BY a.is_pinned DESC, a.created_at DESC
        """)
        announcements = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()
    return render_template("admin_announcements.html", announcements=announcements,
                           line_status=line_announcements.push_status())


@app.route("/system-admin/announcements/<int:announcement_id>/line-push", methods=["POST"])
def push_announcement_to_line(announcement_id):  # 把已發布的公告推播給所有 LINE 好友（會用掉每月推播額度）
    denied = system_admin_required()
    if denied:
        return denied
    ok, message = line_announcements.push_announcement(announcement_id)
    if ok:
        connection = get_db_connection()
        if connection is not None:
            cursor = connection.cursor()
            try:
                log_action(cursor, "update_announcement", "announcement", announcement_id, "公告推播到 LINE")
                connection.commit()
            finally:
                cursor.close()
                connection.close()
    flash(message, "success" if ok else "error")
    return redirect(url_for("admin_announcements"))


@app.route("/system-admin/announcements/<int:announcement_id>/update", methods=["POST"])
def update_admin_announcement(announcement_id):
    denied = system_admin_required()
    if denied:
        return denied
    status = request.form.get("status", "draft")
    if status not in {"draft", "published", "hidden"}:
        status = "draft"
    is_pinned = 1 if request.form.get("is_pinned") else 0
    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("admin_announcements"))
    cursor = connection.cursor()
    try:
        cursor.execute("""
            UPDATE announcements
            SET status = %s, is_pinned = %s,
                publish_at = CASE
                    WHEN %s = 'published' AND publish_at IS NULL THEN NOW()
                    WHEN %s != 'published' THEN NULL ELSE publish_at END
            WHERE announcement_id = %s
        """, (status, is_pinned, status, status, announcement_id))
        log_action(cursor, "update_announcement", "announcement", announcement_id,
                   f"公告狀態更新為 {status}")
        connection.commit()
        flash("公告設定已更新", "success")
    except Exception as error:
        connection.rollback()
        print("更新公告失敗：", error)
        flash("更新公告失敗", "error")
    finally:
        cursor.close()
        connection.close()
    return redirect(url_for("admin_announcements"))


@app.route("/system-admin/statistics")
def admin_statistics():
    denied = system_admin_required()
    if denied:
        return denied
    totals = {"members": 0, "active_members": 0, "trips": 0, "public_trips": 0,
              "announcements": 0}
    trip_statuses = []
    issue_statuses = []
    attraction_totals = {"active": 0, "favorites": 0, "itineraries": 0}
    top_attractions = []
    countries = []
    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
    else:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT
                  (SELECT COUNT(*) FROM users WHERE role='member' AND status!='deleted') AS members,
                  (SELECT COUNT(*) FROM users WHERE role='member' AND status='active') AS active_members,
                  (SELECT COUNT(*) FROM trips WHERE deleted_at IS NULL) AS trips,
                  (SELECT COUNT(*) FROM trips WHERE visibility='public' AND moderation_status='visible' AND deleted_at IS NULL) AS public_trips,
                  (SELECT COUNT(*) FROM announcements) AS announcements
            """)
            totals.update(cursor.fetchone())
            cursor.execute("SELECT status, COUNT(*) AS total FROM trips WHERE deleted_at IS NULL GROUP BY status ORDER BY total DESC")
            trip_statuses = cursor.fetchall()
            cursor.execute("""
                SELECT status, COUNT(*) AS total
                FROM reports
                WHERE target_type='trip' AND reason LIKE %s
                GROUP BY status
            """, (ISSUE_PREFIX + "%",))
            issue_counts = {row["status"]: row["total"] for row in cursor.fetchall()}
            issue_statuses = [
                {"status": status, "label": label, "total": issue_counts.get(status, 0)}
                for status, label in (("pending", "待處理"), ("processing", "處理中"),
                                      ("resolved", "已結案"), ("rejected", "已駁回"))
            ]
            cursor.execute("""
                SELECT
                  (SELECT COUNT(*) FROM attractions WHERE status='active' AND deleted_at IS NULL) AS active,
                  (SELECT COUNT(*) FROM favorites f JOIN attractions a ON a.attraction_id=f.attraction_id
                   WHERE f.target_type='attraction' AND a.status='active' AND a.deleted_at IS NULL) AS favorites,
                  (SELECT COUNT(*) FROM itineraries i
                   JOIN attractions a ON a.attraction_id=i.attraction_id
                   JOIN trips t ON t.trip_id=i.trip_id
                   WHERE a.status='active' AND a.deleted_at IS NULL AND t.deleted_at IS NULL) AS itineraries
            """)
            attraction_totals.update(cursor.fetchone())
            cursor.execute("SELECT country_id, name FROM countries ORDER BY name")
            countries = cursor.fetchall()
            top_attractions = fetch_attraction_rankings(
                cursor, limit=5, sort_by="favorites", favorites_only=True)
        finally:
            cursor.close()
            connection.close()
    attraction_chart_max = max((row["favorite_count"] for row in top_attractions), default=1)
    return render_template("admin_statistics.html", totals=totals,
                           trip_statuses=trip_statuses, issue_statuses=issue_statuses,
                           countries=countries, taiwan_counties=TAIWAN_COUNTIES,
                           attraction_totals=attraction_totals, top_attractions=top_attractions,
                           attraction_chart_max=max(attraction_chart_max, 1))


@app.route("/system-admin/statistics/attractions")
def admin_statistics_attractions():
    denied = system_admin_required()
    if denied:
        return denied
    country_id = request.args.get("country_id", "").strip()
    county = request.args.get("county", "").strip().replace("臺", "台")
    metric = request.args.get("metric", "favorites").strip()
    if country_id and (not country_id.isdigit() or int(country_id) < 1):
        return jsonify(error="無效的國家"), 400
    if county and county not in TAIWAN_COUNTIES:
        return jsonify(error="無效的縣市"), 400
    if metric not in ("favorites", "itineraries"):
        return jsonify(error="無效的排名方式"), 400
    connection = get_db_connection()
    if connection is None:
        return jsonify(error="資料庫連線失敗"), 503
    cursor = connection.cursor(dictionary=True)
    try:
        rows = fetch_attraction_rankings(
            cursor, country_id=None if county else country_id or None,
            county_name=county or None, favorites_only=metric == "favorites",
            positive_only=metric == "itineraries", sort_by=metric, limit=5)
        return jsonify(attractions=[{
            "name": row["name"], "city": row["city"], "country": row["country"],
            "favorite_count": row["favorite_count"],
            "itinerary_count": row["itinerary_count"],
        } for row in rows])
    finally:
        cursor.close()
        connection.close()


@app.route("/system-admin/logs")
def admin_logs():
    denied = system_admin_required()
    if denied:
        return denied
    keyword = request.args.get("keyword", "").strip()
    action = request.args.get("action", "").strip()
    admin_id = request.args.get("admin_id", "").strip()
    if not admin_id.isdigit() or int(admin_id) < 1:
        admin_id = ""
    logs = []
    actions = []
    filtered_admin = None
    connection = get_db_connection()
    if connection is None:
        flash("資料庫連線失敗", "error")
    else:
        cursor = connection.cursor(dictionary=True)
        try:
            conditions = []
            params = []
            if action:
                conditions.append("l.action = %s")
                params.append(action)
            if admin_id:
                conditions.append("l.admin_id = %s")
                params.append(int(admin_id))
                cursor.execute("SELECT username,full_name FROM users WHERE user_id=%s", (int(admin_id),))
                filtered_admin = cursor.fetchone()
            if keyword:
                search = f"%{keyword}%"
                conditions.append("(u.full_name LIKE %s OR u.username LIKE %s OR l.description LIKE %s OR l.ip_address LIKE %s)")
                params.extend([search, search, search, search])
            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            cursor.execute(f"""
                SELECT l.*, u.full_name AS admin_name, u.username AS admin_username
                FROM admin_logs l JOIN users u ON u.user_id = l.admin_id
                {where_clause}
                ORDER BY l.created_at DESC LIMIT 200
            """, tuple(params))
            logs = cursor.fetchall()
            cursor.execute("SELECT DISTINCT action FROM admin_logs ORDER BY action")
            actions = [row["action"] for row in cursor.fetchall()]
        finally:
            cursor.close()
            connection.close()
    labels = dict(ACTION_LABELS)
    labels.update({"handle_issue": "處理問題回報", "create_announcement": "新增公告",
                   "update_announcement": "更新公告",
                   "create_home_banner": "新增首頁輪播圖", "update_home_banner": "更新首頁輪播圖",
                   "delete_home_banner": "刪除首頁輪播圖"})
    return render_template("admin_logs.html", logs=logs, actions=actions,
                           labels=labels, keyword=keyword, selected_action=action,
                           admin_id=admin_id, filtered_admin=filtered_admin)


@app.route("/logout")  # 設定登出路由
def logout():  # 定義登出函式
    session.clear()  # 清空 session，移除登入狀態
    flash("你已成功登出。", "success")  # 顯示登出成功訊息
    return redirect(url_for("login"))  # 導向登入頁


if __name__ == "__main__":  # 僅供本機開發；公開測試請使用 serve_public.py
    trip_reminders.start_scheduler()
    app.run(host="127.0.0.1", debug=False)
