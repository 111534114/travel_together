import io  # 匯入 io，用來在記憶體中組出 CSV 檔案內容
import ipaddress
import os  # 匯入作業系統相關功能，用來處理檔案路徑與資料夾
import random  # 匯入 random，用來隨機挑選不同句型，避免自動產生的描述長得都一樣
import socket
import uuid  # 匯入 uuid，用來產生不重複的檔名
import csv  # 匯入 csv，用來寫出 CSV 格式的內容
from urllib.parse import parse_qs, urljoin, urlparse  # 匯入網址解析工具，用來拆解 Google 圖片檢視頁網址

import requests  # 匯入 requests，用來下載網路上的圖片
from flask import Response, current_app  # 匯入 Response(組成檔案下載回應)、current_app(取得目前執行中的 Flask 應用程式)
from werkzeug.utils import secure_filename  # 匯入 secure_filename，把檔名轉成安全、不含危險字元的格式

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}  # 定義允許上傳的圖片副檔名集合

CONTENT_TYPE_EXTENSIONS = {  # 定義圖片的 Content-Type 對應副檔名，從網址下載圖片時用來判斷格式
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
}

MAX_IMAGE_DOWNLOAD_BYTES = 8 * 1024 * 1024  # 定義從網址下載圖片的大小上限(8MB)，跟表單上傳的限制一致

IMAGE_DOWNLOAD_HEADERS = {  # 定義下載圖片時要帶的 HTTP 表頭，假裝成一般瀏覽器，避免被防盜連機制擋掉
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/png,image/jpeg,image/*,*/*;q=0.8",
}


def _resolve_actual_image_url(url):  # 定義內部函式：如果是 Google 圖片檢視頁網址，改抓裡面真正的圖片網址
    parsed = urlparse(url)  # 把網址拆解成各個組成部分

    if "google." not in parsed.netloc:  # 如果網域不是 google 開頭的網站(不是從 Google 圖片複製來的)
        return url  # 直接回傳原網址，不用特別處理

    if parsed.path != "/imgres":  # 如果不是 Google 圖片的「檢視頁」路徑(/imgres)
        return url  # 直接回傳原網址

    query = parse_qs(parsed.query)  # 把網址上的查詢字串解析成字典

    if "imgurl" in query and query["imgurl"]:  # 如果查詢字串裡有 imgurl 參數(真正的圖片網址就藏在這裡)
        return query["imgurl"][0]  # 回傳解析出來的真正圖片網址

    return url  # 找不到 imgurl 參數，還是回傳原網址(讓後面的下載流程去處理錯誤)


def _validate_remote_image_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("圖片網址必須是有效的 http:// 或 https:// 網址")

    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443)
    except socket.gaierror as error:
        raise ValueError("圖片網址的主機無法解析") from error

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ValueError("圖片網址不可指向本機或內部網路")


def _request_remote_image(url):
    current_url = url
    for _ in range(5):
        _validate_remote_image_url(current_url)
        response = requests.get(
            current_url,
            timeout=10,
            stream=True,
            headers=IMAGE_DOWNLOAD_HEADERS,
            allow_redirects=False,
        )
        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise ValueError("圖片網址重新導向失敗")
            current_url = urljoin(current_url, location)
            continue
        response.raise_for_status()
        return response, current_url
    raise ValueError("圖片網址重新導向次數過多")


def _extension(filename):  # 定義內部函式：取出檔名的副檔名(小寫)
    if "." not in filename:  # 如果檔名裡沒有點(代表沒有副檔名)
        return ""  # 回傳空字串

    return filename.rsplit(".", 1)[1].lower()  # 從最後一個點切開，取後半段並轉小寫作為副檔名


def save_uploaded_image(file_storage, subfolder):  # 定義儲存上傳圖片的函式，subfolder 是要存到哪個子資料夾(例如 attractions)
    if file_storage is None or file_storage.filename == "":  # 如果沒有選擇檔案(欄位是空的)
        return None  # 回傳 None，代表沒有新圖片要處理

    extension = _extension(file_storage.filename)  # 取得上傳檔案的副檔名

    if extension not in ALLOWED_IMAGE_EXTENSIONS:  # 如果副檔名不在允許清單內
        raise ValueError("不支援的圖片格式，請上傳 png、jpg、jpeg、gif 或 webp")  # 拋出例外，讓呼叫端顯示錯誤訊息

    stored_name = f"{uuid.uuid4().hex}.{extension}"  # 用亂數產生的 uuid 當檔名，避免不同使用者上傳同名檔案互相覆蓋
    safe_name = secure_filename(stored_name)  # 再用 secure_filename 過濾一次，確保檔名安全

    upload_dir = os.path.join(current_app.static_folder, "uploads", subfolder)  # 組成實際要存放的資料夾路徑(static/uploads/子資料夾)
    os.makedirs(upload_dir, exist_ok=True)  # 建立資料夾，如果已存在就不報錯

    file_storage.save(os.path.join(upload_dir, safe_name))  # 把上傳的檔案實際寫入硬碟

    return f"uploads/{subfolder}/{safe_name}"  # 回傳相對路徑，方便存進資料庫的 image_path 欄位


def save_image_from_url(url, subfolder):  # 定義函式：從網址下載圖片並存到 static/uploads/子資料夾，回傳相對路徑
    url = (url or "").strip()  # 去除頭尾空白

    if not url:  # 如果網址是空的
        return None  # 回傳 None，代表沒有圖片要處理

    if not url.lower().startswith(("http://", "https://")):  # 如果不是合法的網址格式
        raise ValueError("圖片網址必須是 http:// 或 https:// 開頭")  # 拋出例外，讓呼叫端顯示錯誤訊息

    url = _resolve_actual_image_url(url)  # 如果是 Google 圖片的檢視頁網址，改抓裡面真正的圖片網址

    try:  # 嘗試連線下載圖片
        response, url = _request_remote_image(url)
    except requests.RequestException as error:  # 如果連線失敗、逾時、網址錯誤等
        raise ValueError(f"無法下載圖片：{error}")  # 轉換成統一的錯誤格式

    content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()  # 取得伺服器回傳的檔案類型
    extension = CONTENT_TYPE_EXTENSIONS.get(content_type)  # 先用 Content-Type 判斷副檔名

    if extension is None:  # 如果伺服器沒有給出看得懂的 Content-Type
        extension = _extension(url.split("?")[0])  # 退而求其次，從網址本身猜副檔名(去掉問號後面的查詢參數)

    if extension not in ALLOWED_IMAGE_EXTENSIONS:  # 如果最後還是判斷不出支援的圖片格式
        if content_type.startswith("text/html"):  # 如果抓回來的其實是一個網頁而不是圖片(常見於複製到「檢視頁」網址的情況)
            raise ValueError("這個網址指向的是網頁而不是圖片本身，請改成直接複製圖片檔案的網址")  # 拋出更明確的錯誤說明
        raise ValueError("網址指向的檔案不是支援的圖片格式(png/jpg/jpeg/gif/webp)")  # 拋出例外

    downloaded = bytearray()  # 建立一個可變的位元組陣列，用來累積下載內容

    try:
        for chunk in response.iter_content(chunk_size=65536):  # 一塊一塊(64KB)讀取下載內容
            downloaded.extend(chunk)  # 把這塊資料加進累積內容

            if len(downloaded) > MAX_IMAGE_DOWNLOAD_BYTES:  # 如果累積大小超過上限
                raise ValueError("圖片檔案過大(超過 8MB)")  # 拋出例外，中止下載
    finally:
        response.close()

    stored_name = f"{uuid.uuid4().hex}.{extension}"  # 用亂數產生的 uuid 當檔名，避免不同來源的圖片互相覆蓋
    safe_name = secure_filename(stored_name)  # 再用 secure_filename 過濾一次，確保檔名安全

    upload_dir = os.path.join(current_app.static_folder, "uploads", subfolder)  # 組成實際要存放的資料夾路徑
    os.makedirs(upload_dir, exist_ok=True)  # 建立資料夾，如果已存在就不報錯

    with open(os.path.join(upload_dir, safe_name), "wb") as file:  # 以二進位寫入模式開啟目標檔案
        file.write(downloaded)  # 把下載到的圖片內容寫入硬碟

    return f"uploads/{subfolder}/{safe_name}"  # 回傳相對路徑，方便存進資料庫的 image_path 欄位


def delete_uploaded_image(relative_path):  # 定義刪除已上傳圖片的函式，relative_path 是資料庫裡存的相對路徑
    if not relative_path:  # 如果路徑是空值(代表原本就沒有圖片)
        return  # 直接結束，不用做任何事

    full_path = os.path.join(current_app.static_folder, relative_path)  # 組成圖片在硬碟上的完整路徑

    if os.path.isfile(full_path):  # 如果該檔案確實存在
        try:  # 嘗試刪除檔案
            os.remove(full_path)  # 從硬碟刪除圖片檔案
        except OSError:  # 如果刪除過程發生系統錯誤(例如檔案被占用)
            pass  # 不中斷程式，直接略過(圖片頂多變成孤兒檔案，不影響資料庫資料)


def get_countries(cursor):  # 定義取得所有國家清單的共用函式，cursor 是已開啟的資料庫游標
    cursor.execute("SELECT country_id, name FROM countries ORDER BY name")  # 查詢所有國家，依名稱排序
    return cursor.fetchall()  # 回傳查詢結果(國家清單)


def get_cities(cursor, country_id=None):  # 定義取得城市清單的共用函式，可選擇只取某個國家底下的城市
    if country_id:  # 如果有指定國家 ID
        cursor.execute(
            """
            SELECT city_id, country_id, name
            FROM cities
            WHERE country_id = %s
            ORDER BY name
            """,  # 只查詢屬於該國家的城市，依名稱排序
            (country_id,)  # 帶入國家 ID 參數
        )
    else:  # 如果沒有指定國家 ID
        cursor.execute(
            """
            SELECT city_id, country_id, name
            FROM cities
            ORDER BY name
            """  # 查詢所有城市，依名稱排序
        )

    return cursor.fetchall()  # 回傳查詢結果(城市清單)


def get_categories(cursor, category_type):  # 定義取得指定類型分類清單的共用函式(例如景點/餐廳/住宿分類)
    cursor.execute(
        """
        SELECT category_id, category_name
        FROM categories
        WHERE category_type = %s
        ORDER BY category_name
        """,  # 依分類類型查詢，並依分類名稱排序
        (category_type,)  # 帶入分類類型參數
    )
    return cursor.fetchall()  # 回傳查詢結果(分類清單)


def normalize_place_name(name):  # 定義函式：統一常見的繁體異體字，避免同一個地方因為用字不同被當成兩筆資料
    if not name:  # 如果名稱是空值
        return name  # 直接原樣回傳

    return name.replace("臺", "台")  # 「臺」統一轉成「台」(例如 Google 回傳的「臺北市」對應資料庫既有的「台北市」)


def get_or_create_country(cursor, name):  # 定義函式：依名稱找國家，找不到就自動新增(給 CSV 匯入用)，cursor 需為非字典格式
    name = normalize_place_name(name)  # 先統一異體字，避免「台灣」「臺灣」被當成兩個國家

    cursor.execute("SELECT country_id FROM countries WHERE name = %s", (name,))  # 查詢是否已有同名國家
    row = cursor.fetchone()  # 取得查詢結果(一筆 tuple 或 None)

    if row:  # 如果已經存在
        return row[0]  # 直接回傳該國家的 ID

    cursor.execute("INSERT INTO countries(name) VALUES (%s)", (name,))  # 不存在就新增這個國家
    return cursor.lastrowid  # 回傳新增後產生的國家 ID


def get_or_create_city(cursor, country_id, name):  # 定義函式：依國家 ID 與城市名稱找城市，找不到就自動新增
    name = normalize_place_name(name)  # 先統一異體字，避免「台北市」「臺北市」被當成兩個城市

    cursor.execute(  # 查詢該國家底下是否已有同名城市
        "SELECT city_id FROM cities WHERE country_id = %s AND name = %s",
        (country_id, name)
    )
    row = cursor.fetchone()  # 取得查詢結果

    if row:  # 如果已經存在
        return row[0]  # 直接回傳該城市的 ID

    cursor.execute(  # 不存在就新增這個城市
        "INSERT INTO cities(country_id, name) VALUES (%s, %s)",
        (country_id, name)
    )
    return cursor.lastrowid  # 回傳新增後產生的城市 ID


def get_or_create_category(cursor, category_type, name):  # 定義函式：依類型與名稱找分類，找不到就自動新增
    if not name:  # 如果沒有提供分類名稱
        return None  # 直接回傳 None，代表不設定分類

    cursor.execute(  # 查詢該類型底下是否已有同名分類
        "SELECT category_id FROM categories WHERE category_type = %s AND category_name = %s",
        (category_type, name)
    )
    row = cursor.fetchone()  # 取得查詢結果

    if row:  # 如果已經存在
        return row[0]  # 直接回傳該分類的 ID

    cursor.execute(  # 不存在就新增這個分類
        "INSERT INTO categories(category_type, category_name) VALUES (%s, %s)",
        (category_type, name)
    )
    return cursor.lastrowid  # 回傳新增後產生的分類 ID


PLACE_DESCRIPTION_TEMPLATES_FULL = [  # 定義分類、地點都有時可以隨機挑選的句型，避免每筆描述長得都一樣
    "{category}，位於{location}，是當地值得一遊的景點。",
    "來{location}旅遊，別錯過{name}，這裡是熱門的{category}。",
    "{name}是{location}當地人也推薦的{category}，很適合安排進行程。",
    "想體驗道地的{location}風情，不妨走訪{category}——{name}。",
    "{name}座落於{location}，以{category}聞名，值得安排時間造訪。",
    "如果到{location}旅遊，不妨把{category}{name}排進行程裡。",
]

PLACE_DESCRIPTION_TEMPLATES_CATEGORY_ONLY = [  # 定義只有分類、沒有地點時可以隨機挑選的句型
    "{name}是一處{category}，值得安排時間造訪。",
    "喜歡{category}的話，{name}會是不錯的選擇。",
    "{name}屬於{category}，很適合安排進旅遊行程。",
]

PLACE_DESCRIPTION_TEMPLATES_LOCATION_ONLY = [  # 定義只有地點、沒有分類時可以隨機挑選的句型
    "{name}位於{location}，是當地值得一遊的景點。",
    "來到{location}，不妨順道走訪{name}。",
    "{name}是{location}的知名去處，適合排進行程。",
]

PLACE_DESCRIPTION_TEMPLATES_MINIMAL = [  # 定義分類、地點都沒有時可以隨機挑選的最後備用句型
    "{name}是當地值得一遊的景點。",
    "推薦安排時間造訪{name}。",
]


def build_place_description(name, category_name, country_name, city_name):  # 定義函式：沒有現成簡介時，用已知資料隨機組一段景點描述(保證至少 10-15 字以上，且每次不會長得一樣)
    location = "".join(part for part in (country_name, city_name) if part)  # 把國家、城市名稱接在一起，例如「台灣台北市」

    if category_name and location:  # 如果分類跟地點都有
        template = random.choice(PLACE_DESCRIPTION_TEMPLATES_FULL)  # 從對應句型清單裡隨機挑一種
        return template.format(name=name, category=category_name, location=location)  # 把名稱、分類、地點套進句型

    if category_name:  # 如果只有分類
        template = random.choice(PLACE_DESCRIPTION_TEMPLATES_CATEGORY_ONLY)  # 隨機挑一種句型
        return template.format(name=name, category=category_name)  # 套進句型

    if location:  # 如果只有地點
        template = random.choice(PLACE_DESCRIPTION_TEMPLATES_LOCATION_ONLY)  # 隨機挑一種句型
        return template.format(name=name, location=location)  # 套進句型

    template = random.choice(PLACE_DESCRIPTION_TEMPLATES_MINIMAL)  # 分類、地點都沒有時，從最後備用句型裡隨機挑一種
    return template.format(name=name)  # 套進句型


def csv_response(filename, header, rows):  # 定義共用函式：把表頭與資料列組成可下載的 CSV 回應(給匯出統計、匯入範本共用)
    buffer = io.StringIO()  # 建立一個記憶體中的文字緩衝區
    buffer.write("﻿")  # 寫入 UTF-8 BOM，讓 Excel 開啟 CSV 時能正確辨識中文編碼
    writer = csv.writer(buffer)  # 建立 CSV 寫入器，綁定到這個緩衝區
    writer.writerow(header)  # 寫入表頭那一列
    writer.writerows(rows)  # 寫入所有資料列

    return Response(  # 組成 Flask 回應物件
        buffer.getvalue(),  # 回應內容為緩衝區裡累積的所有文字
        mimetype="text/csv",  # 設定回應的內容類型為 CSV
        headers={"Content-Disposition": f"attachment; filename={filename}"}  # 設定為附件下載，並指定檔名
    )
